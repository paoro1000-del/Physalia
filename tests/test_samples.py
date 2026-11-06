import base64
import gzip
import hashlib
import http.client
import io
import json
import posixpath
import re
import sqlite3
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import unquote_to_bytes
import zipfile

from physalia.generators import generate
from physalia.mazes import CODECS
from physalia.stream_runtime import StreamServer


class MazeTests(unittest.TestCase):
    def test_directory_maze_links_resolve_with_no_filesystem_cycles(self):
        asset = generate("directory_maze", {"depth": 2, "branches": 3, "format": "json", "cross_links": True})
        inventory = json.loads(asset.companions[0].content)
        self.assertEqual(asset.summary["directories"], 13)
        with zipfile.ZipFile(io.BytesIO(asset.content)) as archive:
            names = set(archive.namelist())
            self.assertEqual(len(names), 26)
            for node in inventory["nodes"]:
                path = posixpath.join("" if node["directory"] == "." else node["directory"], "index.html")
                markup = archive.read(path).decode()
                for href in re.findall(r'href="([^"]+)"', markup):
                    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), href))
                    self.assertIn(resolved, names)
            self.assertFalse(any("operator" in name for name in names))
            self.assertTrue(all((info.external_attr >> 16) & 0o170000 != 0o120000 for info in archive.infolist()))
        self.assertTrue(any("index.html" in node["links"] for node in inventory["nodes"] if node["directory"] != "."))

    def test_directory_maze_without_cross_links_is_a_tree(self):
        asset = generate("directory_maze", {"depth": 2, "branches": 2, "cross_links": False})
        nodes = json.loads(asset.companions[0].content)["nodes"]
        self.assertEqual(sum(len(node["links"]) for node in nodes), len(nodes) - 1)

    def test_each_encoding_recovers_a_valid_database_and_matches_digest(self):
        for codec in CODECS:
            with self.subTest(codec=codec):
                asset = generate("encoding_maze", {"layers": 3, "candidates": 2, "format": "sqlite", "codecs": [codec]})
                inventory = json.loads(asset.companions[0].content)
                with zipfile.ZipFile(io.BytesIO(asset.content)) as archive:
                    for entry in inventory["candidates"]:
                        data = archive.read(entry["path"])
                        for expected in entry["decode_order"]:
                            envelope = json.loads(data)
                            self.assertEqual(envelope["encoding"], expected)
                            value = envelope["payload"]
                            if expected == "hex": data = bytes.fromhex(value)
                            elif expected == "percent": data = unquote_to_bytes(value)
                            elif expected == "base64url": data = base64.urlsafe_b64decode(value)
                            elif expected == "gzip_base64": data = gzip.decompress(base64.b64decode(value))
                            else: data = base64.b64decode(value, validate=True)
                        self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"])
                        connection = sqlite3.connect(":memory:")
                        try:
                            connection.deserialize(data)
                            self.assertEqual(connection.execute("SELECT count(*) FROM customers").fetchone()[0], 15)
                        finally:
                            connection.close()

    def test_encoding_candidates_use_independent_records_and_no_revision_metadata(self):
        asset = generate("encoding_maze", {"layers": 2, "candidates": 3, "format": "json", "codecs": ["base64"]})
        inventory = json.loads(asset.companions[0].content)
        documents = []
        with zipfile.ZipFile(io.BytesIO(asset.content)) as archive:
            for entry in inventory["candidates"]:
                self.assertNotIn("revision", entry)
                data = archive.read(entry["path"])
                for expected in entry["decode_order"]:
                    envelope = json.loads(data)
                    self.assertEqual(envelope["encoding"], expected)
                    data = base64.b64decode(envelope["payload"], validate=True)
                documents.append(json.loads(data))
        self.assertTrue(all(item["records"] != documents[0]["records"] for item in documents[1:]))
        self.assertEqual(len({item["reference"] for item in documents}), 3)

    def test_invalid_maze_parameters_fail(self):
        for kind, settings in (("directory_maze", {"depth": 6, "branches": 5}), ("directory_maze", {"cross_links": "yes"}),
                               ("directory_maze", {"formats": ["json"]}), ("directory_maze", {"format": "unsupported"}),
                               ("encoding_maze", {"codecs": ["script"]}),
                               ("encoding_maze", {"candidates": 21}), ("encoding_maze", {"filename": "../path"})):
            with self.subTest(kind=kind, settings=settings), self.assertRaises(ValueError):
                generate(kind, settings)

    def test_encoding_size_is_bounded(self):
        from unittest.mock import patch
        with patch("physalia.mazes.MAX_MAZE_BYTES", 100):
            with self.assertRaises(ValueError):
                generate("encoding_maze", {})

    def test_stream_bundle_is_standalone_and_contains_no_secret(self):
        asset = generate("stream", {"path": "/private/archive.csv", "format": "csv"}, "en")
        operator = json.loads(asset.companions[0].content)
        with zipfile.ZipFile(io.BytesIO(asset.content)) as archive:
            self.assertEqual(set(archive.namelist()), {"serve.py", "stream_config.json", "index.html", "stream-preview.js", "README.txt", "LICENSE"})
            for content in (archive.read(name) for name in archive.namelist()):
                for token in operator["environment"].values():
                    self.assertNotIn(token.encode(), content)
            with tempfile.TemporaryDirectory() as temp:
                script = Path(temp) / "serve.py"
                script.write_bytes(archive.read("serve.py"))
                result = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
                self.assertIn(b"--operator", result.stdout)
        self.assertNotEqual(*operator["environment"].values())
        for path in ("/stop", "/health", "//bad", "/a/../b", "https://elsewhere.invalid/"):
            with self.assertRaises(ValueError):
                generate("stream", {"path": path})


class StreamTests(unittest.TestCase):
    def setUp(self):
        self.token, self.admin = "access-" + "a" * 40, "admin-" + "b" * 40
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        self.server = StreamServer({"port": self.port, "max_streams": 1, "rate_kib": 64}, self.token, self.admin)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.connections = []

    def tearDown(self):
        self.server.stop_event.set()
        for connection in self.connections:
            connection.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, path, token=None, method="GET", host=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        self.connections.append(connection)
        headers = {"Authorization": "Bearer " + token} if token else {}
        if host:
            headers["Host"] = host
        connection.request(method, path, headers=headers)
        return connection, connection.getresponse()

    def test_response_continues_until_operator_stop_without_total_length(self):
        _, response = self.request("/exports/archive.sql", self.token)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Transfer-Encoding"), "chunked")
        self.assertIsNone(response.getheader("Content-Length"))
        self.assertIn(b"CREATE TABLE", response.read(150))
        self.assertIn(b"INSERT INTO", response.read(5000))
        self.assertFalse(response.isclosed())
        _, denied = self.request("/stop", self.token, "POST")
        self.assertEqual(denied.status, 401)
        denied.read()
        self.assertFalse(self.server.stop_event.is_set())
        _, stopped = self.request("/stop", self.admin, "POST")
        self.assertEqual(stopped.status, 200)
        self.assertTrue(json.loads(stopped.read())["stopped"])
        with self.assertRaises(http.client.IncompleteRead):
            response.read()
        _, next_response = self.request("/exports/archive.sql", self.token)
        self.assertEqual(next_response.status, 503)
        next_response.read()

    def test_authentication_concurrency_and_admin_health(self):
        for token in (None, "incorrect", self.admin):
            _, response = self.request("/exports/archive.sql", token)
            self.assertEqual(response.status, 401)
            response.read()
        _, first = self.request("/exports/archive.sql", self.token)
        first.read(50)
        _, second = self.request("/exports/archive.sql", self.token)
        self.assertEqual(second.status, 503)
        second.read()
        _, health = self.request("/health", self.admin)
        self.assertEqual(json.loads(health.read())["active"], 1)
        _, wrong_host = self.request("/health", self.admin, host="other.invalid")
        self.assertEqual(wrong_host.status, 403)
        wrong_host.read()

    def test_stopping_interrupts_bandwidth_wait(self):
        self.server.next_send = __import__("time").monotonic() + 3600
        self.server.stop_event.set()
        self.assertFalse(self.server.pace(1024))


if __name__ == "__main__":
    unittest.main()
