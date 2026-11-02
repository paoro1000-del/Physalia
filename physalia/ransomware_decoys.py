"""Finite file-system decoys and an inert sparse-file creation bundle."""
from __future__ import annotations

import io
import json
import secrets
import zipfile

from physalia.archive_metadata import write_archive_member
from physalia.nesting import Artifact
from physalia.validation import integer


def _archive(files, language):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files:
            write_archive_member(archive, name, content, language=language)
    return output.getvalue()


def _operator(name, data):
    return Artifact(name, "application/json", json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"), role="operator")


def generate_path_maze(settings, language="ja"):
    depth = integer(settings.get("depth", 3), "depth", 1, 4, language)
    branches = integer(settings.get("branches", 3), "branches", 1, 3, language)
    per_dir = integer(settings.get("files", 2), "files", 1, 4, language)
    rng = secrets.SystemRandom()
    folders = ("finance", "operations", "planning", "archive", "reports", "projects", "procurement", "regional", "records")
    names = ("budget_review", "vendor_schedule", "project_handoff", "maintenance_plan", "quarterly_report", "records_index")
    paths = ["workspace_" + secrets.token_hex(3)]
    current = paths[:]
    for _ in range(depth):
        current = [parent + "/" + child for parent in current for child in rng.sample(folders, branches)]
        paths.extend(current)
    members = []
    for directory in paths:
        for stem in rng.sample(names, per_dir):
            reference = secrets.token_hex(4).upper()
            kind = rng.choice(("csv", "txt", "json"))
            if kind == "csv":
                content = f"Reference,Department,Status\n{reference},Planning,Review pending\n".encode()
            elif kind == "json":
                content = json.dumps({"reference": reference, "team": "operations", "status": "draft"}, indent=2).encode()
            else:
                content = f"Operations record\nReference: {reference}\nStatus: pending review\n".encode()
            members.append((f"{directory}/{stem}_{reference.lower()}.{kind}", content))
    rng.shuffle(members)
    summary = {"kind": "path_maze", "directories": len(paths), "documents": len(members)}
    companion = _operator("path_maze.operator.json", {"directories": paths, "files": [n for n, _ in members]})
    return Artifact("path_maze_deployment.zip", "application/zip", _archive(members, language), [companion], summary)


SPARSE_SCRIPT = r'''#!/usr/bin/env python3
"""Create synthetic sparse decoys in a user-selected existing directory."""
import argparse
import json
import os
from pathlib import Path
import sys

NAMES = __NAMES__
SIZE = __SIZE__

def mark_sparse(file):
    if os.name == "nt":
        import ctypes
        import msvcrt
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        call = kernel.DeviceIoControl
        call.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                         wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
        call.restype = wintypes.BOOL
        returned = wintypes.DWORD()
        if not call(wintypes.HANDLE(msvcrt.get_osfhandle(file.fileno())), 0x000900C4,
                    None, 0, None, 0, ctypes.byref(returned), None):
            raise OSError(ctypes.get_last_error(), "filesystem did not enable sparse files")

def check_posix(directory):
    if os.name == "nt":
        return
    import secrets
    probe = directory / (".sparse_probe_" + secrets.token_hex(12))
    created = False
    try:
        with probe.open("xb") as f:
            created = True
            f.truncate(16 * 1024 * 1024)
            info = os.fstat(f.fileno())
            if not hasattr(info, "st_blocks") or info.st_blocks * 512 >= info.st_size // 2:
                raise OSError("filesystem does not report sparse allocation")
    finally:
        if created:
            probe.unlink(missing_ok=True)

def main():
    parser = argparse.ArgumentParser(description="Create synthetic sparse decoys; see README before running.")
    parser.add_argument("directory", help="existing destination directory")
    args = parser.parse_args()
    directory = Path(args.directory).expanduser().resolve(strict=True)
    if not directory.is_dir():
        parser.error("destination must be an existing directory")
    check_posix(directory)
    for name in NAMES:
        path = directory / name
        created = False
        try:
            with path.open("xb") as file:
                created = True
                mark_sparse(file)
                file.write(b"Reference,Team,Status\nSYNTHETIC-104,Planning,Draft\n")
                file.truncate(SIZE)
            print(json.dumps({"created": str(path), "logical_bytes": SIZE}), flush=True)
        except OSError as exc:
            if created:
                try:
                    path.unlink()
                except OSError:
                    pass
            print("Could not create " + str(path) + ": " + str(exc), file=sys.stderr, flush=True)
            return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
'''


def generate_sparse_decoy(settings, language="ja"):
    size_gib = integer(settings.get("size_gib", 1), "size_gib", 1, 32, language)
    count = integer(settings.get("files", 1), "files", 1, 4, language)
    names = [f"{stem}_{secrets.token_hex(5)}.csv" for stem in
             ("financial_forecast", "vendor_ledger", "project_export", "operations_register")[:count]]
    size = size_gib * 1024 ** 3
    script = SPARSE_SCRIPT.replace("__NAMES__", repr(names)).replace("__SIZE__", str(size)).encode("utf-8")
    readme = ("架空スパースファイルの作成\nPython 3.11以降で python create_sparse_decoy.py <既存の配置先> を手動実行します。\n"
              "各ファイルは見かけ上のサイズが大きく、コピー・バックアップ・同期時に容量と時間を消費する場合があります。\n"
              "ファイルシステムがスパース形式に対応しない場合は作成を中止します。正規のバックアップ対象からの除外を検討してください。\n"
              "既存ファイルを上書きしません。実行後の一覧は標準出力と運用者専用JSONで確認できます。\n"
              if language == "ja" else
              "Create synthetic sparse files\nRun python create_sparse_decoy.py <existing-directory> manually with Python 3.11 or later.\n"
              "Copies, backups and sync may consume the full logical size and take considerable time.\n"
              "Creation stops if sparse files are not supported. Consider excluding decoys from normal backups.\n"
              "Existing files are not overwritten. Review stdout and the separate operator JSON for the filenames.\n")
    files = [("create_sparse_decoy.py", script), ("README.txt", readme.encode("utf-8"))]
    companion = _operator("sparse_decoy.operator.json", {"files": names, "logical_bytes_each": size})
    summary = {"kind": "sparse_decoy", "files": count, "size_gib": size_gib}
    return Artifact("sparse_decoy_deployment.zip", "application/zip", _archive(files, language), [companion], summary)
