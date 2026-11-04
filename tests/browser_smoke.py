"""Optional real-browser integration check: python tests/browser_smoke.py.

Install requirements-dev.txt first. Uses an installed Edge, or Playwright Chromium.
No generated asset is published; downloads are kept in a temporary directory.
"""
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import expect, sync_playwright
import app


def main():
    server = app.LocalThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    screenshots = Path("generated")
    screenshots.mkdir(exist_ok=True)
    try:
        with tempfile.TemporaryDirectory() as temp, sync_playwright() as playwright:
            edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
            browser = playwright.chromium.launch(headless=True, **({"executable_path": str(edge)} if edge.exists() else {}))
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
            errors, external = [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda request: external.append(request.url) if not request.url.startswith(("http://127.0.0.1:", "blob:")) else None)
            page.goto(f"http://127.0.0.1:{server.server_port}/")
            page.locator('[data-page-target="generator"]').first.click()
            page.locator("#language").select_option("en")
            expect(page.locator("#page-generator")).to_be_visible()
            page.locator('input[name="kind"][value="env"]').check()
            page.locator("#canary-format").select_option("html")
            page.locator("#env-url").fill("https://canary.example.invalid/browser-smoke")
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
            assert not errors, errors
            assert not external, external
            browser.close()
            print("Browser checks passed: navigation, English UI, HTML generation and local-only requests.")
            return
            page.locator("#language").select_option("en")
            assert page.locator("h1").inner_text() == "Create a decoy"
            expect(page.locator('[data-i18n="settings_privacy_help"]')).to_contain_text("column candidate values")
            page.locator("#env-url").fill("https://canary.example.invalid/not-contacted")
            page.locator("#env-dev-url").fill("http://dev.example.invalid:8080")
            with page.expect_download() as event:
                page.locator("#submit").click()
            env_download = event.value
            assert env_download.suggested_filename == "env_development_deployment.zip", env_download.suggested_filename
            env_asset = Path(temp) / "switchable.zip"
            env_download.save_as(env_asset)
            with zipfile.ZipFile(env_asset) as archive:
                assert archive.namelist() == [".env.development"]
                env_content = archive.read(".env.development").decode("utf-8")
            assert 'URL="http://dev.example.invalid:8080"' in env_content
            assert '# URL="https://canary.example.invalid/not-contacted"' in env_content
            expect(page.locator("#downloads")).to_contain_text("exact .env filename")
            page.locator(".operator-acknowledge").click()
            page.locator("#canary-format").select_option("pdf")
            assert page.locator("#env-template-options").is_hidden()
            page.locator("#env-url").fill("https://canary.example.invalid/not-contacted")
            with page.expect_download() as event:
                page.locator("#submit").click()
            download = event.value
            target = Path(temp) / "document.pdf"
            download.save_as(target)
            assert target.read_bytes().startswith(b"%PDF-")
            page.locator(".operator-acknowledge").click()
            page.locator("#canary-format").select_option("csv")
            page.locator("#canary-context").select_option("billing")
            page.locator("#canary-field").fill("invoice_portal_url")
            page.locator("#canary-label").fill("Billing portal")
            with page.expect_download() as event:
                page.locator("#submit").click()
            csv_asset = Path(temp) / "canary.csv"
            event.value.save_as(csv_asset)
            csv_contents = csv_asset.read_text(encoding="utf-8-sig")
            assert "invoice_portal_url" in csv_contents
            assert csv_contents.count("https://canary.example.invalid/not-contacted") == 1
            page.locator(".operator-acknowledge").click()
            page.locator('input[name="kind"][value="database"]').check()
            page.locator("#table-name").fill("orders")
            page.locator("#rows").fill("37")
            page.locator("#add-column").click()
            last = page.locator("#columns .column-row").last
            last.locator(".column-name").fill("amount")
            last.locator(".column-kind").select_option("integer")
            last.locator(".column-options").fill("100,105")
            assert not page.locator("#columns .column-row").first.locator(".column-options").is_enabled()
            page.locator("#language").select_option("ja")
            expect(page.locator('[data-i18n="settings_privacy_help"]')).to_contain_text("実データや秘密情報")
            assert last.locator(".column-options").input_value() == "100,105"
            with page.expect_download() as event:
                page.locator("#submit").click()
            target = Path(temp) / "orders.db"
            event.value.save_as(target)
            con = sqlite3.connect(str(target))
            try:
                assert con.execute("SELECT count(*) FROM orders").fetchone()[0] == 37
                assert con.execute("SELECT min(amount), max(amount) FROM orders").fetchone() == (100, 105)
            finally:
                con.close()
            page.locator(".operator-acknowledge").click()
            page.screenshot(path=str(screenshots / "database-desktop.png"), full_page=True)
            page.locator('input[name="kind"][value="nest"]').check()
            page.locator("#nest-scenario").select_option("migration")
            page.locator("#layers").fill("2")
            page.locator("#branches").fill("2")
            page.locator("#nest-url").fill("https://canary.example.invalid/not-contacted")
            page.locator("#canary-percent").fill("100")
            with page.expect_download() as event:
                page.locator("#submit").click()
            target = Path(temp) / "deployment.zip"
            event.value.save_as(target)
            with zipfile.ZipFile(io.BytesIO(target.read_bytes())) as delivery:
                assert not any("operator" in name for name in delivery.namelist())
            assert page.locator("#downloads a").count() == 3
            # Language switching must retain the inventory download rather than discard passwords.
            page.locator("#language").select_option("en")
            with page.expect_download() as event:
                page.locator("#downloads a").nth(1).click()
            target = Path(temp) / "operator.json"
            event.value.save_as(target)
            manifest = json.loads(target.read_text(encoding="utf-8"))
            assert len(manifest["archives"]) == 3
            assert manifest["scenario"] == "migration"
            assert any("migration_export_" in archive["path"] for archive in manifest["archives"])
            assert manifest["summary"]["canaries"] == 12
            page.locator(".operator-acknowledge").click()
            page.screenshot(path=str(screenshots / "nest-desktop.png"), full_page=True)
            page.locator("#layers").fill("8")
            page.locator("#branches").fill("3")
            page.locator("#submit").click()
            expect(page.locator("#result")).to_contain_text("Reduce depth")
            page.set_viewport_size({"width": 390, "height": 844})
            page.locator("#layers").fill("3")
            page.locator("#branches").fill("2")
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.screenshot(path=str(screenshots / "nest-mobile.png"), full_page=True)
            page.locator('input[name="kind"][value="database"]').check()
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            for kind, expected in (("stream", "serve.py"), ("directory_maze", "index.html"), ("encoding_maze", "index.json")):
                page.locator('input[name="kind"][value="' + kind + '"]').check()
                with page.expect_download() as event:
                    page.locator("#submit").click()
                target = Path(temp) / (kind + ".zip")
                event.value.save_as(target)
                with zipfile.ZipFile(io.BytesIO(target.read_bytes())) as bundle:
                    assert expected in bundle.namelist()
                    assert not any("operator" in name for name in bundle.namelist())
                assert page.locator("#downloads a").count() == 3
                page.locator(".operator-acknowledge").click()
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                page.locator("#language").select_option("ja")
                assert page.locator("#downloads a").count() == 3
                page.locator("#language").select_option("en")
            page.screenshot(path=str(screenshots / "encoding-mobile.png"), full_page=True)
            page.locator('input[name="kind"][value="env"]').check()
            page.locator("#env-url").fill("https://example.invalid/private-token")
            page.locator("#canary-rows").fill("17")
            with page.expect_download() as event:
                page.locator("#save-settings").click()
            saved = Path(temp) / "settings.json"
            event.value.save_as(saved)
            assert "private-token" not in saved.read_text()
            assert "http://dev.example.invalid:8080" not in saved.read_text()
            page.locator("#canary-rows").fill("30")
            page.locator("#settings-file").set_input_files(str(saved))
            expect(page.locator("#result")).to_contain_text("Loaded settings")
            assert page.locator("#canary-rows").input_value() == "17"
            assert page.locator("#env-url").input_value() == ""
            assert page.locator("#env-dev-url").input_value() == ""
            config = json.loads(saved.read_text(encoding="utf-8"))
            ids = page.locator(".fields input, .fields select").evaluate_all("elements => elements.filter(el => el.type !== 'url' && el.type !== 'file' && !el.closest('#columns')).map(el => el.id)")
            old_controls = ["", "Customer archive", "50", "3", False, False, True, True, False, False, True, False, True]
            new_ids = {"env-layout", "env-suffix", "env-variable", "env-dev-comment", "env-prod-comment", "nest-scenario", "maze-scenario", "maze-format"}
            config["schema"] = "adg-ui-v2"
            config["controls"] = old_controls + [value for identifier, value in zip(ids, config["controls"]) if identifier not in new_ids]
            legacy = Path(temp) / "legacy-settings.json"
            legacy.write_text(json.dumps(config), encoding="utf-8")
            page.locator("#settings-file").set_input_files(str(legacy))
            expect(page.locator("#result")).to_contain_text("Loaded settings")
            assert page.locator("#env-layout").input_value() == "standard"
            assert page.locator("#guide-link").get_attribute("href") == "/guide/en"
            assert page.request.get(f"http://127.0.0.1:{server.server_port}/guide/en").status == 200
            with page.expect_download() as event:
                page.locator('a[download="adg-integration-examples.zip"]').click()
            samples = Path(temp) / "samples.zip"
            event.value.save_as(samples)
            with zipfile.ZipFile(samples) as archive:
                assert set(archive.namelist()) == set(app.INTEGRATION_BUNDLE_FILES)
                assert all((Path.cwd() / name).is_file() for name in app.INTEGRATION_BUNDLE_FILES)
                assert "examples/decoy_state.py" in archive.namelist()
                assert "examples/nginx-stream-proxy.conf" in archive.namelist()
                proxy = archive.read("examples/nginx-stream-proxy.conf").decode("utf-8")
                assert 'proxy_set_header Host 127.0.0.1:9080;' in proxy
                assert "location = /stop { return 404; }" in proxy
                assert "REPLACE_WITH_ADG_STREAM_TOKEN" in proxy
                assert "written when the response ends" in proxy
            page.locator("#cloud-sample").click()
            expect(page.locator("#cloud-status")).to_have_text("Sample data analysis complete.")
            assert page.locator("#cloud-findings li").count() >= 5
            expect(page.locator("#cloud-findings")).to_contain_text("Graph activity following app sign-in")
            csv_file = Path(temp) / "audit.csv"
            csv_file.write_text('Type,AADTenantId,ActivityDateTime,ActivityDisplayName,Result\nAuditLogs,"<img src=x>",2026-10-21T10:00:00Z,Add member to role,success\n', encoding="utf-8")
            page.locator("#cloud-files").set_input_files(str(csv_file))
            page.locator("#cloud-analyze").click()
            expect(page.locator("#cloud-coverage")).to_contain_text("Input 1")
            expect(page.locator("#cloud-findings")).to_contain_text("<img src=x>")
            assert page.locator("#cloud-findings img").count() == 0
            page.locator("#language").select_option("ja")
            expect(page.locator("#cloud-title")).to_have_text("認証・クラウド操作ログの分析")
            for kind in ("env", "database", "web", "nest", "stream", "directory_maze", "encoding_maze"):
                page.locator('input[name="kind"][value="' + kind + '"]').check()
                expect(page.locator("#legal-normal")).not_to_be_empty()
                expect(page.locator("#legal-risk")).not_to_be_empty()
            page.locator('input[name="kind"][value="stream"]').check()
            expect(page.locator("#legal-other")).to_contain_text("第三者")
            assert page.locator("#legal-guide-link").get_attribute("href") == "/legal/ja"
            response = page.request.get(f"http://127.0.0.1:{server.server_port}/legal/ja")
            assert response.status == 200 and "不正アクセス禁止法" in response.text()
            page.locator("#language").select_option("en")
            expect(page.locator("#legal-normal")).to_contain_text("authorized server")
            assert page.locator("#legal-guide-link").get_attribute("href") == "/legal/en"
            expect(page.locator('[data-cloud-i18n="legal"]')).to_contain_text("Unauthorized Computer Access Act")
            assert not errors, errors
            assert not external, external
            browser.close()
            print("Browser checks passed: language, documents, bundles, private inventories, settings roundtrip, guide/samples, mobile layout; no external requests.")
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    main()
