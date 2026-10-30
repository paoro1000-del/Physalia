"""Convert the dedicated nginx JSON log to structured review events.

Usage: python examples/access_events.py < adg-access.jsonl
For keyed route identifiers: python examples/access_events.py --hash-key-file private/adg-route.key < adg-access.jsonl
Read a saved log without shell text conversion: python examples/access_events.py --input adg-access.jsonl
Show readable paths only when needed: python examples/access_events.py --show-path < adg-access.jsonl
For Nginx logs, event time estimates request start from request_seconds; request_completed_at preserves the log timestamp.
Live on Linux: tail -F adg-access.jsonl | python -u examples/access_events.py
No network calls, subprocesses, automatic blocking, or raw prompt interpretation.
"""
import argparse
from datetime import datetime, timedelta
import getpass
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import unicodedata
import warnings


def unique_object(pairs):
    result = {}
    normalized_keys = set()
    for key, value in pairs:
        normalized = key.casefold()
        if normalized in normalized_keys:
            raise ValueError("Duplicate JSON object key")
        normalized_keys.add(normalized)
        result[key] = value
    return result


def visible_path(value):
    output, length = [], 0
    for char in value:
        visible = f"<U+{ord(char):04X}>" if unicodedata.category(char) in ("Cc", "Cf", "Cs", "Zl", "Zp") else char
        if length + len(visible) > 512:
            break
        output.append(visible)
        length += len(visible)
    return "".join(output)


def hashed_route(value, key=None):
    """Return a stable route identifier, optionally protected against guessing."""
    if not isinstance(value, str) or not value.startswith("/"):
        raise ValueError("Route must begin with '/'")
    path = value.split("?", 1)[0].split("#", 1)[0]
    if not path:
        raise ValueError("Route is empty")
    payload = path.encode("utf-8", errors="surrogatepass")
    if key is None:
        return "/sha256/" + hashlib.sha256(payload).hexdigest()
    if not isinstance(key, bytes) or len(key) < 32:
        raise ValueError("The route HMAC key must contain at least 32 bytes")
    return "/hmac-sha256/" + hmac.new(key, payload, hashlib.sha256).hexdigest()


def read_hash_key(path):
    """Read a private HMAC key without following a final-component symlink."""
    path = Path(path)
    try:
        info = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise ValueError("Cannot read route HMAC key file") from exc
    if not stat.S_ISREG(info.st_mode) or path.is_symlink() or info.st_size > 4096:
        raise ValueError("Route HMAC key must be a regular file no larger than 4096 bytes")
    if os.name != "nt" and stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError("Restrict route HMAC key file permissions to its owner (for example chmod 600)")
    # O_NONBLOCK prevents a path swapped to a FIFO after stat() from hanging
    # the process before fstat() can reject the non-regular file.
    flags = (os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
             | getattr(os, "O_NONBLOCK", 0))
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as source:
            opened = os.fstat(source.fileno())
            if (not stat.S_ISREG(opened.st_mode)
                    or (info.st_dev, info.st_ino) != (opened.st_dev, opened.st_ino)):
                raise ValueError("Route HMAC key file changed while opening")
            if os.name != "nt" and stat.S_IMODE(opened.st_mode) & 0o077:
                raise ValueError("Restrict route HMAC key file permissions to its owner (for example chmod 600)")
            key = source.read(4097)
            finished = os.fstat(source.fileno())
            current = path.stat(follow_symlinks=False)
            identity = lambda item: (item.st_dev, item.st_ino, item.st_mode, item.st_size,
                                     item.st_mtime_ns, item.st_ctime_ns)
            if identity(opened) != identity(finished) or identity(finished) != identity(current):
                raise ValueError("Route HMAC key file changed while reading")
    except OSError as exc:
        raise ValueError("Cannot read route HMAC key file") from exc
    if len(key) < 32 or len(key) > 4096:
        raise ValueError("Route HMAC key must contain 32 to 4096 bytes")
    return key


def open_input_file(path):
    """Open a saved regular log without following links or blocking on special files."""
    path = Path(path)
    initial = path.stat(follow_symlinks=False)
    if path.is_symlink() or not stat.S_ISREG(initial.st_mode):
        raise ValueError("--input must name a regular file; use standard input for streams")
    flags = (os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
             | getattr(os, "O_NOFOLLOW", 0))
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        identity = lambda item: (item.st_dev, item.st_ino, item.st_mode, item.st_size,
                                 item.st_mtime_ns, item.st_ctime_ns)
        current = path.stat(follow_symlinks=False)
        if (path.is_symlink() or not stat.S_ISREG(opened.st_mode) or identity(initial) != identity(opened)
                or identity(opened) != identity(current)):
            raise ValueError("Input log changed while opening")
        return os.fdopen(descriptor, "rb")
    except Exception:
        os.close(descriptor)
        raise


def event(record, hash_path=True, hash_key=None):
    if not isinstance(record, dict):
        return None
    status = record.get("status")
    path = record.get("path")
    if type(status) is not int or not 100 <= status <= 599 or not isinstance(path, str) or not path.startswith("/"):
        return None
    # Drop query and fragment data. Hash paths by default because a canary URL
    # may put its secret token in the route; --show-path is an explicit opt-in.
    path = path.split("?", 1)[0].split("#", 1)[0]
    if not path:
        return None
    if hash_path:
        path = hashed_route(path, hash_key)
    else:
        path = visible_path(path)
    method = record.get("method")
    if method not in ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
        method = "OTHER"
    bytes_sent = record.get("bytes")
    # Keep integer metrics exactly representable through JSON and the browser UI.
    if type(bytes_sent) is not int or not 0 <= bytes_sent <= 2**53 - 1:
        bytes_sent = None
    request_seconds = record.get("seconds")
    if isinstance(request_seconds, str):
        if (len(request_seconds) <= 32
                and re.fullmatch(r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", request_seconds.strip())):
            try:
                request_seconds = float(request_seconds)
            except (ValueError, OverflowError):
                request_seconds = None
        else:
            request_seconds = None
    if (isinstance(request_seconds, bool) or not isinstance(request_seconds, (int, float))
            or request_seconds < 0 or request_seconds > 1_000_000_000):
        request_seconds = None
    else:
        try:
            if not math.isfinite(request_seconds):
                request_seconds = None
        except OverflowError:
            request_seconds = None
    timestamp = record.get("time", "")
    if (not isinstance(timestamp, str)
            or any(ord(char) < 32 or 0x7F <= ord(char) <= 0x9F for char in timestamp)):
        timestamp = ""
        completed_at = ""
        parsed_timestamp = None
    else:
        try:
            parsed_timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if parsed_timestamp.tzinfo is None:
                parsed_timestamp = None
        except ValueError:
            parsed_timestamp = None
        completed_at = timestamp[:64] if parsed_timestamp else ""
    if parsed_timestamp and request_seconds is not None:
        try:
            # Nginx writes access logs after response completion. Estimate the
            # request start for delay analysis and retain the logged completion
            # timestamp separately so the estimate is never mistaken for an
            # exact client-side event time.
            timestamp = (parsed_timestamp - timedelta(seconds=request_seconds)).isoformat(timespec="milliseconds")
        except (OverflowError, ValueError):
            timestamp = completed_at
    else:
        timestamp = completed_at
    result = {"event": "decoy_contact", "outcome": "response_2xx" if 200 <= status < 300 else "response_non_2xx",
              "time": timestamp[:64], "method": method,
              "status": status, "review_required": True}
    request_id = record.get("request_id")
    if isinstance(request_id, str) and re.fullmatch(r"[0-9A-Fa-f]{32}", request_id):
        result["request_id"] = request_id.lower()
    # Keep pseudonymous IDs distinct from raw routes. The review tool hashes
    # every value in `path`; it accepts this explicit field only after format
    # validation, so a raw route that happens to look like a digest is hashed.
    result["route_id" if hash_path else "path"] = path[:512]
    if completed_at:
        result["request_completed_at"] = completed_at
    if bytes_sent is not None:
        result["body_bytes_sent"] = bytes_sent
    if request_seconds is not None:
        result["request_seconds"] = request_seconds
    limit_status = record.get("limit_req_status")
    if limit_status in ("PASSED", "DELAYED", "REJECTED", "DELAYED_DRY_RUN", "REJECTED_DRY_RUN"):
        result["rate_limit_status"] = limit_status
    connection_status = record.get("limit_conn_status")
    if connection_status in ("PASSED", "REJECTED", "REJECTED_DRY_RUN"):
        result["connection_limit_status"] = connection_status
    return result


def main():
    parser = argparse.ArgumentParser(description="Convert decoy access logs to structured events.")
    path_group = parser.add_mutually_exclusive_group()
    path_group.add_argument("--show-path", action="store_true",
                            help="include the readable route in output (may expose canary tokens)")
    path_group.add_argument("--hash-path", action="store_true", help=argparse.SUPPRESS)
    path_group.add_argument("--hash-route", action="store_true",
                            help="interactively compute the event identifier for a private Nginx $uri route")
    parser.add_argument("--hash-key-file", type=Path,
                        help="operator-only key file (32+ random bytes) for HMAC-SHA-256 route identifiers")
    parser.add_argument("--input", type=Path,
                        help="read a saved JSONL log as raw bytes instead of reading standard input")
    args = parser.parse_args()
    if args.hash_route and args.input:
        parser.error("--input cannot be combined with --hash-route")
    if args.show_path and args.hash_key_file:
        parser.error("--show-path cannot be combined with --hash-key-file; choose readable or keyed route output")
    try:
        hash_key = read_hash_key(args.hash_key_file) if args.hash_key_file else None
    except ValueError as exc:
        parser.error(str(exc))
    if hash_key is None and not args.show_path:
        print(
            "Warning: route IDs use unkeyed SHA-256; predictable paths can be guessed. "
            "Use --hash-key-file to prevent offline guessing.",
            file=sys.stderr,
        )
    if args.hash_key_file and os.name == "nt":
        print(
            "Warning: Windows file ACLs are not validated. Restrict access to the key and its parent directory, "
            "then verify effective permissions with icacls.",
            file=sys.stderr,
        )
    if args.hash_route:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                route = getpass.getpass("Nginx $uri route (input hidden): ")
        except getpass.GetPassWarning:
            parser.error("Secure route input requires a terminal that can disable echo.")
        except EOFError:
            parser.error("No route was entered.")
        try:
            print(hashed_route(route, hash_key))
        except ValueError as exc:
            parser.error(str(exc))
        return
    try:
        source = open_input_file(args.input) if args.input else sys.stdin.buffer
    except (OSError, ValueError) as exc:
        parser.error(str(exc) if isinstance(exc, ValueError)
                     else f"Cannot open input log file: {exc.strerror or 'I/O error'}")
    try:
        line_number = 0
        while True:
            line = source.readline(16385)
            if not line:
                break
            line_number += 1
            too_long = len(line) > 16384
            if len(line) == 16384 and not line.endswith(b"\n"):
                # readline(size) may stop at the size limit before it reaches
                # the record delimiter. Distinguish a maximum-size final line
                # from a longer record before parsing any continuation as a
                # separate JSON event.
                extra = source.read(1)
                if extra:
                    too_long = True
                    line += extra
            if too_long:
                while line and not line.endswith(b"\n"):
                    line = source.readline(16385)
                print(f"Skipped oversized log record at input line {line_number}", file=sys.stderr)
                continue
            try:
                result = event(json.loads(line, object_pairs_hook=unique_object),
                               hash_path=not args.show_path, hash_key=hash_key)
            except (ValueError, UnicodeError, RecursionError):
                print(f"Skipped malformed log record at input line {line_number}", file=sys.stderr)
                continue
            if result:
                print(json.dumps(result, ensure_ascii=True, allow_nan=False), flush=True)
    finally:
        if args.input:
            source.close()


if __name__ == "__main__":
    main()
