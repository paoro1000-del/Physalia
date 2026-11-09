"""Finite file-system decoys and an inert sparse-file creation bundle."""
from __future__ import annotations

import html
import io
import json
import logging
import os
import posixpath
import secrets
import zipfile
import time
from datetime import date

from physalia.archive_metadata import write_archive_member
from physalia.formats import STATIC_HTML_SECURITY_META
from physalia.nesting import Artifact
from physalia.validation import integer

MAX_PATH_MAZE_MEMBERS = 500_000
MAX_SPARSE_SIZE_GIB = 1024
SPARSE_SIZE_VARIATION_PER_MILLE = 5  # +/-0.5% around the selected nominal size
LOGGER = logging.getLogger("physalia")


def _tar_number(value, width):
    """Encode a nonnegative ustar octal field."""
    encoded = f"{value:0{width - 1}o}".encode("ascii") + b"\0"
    if len(encoded) > width:
        raise ValueError("TAR numeric field is too large")
    return encoded.rjust(width, b"0")


def _tar_header(name, size, typeflag):
    encoded_name = name.encode("utf-8")
    if len(encoded_name) > 100:
        raise ValueError("TAR member name is too long")
    block = bytearray(512)
    block[0:len(encoded_name)] = encoded_name
    block[100:108] = _tar_number(0o644, 8)
    block[108:116] = _tar_number(0, 8)
    block[116:124] = _tar_number(0, 8)
    block[124:136] = _tar_number(size, 12)
    block[136:148] = _tar_number(int(time.time()), 12)
    block[148:156] = b"        "
    block[156:157] = typeflag
    block[257:263] = b"ustar\0"
    block[263:265] = b"00"
    checksum = sum(block)
    block[148:156] = f"{checksum:06o}\0 ".encode("ascii")
    return bytes(block)


def _pax_record(key, value):
    body = f" {key}={value}\n".encode("utf-8")
    length = len(body) + 1
    while True:
        encoded = str(length).encode("ascii") + body
        if len(encoded) == length:
            return encoded
        length = len(encoded)


def create_sparse_tar(filename, logical_size, prefix):
    """Write an uncompressed PAX 1.0 sparse TAR containing one sparse member."""
    if (not isinstance(filename, str) or not filename or "/" in filename or "\\" in filename
            or filename in (".", "..") or logical_size < len(prefix)):
        raise ValueError("Invalid sparse TAR member")
    sparse_map = f"1\n0\n{len(prefix)}\n".encode("ascii")
    map_area = sparse_map + b"\0" * (-len(sparse_map) % 512)
    payload = map_area + prefix + b"\0" * (-len(prefix) % 512)
    pax = b"".join((
        _pax_record("GNU.sparse.major", "1"),
        _pax_record("GNU.sparse.minor", "0"),
        _pax_record("GNU.sparse.name", filename),
        _pax_record("GNU.sparse.realsize", str(logical_size)),
    ))
    header_name = "PaxHeaders.0/sparse"
    member_name = "GNUSparseFile.0/" + filename
    return b"".join((
        _tar_header(header_name, len(pax), b"x"), pax,
        b"\0" * (-len(pax) % 512),
        _tar_header(member_name, len(payload), b"0"), payload,
        b"\0" * 1024,
    ))


def _probe_posix_sparse_support(directory):
    """Check hole allocation on the destination filesystem before creating the requested file.

    A failed probe can allocate at most 8 MiB on a filesystem that stores holes
    densely, avoiding a potentially enormous write before the allocation check.
    """
    import tempfile

    probe_size = 8 * 1024 * 1024
    LOGGER.debug("sparse_filesystem_probe_started probe_bytes=%d", probe_size)
    try:
        with tempfile.TemporaryFile(mode="w+b", dir=directory) as probe:
            probe.seek(probe_size - 1)
            probe.write(b"\0")
            probe.flush()
            info = os.fstat(probe.fileno())
            if not hasattr(info, "st_blocks"):
                raise OSError("Filesystem does not report sparse allocation")
            allocated = info.st_blocks * 512
            if allocated >= probe_size // 2:
                raise OSError("Filesystem does not create sparse files")
    except Exception as exc:
        LOGGER.warning("sparse_filesystem_probe_failed error_type=%s", type(exc).__name__)
        raise
    LOGGER.debug("sparse_filesystem_probe_complete probe_bytes=%d allocated_bytes=%d",
                 probe_size, allocated)


def create_sparse_file(directory, filename, logical_size, prefix):
    """Create a sparse file exclusively and reject filesystems that allocate it densely."""
    from pathlib import Path

    started = time.monotonic()
    LOGGER.debug("sparse_file_create_started logical_bytes=%d prefix_bytes=%d",
                 logical_size, len(prefix))
    folder = Path(directory)
    if not folder.is_absolute():
        raise ValueError("Destination must be an absolute directory path")
    folder = folder.resolve(strict=True)
    if not folder.is_dir() or Path(filename).name != filename:
        raise ValueError("Invalid destination directory or filename")
    if os.name != "nt":
        # POSIX-like filesystems represent holes implicitly. Verify the target
        # volume first so an unsupported filesystem cannot densely allocate
        # the requested (potentially 1 TiB) logical size.
        _probe_posix_sparse_support(folder)
    target = folder / filename
    created = False
    try:
        with target.open("xb") as file:
            created = True
            if os.name == "nt":
                import ctypes
                import msvcrt
                from ctypes import wintypes

                kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                handle = wintypes.HANDLE(msvcrt.get_osfhandle(file.fileno()))
                device_io = kernel.DeviceIoControl
                device_io.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                                      wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                                      wintypes.LPVOID]
                device_io.restype = wintypes.BOOL
                returned = wintypes.DWORD()
                if not device_io(handle, 0x000900C4, None, 0, None, 0, ctypes.byref(returned), None):
                    raise OSError(ctypes.get_last_error(), "Filesystem does not support sparse files")
                LOGGER.debug("sparse_filesystem_verified platform=windows")
            file.write(prefix)
            # Writing the final byte leaves the intervening range sparse on
            # NTFS; Windows' CRT truncate can physically zero the whole gap.
            file.seek(logical_size - 1)
            file.write(b"\0")
            file.flush()
            if os.name == "nt":
                class FileStandardInfo(ctypes.Structure):
                    _fields_ = [("allocation_size", ctypes.c_longlong), ("end_of_file", ctypes.c_longlong),
                                ("number_of_links", wintypes.DWORD), ("delete_pending", wintypes.BOOLEAN),
                                ("directory", wintypes.BOOLEAN)]

                info = FileStandardInfo()
                get_info = kernel.GetFileInformationByHandleEx
                get_info.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
                get_info.restype = wintypes.BOOL
                if not get_info(handle, 1, ctypes.byref(info), ctypes.sizeof(info)):
                    raise OSError(ctypes.get_last_error(), "Could not check sparse allocation")
                allocated = info.allocation_size
            else:
                info = os.fstat(file.fileno())
                if not hasattr(info, "st_blocks"):
                    raise OSError("Filesystem does not report sparse allocation")
                allocated = info.st_blocks * 512
            if allocated >= logical_size // 2:
                raise OSError("Filesystem did not create a sparse file")
            LOGGER.debug("sparse_file_allocation_verified logical_bytes=%d allocated_bytes=%d",
                         logical_size, allocated)
        LOGGER.info("sparse_file_create_complete logical_bytes=%d elapsed_ms=%d",
                    logical_size, max(0, round((time.monotonic() - started) * 1000)))
        return str(target)
    except Exception as exc:
        LOGGER.warning("sparse_file_create_failed error_type=%s", type(exc).__name__)
        LOGGER.debug("sparse_file_create_traceback", exc_info=True)
        if created:
            try:
                target.unlink()
                LOGGER.debug("sparse_partial_file_removed")
            except OSError:
                LOGGER.error("sparse_partial_file_removal_failed", exc_info=True)
                pass
        raise


def _archive(files, language):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files:
            write_archive_member(archive, name, content, language=language)
    return output.getvalue()


def _operator(name, data):
    return Artifact(name, "application/json", json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"), role="operator")


def generate_path_maze(settings, language="ja"):
    started = time.monotonic()
    LOGGER.debug("path_maze_generation_started setting_keys=%s",
                 ",".join(sorted(key for key in settings if isinstance(key, str))))
    ja = language == "ja"
    os_type = settings.get("os_type", "windows")
    profiles = {
        "windows": {
            "folders": ("AppData", "Documents", "Downloads", "ProgramData", "Program Files", "Public",
                        "Services", "Logs", "Backups", "Shared", "Packages", "Profiles"),
            "spine": ("Users", "Data", "Prog", "Share", "Config", "Logs", "Svc", "Ops", "Docs", "Cache", "Pkg", "Common"),
            "files": ("BudgetReview", "VendorSchedule", "ProjectHandoff", "MaintenancePlan", "QuarterlyReport",
                      "RecordsIndex", "ServiceSummary", "CostAllocation", "DeliveryStatus", "ApprovalLog",
                      "AssetRegister", "RenewalSchedule", "AccessMatrix", "WorkPlan", "AccountSummary", "ChangeHistory"),
            "branch_style": "windows",
            "path_limit": 220,
        },
        "unix": {
            "folders": ("etc", "usr", "var", "opt", "srv", "home", "lib", "share", "local", "spool", "cache", "data"),
            "spine": ("var", "usr", "opt", "srv", "home", "etc", "share", "local", "lib", "spool", "cache", "data"),
            "files": ("budget_review", "vendor_schedule", "project_handoff", "maintenance_plan", "quarterly_report",
                      "records_index", "service_summary", "cost_allocation", "delivery_status", "approval_log",
                      "asset_register", "renewal_schedule", "access_matrix", "work_plan", "account_summary", "change_history"),
            "branch_style": "unix",
            "path_limit": 3000,
        },
        "macos": {
            "folders": ("Library", "Application Support", "Group Containers", "Containers", "Preferences", "Caches",
                        "Shared", "Documents", "Frameworks", "Resources", "LaunchAgents", "Logs"),
            "spine": ("Users", "Library", "Application Support", "Group Containers", "Containers", "Shared",
                      "Documents", "Preferences", "Caches", "Logs", "Resources", "Frameworks"),
            "files": ("Budget Review", "Vendor Schedule", "Project Handoff", "Maintenance Plan", "Quarterly Report",
                      "Records Index", "Service Summary", "Cost Allocation", "Delivery Status", "Approval Log",
                      "Asset Register", "Renewal Schedule", "Access Matrix", "Work Plan", "Account Summary", "Change History"),
            "branch_style": "macos",
            "path_limit": 900,
        },
    }
    if not isinstance(os_type, str) or os_type not in profiles:
        raise ValueError("対象OSはwindows、unix、macosから選択してください。"
                         if ja else "Choose a supported path profile: windows, unix or macos.")
    depth = integer(settings.get("depth", 20), "depth", 1, 20, language)
    branches = integer(settings.get("branches", 890), "branches", 1, 1500, language)
    per_dir = integer(settings.get("files", 3), "files", 1, 4, language)
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
    profile = profiles[os_type]
    folders = profile["folders"]
    spine_folders = profile["spine"]
    names = profile["files"]
    root_name = {"windows": "Workspace_", "unix": "workspace_", "macos": "Workspace "}[os_type]
    paths = [root_name + secrets.token_hex(3)]
    parent_by_path = {paths[0]: None}
    children_by_path = {paths[0]: []}
    current = paths[0]
    output = io.BytesIO()
    archive = zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED)

    def write_member(name, content):
        components = name.split("/")
        if any(not part or len(part.encode("utf-8")) > 240 for part in components):
            raise ValueError("パス構成要素が共通ファイル名の安全な長さを超えます。"
                             if ja else "A path component exceeds the portable filename budget.")
        if os_type == "windows":
            forbidden = set('<>:"\\|?*')
            reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                        *(f"LPT{i}" for i in range(1, 10))}
            if any(any(char in forbidden for char in part) or part.endswith((" ", "."))
                   or part.split(".", 1)[0].upper() in reserved for part in components):
                raise ValueError("Windowsで使えないファイル名が含まれています。"
                                 if ja else "The generated path contains a name disallowed by Windows.")
        if len(name.encode("utf-8")) > profile["path_limit"]:
            raise ValueError("選択したOSプロファイルの相対パス長の上限を超えます。"
                             if ja else "A path exceeds the selected OS profile's relative path budget.")
        write_archive_member(archive, name, content, language=language)

    def add_folder(parent, name):
        path = f"{parent}/{name}"
        if (not name or len(name.encode("utf-8")) > 240
                or len(path.encode("utf-8")) > profile["path_limit"]):
            raise ValueError("フォルダー名またはパスが選択したOSプロファイルの上限を超えます。"
                             if ja else "A folder exceeds the selected OS profile's path limits.")
        paths.append(path)
        parent_by_path[path] = parent
        children_by_path[path] = []
        children_by_path[parent].append(path)
        return path

    for _ in range(depth):
        continuation_name = rng.choice(spine_folders)
        child_names = {}
        while len(child_names) < branches - 1:
            stem = rng.choice(folders)
            year = rng.randrange(current_date.year - 8, current_date.year + 5)
            quarter = rng.randrange(1, 5)
            region = rng.choice(("north", "south", "east", "west", "central", "domestic",
                                 "overseas", "na", "eu", "apac", "online", "retail"))
            batch = rng.randrange(1000)
            style = profile["branch_style"]
            if style == "windows":
                candidate = f"{stem[:5]}_{year % 100:02d}q{quarter}_{region[:2]}_{batch:03d}"
            elif style == "macos":
                candidate = f"{stem.replace(' ', '')[:10]} {year} Q{quarter} {region.title()} {batch:03d}"
            else:
                candidate = f"{stem}_{year}_q{quarter}_{region}_{batch:03d}"
            key = candidate if os_type == "unix" else candidate.casefold()
            child_names.setdefault(key, candidate)
        child_names = list(child_names.values())
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
            write_member(name, content)

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
        write_member(f"{directory}/index.html", page)

    root_path = paths[0]
    start_title = "共有資料の入口" if ja else "Workspace records"
    start_link = "フォルダー一覧を開く" if ja else "Open folder index"
    start_page = (f'''<!doctype html><html lang="{'ja' if ja else 'en'}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">{STATIC_HTML_SECURITY_META}<title>{start_title}</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f5f7fa;color:#26364b;font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}main{{max-width:760px;margin:48px auto;padding:26px;background:#fff;border:1px solid #dbe2ea;border-radius:8px}}h1{{font-size:22px}}p{{color:#65758b}}a{{color:#1769aa}}
</style></head><body><main><p>{'部門共有' if ja else 'Department workspace'}</p><h1>{start_title}</h1><p>{'共有資料のフォルダー構成を確認できます。' if ja else 'Browse the shared records and folder index.'}</p><a href="{html.escape(posixpath.join(root_path, 'index.html'), quote=True)}">{start_link}</a></main></body></html>''').encode("utf-8")
    write_member("index.html", start_page)
    archive.close()
    documents = [name for directory_files in files_by_path.values() for name, _ in directory_files]
    index_files = ["index.html", *(f"{directory}/index.html" for directory in paths)]
    summary = {"kind": "path_maze", "os_type": os_type, "directories": len(paths), "documents": len(documents),
               "index_pages": len(index_files), "shortcuts": len(shortcuts)}
    companion = _operator("path_maze.operator.json", {"directories": paths, "files": documents,
                                                       "index_pages": index_files, "entry_page": "index.html",
                                                       "shortcuts": shortcuts})
    package = output.getvalue()
    LOGGER.info("path_maze_generation_complete directories=%d documents=%d indexes=%d shortcuts=%d archive_bytes=%d elapsed_ms=%d",
                len(paths), len(documents), len(index_files), len(shortcuts), len(package),
                max(0, round((time.monotonic() - started) * 1000)))
    return Artifact("path_maze_deployment.zip", "application/zip", package, [companion], summary)
    package = output.getvalue()
    LOGGER.info("path_maze_generation_complete directories=%d documents=%d indexes=%d shortcuts=%d archive_bytes=%d elapsed_ms=%d",
                len(paths), len(documents), len(index_files), len(shortcuts), len(package),
                max(0, round((time.monotonic() - started) * 1000)))
    return Artifact("path_maze_deployment.zip", "application/zip", package, [companion], summary)


def generate_sparse_decoy(settings, language="ja"):
    LOGGER.debug("sparse_decoy_metadata_started setting_keys=%s",
                 ",".join(sorted(key for key in settings if isinstance(key, str))))
    size_gib = integer(settings.get("size_gib", 1), "size_gib", 1, MAX_SPARSE_SIZE_GIB, language)
    extension = settings.get("extension", "csv")
    if not isinstance(extension, str) or extension not in (
            "csv", "pdf", "xlsx", "docx", "zip", "bak", "db", "log", "txt", "xml"):
        raise ValueError("Invalid sparse decoy extension")
    stem = secrets.choice(("financial_forecast", "vendor_ledger", "project_export", "operations_register"))
    filename = f"{stem}_{secrets.token_hex(5)}.{extension}"
    gib = 1024 ** 3
    nominal_size = size_gib * gib
    maximum_variation = nominal_size * SPARSE_SIZE_VARIATION_PER_MILLE // 1000
    minimum_variation = -maximum_variation
    maximum_variation = min(maximum_variation, MAX_SPARSE_SIZE_GIB * gib - nominal_size)
    variation = secrets.randbelow(maximum_variation - minimum_variation + 1) + minimum_variation
    size = nominal_size + variation
    actual_size_gib = round(size / gib, 3)
    companion = _operator("sparse_decoy.operator.json", {
        "files": [filename], "logical_bytes_each": size,
        "requested_size_gib": size_gib,
        "display_extension_only": extension})
    summary = {"kind": "sparse_decoy", "files": 1, "size_gib": actual_size_gib,
               "size_bytes": size, "requested_size_gib": size_gib,
               "extension": extension, "filename": filename}
    LOGGER.info("sparse_size_randomized requested_gib=%d actual_gib=%.3f logical_bytes=%d",
                size_gib, actual_size_gib, size)
    # This prefix is written to the sparse file at the chosen destination.
    content = b"Reference,Team,Status\nSYNTHETIC-104,Planning,Draft\n"
    return Artifact(filename, "application/octet-stream", content, [companion], summary)
