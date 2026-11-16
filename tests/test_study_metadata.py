"""Regression checks for safe study metadata file reads."""

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import check_study_metadata_schema as validator


def snapshot(info, **changes):
    fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
    values = {field: getattr(info, field) for field in fields}
    values.update(changes)
    return SimpleNamespace(**values)


class StudyMetadataReadTests(unittest.TestCase):
    def test_windows_cross_source_ctime_difference_does_not_reject_same_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metadata.json"
            path.write_text('{"ok": true}', encoding="utf-8")
            real_fstat = os.fstat

            def different_ctime(fd):
                info = real_fstat(fd)
                return snapshot(info, st_ctime_ns=path.stat().st_ctime_ns + 123456789)

            with (
                patch.object(validator, "WINDOWS", True),
                patch.object(validator.os, "fstat", different_ctime),
            ):
                self.assertEqual(validator._load_json(path), {"ok": True})

    def test_change_during_read_is_rejected_on_windows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metadata.json"
            path.write_text('{"ok": true}', encoding="utf-8")
            real_fstat = os.fstat
            calls = 0

            def changing_ctime(fd):
                nonlocal calls
                calls += 1
                info = real_fstat(fd)
                return snapshot(info, st_ctime_ns=info.st_ctime_ns + calls)

            with (
                patch.object(validator, "WINDOWS", True),
                patch.object(validator.os, "fstat", changing_ctime),
            ):
                with self.assertRaisesRegex(OSError, "changed while reading"):
                    validator._load_json(path)

    def test_replaced_file_is_rejected_on_open(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metadata.json"
            path.write_text('{"ok": true}', encoding="utf-8")
            real_fstat = os.fstat

            def other_inode(fd):
                info = real_fstat(fd)
                return snapshot(info, st_ino=info.st_ino + 1)

            with (
                patch.object(validator, "WINDOWS", True),
                patch.object(validator.os, "fstat", other_inode),
            ):
                with self.assertRaisesRegex(OSError, "changed while opening"):
                    validator._load_json(path)


if __name__ == "__main__":
    unittest.main()
