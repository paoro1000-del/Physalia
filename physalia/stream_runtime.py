"""Standalone authenticated streaming sample. Python standard library only.

This file is also shipped as serve.py inside generated sample bundles.
The response has no total byte/time limit and is terminated by disconnect or stop.
"""
import argparse
from collections.abc import Mapping
from datetime import datetime, timezone
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import socket
import stat
import sys
import threading
import time

MAX_CONFIG_BYTES = 64 * 1024
MAX_OPERATOR_BYTES = 1024 * 1024
HEADER_DEADLINE_SECONDS = 10
STREAM_SOCKET_INACTIVITY_TIMEOUT_SECONDS = 5
AUTH_FAILURE_SUMMARY_INTERVAL_SECONDS = 10
DOWNLOAD_TICKET_TTL_SECONDS = 30
MAX_DOWNLOAD_TICKETS = 32
EVENT_LOCK = threading.Lock()


def message(language, english, japanese):
    return japanese if language == "ja" else english


def safe_display(value):
    """Escape terminal controls and bidi formatting in untrusted error text."""
    printable = "".join(
        character if character.isprintable() else
        (f"\\u{ord(character):04x}" if ord(character) <= 0xFFFF else f"\\U{ord(character):08x}")
        for character in str(value))
    return json.dumps(printable, ensure_ascii=False)[1:-1]


def emit_event(event, **fields):
    """Write a secret-free JSON event to stdout for a service log collector."""
    record = {"timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"), "event": event, **fields}
    try:
        line = json.dumps(record, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
        with EVENT_LOCK:
            print(line, flush=True)
    except OSError:
        # A closed log pipe must not terminate a legitimate response handler.
        pass


def read_json(path, maximum, language="ja", private=False):
    before = os.stat(path, follow_symlinks=False)
    if private and os.name != "nt" and stat.S_IMODE(before.st_mode) & 0o077:
        raise ValueError(message(language,
                                 "Restrict operator JSON permissions to its owner (for example chmod 600)",
                                 "\u7ba1\u7406\u8005\u7528JSON\u306fchmod 600\u306a\u3069\u3067\u6240\u6709\u8005\u306e\u307f\u306b\u8aad\u307f\u53d6\u308a\u3092\u5236\u9650\u3057\u3066\u304f\u3060\u3055\u3044"))
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(message(language, "Configuration must be a regular file",
                                 "設定ファイルは通常ファイルでなければなりません"))
    if before.st_size > maximum:
        raise ValueError(message(language, f"JSON file exceeds {maximum} bytes: {path.name}",
                                 f"JSONファイルが{maximum}バイトを超えています: {path.name}"))
    flags = (os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
             | getattr(os, "O_NOFOLLOW", 0))
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        identity = lambda item: (item.st_dev, item.st_ino, item.st_size,
                                 item.st_mtime_ns, item.st_ctime_ns)
        if (not stat.S_ISREG(opened.st_mode) or identity(before) != identity(opened)
                or opened.st_size > maximum):
            raise ValueError(message(language, "Configuration file changed, is not regular, or exceeds size limit",
                                     "\u8a2d\u5b9a\u30d5\u30a1\u30a4\u30eb\u304c\u5909\u66f4\u3055\u308c\u305f\u304b\u3001\u901a\u5e38\u30d5\u30a1\u30a4\u30eb\u3067\u306a\u3044\u304b\u3001\u30b5\u30a4\u30ba\u4e0a\u9650\u3092\u8d85\u3048\u3066\u3044\u307e\u3059"))
        if private and os.name != "nt" and stat.S_IMODE(opened.st_mode) & 0o077:
            raise ValueError(message(language,
                                     "Restrict operator JSON permissions to its owner (for example chmod 600)",
                                     "\u7ba1\u7406\u8005\u7528JSON\u306fchmod 600\u306a\u3069\u3067\u6240\u6709\u8005\u306e\u307f\u306b\u8aad\u307f\u53d6\u308a\u3092\u5236\u9650\u3057\u3066\u304f\u3060\u3055\u3044"))
        with os.fdopen(descriptor, "rb") as source:
            descriptor = -1
            raw = source.read(maximum + 1)
            final = os.fstat(source.fileno())
            path_final = os.stat(path, follow_symlinks=False)
            if identity(opened) != identity(final) or identity(final) != identity(path_final):
                raise ValueError(message(language, "Configuration file changed while reading",
                                         "\u8a2d\u5b9a\u30d5\u30a1\u30a4\u30eb\u306f\u8aad\u307f\u8fbc\u307f\u4e2d\u306b\u5909\u66f4\u3055\u308c\u307e\u3057\u305f"))
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if len(raw) > maximum:
        raise ValueError(message(language, f"JSON file exceeds {maximum} bytes: {path.name}",
                                 f"JSONファイルが{maximum}バイトを超えています: {path.name}"))
    return json.loads(raw.decode("utf-8"), object_pairs_hook=lambda pairs: _unique_json_object(pairs, language),
                      parse_constant=lambda value: _reject_json_constant(value, language))


def _reject_json_constant(value, language):
    raise ValueError(message(language, f"Non-standard JSON constant: {value}",
                             f"標準外のJSON定数です: {value}"))


def _unique_json_object(pairs, language="ja"):
    """Reject ambiguous keys in operator-controlled config and credential files."""
    result = {}
    normalized_keys = set()
    for key, value in pairs:
        normalized = key.casefold()
        if normalized in normalized_keys:
            raise ValueError(message(language, "Duplicate JSON object key", "JSONオブジェクト内に重複したキーがあります"))
        normalized_keys.add(normalized)
        result[key] = value
    return result


def validate_config(config, language="ja"):
    if not isinstance(config, dict):
        raise ValueError(message(language, "Invalid stream configuration", "配信設定が不正です"))
    allowed_fields = {"port", "rate_kib", "max_streams", "path", "format"}
    if set(config) - allowed_fields:
        raise ValueError(message(language, "Configuration contains unsupported fields",
                                 "設定に未対応の項目があります"))
    # Keep manually edited configs aligned with the GUI generator and avoid
    # ephemeral port 0, whose actual listener would differ from the bundled docs.
    for key, default, low, high in (("port", 9080, 1024, 65535), ("rate_kib", 8, 1, 64), ("max_streams", 2, 1, 8)):
        value = config.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ValueError(message(language,
                                     f"{key} must be between {low} and {high}",
                                     f"{key}は{low}〜{high}の範囲で指定してください"))
        config[key] = value
    path = config.get("path", "/exports/archive.sql")
    if (not isinstance(path, str) or len(path) > 160 or not re.fullmatch(r"/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_.-]+", path)
            or ".." in path or path in ("/", "/stop", "/health", "/download-ticket")
            or path.startswith("/download/")
            or any(part == "." or part.endswith(".") for part in path[1:].split("/"))):
        raise ValueError(message(language, "Invalid download path", "配信パスが不正です"))
    config["path"] = path
    stream_format = config.get("format", "sql")
    if not isinstance(stream_format, str) or stream_format not in ("sql", "csv", "txt"):
        raise ValueError(message(language, "Invalid stream format", "配信形式が不正です"))
    config["format"] = stream_format
    return config


class StreamServer(ThreadingHTTPServer):
    # server_close() sets stop_event and joins active handlers. This lets
    # stream_ended events flush before a clean Ctrl+C shutdown exits.
    daemon_threads = False
    allow_reuse_address = True

    def __init__(self, config, access_token, admin_token, language="ja"):
        self.config = validate_config(dict(config), language)
        for token in (access_token, admin_token):
            if (not isinstance(token, str) or not 32 <= len(token) <= 256
                    or not re.fullmatch(r"[A-Za-z0-9._~+/-]{32,256}={0,2}", token)):
                raise ValueError(message(language, "Use separate Bearer-compatible ASCII tokens of 32–256 characters",
                                         "トークンは32〜256文字のASCIIで指定してください"))
        if hmac.compare_digest(access_token, admin_token):
            raise ValueError(message(language, "Use different access/admin tokens",
                                     "配信用と管理用は別トークンにしてください"))
        self.access_token, self.admin_token = access_token, admin_token
        # stream_id restarts at one for each process. This random, non-secret
        # identifier lets a collector pair events without colliding across
        # service restarts.
        self.run_id = secrets.token_hex(8)
        self.stop_event = threading.Event()
        self.stream_slots = threading.BoundedSemaphore(self.config["max_streams"])
        self.worker_slots = threading.BoundedSemaphore(self.config["max_streams"] + 4)
        self.pace_lock = threading.Lock()
        self.next_send = 0.0
        self.counters_lock = threading.Lock()
        self.active = self.payload_bytes_sent = self.started = 0
        self.auth_failure_lock = threading.Lock()
        self.auth_failure_condition = threading.Condition(self.auth_failure_lock)
        self.auth_failure_counts = {}
        self.auth_failure_closing = False
        self.auth_failure_emissions = 0
        self.ticket_lock = threading.Lock()
        self.download_tickets = {}
        super().__init__(("127.0.0.1", self.config["port"]), StreamHandler)

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(STREAM_SOCKET_INACTIVITY_TIMEOUT_SECONDS)
        return connection, address

    def process_request(self, request, address):
        if not self.worker_slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, address)
        except Exception:
            self.worker_slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.worker_slots.release()

    def handle_error(self, request, address):
        # BaseServer's default traceback includes the client address. Keep
        # diagnostics structured and avoid logging request or peer details.
        error_type = sys.exc_info()[0]
        emit_event("request_handler_error", run_id=self.run_id,
                   error_type=error_type.__name__ if error_type else "UnknownError")

    def pace(self, size):
        with self.pace_lock:
            now = time.monotonic()
            scheduled = max(now, self.next_send)
            self.next_send = scheduled + size / (self.config["rate_kib"] * 1024)
        return not self.stop_event.wait(max(0, scheduled - now))

    def issue_download_ticket(self):
        now = time.monotonic()
        with self.ticket_lock:
            self.download_tickets = {ticket: expires for ticket, expires in self.download_tickets.items()
                                     if expires > now}
            if len(self.download_tickets) >= MAX_DOWNLOAD_TICKETS:
                return None
            ticket = secrets.token_urlsafe(32)
            self.download_tickets[ticket] = now + DOWNLOAD_TICKET_TTL_SECONDS
            return ticket

    def consume_download_ticket(self, ticket):
        now = time.monotonic()
        with self.ticket_lock:
            expires = self.download_tickets.pop(ticket, 0)
            return expires > now

    def record_auth_failure(self, scope, method):
        """Emit an immediate count and flush suppressed failures after 10 seconds."""
        now = time.monotonic()
        event = None
        with self.auth_failure_lock:
            key = (scope, method)
            state = self.auth_failure_counts.setdefault(
                key, {"count": 0, "emitted_count": 0, "last_emitted": None, "timer": None})
            state["count"] += 1
            elapsed = (now - state["last_emitted"]
                       if state["last_emitted"] is not None else None)
            if elapsed is None or elapsed >= AUTH_FAILURE_SUMMARY_INTERVAL_SECONDS:
                timer = state["timer"]
                if timer is not None:
                    timer.cancel()
                    state["timer"] = None
                state["last_emitted"] = now
                state["emitted_count"] = state["count"]
                event = (scope, method, state["count"])
            elif state["timer"] is None:
                timer = threading.Timer(
                    max(0, AUTH_FAILURE_SUMMARY_INTERVAL_SECONDS - elapsed),
                    self._flush_auth_failure_summary, args=(key,))
                timer.daemon = True
                state["timer"] = timer
                timer.start()
        if event is not None:
            self._emit_auth_failure_summary(*event)

    def _emit_auth_failure_summary(self, scope, method, count):
        # Do not include request paths, IP addresses, request IDs supplied
        # by clients, Authorization values, or account identifiers.
        emit_event("stream_auth_failure_summary", run_id=self.run_id,
                   scope=scope, method=method, failures_total=count)

    def _flush_auth_failure_summary(self, key):
        event = None
        with self.auth_failure_lock:
            if self.auth_failure_closing:
                return
            state = self.auth_failure_counts.get(key)
            if state is None:
                return
            state["timer"] = None
            if state["count"] > state["emitted_count"]:
                state["last_emitted"] = time.monotonic()
                state["emitted_count"] = state["count"]
                event = (*key, state["count"])
                self.auth_failure_emissions += 1
        if event is not None:
            try:
                self._emit_auth_failure_summary(*event)
            finally:
                with self.auth_failure_condition:
                    self.auth_failure_emissions -= 1
                    self.auth_failure_condition.notify_all()

    def _flush_pending_auth_failure_summaries(self):
        events = []
        with self.auth_failure_condition:
            self.auth_failure_closing = True
            for key, state in self.auth_failure_counts.items():
                timer = state["timer"]
                if timer is not None:
                    timer.cancel()
                    state["timer"] = None
                if state["count"] > state["emitted_count"]:
                    state["emitted_count"] = state["count"]
                    state["last_emitted"] = time.monotonic()
                    events.append((*key, state["count"]))
            # A timer may have committed an event immediately before closing
            # began. Wait until its stdout write completes before returning.
            while self.auth_failure_emissions:
                self.auth_failure_condition.wait()
        for event in events:
            self._emit_auth_failure_summary(*event)

    def server_close(self):
        self.stop_event.set()
        super().server_close()
        self._flush_pending_auth_failure_summaries()


def chunks(kind):
    if kind == "sql":
        yield b"-- account export\nBEGIN TRANSACTION;\nCREATE TABLE accounts (id INTEGER, reference TEXT, amount REAL);\n"
    elif kind == "csv":
        yield b"id,reference,amount\n"
    else:
        yield b"Operations archive\n"
    index = 0
    while True:
        block = bytearray()
        while len(block) < 1024:
            index += 1
            # Keep the stream infinite while avoiding an obvious arithmetic
            # pattern in every field beyond the naturally increasing row ID.
            reference = f"AC-{secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}{secrets.randbelow(100_000_000):08d}"
            amount = f"{(secrets.randbelow(499_001) + 1_000) / 100:.2f}"
            if kind == "sql": line = f"INSERT INTO accounts VALUES ({index}, '{reference}', {amount});\n"
            elif kind == "csv": line = f"{index},{reference},{amount}\n"
            else: line = f"Entry {index} | Reference: {reference} | Amount: {amount}\n"
            block.extend(line.encode("ascii"))
        yield bytes(block)


class StreamHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ArchiveService"
    sys_version = ""

    def handle(self):
        # A socket inactivity timeout alone permits a slow client to occupy a
        # worker indefinitely by sending one byte just before each timeout.
        # Bound the complete request-line/header phase as well. The streaming
        # response begins only after parse_request cancels this timer.
        self._request_headers_complete = False
        self._header_deadline_timer = threading.Timer(
            HEADER_DEADLINE_SECONDS, self._abort_incomplete_headers)
        self._header_deadline_timer.daemon = True
        self._header_deadline_timer.start()
        try:
            super().handle()
        except (OSError, socket.timeout):
            # The deadline callback shuts down a slow header read. Do not emit
            # a handler-error event for that expected connection close.
            self.close_connection = True
        finally:
            self._header_deadline_timer.cancel()

    def _abort_incomplete_headers(self):
        if self._request_headers_complete:
            return
        try:
            self.connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def parse_request(self):
        parsed = super().parse_request()
        self._request_headers_complete = True
        self._header_deadline_timer.cancel()
        return parsed

    def log_message(self, *_):
        pass  # No authorization headers, request paths or secret values in logs.

    def authorized(self, admin=False):
        token = self.server.admin_token if admin else self.server.access_token
        values = self.headers.get_all("Authorization", [])
        return len(values) == 1 and hmac.compare_digest(values[0].encode("utf-8"), ("Bearer " + token).encode("ascii"))

    def valid_host(self):
        values = self.headers.get_all("Host", [])
        return len(values) == 1 and values[0] == f"127.0.0.1:{self.server.server_port}"

    def request_identifier(self):
        """Return a bounded correlation ID or create one for direct clients."""
        values = self.headers.get_all("X-Request-ID", [])
        if len(values) == 1 and re.fullmatch(r"[0-9A-Fa-f]{32}", values[0]):
            return values[0].lower()
        return secrets.token_hex(16)

    def reply(self, status, payload):
        data = json.dumps(payload, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        self.wfile.write(data)

    def reply_head(self, status, payload):
        """Return the corresponding JSON error headers without a HEAD body."""
        data = json.dumps(payload, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

    def serve_preview_asset(self, filename, content_type):
        try:
            content = (Path(__file__).resolve().with_name(filename)).read_bytes()
        except OSError:
            return self.reply(404, {"error": "not found"})
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; script-src 'self'; connect-src 'self'; form-action 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        self.wfile.write(content)

    def do_GET(self):
        if not self.valid_host():
            return self.reply(403, {"error": "host"})
        if self.path == "/health":
            if not self.authorized(admin=True):
                self.server.record_auth_failure("admin", "GET")
                return self.reply(401, {"error": "authorization"})
            with self.server.counters_lock:
                return self.reply(200, {"run_id": self.server.run_id,
                                        "stopped": self.server.stop_event.is_set(), "active": self.server.active,
                                        "started": self.server.started,
                                        "payload_bytes_sent": self.server.payload_bytes_sent})
        if self.path == "/":
            return self.serve_preview_asset("index.html", "text/html; charset=utf-8")
        if self.path == "/stream-preview.js":
            return self.serve_preview_asset("stream-preview.js", "text/javascript; charset=utf-8")
        ticket_stream = self.path.startswith("/download/")
        if ticket_stream:
            ticket = self.path.removeprefix("/download/")
            if not re.fullmatch(r"[A-Za-z0-9_-]{40,50}", ticket) or not self.server.consume_download_ticket(ticket):
                return self.reply(404, {"error": "not found"})
        elif self.path != self.server.config["path"]:
            return self.reply(404, {"error": "not found"})
        if not ticket_stream and not self.authorized():
            self.server.record_auth_failure("stream", "GET")
            return self.reply(401, {"error": "authorization"})
        if self.server.stop_event.is_set() or not self.server.stream_slots.acquire(blocking=False):
            return self.reply(503, {"error": "unavailable"})
        with self.server.counters_lock:
            self.server.active += 1
            self.server.started += 1
            stream_id = self.server.started
            active = self.server.active
        request_id = self.request_identifier()
        # The configured route can contain an operator-chosen identifier. Keep
        # it out of application events; a single stream endpoint needs no path
        # field to correlate its start/end events.
        emit_event("stream_started", run_id=self.server.run_id, stream_id=stream_id,
                   request_id=request_id,
                   format=self.server.config["format"], active=active)
        stream_started_at = time.monotonic()
        stream_payload_bytes = 0
        termination_reason = "handler_error"
        error_type = None
        try:
            self.send_response(200)
            content_type = ("text/csv; charset=utf-8" if self.server.config["format"] == "csv"
                            else "text/plain; charset=utf-8")
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Disposition", 'attachment; filename="archive.' + self.server.config["format"] + '"')
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("Cache-Control", "no-store, no-transform")
            self.send_header("X-Accel-Buffering", "no")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Request-ID", request_id)
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            for block in chunks(self.server.config["format"]):
                if not self.server.pace(len(block)):
                    termination_reason = "operator_stop"
                    break
                self.wfile.write(f"{len(block):X}\r\n".encode("ascii") + block + b"\r\n")
                self.wfile.flush()
                # Count bytes accepted by the server-side socket write path;
                # this is not a transport acknowledgement or proof of receipt.
                with self.server.counters_lock:
                    self.server.payload_bytes_sent += len(block)
                stream_payload_bytes += len(block)
            # No terminating chunk: operator stop closes an intentionally incomplete export.
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, socket.timeout, OSError) as exc:
            if self.server.stop_event.is_set():
                termination_reason = "operator_stop"
            elif isinstance(exc, socket.timeout):
                termination_reason = "write_timeout"
            elif isinstance(exc, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)):
                termination_reason = "client_disconnected"
            else:
                termination_reason = "transport_error"
        except Exception as exc:
            termination_reason = "handler_error"
            error_type = type(exc).__name__
        finally:
            with self.server.counters_lock:
                self.server.active -= 1
                active = self.server.active
            fields = {"run_id": self.server.run_id, "stream_id": stream_id,
                      "request_id": request_id,
                      "payload_bytes_sent": stream_payload_bytes,
                      "duration_ms": max(0, round((time.monotonic() - stream_started_at) * 1000)),
                      "stopped": self.server.stop_event.is_set(), "reason": termination_reason, "active": active}
            if error_type:
                fields["error_type"] = error_type
            emit_event("stream_ended", **fields)
            self.server.stream_slots.release()

    def do_HEAD(self):
        # Nginx allows HEAD whenever GET is allowed. Answer without opening an
        # unbounded stream, but authenticate and record the probe.
        if not self.valid_host():
            return self.reply_head(403, {"error": "host"})
        if self.path != self.server.config["path"]:
            return self.reply_head(404, {"error": "not found"})
        if not self.authorized():
            self.server.record_auth_failure("stream", "HEAD")
            return self.reply_head(401, {"error": "authorization"})
        if self.server.stop_event.is_set():
            return self.reply_head(503, {"error": "unavailable"})
        request_id = self.request_identifier()
        emit_event("stream_probe", run_id=self.server.run_id, request_id=request_id, method="HEAD",
                   format=self.server.config["format"])
        self.send_response(200)
        content_type = ("text/csv; charset=utf-8" if self.server.config["format"] == "csv"
                        else "text/plain; charset=utf-8")
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", 'attachment; filename="archive.' + self.server.config["format"] + '"')
        # Match GET framing metadata without sending a body, as required for HEAD semantics.
        self.send_header("Transfer-Encoding", "chunked")
        self.send_header("Cache-Control", "no-store, no-transform")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Request-ID", request_id)
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

    def do_POST(self):
        if not self.valid_host():
            return self.reply(403, {"error": "host"})
        if self.path == "/download-ticket":
            if not self.authorized():
                self.server.record_auth_failure("stream", "POST")
                return self.reply(401, {"error": "authorization"})
            ticket = self.server.issue_download_ticket()
            if ticket is None:
                return self.reply(503, {"error": "unavailable"})
            emit_event("stream_download_ticket_issued", run_id=self.server.run_id,
                       expires_in=DOWNLOAD_TICKET_TTL_SECONDS)
            return self.reply(200, {"download_url": "/download/" + ticket,
                                    "expires_in": DOWNLOAD_TICKET_TTL_SECONDS})
        if self.path != "/stop":
            return self.reply(404, {"error": "not found"})
        if not self.authorized(admin=True):
            self.server.record_auth_failure("admin", "POST")
            return self.reply(401, {"error": "authorization"})
        self.server.stop_event.set()
        return self.reply(200, {"stopped": True})


def main():
    # argparse help and errors include Japanese text by default. GitHub's
    # Windows runners may redirect stdout/stderr through a legacy cp1252 codec.
    # UTF-8 keeps the standalone bundle usable in redirected Windows sessions.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="backslashreplace")
    bootstrap_parser = argparse.ArgumentParser(add_help=False)
    bootstrap_parser.add_argument("--lang", choices=("ja", "en"), default="ja")
    language = bootstrap_parser.parse_known_args()[0].lang
    language_parser = argparse.ArgumentParser(add_help=False)
    language_parser.add_argument("--lang", choices=("ja", "en"), default=language,
                                 help=message(language, "Console language", "表示言語"))
    parser = argparse.ArgumentParser(
        description=message(language, "Infinite Stream sample", "インフィニット・ストリーム検証サーバー"),
        parents=[language_parser])
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("stream_config.json"))
    parser.add_argument("--operator", type=Path,
                        help=message(language, "Private operator JSON", "管理者専用JSON"))
    args = parser.parse_args()
    try:
        config = read_json(args.config, MAX_CONFIG_BYTES, args.lang)
        if args.operator:
            operator_data = read_json(args.operator, MAX_OPERATOR_BYTES, args.lang, private=True)
            if not isinstance(operator_data, dict) or not isinstance(operator_data.get("environment"), Mapping):
                raise ValueError(message(args.lang, "Operator JSON must contain an environment object",
                                         "管理者JSONにはenvironmentオブジェクトが必要です"))
            credentials = operator_data["environment"]
            if os.name == "nt":
                print(message(
                    args.lang,
                    "Warning: Windows ACLs are not validated. Restrict this operator file and its parent directory, then verify effective permissions with icacls.",
                    "\u8b66\u544a: Windows\u306eACL\u306f\u691c\u67fb\u3055\u308c\u307e\u305b\u3093\u3002\u7ba1\u7406\u8005\u5c02\u7528JSON\u3068\u89aa\u30d5\u30a9\u30eb\u30c0\u30fc\u3078\u306e\u30a2\u30af\u30bb\u30b9\u3092\u5236\u9650\u3057\u3001icacls\u3067\u5b9f\u52b9\u6a29\u9650\u3092\u78ba\u8a8d\u3057\u3066\u304f\u3060\u3055\u3044."),
                    file=sys.stderr, flush=True)
        else:
            credentials = os.environ
        if not isinstance(credentials, Mapping):
            raise ValueError(message(args.lang, "Operator credentials must be a JSON object", "管理用認証情報はJSONオブジェクトで指定してください"))
        server = StreamServer(config, credentials.get("ADG_STREAM_TOKEN"), credentials.get("ADG_STREAM_ADMIN_TOKEN"), args.lang)
    except json.JSONDecodeError:
        parser.error(message(args.lang, "Invalid JSON in configuration or operator file",
                             "設定または管理者JSONの形式が不正です"))
    except UnicodeError:
        parser.error(message(args.lang, "JSON files must use UTF-8 encoding", "JSONファイルはUTF-8で保存してください"))
    except RecursionError:
        parser.error(message(args.lang, "JSON nesting is too deep", "JSONの入れ子が深すぎます"))
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        parser.error(safe_display(exc))
    emit_event("server_started", run_id=server.run_id, host="127.0.0.1", port=server.server_port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
