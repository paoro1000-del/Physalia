import csv
import io
import itertools
import json
import sqlite3
import string
import unittest
import zipfile
from unittest.mock import patch

from openpyxl import load_workbook
from pptx import Presentation
import pyzipper

from physalia.formats import FORMATS
from physalia.generators import generate
from physalia.passwords import make_password, validate_policy

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

URL = "https://canary.example.invalid/unique-token?ref=testing&mode=archive"


class DocumentTests(unittest.TestCase):
    def test_commented_production_env_is_a_realistic_inert_configuration(self):
        settings = {"format": "env", "env_layout": "commented_production", "canary_url": URL,
                    "env_dev_url": "http://dev.example.invalid:8080", "env_variable": "URL"}
        asset = generate("env", settings)
        self.assertEqual(asset.name, ".env.development")
        self.assertEqual(asset.companions[0].role, "deployment")
        with zipfile.ZipFile(io.BytesIO(asset.companions[0].content)) as package:
            self.assertEqual(package.namelist(), [".env.development"])
            self.assertEqual(package.read(".env.development"), asset.content)
        inventory = json.loads(asset.companions[1].content)
        self.assertEqual(inventory["operator_files"], [])
        self.assertEqual(inventory["deployment_packages"][0]["name"], asset.companions[0].name)
        content = asset.content.decode("utf-8")
        self.assertIn('URL="http://dev.example.invalid:8080"', content)
        self.assertIn('# URL="' + URL + '"', content)
        self.assertIn("本番環境用URL", content)
        self.assertFalse(any(URL in line and not line.lstrip().startswith("#") for line in content.splitlines()))
        self.assertEqual(content.count(URL), 1)
        custom = generate("env", {**settings, "env_suffix": "staging", "env_variable": "API_URL",
                                  "env_dev_comment": "Local endpoint", "env_prod_comment": "Release endpoint"}, "en")
        self.assertEqual(custom.name, ".env.staging")
        self.assertIn('# API_URL="' + URL + '"', custom.content.decode())
        self.assertIn("# Release endpoint", custom.content.decode())
        named = generate("env", {**settings, "filename": "team_config"})
        self.assertEqual(named.name, "team_config.env")

    def test_commented_env_rejects_injected_keys_urls_comments_and_filenames(self):
        base = {"format": "env", "env_layout": "commented_production", "canary_url": URL}
        invalid = ({"env_suffix": "../production"}, {"env_variable": "X\nBAD=1"},
                   {"env_dev_url": "http://example.invalid/$(whoami)"}, {"env_dev_url": "http://example.invalid/\"bad"},
                   {"env_dev_comment": "ok\nBAD=1"}, {"canary_url": "https://example.invalid/$(whoami)"})
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                generate("env", {**base, **value})
        empty = generate("env", {**base, "canary_url": ""})
        self.assertIn('# URL="https://example.invalid/replace-me"', empty.content.decode())

    def test_custom_canary_context_in_text_formats_and_database(self):
        settings = {"canary_context": "billing", "canary_field": "finance_portal_url", "canary_label": "請求明細", "canary_url": URL, "rows": 3}
        env = generate("env", {**settings, "format": "env"}).content.decode()
        self.assertIn("FINANCE_PORTAL_URL='" + URL + "'", env)
        doc = json.loads(generate("env", {**settings, "format": "json"}).content)
        self.assertEqual(doc["finance_portal_url"], URL)
        rows = list(csv.reader(io.StringIO(generate("env", {**settings, "format": "csv"}).content.decode("utf-8-sig"))))
        self.assertEqual(rows[0][-1], "finance_portal_url")
        self.assertEqual([row[-1] for row in rows[1:]], [URL, "", ""])
        content = generate("env", {**settings, "format": "txt"}).content.decode()
        self.assertIn("請求明細: " + URL, content)
        con = sqlite3.connect(":memory:")
        try:
            con.deserialize(generate("env", {**settings, "format": "sqlite"}).content)
            self.assertEqual(con.execute("SELECT name, endpoint FROM billing_links").fetchone(), ("finance_portal_url", URL))
        finally:
            con.close()

    def test_custom_canary_context_in_hyperlinked_documents(self):
        settings = {"canary_context": "support", "canary_field": "portal_url", "canary_label": '=1+1', "canary_url": URL, "rows": 3}
        book = load_workbook(io.BytesIO(generate("env", {**settings, "format": "xlsx"}).content))
        try:
            self.assertNotIn("Connections", book.sheetnames)
            self.assertEqual(book["Accounts"]["E2"].value, "portal_url")
            self.assertEqual(book["Accounts"]["E3"].value, "=1+1")
            self.assertEqual(book["Accounts"]["E3"].data_type, "s")
            self.assertEqual(book["Accounts"]["E3"].hyperlink.target, URL)
        finally:
            book.close()
        presentation = Presentation(io.BytesIO(generate("env", {**settings, "format": "pptx"}).content))
        links = [(run.text, run.hyperlink.address) for slide in presentation.slides for shape in slide.shapes if shape.has_text_frame
                 for paragraph in shape.text_frame.paragraphs for run in paragraph.runs if run.hyperlink.address]
        self.assertIn(("=1+1", URL), links)
        html = generate("env", {**settings, "format": "html", "canary_label": "<portal>"}).content.decode()
        self.assertIn("&lt;portal&gt;", html)
        self.assertIn(URL.replace("&", "&amp;"), html)
        if PdfReader:
            pdf = PdfReader(io.BytesIO(generate("env", {**settings, "format": "pdf"}).content))
            self.assertEqual(pdf.pages[0]["/Annots"][0].get_object()["/A"]["/URI"], URL)

    def test_context_validates_keys_and_profile_without_line_injection(self):
        for invalid in ("title", "id", "APP_ENV", "bad\nINJECTED=1", 'bad";DROP_TABLE'):
            with self.subTest(field=invalid), self.assertRaises(ValueError):
                generate("env", {"canary_context": "service", "canary_field": invalid})
        with self.assertRaises(ValueError):
            generate("env", {"canary_context": "unknown"})
        with self.assertRaises(ValueError):
            generate("env", {"canary_context": "service", "canary_label": "bad\nline"})

    def test_env_uses_hidden_configuration_name_by_default(self):
        self.assertEqual(generate("env", {"format": "env"}).name, ".env")

    def test_all_formats_have_real_structures_and_preserve_url(self):
        for fmt in FORMATS:
            with self.subTest(fmt=fmt):
                asset = generate("env", {"format": fmt, "canary_url": URL, "rows": 3, "title": "取引先 <Archive> & accounts", "filename": "quarterly_report"})
                self.assertTrue(asset.name.startswith("quarterly_report."))
                data = asset.content
                if fmt == "xlsx":
                    book = load_workbook(io.BytesIO(data))
                    self.assertEqual(book["Accounts"].max_row, 5)
                    self.assertEqual(book["Connections"]["B2"].hyperlink.target, URL)
                    book.close()
                elif fmt == "pptx":
                    presentation = Presentation(io.BytesIO(data))
                    self.assertEqual(len(presentation.slides), 2)
                    links = [run.hyperlink.address for slide in presentation.slides for shape in slide.shapes if shape.has_text_frame
                             for paragraph in shape.text_frame.paragraphs for run in paragraph.runs]
                    self.assertIn(URL, links)
                elif fmt == "sqlite":
                    con = sqlite3.connect(":memory:")
                    try:
                        con.deserialize(data)
                        self.assertEqual(con.execute("SELECT count(*) FROM customers").fetchone()[0], 3)
                        self.assertEqual(con.execute("SELECT endpoint FROM service_connections").fetchone()[0], URL)
                    finally:
                        con.close()
                elif fmt == "pdf":
                    self.assertTrue(data.startswith(b"%PDF-"))
                    self.assertTrue(data.rstrip().endswith(b"%%EOF"))
                elif fmt == "csv":
                    rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))
                    self.assertEqual(len(rows), 4)
                    self.assertEqual(rows[1][-1], URL)
                elif fmt == "json":
                    doc = json.loads(data)
                    self.assertEqual(len(doc["records"]), 3)
                    self.assertEqual(doc["archive_endpoint"], URL)
                elif fmt == "html":
                    self.assertIn(b"&lt;Archive&gt;", data)
                    self.assertIn(URL.replace("&", "&amp;").encode(), data)
                    self.assertNotIn(b"<script", data)
                else:
                    self.assertIn(URL.encode(), data)

    @unittest.skipUnless(PdfReader, "Install requirements-dev.txt for PDF parser verification")
    def test_pdf_is_readable_and_has_click_link_without_auto_actions(self):
        asset = generate("env", {"format": "pdf", "title": "顧客情報", "rows": 80, "canary_url": URL})
        pdf = PdfReader(io.BytesIO(asset.content))
        self.assertGreater(len(pdf.pages), 1)
        self.assertIn("顧客情報", pdf.pages[0].extract_text())
        self.assertNotIn("/OpenAction", pdf.trailer["/Root"])
        annotations = [a.get_object() for a in pdf.pages[0]["/Annots"]]
        self.assertEqual(annotations[0]["/A"]["/URI"], URL)
        self.assertEqual(annotations[0]["/A"]["/S"], "/URI")

    def test_excel_title_is_literal_text_not_formula(self):
        asset = generate("env", {"format": "xlsx", "title": '=HYPERLINK("https://example.invalid","text")'})
        book = load_workbook(io.BytesIO(asset.content))
        self.assertEqual(book.active["A1"].data_type, "s")
        book.close()

    def test_filename_and_invalid_format_rejected(self):
        for name in ("../escape", "C:\\file", "a/b", "NUL", "CON", "trailing."):
            with self.subTest(name=name), self.assertRaises(ValueError):
                generate("env", {"filename": name})
        with self.assertRaises(ValueError):
            generate("env", {"format": "exe"})


class SchemaTests(unittest.TestCase):
    def test_decimal_rounding_never_escapes_narrow_bounds(self):
        asset = generate("database", {"rows": 20, "columns": [{"name": "amount", "kind": "decimal", "min": 50.501, "max": 50.509}]})
        con = sqlite3.connect(":memory:")
        try:
            con.deserialize(asset.content)
            self.assertTrue(all(50.501 <= amount <= 50.509 for (amount,) in con.execute("SELECT amount FROM customers")))
        finally:
            con.close()

    def test_custom_schema_types_ranges_candidates_and_record_count(self):
        columns = [
            {"name": "order_id", "kind": "id"}, {"name": "contact", "kind": "name"},
            {"name": "total", "kind": "decimal", "min": 50.5, "max": 60.5},
            {"name": "quantity", "kind": "integer", "min": 2, "max": 4},
            {"name": "state", "kind": "status", "values": ["approved", "queued"]},
            {"name": "memo", "kind": "text", "values": ["O'Brien; DROP TABLE orders; --"]},
            {"name": "created_on", "kind": "date"}, {"name": "reference", "kind": "uuid"},
        ]
        asset = generate("database", {"table": "orders", "columns": columns, "rows": 137})
        con = sqlite3.connect(":memory:")
        try:
            con.deserialize(asset.content)
            schema = con.execute("PRAGMA table_info(orders)").fetchall()
            self.assertEqual([v[1] for v in schema], [c["name"] for c in columns])
            self.assertEqual([v[2] for v in schema][:4], ["INTEGER", "TEXT", "REAL", "INTEGER"])
            data = con.execute("SELECT * FROM orders").fetchall()
            self.assertEqual(len(data), 137)
            self.assertEqual(data[-1][0], 137)
            self.assertTrue(all(50.5 <= r[2] <= 60.5 and 2 <= r[3] <= 4 and r[4] in ("approved", "queued") for r in data))
            self.assertEqual(data[0][5], columns[5]["values"][0])
            self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        finally:
            con.close()

    def test_invalid_schema_does_not_execute_sql(self):
        settings = [
            {"table": 'bad"; DROP TABLE x; --'}, {"columns": []}, {"columns": [{"name": "id", "kind": "unknown"}]},
            {"columns": [{"name": "id", "kind": "id"}, {"name": "ID", "kind": "text"}]},
            {"columns": [{"name": "x", "kind": "integer", "min": 9, "max": 1}]},
            {"columns": [{"name": "x", "kind": "decimal", "min": float("inf")}]},
            {"columns": [{"name": "x", "kind": "text", "values": []}]},
            {"columns": [{"name": "sqlite_test", "kind": "text"}]},
        ]
        for setting in settings:
            with self.subTest(setting=setting), self.assertRaises(ValueError):
                generate("database", setting)


class NestTests(unittest.TestCase):
    def walk(self, content, manifest):
        entries = {entry["path"]: entry for entry in manifest["archives"]}
        seen, docs = [], []
        def visit(data, location):
            entry = entries[location]
            seen.append(location)
            with pyzipper.AESZipFile(io.BytesIO(data)) as archive:
                self.assertTrue(all(info.flag_bits & 1 for info in archive.infolist()))
                with self.assertRaises((RuntimeError, pyzipper.BadZipFile)):
                    archive.read(archive.namelist()[0], pwd=b"not-the-password")
                for name in archive.namelist():
                    self.assertFalse(name.startswith("/") or ".." in name.split("/"))
                    value = archive.read(name, pwd=entry["password"].encode())
                    if name.endswith(".zip"):
                        visit(value, location + "!/" + name)
                    elif not name.endswith(".access.txt"):
                        docs.append((location + "!/" + name, value))
        with zipfile.ZipFile(io.BytesIO(content)) as delivery:
            self.assertFalse(any("operator" in name for name in delivery.namelist()))
            visit(delivery.read(manifest["deployment"]), manifest["deployment"])
        return seen, docs

    def test_branching_zip_round_trip_and_independent_passwords(self):
        asset = generate("nest", {"layers": 3, "branches": 2, "decoys": 4, "canary_url": URL, "canary_percent": 100,
                                  "directories": ["finance"], "format": "env"})
        self.assertEqual(len(asset.companions), 2)
        self.assertTrue(asset.companions[1].name.endswith(".inventory.json"))
        manifest = json.loads(asset.companions[0].content)
        seen, docs = self.walk(asset.content, manifest)
        self.assertEqual(len(seen), 7)
        self.assertEqual(len(docs), 28)
        self.assertEqual(manifest["summary"]["canaries"], 28)
        for entry in manifest["archives"]:
            self.assertEqual(len(entry["password"]), {1: 9, 2: 11, 3: 13}[entry["depth"]])
            self.assertEqual(bool(entry["hint"]), entry["depth"] <= 2)
        self.assertTrue(all("!/finance/" in path for path, _ in docs))
        self.assertTrue(all(item["canary"] for item in manifest["documents"]))

    def test_no_canary_and_no_clues_when_disabled(self):
        asset = generate("nest", {"layers": 2, "branches": 1, "decoys": 2, "format": "txt", "canary_url": URL,
                                  "canary_percent": 0, "password_policy": {"hints": "none"}})
        manifest = json.loads(asset.companions[0].content)
        _, docs = self.walk(asset.content, manifest)
        self.assertTrue(all(URL.encode() not in value for _, value in docs))
        self.assertTrue(all(entry["hint"] is None for entry in manifest["archives"]))
        with zipfile.ZipFile(io.BytesIO(asset.content)) as delivery:
            self.assertEqual(len(delivery.namelist()), 1)

    def test_nesting_limits_are_checked_before_rendering(self):
        for setting in ({"layers": 8, "branches": 3}, {"layers": 0}, {"decoys": 11}, {"format": "unsupported"},
                        {"formats": ["txt", "xlsx"]}, {"format_weights": {"txt": 1}},
                        {"directories": ["../"]}, {"canary_percent": 101}):
            with self.subTest(setting=setting), patch("physalia.nesting.render") as renderer:
                with self.assertRaises(ValueError):
                    generate("nest", setting)
                renderer.assert_not_called()

    def test_content_budget_is_enforced(self):
        with patch("physalia.nesting.MAX_CONTENT_BYTES", 10):
            with self.assertRaises(ValueError):
                generate("nest", {"layers": 1, "decoys": 1})

    def test_small_word_only_candidate_set_does_not_loop_forever(self):
        asset = generate("nest", {"layers": 4, "branches": 3, "decoys": 0, "password_policy": {
            "words": ["Project"], "min_length": 4, "max_length": 4,
            "lowercase": True, "uppercase": False, "digits": False, "symbols": False}})
        manifest = json.loads(asset.companions[0].content)
        self.assertEqual(len(manifest["archives"]), 40)

    def test_selected_format_is_used_for_all_decoys(self):
        asset = generate("nest", {"layers": 1, "decoys": 10, "format": "xlsx"})
        manifest = json.loads(asset.companions[0].content)
        self.assertEqual(manifest["document_format"], "xlsx")
        self.assertTrue(all(doc["format"] == "xlsx" for doc in manifest["documents"]))


class PasswordTests(unittest.TestCase):
    def test_custom_words_and_configurable_hint_mask(self):
        policy = validate_policy({"words": ["project"], "digits": False, "symbols": False,
                                  "min_length": 9, "max_length": 9, "hint_characters": 5})
        password, hint = make_password(policy, 1, 3)
        self.assertTrue(password.startswith("Project"))
        self.assertEqual(hint, password[:4] + "?????")

    def test_all_character_class_policies_and_lengths(self):
        keys = ("lowercase", "uppercase", "digits", "symbols")
        alphabets = (string.ascii_lowercase, string.ascii_uppercase, string.digits, "!@#_$%+-")
        for mode, flags in itertools.product(("random", "memorable"), itertools.product((False, True), repeat=4)):
            if not any(flags) or (mode == "memorable" and not any(flags[:2])):
                continue
            for length in (4, 9, 13, 64):
                with self.subTest(mode=mode, flags=flags, length=length):
                    policy = validate_policy(dict(mode=mode, min_length=length, max_length=length, **dict(zip(keys, flags))))
                    password, hint = make_password(policy, 1, 3)
                    self.assertEqual(len(password), length)
                    for enabled, alphabet in zip(flags, alphabets):
                        self.assertEqual(any(c in alphabet for c in password), enabled)
                    self.assertEqual(hint, password[:-2] + "??")

    def test_invalid_policies(self):
        for settings in ({"min_length": 14, "max_length": 9}, {"lowercase": False, "uppercase": False},
                         {"mode": "random", "lowercase": False, "uppercase": False, "digits": False, "symbols": False},
                         {"digits": "yes"}, {"min_length": True}, {"hints": "unknown"},
                         {"hint_characters": 1}, {"words": []}, {"words": ["bad/word"]}):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                validate_policy(settings)
