"""Small real-browser smoke test for the local generation flow.

Install requirements-dev.txt first. Uses installed Edge or Playwright Chromium.
Generated files and browser data stay in temporary storage.
"""

import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import expect, sync_playwright

import app


def main():
    server = app.LocalThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory() as temp, sync_playwright() as playwright:
            edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
            browser = playwright.chromium.launch(
                headless=True,
                **({"executable_path": str(edge)} if edge.exists() else {}),
            )
            try:
                page = browser.new_page(accept_downloads=True)
                errors, external = [], []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on(
                    "request",
                    lambda request: (
                        external.append(request.url)
                        if not request.url.startswith(("http://127.0.0.1:", "blob:"))
                        else None
                    ),
                )
                page.goto(f"http://127.0.0.1:{server.server_port}/")
                page.locator('[data-page-target="generator"]').first.click()
                page.locator("#language").select_option("en")
                expect(page.locator("#page-generator")).to_be_visible()
                page.locator('input[name="kind"][value="env"]').check()
                page.locator("#canary-format").select_option("html")
                page.locator("#env-url").fill(
                    "https://canary.example.invalid/browser-smoke"
                )
                page.locator("#submit").click()
                expect(page.locator("#downloads")).to_be_visible()
                with page.expect_download() as download_event:
                    page.locator("#downloads a[download]").first.click()
                download = download_event.value
                assert download.suggested_filename.startswith("Physalia_")
                assert download.suggested_filename.endswith(".html")
                target = Path(temp) / download.suggested_filename
                download.save_as(target)
                document = target.read_text(encoding="utf-8")
                assert "<!doctype html>" in document.lower()
                assert "https://canary.example.invalid/browser-smoke" in document
                requests = []
                page.on("request", lambda request: requests.append(request.post_data_json)
                        if request.method == "POST" and request.url.endswith("/api/generate") else None)
                page.locator('input[name="kind"][value="fake_trap"]').check()
                for enabled, url in ((False, "https://canary.example.invalid/private"),
                                     (True, ""),
                                     (True, "https://canary.example.invalid/fake-trap")):
                    page.locator("#fake-embed-canary").check()
                    page.locator("#fake-canary-url").fill(url)
                    if not enabled:
                        page.locator("#fake-embed-canary").uncheck()
                    page.locator("#submit").click()
                    expect(page.locator("#downloads")).to_be_visible()
                    with page.expect_download() as download_event:
                        page.locator("#downloads a[download]").first.click()
                    trap_file = Path(temp) / "fake-trap.html"
                    download_event.value.save_as(trap_file)
                    trap_html = trap_file.read_text(encoding="utf-8")
                    settings = requests[-1]["settings"]
                    assert settings["embed_canary"] == bool(enabled and url), settings
                    assert settings["canary_url"] == (url if enabled else ""), settings
                    assert ("contact-marker\" src=" in trap_html) == bool(enabled and url)
                    if url:
                        assert (url in trap_html) == bool(enabled), trap_html
                assert not errors, errors
                assert not external, external
                print(
                    "Browser checks passed: navigation, English UI, HTML generation and local-only requests."
                )
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    main()
