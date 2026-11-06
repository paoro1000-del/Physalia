"""Finite file-system decoys and an inert sparse-file creation bundle."""
from __future__ import annotations

import html
import io
import json
import posixpath
import secrets
import zipfile
from datetime import date

from physalia.archive_metadata import write_archive_member
from physalia.formats import STATIC_HTML_SECURITY_META
from physalia.nesting import Artifact
from physalia.validation import integer

MAX_PATH_MAZE_MEMBERS = 500_000


def _archive(files, language):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files:
            write_archive_member(archive, name, content, language=language)
    return output.getvalue()


def _operator(name, data):
    return Artifact(name, "application/json", json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"), role="operator")


def generate_path_maze(settings, language="ja"):
    ja = language == "ja"
    depth = integer(settings.get("depth", 20), "depth", 1, 20, language)
    branches = integer(settings.get("branches", 1000), "branches", 1, 1500, language)
    per_dir = integer(settings.get("files", 1), "files", 1, 4, language)
    # Preserve a deep spine and recursively expand each lateral branch into a
    # small subtree. This gives every wide branch nested folders without the
    # exponential growth of a complete B-ary tree.
    directory_count = 1 + depth * (1 + (branches - 1) * 7)
    member_count = directory_count * (per_dir + 1) + 1  # each folder has files and an HTML index, plus root landing page
    if member_count > MAX_PATH_MAZE_MEMBERS:
        raise ValueError("生成件数がZIP内の500,000項目上限を超えます。階層・横分岐数・各フォルダーのファイル数を減らしてください。"
                         if ja else
                         "Path Maze exceeds the 500,000 archive-member limit; reduce depth, branches or files per folder.")
    rng = secrets.SystemRandom()
    current_date = date.today()
    fiscal_year = current_date.year if current_date.month >= 4 else current_date.year - 1
    fiscal_quarter = ((current_date.month - 4) % 12) // 3 + 1
    reporting_period = f"FY{fiscal_year}-Q{fiscal_quarter}"
    folders = ("finance", "operations", "planning", "archive", "reports", "projects", "procurement", "regional", "records", "contracts", "delivery", "support")
    spine_folders = ("fin", "ops", "plan", "arch", "rpt", "proj", "proc", "reg", "rec", "ctr", "del", "sup")
    names = ("budget_review", "vendor_schedule", "project_handoff", "maintenance_plan", "quarterly_report", "records_index", "service_summary", "cost_allocation", "delivery_status", "approval_log", "asset_register", "renewal_schedule", "access_matrix", "work_plan", "account_summary", "change_history")
    paths = ["workspace_" + secrets.token_hex(3)]
    parent_by_path = {paths[0]: None}
    children_by_path = {paths[0]: []}
    current = paths[0]
    output = io.BytesIO()
    archive = zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED)

    def add_folder(parent, name):
        path = f"{parent}/{name}"
        paths.append(path)
        parent_by_path[path] = parent
        children_by_path[path] = []
        children_by_path[parent].append(path)
        return path

    for _ in range(depth):
        continuation_name = rng.choice(spine_folders)
        child_names = set()
        while len(child_names) < branches - 1:
            stem = rng.choice(folders)
            year = rng.randrange(current_date.year - 8, current_date.year + 5)
            quarter = rng.randrange(1, 5)
            region = rng.choice(("north", "south", "east", "west", "central", "domestic",
                                 "overseas", "na", "eu", "apac", "online", "retail"))
            batch = rng.randrange(1000)
            child_names.add(f"{stem}_{year}_q{quarter}_{region}_{batch:03d}")
        child_names = list(child_names)
        child_names.append(continuation_name)
        rng.shuffle(child_names)
        for child in child_names:
            branch_root = add_folder(current, child)
            if child == continuation_name:
                next_spine = branch_root
                continue
            # Keep each branch at seven folders, but vary how its six nested
            # folders are distributed so the whole tree is not a repeated grid.
            subfolder_count = rng.choice((2, 3))
            sub_paths = []
            for subfolder in rng.sample(folders, subfolder_count):
                sub_path = add_folder(branch_root, subfolder)
                sub_paths.append(sub_path)
            for leaf_index in range(6 - subfolder_count):
                leaf_parent = rng.choice(sub_paths)
                leaf_name = f"{rng.choice(folders)}_{leaf_index + 1:02d}"
                add_folder(leaf_parent, leaf_name)
        current = next_spine

    files_by_path = {}
    for directory in paths:
        files_by_path[directory] = []
        for stem in rng.sample(names, per_dir):
            reference = secrets.token_hex(4).upper()
            kind = rng.choice(("csv", "txt", "json"))
            if kind == "csv":
                content = (f"Reference,Reporting period,Owner team,Review state\n"
                           f"{reference},{reporting_period},Planning,Review pending\n"
                           f"{secrets.token_hex(4).upper()},{reporting_period},Operations,In progress\n").encode()
            elif kind == "json":
                content = json.dumps({"reference": reference, "period": reporting_period,
                                      "owner_team": "operations", "review_state": "draft",
                                      "updated": current_date.isoformat()}, indent=2).encode()
            else:
                content = (f"Operations record\nReference: {reference}\nReporting period: {reporting_period}\n"
                           "Owner team: Planning\nReview state: Pending\n").encode()
            name = f"{directory}/{stem}_{reference.lower()}.{kind}"
            files_by_path[directory].append((name, stem.replace("_", " ")))
            write_archive_member(archive, name, content, language=language)

    # Each folder gets a local index with child-folder navigation and cross-branch
    # references. The links form a bounded graph; they never leave the archive.
    shortcuts = []
    today = current_date.isoformat()
    for directory in paths:
        ancestors = []
        ancestor = directory
        while ancestor:
            ancestors.append(ancestor)
            ancestor = parent_by_path[ancestor]
        ancestors.reverse()
        breadcrumbs = " <span aria-hidden=\"true\">/</span> ".join(
            f'<a href="{html.escape(posixpath.relpath(f"{path}/index.html", directory), quote=True)}">'
            f'{html.escape(path.rsplit("/", 1)[-1])}</a>' for path in ancestors[:-1])
        folder_links = "".join(
            f'<li><a href="{html.escape(posixpath.relpath(f"{child}/index.html", directory), quote=True)}">'
            f'{html.escape(child.rsplit("/", 1)[-1])}</a><span>{"フォルダー" if ja else "Folder"}</span></li>'
            for child in children_by_path[directory])
        file_links = "".join(
            f'<li><a href="{html.escape(posixpath.basename(name), quote=True)}">{html.escape(label)}</a>'
            f'<span>{html.escape(name.rsplit(".", 1)[-1].upper())}</span></li>'
            for name, label in files_by_path[directory])
        excluded = {directory, *children_by_path[directory]}
        if parent_by_path[directory] is not None:
            excluded.add(parent_by_path[directory])
        shortcut_count = min(max(0, len(paths) - len(excluded)), rng.randint(1, 3))
        shortcut_targets = set()
        while len(shortcut_targets) < shortcut_count:
            candidate = rng.choice(paths)
            if candidate not in excluded:
                shortcut_targets.add(candidate)
        shortcut_links = "".join(
            f'<li><a href="{html.escape(posixpath.relpath(f"{target}/index.html", directory), quote=True)}">'
            f'{html.escape(target.rsplit("/", 1)[-1])}</a><span>{"関連フォルダー" if ja else "Related folder"}</span></li>'
            for target in shortcut_targets)
        shortcuts.extend({"from": f"{directory}/index.html", "to": f"{target}/index.html"}
                         for target in shortcut_targets)
        directory_label = html.escape(directory.rsplit("/", 1)[-1])
        page_title = "部門共有資料" if ja else "Department records"
        folder_heading = "フォルダー内の資料" if ja else "Folder contents"
        related_heading = "関連資料へのショートカット" if ja else "Related folders"
        files_heading = "ファイル一覧" if ja else "Files"
        date_label = "更新日" if ja else "Updated"
        folder_word = "フォルダー" if ja else "folders"
        file_word = "ファイル" if ja else "files"
        page = f'''<!doctype html><html lang="{'ja' if ja else 'en'}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">{STATIC_HTML_SECURITY_META}<meta name="description" content="{page_title}"><title>{directory_label} · {page_title}</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f5f7fa;color:#26364b;font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}main{{max-width:980px;margin:32px auto;padding:0 20px}}header{{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #dbe2ea;padding:0 0 16px}}header strong{{font-size:17px}}header small,nav,.meta,li span,footer{{color:#65758b;font-size:12px}}nav{{margin:18px 0}}nav a{{color:#52667e;text-decoration:none}}h1{{font-size:24px;margin:8px 0}}.summary{{display:flex;gap:18px;flex-wrap:wrap;color:#65758b;font-size:12px;margin:14px 0 22px}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}section{{background:#fff;border:1px solid #dbe2ea;border-radius:8px;padding:18px 20px}}h2{{font-size:15px;margin:0 0 12px}}ul{{list-style:none;margin:0;padding:0}}li{{display:flex;justify-content:space-between;gap:14px;padding:9px 0;border-top:1px solid #edf0f4}}li:first-child{{border-top:0}}li a{{color:#1769aa;text-decoration:none}}li a:hover{{text-decoration:underline}}footer{{margin:22px 0}}@media(max-width:680px){{main{{margin:20px auto;padding:0 14px}}.grid{{grid-template-columns:1fr}}header{{align-items:flex-start;gap:10px;flex-direction:column}}}}
</style></head><body><main><header><strong>{page_title}</strong><small>{directory_label}</small></header><nav aria-label="{'パンくずリスト' if ja else 'Breadcrumb'}">{breadcrumbs or page_title}</nav><h1>{folder_heading}</h1><div class="summary"><span>{len(children_by_path[directory])} {folder_word}</span><span>{len(files_by_path[directory])} {file_word}</span><span>{date_label}: <time datetime="{today}">{today}</time></span></div><div class="grid"><section><h2>{folder_heading}</h2><ul>{folder_links or '<li>—</li>'}</ul></section><section><h2>{related_heading}</h2><ul>{shortcut_links or '<li>—</li>'}</ul></section><section><h2>{files_heading}</h2><ul>{file_links or '<li>—</li>'}</ul></section></div><footer>{page_title} · {directory_label}</footer></main></body></html>'''.encode("utf-8")
        write_archive_member(archive, f"{directory}/index.html", page, language=language)

    root_path = paths[0]
    start_title = "共有資料の入口" if ja else "Workspace records"
    start_link = "フォルダー一覧を開く" if ja else "Open folder index"
    start_page = (f'''<!doctype html><html lang="{'ja' if ja else 'en'}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">{STATIC_HTML_SECURITY_META}<title>{start_title}</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f5f7fa;color:#26364b;font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}main{{max-width:760px;margin:48px auto;padding:26px;background:#fff;border:1px solid #dbe2ea;border-radius:8px}}h1{{font-size:22px}}p{{color:#65758b}}a{{color:#1769aa}}
</style></head><body><main><p>{'部門共有' if ja else 'Department workspace'}</p><h1>{start_title}</h1><p>{'共有資料のフォルダー構成を確認できます。' if ja else 'Browse the shared records and folder index.'}</p><a href="{html.escape(posixpath.join(root_path, 'index.html'), quote=True)}">{start_link}</a></main></body></html>''').encode("utf-8")
    write_archive_member(archive, "index.html", start_page, language=language)
    archive.close()
    documents = [name for directory_files in files_by_path.values() for name, _ in directory_files]
    index_files = ["index.html", *(f"{directory}/index.html" for directory in paths)]
    summary = {"kind": "path_maze", "directories": len(paths), "documents": len(documents),
               "index_pages": len(index_files), "shortcuts": len(shortcuts)}
    companion = _operator("path_maze.operator.json", {"directories": paths, "files": documents,
                                                       "index_pages": index_files, "entry_page": "index.html",
                                                       "shortcuts": shortcuts})
    return Artifact("path_maze_deployment.zip", "application/zip", output.getvalue(), [companion], summary)


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
