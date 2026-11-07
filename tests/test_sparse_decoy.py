import base64
import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest

import app
from physalia.ransomware_decoys import create_sparse_file


def allocated_bytes(path):
    if os.name != "nt":
        return path.stat().st_blocks * 512
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    get_size = kernel.GetCompressedFileSizeW
    get_size.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    get_size.restype = wintypes.DWORD
    high = wintypes.DWORD()
    ctypes.set_last_error(0)
    low = get_size(str(path), ctypes.byref(high))
    if low == 0xFFFFFFFF and ctypes.get_last_error():
        raise OSError(ctypes.get_last_error(), "Cannot read allocated size")
    return (high.value << 32) | low


class SparseDecoyTests(unittest.TestCase):
    def test_exclusive_creation_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory) / "sample.csv"
            existing.write_bytes(b"existing")
            with self.assertRaises(FileExistsError):
                create_sparse_file(directory, existing.name, 1024 ** 3, b"synthetic")
            self.assertEqual(existing.read_bytes(), b"existing")

    def test_failed_allocation_check_removes_new_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "dense.csv"
            with self.assertRaises(OSError):
                create_sparse_file(directory, target.name, 1024, b"x" * 1024)
            self.assertFalse(target.exists())

    def test_api_creates_sparse_file_and_matching_operator_list(self):
        server = app.LocalThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                body = json.dumps({"kind": "sparse_decoy", "settings": {"size_gib": 10, "extension": "csv"},
                                   "destination": directory})
                conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
                try:
                    with self.assertLogs("physalia", level="INFO") as logs:
                        conn.request("POST", "/api/generate", body, {
                            "Content-Type": "application/json", "Origin": f"http://127.0.0.1:{server.server_port}",
                            "X-ADG-Token": app.SESSION_TOKEN, "X-ADG-Language": "en"})
                        response = conn.getresponse()
                        data = json.loads(response.read())
                        self.assertEqual(response.status, 200, data)
                    self.assertTrue(any("sparse_created requested_gib=10 actual_gib=" in line and "extension=csv" in line for line in logs.output))
                    self.assertNotIn(directory, "\n".join(logs.output))
                finally:
                    conn.close()
                target = Path(data["savedPath"])
                self.assertEqual(target.parent, Path(directory).resolve())
                self.assertEqual(target.name, data["name"])
                self.assertTrue(target.name.endswith(".csv"))
                nominal_size = 10 * 1024 ** 3
                actual_size = target.stat().st_size
                self.assertLessEqual(abs(actual_size - nominal_size), nominal_size // 200)
                self.assertEqual(data["summary"]["size_bytes"], actual_size)
                self.assertEqual(data["summary"]["requested_size_gib"], 10)
                self.assertLess(allocated_bytes(target), target.stat().st_size // 32)
                with target.open("rb") as file:
                    self.assertTrue(file.read(64).startswith(b"Reference,Team,Status\n"))
                    file.seek(-1, os.SEEK_END)
                    self.assertEqual(file.read(1), b"\x00")
                self.assertNotIn("content", data)
                self.assertNotIn("downloadUrl", data)
                self.assertEqual(len(data["companions"]), 1)
                operator = json.loads(base64.b64decode(data["companions"][0]["content"]))
                self.assertEqual(operator["files"], [target.name])
                self.assertEqual(operator["logical_bytes_each"], target.stat().st_size)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
