"""Standard-library server included in the standalone canary homepage kit."""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import math
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
LOG = ROOT / "logs" / "contacts.jsonl"
MAX_BODY = 16 * 1024
EVENT_TTL = 300
events: dict[str, tuple[str, float]] = {}
events_lock = threading.Lock()
log_lock = threading.Lock()
ENV_KEYS = frozenset("language languages platform vendor user_agent plugins mime_types do_not_track timezone screen_orientation screen_width screen_height screen_available_width screen_available_height viewport_width viewport_height color_depth pixel_ratio timezone_offset hardware_concurrency device_memory max_touch_points webdriver cookies_enabled online pdf_viewer global_privacy_control touch_capable reduced_motion dark_mode connection_type connection_downlink connection_rtt connection_save_data webgl_vendor webgl_renderer webgl_version gpu_vendor gpu_renderer ua_mobile ua_platform ua_brands ua_architecture ua_bitness ua_model ua_platform_version ua_wow64 ua_form_factors ua_full_versions".split())
LOCATION_KEYS = frozenset("latitude longitude accuracy altitude altitude_accuracy heading speed timestamp".split())


def record(event: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with log_lock, LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")


def finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


class Handler(BaseHTTPRequestHandler):
    server_version = "CanaryHomepage/1.0"
    sys_version = ""

    def log_message(self, _format: str, *args) -> None:
        return

    def reply(self, status: int, mime: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; style-src 'self'; script-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        assets = {"/canary.js": ("canary.js", "text/javascript; charset=utf-8"),
                  "/style.css": ("style.css", "text/css; charset=utf-8")}
        if path in assets:
            name, mime = assets[path]
            self.reply(200, mime, (SITE / name).read_bytes())
            return
        if path not in ("/", "/index.html"):
            self.reply(404, "text/plain; charset=utf-8", b"Not found\n")
            return
        now = time.time()
        with events_lock:
            for key, (_, created) in list(events.items()):
                if now - created > EVENT_TTL:
                    events.pop(key, None)
            event_id, nonce = secrets.token_urlsafe(18), secrets.token_urlsafe(24)
            events[event_id] = (nonce, now)
        record({"type":"http_request", "event_id":event_id,
                "time":dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "source_ip":self.client_address[0], "method":self.command,
                "http_version":self.request_version,
                "headers":{key:self.headers.get(key, "")[:1024] for key in (
                    "User-Agent", "Accept-Language", "Accept", "Sec-CH-UA",
                    "Sec-CH-UA-Platform", "Sec-CH-UA-Mobile", "Sec-Fetch-Site",
                    "Sec-Fetch-Mode", "Sec-Fetch-Dest") if self.headers.get(key)}})
        page = (SITE / "index.html").read_text(encoding="utf-8")
        page = page.replace("__EVENT_ID__", html.escape(event_id, quote=True))
        page = page.replace("__EVENT_NONCE__", html.escape(nonce, quote=True))
        self.reply(200, "text/html; charset=utf-8", page.encode("utf-8"))

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/api/contact":
            self.reply(404, "text/plain; charset=utf-8", b"Not found\n")
            return
        host, origin = self.headers.get("Host", ""), self.headers.get("Origin", "")
        parsed_origin = urlsplit(origin)
        if not host or parsed_origin.netloc.lower() != host.lower() or parsed_origin.scheme not in ("http", "https"):
            self.reply(403, "application/json; charset=utf-8", b'{"error":"origin"}')
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
            if not 0 < length <= MAX_BODY:
                raise ValueError("size")
            payload = json.loads(self.rfile.read(length))
            event_id, nonce = payload.get("event_id"), payload.get("nonce")
            if not isinstance(event_id, str) or not isinstance(nonce, str):
                raise ValueError("token")
            with events_lock:
                issued = events.get(event_id)
                if not issued or time.time() - issued[1] > EVENT_TTL or not secrets.compare_digest(issued[0], nonce):
                    self.reply(403, "application/json; charset=utf-8", b'{"error":"event"}')
                    return
            environment = payload.get("environment", {})
            location = payload.get("location", {})
            if not isinstance(environment, dict) or not isinstance(location, dict):
                raise ValueError("shape")
            safe_environment = {}
            for key, value in environment.items():
                if key not in ENV_KEYS or not isinstance(value, (str, int, float, bool)):
                    continue
                if isinstance(value, str):
                    safe_environment[key] = value[:512]
                elif isinstance(value, float) and not math.isfinite(value):
                    continue
                else:
                    safe_environment[key] = value
            status = location.get("status", "pending")
            if status not in {"pending", "granted", "denied", "unavailable", "timeout", "unsupported"}:
                status = "unavailable"
            safe_location = {"status":status}
            if status == "granted":
                for key in LOCATION_KEYS:
                    value = location.get(key)
                    if finite(value):
                        safe_location[key] = value
            record({"type":"browser_environment", "event_id":event_id,
                    "time":dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                    "environment":safe_environment, "location":safe_location})
            self.reply(200, "application/json; charset=utf-8", b'{"ok":true}')
        except (ValueError, TypeError, json.JSONDecodeError, AttributeError):
            self.reply(400, "application/json; charset=utf-8", b'{"error":"invalid"}')


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an isolated canary homepage.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=8765, help="Port (default: 8765).")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True
    print(f"Listening at http://{args.host}:{args.port}/; log: {LOG}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
