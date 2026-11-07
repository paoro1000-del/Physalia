import base64
from datetime import date, datetime, timedelta
import http.client
import json
import re
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.exceptions import InvalidTag

import app
import decrypt
from physalia.generators import decrypt_layer, encrypt_layer, generate


class GeneratorTests(unittest.TestCase):
    def test_nested_encryption_round_trip_and_wrong_password(self):
        data = b'{"record":"sample"}'
        for _ in range(3):
            data = encrypt_layer(data, "example-passphrase")
        with self.assertRaises(InvalidTag):
            decrypt_layer(data, "wrong-password")
        for _ in range(3):
            data = decrypt_layer(data, "example-passphrase")
        self.assertEqual(json.loads(data)["record"], "sample")

    def test_decrypt_command_never_overwrites_output(self):
        data = encrypt_layer(encrypt_layer(b'{}', "example-passphrase"), "example-passphrase")
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "input.adg", Path(directory) / "output.json"
            source.write_bytes(data)
            output.write_text("existing", encoding="utf-8")
            with patch("decrypt.getpass.getpass", return_value="example-passphrase"), patch(
                "sys.argv", ["decrypt.py", str(source), str(output)]
            ):
                with self.assertRaises(SystemExit) as stopped:
                    decrypt.main()
            self.assertEqual(stopped.exception.code, 2)
            self.assertEqual(output.read_text(encoding="utf-8"), "existing")

    def test_database_is_a_real_sqlite_database_with_synthetic_rows(self):
        _, _, data = generate("database", {"rows": 7})
        connection = sqlite3.connect(":memory:")
        try:
            connection.deserialize(data)
            records = connection.execute("SELECT email FROM customers").fetchall()
            self.assertEqual(len(records), 7)
            self.assertTrue(all(email.rsplit("@", 1)[1].endswith("example.invalid") for (email,) in records))
        finally:
            connection.close()

    def test_synthetic_dates_and_card_expiries_follow_generation_time(self):
        asset = generate("database", {"rows": 100, "columns": [
            {"name": "last_seen", "kind": "date"},
            {"name": "updated_at", "kind": "datetime"},
            {"name": "card_expiry", "kind": "card_expiry"},
        ]})
        connection = sqlite3.connect(":memory:")
        try:
            connection.deserialize(asset.content)
            today, now = date.today(), datetime.now()
            lower_date = today - timedelta(days=730)
            lower_time = now - timedelta(days=730)
            for last_seen, updated_at, expiry in connection.execute(
                    "SELECT last_seen, updated_at, card_expiry FROM customers"):
                self.assertGreaterEqual(date.fromisoformat(last_seen), lower_date)
                self.assertLessEqual(date.fromisoformat(last_seen), today)
                timestamp = datetime.fromisoformat(updated_at)
                self.assertGreaterEqual(timestamp, lower_time)
                self.assertLessEqual(timestamp, now)
                month, year = map(int, expiry.split("/"))
                self.assertIn(month, range(1, 13))
                self.assertGreater(year, today.year % 100)
                self.assertLessEqual(year, (today.year + 5) % 100)
        finally:
            connection.close()

    def test_env_preserves_token_and_does_not_accept_line_injection(self):
        url = "https://canary.example.invalid/token?key=example"
        _, _, content = generate("env", {"canary_url": url})
        self.assertIn(url, content.decode())
        with self.assertRaises(ValueError):
            generate("env", {"canary_url": "https://example.invalid/\nINJECTED=yes"})

    def test_canary_url_rejects_values_that_cannot_reach_the_monitor(self):
        for url in (
            "https://canary.example.invalid/token#fragment",
            "https://bad host.invalid/token",
            "https://bad..host.invalid/token",
            "https://-bad.example.invalid/token",
            "https://canary.example.invalid:0/token",
            "https://canary.example.invalid:65536/token",
            "https://user@canary.example.invalid/token",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                generate("web", {"canary_url": url})
        url = "https://canary.example.invalid:8443/token?ref=example"
        self.assertIn(url.encode(), generate("web", {"canary_url": url}).content)

    def test_web_rejects_retired_title_and_unsafe_url(self):
        with self.assertRaises(ValueError):
            generate("web", {"title": '<script>alert(1)</script>', "canary_url": ""})
        with self.assertRaises(ValueError):
            generate("web", {"canary_url": "javascript:alert(1)"})

    def test_generated_web_uses_selected_language(self):
        for language, expected in (("ja", "アーカイブの一覧"), ("en", "Archive list")):
            _, _, content = generate("web", {"scenario": "archive", "canary_url": ""}, language)
            page = content.decode("utf-8")
            self.assertIn('<html lang="' + language + '">', page)
            self.assertIn("最近のファイル" if language == "ja" else "Archive index", page)

    def test_cli_language_option(self):
        for command, expected in (("app.py", "Start the local GUI"), ("decrypt.py", "Decrypt the layers")):
            completed = subprocess.run([sys.executable, command, "--lang", "en", "--help"],
                                       check=True, capture_output=True, text=True, encoding="utf-8")
            self.assertIn(expected, completed.stdout)

    def test_english_catalog_covers_interface_translation_keys(self):
        result = subprocess.run([sys.executable, "scripts/check_ui_translations.py"],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_resource_parameters_are_rejected(self):
        for payload in ({"rows": 0}, {"rows": 100001}, {"rows": True}):
            with self.assertRaises(ValueError):
                generate("database", payload)
        with self.assertRaises(ValueError):
            generate("nest", {"layers": 9})


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = app.LocalThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.host = f"127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def test_page_and_authorized_generation(self):
        status, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(app.SESSION_TOKEN.encode(), body)
        payload = json.dumps({"kind": "env", "settings": {"canary_url": ""}})
        status, body = self.request("POST", "/api/generate", payload, {
            "Content-Type": "application/json", "Origin": "http://" + self.host,
            "X-ADG-Token": app.SESSION_TOKEN,
        })
        self.assertEqual(status, 200)
        self.assertIn(b"example.invalid", base64.b64decode(json.loads(body)["content"]))

    def test_page_uses_configured_version(self):
        with patch.object(app, "APP_VERSION", "2.1.0 <preview>"):
            status, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"ver: 2.1.0 &lt;preview&gt;", body)
        self.assertNotIn(b"__APP_VERSION__", body)

    def test_cross_origin_and_dns_rebinding_are_rejected(self):
        payload = json.dumps({"kind": "env", "settings": {}})
        status, _ = self.request("POST", "/api/generate", payload, {
            "Content-Type": "application/json", "Origin": "https://attacker.invalid",
            "X-ADG-Token": app.SESSION_TOKEN,
        })
        self.assertEqual(status, 403)
        status, _ = self.request("GET", "/", headers={"Host": "attacker.invalid"})
        self.assertEqual(status, 403)
        status, _ = self.request("POST", "/api/generate", payload, {
            "Content-Type": "application/json", "Origin": "http://" + self.host,
            "X-ADG-Token": "incorrect",
        })
        self.assertEqual(status, 403)

    def test_api_errors_follow_selected_language(self):
        payload = json.dumps({"kind": "database", "settings": {"rows": 0}})
        for language, expected in (("ja", "件数"), ("en", "Record count")):
            status, body = self.request("POST", "/api/generate", payload, {
                "Content-Type": "application/json", "Origin": "http://" + self.host,
                "X-ADG-Token": app.SESSION_TOKEN, "X-ADG-Language": language,
            })
            self.assertEqual(status, 400)
            self.assertIn(expected, json.loads(body)["error"])
if __name__ == "__main__":
    unittest.main()
