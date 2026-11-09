"""Deployable samples: static directory graphs, encoded candidates, stream server."""
import base64
import gzip
import hashlib
import html
import io
import json
import logging
from pathlib import Path
import posixpath
import re
import secrets
import time
from urllib.parse import quote_from_bytes
import zipfile

from physalia.archive_metadata import write_archive_member
from physalia.database import records
from physalia.formats import FORMATS, STATIC_HTML_SECURITY_META, render, render_switchable_env, resolve_context
from physalia.i18n import translate
from physalia.nesting import Artifact
from physalia.naming import FORMAT_NAMES, plausible_filename
from physalia.stream_runtime import validate_config
from physalia.scenarios import place_canary, scenario_for
from physalia.validation import CanaryURLCycle, canary_url_list, filename, integer, text

LOGGER = logging.getLogger("physalia")

CODECS = ("base64", "base64url", "hex", "percent", "gzip_base64")
MAX_MAZE_BYTES = 16 * 1024 * 1024
MAX_DIRECTORIES = 400
WINDOWS_RESERVED_NAMES = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(10)),
                          *(f"lpt{i}" for i in range(10))}
DIRECTORY_NAMES = (
    "accounts", "archive", "backups", "billing", "compliance", "config", "contracts",
    "customers", "departments", "exports", "finance", "imports", "inventory", "legal",
    "migrations", "operations", "projects", "reports", "retention", "shared", "support",
    "users", "vendors", "workflows",
)
DIRECTORY_LABELS = {
    "accounts": ("Accounts", "アカウント"), "archive": ("Archive", "アーカイブ"),
    "backups": ("Backups", "バックアップ"), "billing": ("Billing", "請求"),
    "compliance": ("Compliance", "コンプライアンス"), "config": ("Configuration", "設定"),
    "contracts": ("Contracts", "契約"), "customers": ("Customers", "顧客"),
    "departments": ("Departments", "部門"), "exports": ("Exports", "エクスポート"),
    "finance": ("Finance", "財務"), "imports": ("Imports", "インポート"),
    "inventory": ("Inventory", "在庫"), "legal": ("Legal", "法務"),
    "migrations": ("Migrations", "移行"), "operations": ("Operations", "運用"),
    "projects": ("Projects", "プロジェクト"), "reports": ("Reports", "レポート"),
    "retention": ("Retention", "保管"), "shared": ("Shared files", "共有ファイル"),
    "support": ("Support", "サポート"), "users": ("Users", "ユーザー"),
    "vendors": ("Vendors", "取引先"), "workflows": ("Workflows", "ワークフロー"),
}
ENV_CANDIDATE_PATHS = (
    ".env", ".env.production", ".env.production.local", ".env.staging", ".env.test", ".env.development",
    ".env.previous", "config/.env", "config/.env.production", "config/.env.production.local",
    "config/.env.staging", "config/.env.test", "backend/.env", "backend/.env.production", "backend/.env.production.local",
    "services/api/.env", "services/api/.env.production", "services/worker/.env",
    "services/worker/.env.production", "deploy/.env.production", "runtime/.env", "runtime/.env.production",
)


def selection(value, choices, language):
    if (not isinstance(value, list) or not value or len(value) > len(choices)
            or any(not isinstance(v, str) or v not in choices for v in value) or len(set(value)) != len(value)):
        raise ValueError(translate("codecs_error", language))
    return value


def validate_bundle_files(files, language="ja"):
    """Reject unsafe or ambiguous ZIP members before writing any archive."""
    seen_files, seen_directories = set(), set()
    for path, content in files:
        if not isinstance(path, str) or not isinstance(content, bytes):
            raise ValueError(translate("invalid_input", language))
        parts = path.split("/")
        if (not path or len(path) > 1024 or path.startswith("/") or "\\" in path
                or any(part in ("", ".", "..") or not re.fullmatch(r"[A-Za-z0-9_.-]{1,255}", part)
                       or part.endswith(".") or ":" in part
                       or part.split(".", 1)[0].casefold() in WINDOWS_RESERVED_NAMES
                       for part in parts)):
            raise ValueError(translate("invalid_input", language))
        normalized = path.casefold()
        prefixes = ["/".join(parts[:index]).casefold() for index in range(1, len(parts))]
        if (normalized in seen_files or normalized in seen_directories
                or any(prefix in seen_files for prefix in prefixes)):
            raise ValueError(translate("invalid_input", language))
        seen_files.add(normalized)
        seen_directories.update(prefixes)


def bundle(name, files, inventory, summary, language="ja", size_error_key="maze_size_limit"):
    validate_bundle_files(files, language)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, data in files:
            write_archive_member(archive, path, data, language=language)
    deployment = output.getvalue()
    if len(deployment) > MAX_MAZE_BYTES:
        raise ValueError(translate(size_error_key, language))
    operator = Artifact(name + ".operator.json", "application/json",
                        json.dumps(inventory, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8"))
    return Artifact(name + "_deployment.zip", "application/zip", deployment, [operator], summary)


def generate_directory_maze(settings, language="ja"):
    started = time.monotonic()
    LOGGER.info("directory_maze_started language=%s", language)
    depth = integer(settings.get("depth", 3), "maze_depth", 1, 6, language)
    branches = integer(settings.get("branches", 3), "branches", 1, 5, language)
    per_directory = integer(settings.get("files_per_directory", 1), "files_per_directory", 1, 3, language)
    total = sum(branches ** n for n in range(depth + 1))
    if total > MAX_DIRECTORIES:
        raise ValueError(translate("directory_limit", language, count=total, maximum=MAX_DIRECTORIES))
    cycles = settings.get("cross_links", True)
    if not isinstance(cycles, bool):
        raise ValueError(translate("invalid_input", language))
    fmt = settings.get("format", "json")
    if not isinstance(fmt, str) or fmt not in FORMATS:
        raise ValueError(translate("invalid_format", language))
    url_cycle = CanaryURLCycle(canary_url_list(settings, language))
    scenario_name, scenario = scenario_for(settings, language)
    context = resolve_context({"canary_context": scenario["context"]}, language)
    name = plausible_filename("directory_maze")
    title = text(settings.get("title", ""), "title", 80, language) or scenario["title"]
    rng = secrets.SystemRandom()
    introductions = (
        ("Reference files for the current review cycle.", "Browse the related workspaces and retained exports below.",
         "Shared records and working documents for the operations team.", "Use the linked indexes to locate adjacent review material.")
        if language == "en" else
        ("現在の確認期間に関する参考ファイルです。", "関連する作業領域と保管済みの出力を掲載しています。",
         "運用チームで共有する記録と作業用文書です。", "関連資料はリンク先の一覧から確認できます。")
    )
    nodes, children, files, inventory, size = [""], {}, [], [], 0
    current = [""]
    for _ in range(depth):
        next_level = []
        for parent in current:
            children[parent] = []
            parent_name = posixpath.basename(parent)
            candidates = tuple(folder for folder in DIRECTORY_NAMES if folder != parent_name)
            for folder in rng.sample(candidates, branches):
                child = posixpath.join(parent, folder)
                children[parent].append(child)
                nodes.append(child)
                next_level.append(child)
        current = next_level
    for node in nodes:
        links, documents = [], []
        canary_files = []
        for child in children.get(node, []):
            links.append(posixpath.join(child, "index.html"))
        if cycles:
            links.extend(posixpath.join(other, "index.html") for other in rng.sample(nodes, min(2, len(nodes))) if other != node)
            if node:
                links.append(posixpath.join(posixpath.dirname(node), "index.html"))
        links = list(dict.fromkeys(links))
        env_count = 0
        used_leaves = set()
        for _ in range(per_directory):
            token_url = url_cycle.next()
            if fmt == "env":
                leaf = (".env.development", ".env.development_backup", ".env.development_previous")[env_count]
                env_count += 1
                used_leaves.add(leaf)
            else:
                extension = FORMATS[fmt][0]
                candidates = [f"{stem}.{extension}" for stem in FORMAT_NAMES[fmt]
                              if f"{stem}.{extension}" not in used_leaves]
                leaf = rng.choice(candidates)
                used_leaves.add(leaf)
            path = posixpath.join(node, leaf)
            # Generate synthetic records and a reference for each document.
            data = list(records(scenario["columns"], 12, language))
            canary_cell = place_canary(scenario, data, token_url)
            reference = secrets.token_hex(6).upper()
            content = (render_switchable_env({"env_variable": scenario["env_key"]}, title, token_url, language)
                       if fmt == "env" else render(fmt, title, token_url, data, language,
                                                   reference=reference, context=context,
                                                   columns=scenario["columns"], table=scenario["table"],
                                                   canary_cell=canary_cell))
            size += len(content)
            if size > MAX_MAZE_BYTES:
                raise ValueError(translate("directory_maze_size_limit", language))
            files.append((path, content))
            documents.append(path)
            if token_url:
                canary_record = {"path": path, "url": token_url}
                if fmt == "env":
                    canary_record["field"] = scenario["env_key"]
                    canary_record["location"] = "commented production setting"
                elif scenario.get("canary_field") and canary_cell is not None:
                    canary_record["field"] = scenario["columns"][canary_cell[1]]["name"]
                    canary_record["record"] = canary_cell[0] + 1
                canary_files.append(canary_record)
        index_links = "".join(
            f'<li><a href="{html.escape(posixpath.relpath(path, node or "."), quote=True)}">'
            f'{html.escape(posixpath.basename(posixpath.dirname(path)) or title)}</a></li>' for path in links
        )
        document_links = "".join(
            f'<li><a href="{html.escape(posixpath.basename(path), quote=True)}">'
            f'{html.escape(posixpath.basename(path))}</a></li>' for path in documents
        )
        folder = posixpath.basename(node)
        label = DIRECTORY_LABELS.get(folder, (folder.title(), folder))[0 if language == "en" else 1]
        context_label = label or title
        page_title = title if not node else f"{label} | {title}"
        breadcrumb = " / ".join([title] + [DIRECTORY_LABELS.get(part, (part.title(), part))[0 if language == "en" else 1]
                                          for part in node.split("/") if part])
        description = rng.choice(introductions)
        if language == "en":
            detail = rng.choice(("The related {label} files are grouped in the indexes below.",
                                 "Use the links to review adjacent {label} material.",
                                 "Supporting {label} records may be filed in neighboring folders.",
                                 "The folder index includes other {label} working areas."))
        else:
            detail = rng.choice(("{label}に関連するファイルは下の一覧にまとめています。",
                                 "リンク先から{label}の関連資料を確認できます。",
                                 "補足となる{label}の記録は隣接するフォルダーにも保管しています。",
                                 "フォルダー一覧には{label}の作業領域も含まれます。"))
        description = f"{description} {detail.format(label=context_label)}"
        page = (f'<!doctype html><html lang="{language}"><head><meta charset="utf-8">'
                f'<meta name="viewport" content="width=device-width, initial-scale=1">'
                f'{STATIC_HTML_SECURITY_META}'
                f'<title>{html.escape(page_title)}</title><style>'
                'body{font:16px/1.55 system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1.25rem;color:#263746}'
                'header,section{margin:1.25rem 0;padding:1rem 1.25rem;border:1px solid #dce3e8;border-radius:8px}'
                '.crumb{color:#596b78;font-size:.9rem}h1{font-size:1.6rem}a{color:#145d83}'
                '</style></head><body><main><header>'
                f'<p class="crumb">{html.escape(breadcrumb)}</p><h1>{html.escape(page_title)}</h1>'
                f'<p>{html.escape(description)}</p></header>'
                f'<section><h2>{"Related indexes" if language == "en" else "関連する一覧"}</h2><ul>{index_links}</ul></section>'
                f'<section><h2>{"Documents" if language == "en" else "文書"}</h2><ul>{document_links}</ul></section>'
                '</main></body></html>').encode("utf-8")
        size += len(page)
        if size > MAX_MAZE_BYTES:
            raise ValueError(translate("directory_maze_size_limit", language))
        files.append((posixpath.join(node, "index.html"), page))
        inventory.append({"directory": node or ".", "links": links, "documents": documents,
                          "canary_files": canary_files})
    rng.shuffle(files)
    canary_placements = sum(len(item["canary_files"]) for item in inventory)
    canary_examples = [
        {"path": entry["path"], "field": entry.get("field"),
         "record": entry.get("record"), "location": entry.get("location")}
        for item in inventory for entry in item["canary_files"]
    ][:3]
    summary = {"kind": "directory_maze", "directories": total, "documents": total * per_directory,
               "canary_placements": canary_placements, "canary_location_examples": canary_examples}
    artifact = bundle(name, files, {"warning": translate("maze_operator_warning", language), "entrypoint": "index.html",
                                    "scenario": scenario_name, "schema": scenario["schema"],
                                    "nodes": inventory, "summary": summary}, summary, language, "directory_maze_size_limit")
    LOGGER.info("directory_maze_complete directories=%d documents=%d canary_placements=%d archive_bytes=%d elapsed_ms=%d",
                total, total * per_directory, canary_placements, len(artifact.content),
                max(0, round((time.monotonic() - started) * 1000)))
    return artifact


def encode_payload(data, codec):
    if codec == "hex": return data.hex()
    if codec == "percent": return quote_from_bytes(data, safe="")
    if codec == "base64url": return base64.urlsafe_b64encode(data).decode("ascii")
    if codec == "gzip_base64":
        gzip_mtime = int(time.time()) - secrets.randbelow(180 * 24 * 60 * 60 + 1)
        data = gzip.compress(data, mtime=gzip_mtime)
    return base64.b64encode(data).decode("ascii")


def generate_encoding_maze(settings, language="ja"):
    started = time.monotonic()
    LOGGER.info("encoding_maze_started language=%s", language)
    layers = integer(settings.get("layers", 4), "layers", 1, 8, language)
    count = integer(settings.get("candidates", 5), "candidates", 1, 20, language)
    codecs = selection(settings.get("codecs", ["base64", "hex", "percent", "gzip_base64"]), CODECS, language)
    fmt = settings.get("format", "json")
    if not isinstance(fmt, str) or fmt not in FORMATS:
        raise ValueError(translate("invalid_format", language))
    url_cycle = CanaryURLCycle(canary_url_list(settings, language))
    scenario_name, scenario = scenario_for(settings, language)
    context = resolve_context({"canary_context": scenario["context"]}, language)
    name = plausible_filename("encoding_maze")
    rng = secrets.SystemRandom()
    extension = FORMATS[fmt][0]
    if fmt == "env":
        candidates = list(ENV_CANDIDATE_PATHS)
    else:
        suffixes = ("", "_archive", "_review", "_reconciled", "_regional", "_summary", "_operations", "_consolidated", "_reference")
        candidates = [f"exports/{stem}{suffix}.{extension}"
                      for stem in scenario["file_stems"] for suffix in suffixes]
    rng.shuffle(candidates)
    paths = candidates[:count]
    files, inventory, size = [], [], 0
    for path in paths:
        # Generate each candidate document independently.
        document_title = scenario["title"]
        candidate_records = list(records(scenario["columns"], 15, language))
        reference = secrets.token_hex(6).upper()
        token_url = url_cycle.next()
        canary_cell = place_canary(scenario, candidate_records, token_url)
        app_env = ("production" if ".env.production" in path else
                   "staging" if ".env.staging" in path else
                   "test" if ".env.test" in path else "development")
        if fmt == "env":
            content = render_switchable_env({"env_variable": scenario["env_key"]}, document_title,
                                            token_url, language, environment=app_env)
        else:
            content = render(fmt, document_title, token_url, candidate_records,
                             language, reference=reference, context=context, columns=scenario["columns"],
                             table=scenario["table"], canary_cell=canary_cell)
        digest = hashlib.sha256(content).hexdigest()
        pipeline = []
        for _ in range(layers):
            codec = rng.choice(codecs)
            # Limit before expansion and after serialization; no archive bomb or unbounded allocation.
            multiplier = 3 if codec == "percent" else 2 if codec == "hex" else 1.4
            if len(content) * multiplier + 1024 > MAX_MAZE_BYTES:
                raise ValueError(translate("encoding_maze_size_limit", language))
            content = json.dumps({"encoding": codec, "payload": encode_payload(content, codec)},
                                 separators=(",", ":"), allow_nan=False).encode("utf-8")
            pipeline.insert(0, codec)
        if size + len(content) > MAX_MAZE_BYTES:
            raise ValueError(translate("encoding_maze_size_limit", language))
        size += len(content)
        files.append((path, content))
        detail = {"path": path, "decode_order": pipeline,
                  "decoded_format": fmt, "sha256": digest, "canary": bool(token_url)}
        if token_url:
            detail["canary_url"] = token_url
            if fmt == "env":
                detail["canary_field"] = scenario["env_key"]
                detail["canary_location"] = "commented production setting"
            elif scenario.get("canary_field") and canary_cell is not None:
                detail["canary_field"] = scenario["columns"][canary_cell[1]]["name"]
                detail["canary_record"] = canary_cell[0] + 1
        inventory.append(detail)
    public_paths = paths.copy()
    rng.shuffle(public_paths)
    index = {"exports": [{"path": path} for path in public_paths]}
    index_content = json.dumps(index, indent=2, allow_nan=False).encode("utf-8")
    if size + len(index_content) > MAX_MAZE_BYTES:
        raise ValueError(translate("encoding_maze_size_limit", language))
    rng.shuffle(files)
    files.append(("index.json", index_content))
    canary_examples = [
        {"path": item["path"], "field": item.get("canary_field"),
         "record": item.get("canary_record"), "location": item.get("canary_location")}
        for item in inventory if item["canary"]
    ][:3]
    summary = {"kind": "encoding_maze", "scenario": scenario_name, "candidates": count, "layers": layers,
               "canary_placements": sum(bool(item["canary"]) for item in inventory),
               "canary_location_examples": canary_examples}
    artifact = bundle(name, files, {"warning": translate("maze_operator_warning", language), "candidates": inventory, "summary": summary}, summary, language, "encoding_maze_size_limit")
    LOGGER.info("encoding_maze_complete candidates=%d layers=%d canary_placements=%d archive_bytes=%d elapsed_ms=%d",
                count, layers, summary["canary_placements"], len(artifact.content),
                max(0, round((time.monotonic() - started) * 1000)))
    return artifact


def _stream_preview(language):
    ja = language == "ja"
    words = ("インフィニット・ストリーム配信", "配信用トークン", "ダウンロードリンクを作成",
             "ダウンロードを開始", "管理用トークン（停止時のみ）", "すべての配信を停止",
             "配信は無期限です。ダウンロードをキャンセルするか、管理用トークンで停止してください。",
             "トークンは保存されません。サーバー終了はコンソールで Ctrl+C を押してください。",
             "待機中") if ja else (
             "Infinite Stream delivery", "Access token", "Create download link", "Start download",
             "Admin token (stop only)", "Stop all streams",
             "The stream has no time or size limit. Cancel the download or stop delivery with the admin token.",
             "Tokens are not stored. Press Ctrl+C in the server console to end the process.", "Ready")
    title, access_label, create_label, download_label, admin_label, stop_label, warning, note, ready = words
    html_doc = f'''<!doctype html><html lang="{language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta name="referrer" content="no-referrer"><title>{title}</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f3f6fa;color:#172b4d;font:16px/1.55 system-ui,sans-serif}}main{{max-width:720px;margin:8vh auto;padding:0 20px}}section{{background:white;border:1px solid #dfe4ec;border-radius:10px;padding:28px}}h1{{font-size:23px;margin:0}}p{{color:#44546a}}label{{display:block;font-size:14px;font-weight:600;margin:18px 0 6px}}input{{width:100%;padding:12px;border:1px solid #bdc7d6;border-radius:6px;font:inherit}}button,a{{display:inline-block;margin:14px 8px 0 0;padding:11px 16px;border:0;border-radius:6px;background:#1769aa;color:white;font:inherit;font-weight:650;text-decoration:none;cursor:pointer}}.stop{{background:#7f1d1d}}[hidden]{{display:none}}#status{{min-height:1.5em;font-size:14px}}
</style><script src="/stream-preview.js" defer></script></head><body><main><section><h1>{title}</h1><p>{warning}</p><label for="access-token">{access_label}</label><input id="access-token" type="password" autocomplete="off"><button id="create-link">{create_label}</button><a id="download-link" href="#" hidden>{download_label}</a><label for="admin-token">{admin_label}</label><input id="admin-token" type="password" autocomplete="off"><button id="stop-streams" class="stop">{stop_label}</button><p id="status" role="status" aria-live="polite">{ready}</p><small>{note}</small></section></main></body></html>'''
    js = '''"use strict";
const access=document.getElementById("access-token"),admin=document.getElementById("admin-token"),create=document.getElementById("create-link"),link=document.getElementById("download-link"),stop=document.getElementById("stop-streams"),status=document.getElementById("status"),ja=document.documentElement.lang==="ja";
async function post(path,token){return fetch(path,{method:"POST",headers:{Authorization:`Bearer ${token}`},cache:"no-store",credentials:"same-origin",redirect:"error"});}
create.addEventListener("click",async()=>{link.hidden=true;if(!access.value){status.textContent=ja?"配信用トークンを入力してください。":"Enter the access token.";return;}create.disabled=true;try{const r=await post("/download-ticket",access.value);if(!r.ok)throw Error();const d=await r.json();link.href=d.download_url;link.hidden=false;status.textContent=ja?`リンクは${d.expires_in}秒で期限切れです。クリックすると配信を開始します。`:`Link expires in ${d.expires_in} seconds. Click it to start the stream.`;}catch(_){status.textContent=ja?"リンクを作成できません。トークンとサーバーを確認してください。":"Could not create link. Check token and server.";}finally{create.disabled=false;}});
stop.addEventListener("click",async()=>{if(!admin.value){status.textContent=ja?"管理用トークンを入力してください。":"Enter the admin token.";return;}stop.disabled=true;try{const r=await post("/stop",admin.value);if(!r.ok)throw Error();status.textContent=ja?"配信を停止しました。プロセスは稼働中です。":"Delivery stopped. The process is still running.";}catch(_){status.textContent=ja?"停止できません。トークンとサーバーを確認してください。":"Could not stop delivery. Check token and server.";}finally{stop.disabled=false;}});
link.addEventListener("click",()=>{link.hidden=true;status.textContent=ja?"配信中です。終了するにはダウンロードをキャンセルしてください。":"Streaming. Cancel the download to stop it.";});
'''
    return html_doc.encode("utf-8"), js.encode("utf-8")


def generate_stream_sample(settings, language="ja"):
    started = time.monotonic()
    LOGGER.info("stream_sample_started language=%s", language)
    rate = integer(settings.get("rate_kib", 8), "rate_kib", 1, 64, language)
    maximum = integer(settings.get("max_streams", 2), "max_streams", 1, 8, language)
    port = integer(settings.get("port", 9080), "stream_port", 1024, 65535, language)
    path = text(settings.get("path", "/exports/archive.sql"), "stream_path", 160, language)
    fmt = settings.get("format", "sql")
    try:
        config = validate_config({"port": port, "path": path, "format": fmt, "rate_kib": rate, "max_streams": maximum})
    except ValueError as exc:
        raise ValueError(translate("stream_config_error", language)) from exc
    name = plausible_filename("stream")
    environment = {"ADG_STREAM_TOKEN": secrets.token_urlsafe(32), "ADG_STREAM_ADMIN_TOKEN": secrets.token_urlsafe(32)}
    license_note = ("ライセンス：Apache License 2.0（LICENSEを参照）\n\n" if language == "ja"
                    else "License: Apache License 2.0 (see LICENSE).\n\n")
    readme = license_note + translate("stream_bundle_readme", language, operator=name + ".operator.json", port=port, path=path)
    readme += "\n" + translate("stream_bundle_token_note", language)
    readme += "\n" + translate("stream_bundle_operator_permissions", language)
    readme += "\n" + translate("stream_bundle_config_note", language)
    readme += "\n" + translate("stream_bundle_end_reason", language)
    readme += ("\nプレビュー: サーバー起動後に http://127.0.0.1:" + str(port) + "/ を開き、管理者用JSONの配信用トークンを入力します。リンクをクリックするとブラウザーのダウンロードとして無期限配信を開始します。停止はダウンロードのキャンセル、またはプレビュー画面で管理用トークンを使ってください。\n"
               if language == "ja" else
               "\nPreview: after starting the server, open http://127.0.0.1:" + str(port) + "/ and enter the access token from the operator JSON. Clicking the link starts an unbounded browser download. Cancel the download, or use the admin token in the preview to stop delivery.\n")
    license_path = Path(__file__).resolve().parents[1] / "LICENSE"
    preview_html, preview_js = _stream_preview(language)
    files = [("LICENSE", license_path.read_bytes()),
             ("serve.py", Path(__file__).with_name("stream_runtime.py").read_bytes()),
             ("stream_config.json", json.dumps(config, indent=2, allow_nan=False).encode("utf-8")),
             ("index.html", preview_html), ("stream-preview.js", preview_js),
             ("README.txt", readme.encode("utf-8"))]
    summary = {"kind": "stream", "rate_kib": rate, "max_streams": maximum,
               "preview_url": f"http://127.0.0.1:{port}/",
               "preview_html": preview_html.decode("utf-8")}
    artifact = bundle(name, files, {"warning": translate("stream_operator_warning", language), "environment": environment,
                                   "download_url": f"http://127.0.0.1:{port}{path}", "stop_url": f"http://127.0.0.1:{port}/stop"}, summary, language)
    LOGGER.info("stream_sample_complete rate_kib=%d max_streams=%d files=%d archive_bytes=%d elapsed_ms=%d",
                rate, maximum, len(files), len(artifact.content),
                max(0, round((time.monotonic() - started) * 1000)))
    return artifact
