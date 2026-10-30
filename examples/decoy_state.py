"""Framework-neutral fake-state sample; NOT a production authentication server.

Call only after a trusted server has classified a honeyword match.
Keep returned IDs in a separate decoy-only session cookie, never a production JWT.
Decoy routes must reject production sessions; production routes must reject these IDs.
Only a SHA-256 digest of each random session ID is retained in the in-memory lookup table.
Thread-safe within one process, but not shared across worker processes or hosts.
No production storage, network access, code execution or password handling.
"""
import hashlib
import math
import secrets
import threading
import time


class DecoyCapacityError(RuntimeError):
    """Raised when no additional isolated decoy session can be allocated."""


class DecoyState:
    def __init__(self, capacity=100, ttl=900, delay=3):
        if (type(capacity) is not int or type(ttl) is not int or type(delay) is not int
                or not 1 <= capacity <= 1000 or not 1 <= ttl <= 3600 or not 0 <= delay <= 30):
            raise ValueError("Invalid session limits")
        self.capacity, self.ttl, self.delay = capacity, ttl, delay
        self.sessions = {}
        self.lock = threading.Lock()

    @staticmethod
    def _session_key(sid):
        return hashlib.sha256(sid.encode("ascii")).digest()

    def _prune(self):
        now = time.monotonic()
        for key in list(self.sessions):
            if self.sessions[key]["expires"] <= now:
                del self.sessions[key]

    def create(self):
        with self.lock:
            self._prune()
            if len(self.sessions) >= self.capacity:
                # The authentication adapter must fail closed on this error;
                # it must never treat a honeyword as a genuine login.
                raise DecoyCapacityError("Session capacity reached")
            sid = secrets.token_urlsafe(32)
            self.sessions[self._session_key(sid)] = {
                "expires": time.monotonic() + self.ttl,
                "values": {"retention_days": 30, "export_format": "csv"}, "pending": None}
            return sid

    def _get(self, sid):
        # Cookies and framework adapters supply untrusted values. Reject
        # non-strings before using them as dictionary keys.
        if not isinstance(sid, str) or len(sid) > 128 or not sid.isascii():
            raise ValueError("Session expired or unknown")
        self._prune()
        now = time.monotonic()
        key = self._session_key(sid)
        state = self.sessions.get(key)
        if state is None:
            raise ValueError("Session expired or unknown")
        # Check the selected entry against the same clock reading used for
        # pending updates. This closes the expiry boundary between bulk
        # pruning and lookup, so a just-expired session cannot be served.
        if state["expires"] <= now:
            del self.sessions[key]
            raise ValueError("Session expired or unknown")
        pending = state["pending"]
        if pending and pending[0] <= now:
            state["values"].update(pending[1])
            state["pending"] = None
        return state

    def read(self, sid):
        with self.lock:
            state = self._get(sid)
            now = time.monotonic()
            pending = state["pending"]
            # Recheck at the read boundary. The update may become due just
            # after _get()'s clock sample; do not report pending with 0s and
            # require an unnecessary second read.
            if pending and pending[0] <= now:
                state["values"].update(pending[1])
                state["pending"] = None
            pending = state["pending"]
            result = {"settings": dict(state["values"]),
                      "status": "pending" if pending else "applied"}
            if pending:
                remaining = pending[0] - now
                result["retry_after_seconds"] = max(0, math.ceil(remaining))
            return result

    def update(self, sid, values):
        if not isinstance(values, dict):
            raise ValueError("Unknown setting")
        # Validate and store the same snapshot so a caller cannot mutate a
        # shared request dictionary between validation and queuing.
        changes = values.copy()
        if not changes or set(changes) - {"retention_days", "export_format"}:
            raise ValueError("Unknown setting")
        if "retention_days" in changes and (type(changes["retention_days"]) is not int or not 1 <= changes["retention_days"] <= 365):
            raise ValueError("retention_days must be 1..365")
        if "export_format" in changes and (type(changes["export_format"]) is not str
                                            or changes["export_format"] not in ("csv", "json", "xlsx")):
            raise ValueError("Unknown export format")
        with self.lock:
            state = self._get(sid)
            if state["pending"]:
                raise ValueError("Previous change is still pending")
            if self.delay == 0:
                state["values"].update(changes)
                return {"status": "applied", "retry_after_seconds": 0}
            state["pending"] = (time.monotonic() + self.delay, changes)
            return {"status": "pending", "retry_after_seconds": self.delay}

    def revoke(self, sid):
        if not isinstance(sid, str) or len(sid) > 128 or not sid.isascii():
            return
        with self.lock:
            self.sessions.pop(self._session_key(sid), None)
