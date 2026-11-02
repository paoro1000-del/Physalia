"""Start a local-only browser interface for generating decoy assets."""

from __future__ import annotations

import argparse
import base64
import errno
import html
import json
import io
import math
import re
import secrets
import socket
import stat
import sys
import threading
import time
import zipfile
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath

from physalia.generators import generate
from physalia.i18n import translate
from physalia.database import public_templates

STATIC = Path(__file__).parent / "web"
APP_VERSION = (STATIC.parent / "VERSION").read_text(encoding="utf-8").strip()
INTEGRATION_BUNDLE_FILES = (
    "LICENSE", "README.md", "README_en.md", "SECURITY.md",
    "docs/deployment_ja.md", "docs/deployment_en.md", "docs/legal_ja.md", "docs/legal_en.md",
    "docs/deception_evaluation.md",
    "docs/log-review-guide_ja.md", "docs/log-review-guide_en.md",
    "examples/nginx-decoy.conf", "examples/nginx-stream-proxy.conf",
    "examples/nginx-stream-token.conf.example", "examples/decoy_state.py",
    "examples/decoy-contact-sample.jsonl",
    "examples/agent-tool-approval-template.json",
    "examples/evaluate_deception.py", "examples/deception-evaluation-sample.json",
    "scripts/check_study_metadata_schema.py",
    "examples/deception-study-metadata-template.json",
    "examples/deception-study-metadata-template.schema.json",
    "examples/verify_inventory.py",
)
_INTEGRATION_BUNDLE_CACHE = None
_INTEGRATION_BUNDLE_LOCK = threading.Lock()
MAX_INTEGRATION_BUNDLE_BYTES = 64 * 1024 * 1024
# Covers the UI's bounded 30-column schema and up to 820,000 characters of
# canary URL assignments, including UTF-8 and JSON escaping overhead.
MAX_REQUEST = 4 * 1024 * 1024
SESSION_TOKEN = secrets.token_urlsafe(32)
GENERATION_SLOT = threading.BoundedSemaphore(1)
MAX_HTTP_WORKERS = 16
REQUEST_TIMEOUT_SECONDS = 10
REQUEST_HEADER_DEADLINE_SECONDS = 10
REQUEST_BODY_TIMEOUT_SECONDS = 30
REQUEST_BODY_CHUNK_BYTES = 64 * 1024
RESPONSE_WRITE_TIMEOUT_SECONDS = 120


def integration_bundle():
    """Build the fixed, secret-free integration bundle once per process."""
    global _INTEGRATION_BUNDLE_CACHE
    if _INTEGRATION_BUNDLE_CACHE is None:
        with _INTEGRATION_BUNDLE_LOCK:
            if _INTEGRATION_BUNDLE_CACHE is None:
                output = io.BytesIO()
                with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    root = STATIC.parent.resolve(strict=True)
                    total_size = 0
                    for name in INTEGRATION_BUNDLE_FILES:
                        relative = PurePosixPath(name)
                        if relative.is_absolute() or not relative.parts or any(
                                part in ("", ".", "..") for part in relative.parts):
                            raise ValueError("Invalid integration bundle path")
                        candidate = root
                        for part in relative.parts:
                            candidate = candidate / part
                            if candidate.is_symlink():
                                raise ValueError("Integration bundle files cannot be symbolic links")
                        resolved = candidate.resolve(strict=True)
                        if not resolved.is_relative_to(root):
                            raise ValueError("Integration bundle path escapes the project directory")
                        metadata = resolved.stat()
                        if not stat.S_ISREG(metadata.st_mode):
                            raise ValueError("Integration bundle entries must be regular files")
                        total_size += metadata.st_size
                        if total_size > MAX_INTEGRATION_BUNDLE_BYTES:
                            raise ValueError("Integration bundle exceeds its size limit")
                        archive.writestr(name, resolved.read_bytes())
                bundle = output.getvalue()
                if len(bundle) > MAX_INTEGRATION_BUNDLE_BYTES:
                    raise ValueError("Integration bundle exceeds its size limit")
                _INTEGRATION_BUNDLE_CACHE = bundle
    return _INTEGRATION_BUNDLE_CACHE


def _reject_json_constant(language):
    raise ValueError(translate("invalid_input", language))


def _parse_finite_json_float(value, language):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(translate("invalid_input", language))
    return number


def render_quickstart(content: bytes, language: str) -> bytes:
    """Render the bundled quick-start Markdown without adding a dependency."""
    language = language if language in ("ja", "en") else "ja"
    detailed_guide = f"/guide/{language}"

    def inline(text):
        parts, position = [], 0
        pattern = re.compile(r"`([^`]+)`|\*\*([^*]+)\*\*")
        for match in pattern.finditer(text):
            parts.append(html.escape(text[position:match.start()]))
            if match.group(1) is not None:
                value = match.group(1)
                if value == detailed_guide:
                    parts.append(f'<a href="{detailed_guide}">{html.escape(value)}</a>')
                else:
                    parts.append(f"<code>{html.escape(value)}</code>")
            else:
                parts.append(f"<strong>{html.escape(match.group(2))}</strong>")
            position = match.end()
        parts.append(html.escape(text[position:]))
        return "".join(parts)

    blocks, paragraph, list_items = [], [], []

    def flush():
        if paragraph:
            blocks.append("<p>" + inline(" ".join(paragraph)) + "</p>")
            paragraph.clear()
        if list_items:
            blocks.append("<ul>" + "".join(f"<li>{inline(item)}</li>" for item in list_items) + "</ul>")
            list_items.clear()

    for raw_line in content.decode("utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            flush()
        elif line.startswith("# "):
            flush()
            blocks.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.startswith("## "):
            flush()
            blocks.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("- "):
            if paragraph:
                flush()
            list_items.append(line[2:])
        else:
            if list_items:
                flush()
            paragraph.append(line)
    flush()
    title = "Create your first sample" if language == "en" else "まずはサンプルを作る"
    back_label = "Back to the generator" if language == "en" else "生成画面に戻る"
    page = f'''<!doctype html>
<html lang="{language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; object-src 'none'; base-uri 'none'; form-action 'none">
<title>{html.escape(title)}</title><style>*{{box-sizing:border-box}}body{{margin:0;background:#f3f6fa;color:#233247;font:16px/1.7 system-ui,-apple-system,"Segoe UI",sans-serif}}main{{max-width:780px;margin:32px auto;padding:28px;background:white;border:1px solid #dfe7eb;border-radius:10px}}h1{{margin-top:0;font-size:26px}}h2{{margin-top:28px;font-size:19px;color:#214e4c}}p,ul{{margin:12px 0}}li{{padding:3px 0}}code{{padding:2px 5px;background:#f0f4f6;border-radius:4px;font-size:.92em}}a{{color:#126653}}.back-link{{display:inline-block;margin-bottom:18px;font-size:14px}}a:focus-visible{{outline:3px solid #397ca7;outline-offset:3px}}@media(max-width:820px){{main{{margin:12px;padding:20px;border-radius:0}}}}</style></head>
<body><main><nav aria-label="{html.escape(back_label)}"><a class="back-link" href="/">← {html.escape(back_label)}</a></nav>{''.join(blocks)}</main></body></html>'''
    return page.encode("utf-8")


class LocalThreadingHTTPServer(ThreadingHTTPServer):
    """Bound local client threads and slow-request resource use."""

    daemon_threads = True

    def __init__(self, server_address, handler):
        self.worker_slots = threading.BoundedSemaphore(MAX_HTTP_WORKERS)
        super().__init__(server_address, handler)

    def handle_error(self, request, client_address):
        # The base implementation prints a traceback and peer address. Keep
        # unexpected handler failures structured and avoid request details.
        error_type = sys.exc_info()[0]
        record = {"event": "http_handler_error",
                  "error_type": error_type.__name__ if error_type else "UnknownError"}
        try:
            print(json.dumps(record, separators=(",", ":"), allow_nan=False), flush=True)
        except OSError:
            pass

    def get_request(self):
        connection, address = super().get_request()
        # Covers slow headers and request bodies. This is an inactivity timeout,
        # not a limit on how long a normal response may take to finish.
        connection.settimeout(REQUEST_TIMEOUT_SECONDS)
        return connection, address

    def process_request(self, request, client_address):
        if not self.worker_slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.worker_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.worker_slots.release()


class Handler(BaseHTTPRequestHandler):
    server_version = "Physalia"
    sys_version = ""

    def log_message(self, format, *args):
        # URLs and request bodies can contain sensitive token material.
        return

    def handle(self):
        # The socket timeout limits inactivity between bytes. Also bound the
        # complete request-line/header phase so a slow client cannot occupy a
        # worker indefinitely by dripping bytes before the body deadline starts.
        self._start_header_deadline()
        try:
            super().handle()
        except (OSError, socket.timeout):
            self.close_connection = True
        finally:
            self._header_deadline_timer.cancel()

    def _start_header_deadline(self):
        self._request_headers_complete = False
        self._header_deadline_timer = threading.Timer(
            REQUEST_HEADER_DEADLINE_SECONDS, self._abort_incomplete_headers)
        self._header_deadline_timer.daemon = True
        self._header_deadline_timer.start()

    def _abort_incomplete_headers(self):
        if not self._request_headers_complete:
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def handle_one_request(self):
        # The base implementation reads the request line before parse_request.
        # Start each persistent-connection deadline before that read as well.
        if self._request_headers_complete:
            self._start_header_deadline()
        return super().handle_one_request()

    def parse_request(self):
        parsed = super().parse_request()
        self._request_headers_complete = True
        self._header_deadline_timer.cancel()
        return parsed

    def _headers(self, status: int, mime: str, body: bytes, csp: str | None = None):
        # Request parsing uses a short timeout to bound slow clients. Give
        # finite artifact responses a longer write window so large downloads
        # are not cut off by the request-header timeout.
        self.connection.settimeout(RESPONSE_WRITE_TIMEOUT_SECONDS)
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()")
        self.send_header("Content-Security-Policy", csp or "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict):
        self._headers(status, "application/json; charset=utf-8",
                      json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"))

    def _single_header(self, name):
        values = self.headers.get_all(name, [])
        return values[0] if len(values) == 1 else None

    def _read_body(self, size):
        deadline = time.monotonic() + REQUEST_BODY_TIMEOUT_SECONDS
        body = bytearray()
        while len(body) < size:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            self.connection.settimeout(remaining)
            chunk = self.rfile.read1(min(REQUEST_BODY_CHUNK_BYTES, size - len(body)))
            if not chunk:
                break
            body.extend(chunk)
        self.connection.settimeout(REQUEST_TIMEOUT_SECONDS)
        return body

    @staticmethod
    def _unique_json_object(pairs, language):
        result = {}
        normalized_keys = set()
        for key, value in pairs:
            normalized = key.casefold()
            if normalized in normalized_keys:
                raise ValueError(translate("invalid_input", language))
            result[key] = value
            normalized_keys.add(normalized)
        return result

    def _valid_host(self):
        return self._single_header("Host") == f"127.0.0.1:{self.server.server_port}"

    def _language(self):
        language = self.headers.get("X-ADG-Language", "ja")
        return language if language in ("ja", "en") else "ja"

    def do_GET(self):
        language = self._language()
        if not self._valid_host():
            return self._json(403, {"error": translate("forbidden_host", language)})
        if self.path == "/api/database-templates":
            return self._json(200, {"templates": public_templates(language)})
        if self.path == "/license":
            content = (STATIC.parent / "LICENSE").read_bytes()
            return self._headers(200, "text/plain; charset=utf-8", content)
        if self.path in ("/guide", "/guide/en", "/guide/ja"):
            suffix = "en" if self.path.endswith("/en") else "ja"
            content = (STATIC.parent / "docs" / f"deployment_{suffix}.md").read_bytes()
            return self._headers(200, "text/plain; charset=utf-8", content)
        if self.path in ("/quickstart/en", "/quickstart/ja"):
            suffix = "en" if self.path.endswith("/en") else "ja"
            content = (STATIC.parent / "docs" / f"quickstart_{suffix}.md").read_bytes()
            return self._headers(
                200, "text/html; charset=utf-8", render_quickstart(content, suffix),
                csp="default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
            )
        if self.path in ("/log-guide/en", "/log-guide/ja"):
            suffix = "en" if self.path.endswith("/en") else "ja"
            content = (STATIC.parent / "docs" / f"log-review-guide_{suffix}.md").read_bytes()
            return self._headers(
                200, "text/html; charset=utf-8", render_quickstart(content, suffix),
                csp="default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
            )
        if self.path in ("/legal/en", "/legal/ja"):
            suffix = "en" if self.path.endswith("/en") else "ja"
            content = (STATIC.parent / "docs" / f"legal_{suffix}.md").read_bytes()
            return self._headers(200, "text/plain; charset=utf-8", content)
        if self.path == "/integration-kit.zip":
            return self._headers(200, "application/zip", integration_bundle())
        files = {"/": ("index.html", "text/html; charset=utf-8"),
                 "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                 "/json_utils.js": ("json_utils.js", "text/javascript; charset=utf-8"),
                 "/style.css": ("style.css", "text/css; charset=utf-8"),
                 }
        if self.path not in files:
            return self._json(404, {"error": translate("not_found", language)})
        name, mime = files[self.path]
        content = (STATIC / name).read_bytes()
        if name == "index.html":
            content = content.replace(b"__SESSION_TOKEN__", SESSION_TOKEN.encode("ascii"))
            content = content.replace(b"__MAX_GENERATION_REQUEST_BYTES__", str(MAX_REQUEST).encode("ascii"))
            content = content.replace(b"__APP_VERSION__", html.escape(APP_VERSION).encode("utf-8"))
        self._headers(200, mime, content)

    def do_POST(self):
        # Some validation failures happen before the request body is consumed.
        # Never reuse that HTTP/1.1 connection and parse leftover body bytes as
        # a second request.
        self.close_connection = True
        language = self._language()
        origin = f"http://127.0.0.1:{self.server.server_port}"
        session_token = self._single_header("X-ADG-Token") or ""
        token_valid = session_token.isascii() and secrets.compare_digest(session_token, SESSION_TOKEN)
        if (not self._valid_host() or self._single_header("Origin") != origin
                or not token_valid):
            return self._json(403, {"error": translate("forbidden", language)})
        if self.path != "/api/generate":
            return self._json(404, {"error": translate("not_found", language)})
        content_types = self.headers.get_all("Content-Type", [])
        charset = self.headers.get_content_charset()
        if (len(content_types) != 1 or self.headers.get_content_type() != "application/json"
                or (charset is not None and charset.casefold() not in ("utf-8", "utf8"))):
            return self._json(415, {"error": translate("json_required", language)})
        try:
            lengths = self.headers.get_all("Content-Length", [])
            if self.headers.get_all("Transfer-Encoding") or len(lengths) != 1:
                raise ValueError(translate("invalid_input", language))
            raw_length = lengths[0]
            if not raw_length.isascii() or not raw_length.isdecimal():
                raise ValueError(translate("invalid_input", language))
            size = int(raw_length)
            if not 0 < size <= MAX_REQUEST:
                raise ValueError(translate("request_size", language))
            body = self._read_body(size)
            if len(body) != size:
                raise ValueError(translate("invalid_input", language))
            # JSON exchanged by the browser UI is UTF-8. Decode explicitly
            # instead of allowing json.loads(bytes) to auto-detect UTF-16/32,
            # which can make different clients interpret the same request
            # under different encodings.
            data = json.loads(body.decode("utf-8"), object_pairs_hook=lambda pairs: self._unique_json_object(pairs, language),
                              parse_constant=lambda _value: _reject_json_constant(language),
                              parse_float=lambda value: _parse_finite_json_float(value, language))
            if not isinstance(data, dict):
                raise ValueError(translate("invalid_input", language))
            if not GENERATION_SLOT.acquire(blocking=False):
                return self._json(429, {"error": translate("generation_in_progress", language)})
            try:
                asset = generate(data.get("kind"), data.get("settings"), language)
                def encode(item):
                    return {"name": item.name, "mime": item.mime, "role": item.role,
                            "content": base64.b64encode(item.content).decode("ascii")}
                response = {**encode(asset),
                            "companions": [encode(item) for item in asset.companions],
                            "summary": asset.summary}
                # Keep the generation slot until the encoded response is sent;
                # otherwise another large artifact can multiply peak memory.
                self._json(200, response)
            finally:
                GENERATION_SLOT.release()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # The client may close while a large artifact response is being
            # written. Do not attempt to send a second error response.
            self.close_connection = True
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
            self._json(400, {"error": translate("invalid_input", language)})
        except TimeoutError:
            self._json(408, {"error": translate("request_timeout", language)})
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
        except Exception:
            self._json(500, {"error": translate("generation_failed", language)})
def main():
    language_parser = argparse.ArgumentParser(add_help=False)
    language_parser.add_argument("--lang", choices=("ja", "en"), default="ja")
    language = language_parser.parse_known_args()[0].lang
    parser = argparse.ArgumentParser(description=translate("server_description", language), parents=[language_parser])
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true", help=translate("open_help", language))
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error(translate("port_error", language))
    try:
        server = LocalThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            parser.exit(1, translate("port_in_use", language, port=args.port) + "\n")
        raise
    url = f"http://127.0.0.1:{server.server_port}/"
    print(translate("server_started", language, url=url), flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
