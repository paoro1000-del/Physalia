"""Generate inert decoy assets. No network access or deployment is performed."""

from __future__ import annotations

import html
import io
import os
import secrets
import zipfile
from datetime import date, timedelta

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from physalia.archive_metadata import write_archive_member
from physalia.i18n import translate
from physalia.validation import (text as _text, canary_url as _canary_url,
                                         filename, reject_unsafe_text_tree,
                                         vault_decoy_domain)
from physalia.database import (DATABASE_TEMPLATES, _template_columns_with_labels,
                                      database_settings, records as database_records, sqlite_bytes)
from physalia.formats import PREVIEW_ROW_LIMIT, STATIC_HTML_SECURITY_META, generate_canary, render
from physalia.nesting import MAX_LAYERS, Artifact, generate_nest
from physalia.mazes import generate_directory_maze, generate_encoding_maze, generate_stream_sample
from physalia.naming import plausible_filename
from physalia.inventory import attach_inventory
from physalia.tripwire import generate_ransomware_tripwire
from physalia.ransomware_decoys import generate_path_maze, generate_sparse_decoy

MAGIC = b"ADG1"
def _derive_key(password: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=2**14, r=8, p=1).derive(password.encode("utf-8"))


def encrypt_layer(data: bytes, password: str) -> bytes:
    salt, nonce = os.urandom(16), os.urandom(12)
    header = MAGIC + salt + nonce
    return header + AESGCM(_derive_key(password, salt)).encrypt(nonce, data, header)


def decrypt_layer(data: bytes, password: str, language: str = "ja") -> bytes:
    if len(data) < 48 or data[:4] != MAGIC:
        raise ValueError(translate("invalid_format", language))
    return AESGCM(_derive_key(password, data[4:20])).decrypt(data[20:32], data[32:], data[:32])


def generate_env(settings: dict, language: str = "ja") -> Artifact:
    name, mime, content, summary = generate_canary(settings, language, include_metadata=True)
    if not name.startswith(".env"):
        return Artifact(name, mime, content, summary=summary)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        write_archive_member(archive, name, content, language=language)
    archive_name = name.lstrip(".").replace(".", "_") + "_deployment.zip"
    packaged = Artifact(archive_name, "application/zip", output.getvalue(), role="deployment")
    return Artifact(name, mime, content, [packaged], summary)


def generate_database(settings: dict, language: str = "ja") -> Artifact:
    table, columns, row_count = database_settings(settings, language)
    template_id = settings.get("template", "customers")
    template_labels = ({column["name"]: column["label"]
                        for column in _template_columns_with_labels(template_id, language)}
                       if template_id in DATABASE_TEMPLATES else {})
    basename = (filename(settings["filename"], language) if settings.get("filename")
                else plausible_filename("database", extension="sqlite", profile=template_id))
    url = _canary_url(settings.get("canary_url", ""), language)
    summary = {"kind": "database", "table": table, "tables": 1, "rows": row_count,
               "columns": len(columns), "template": template_id,
               "preview_columns": [column["name"] for column in columns],
               "preview_labels": [template_labels.get(column["name"], column["name"]) for column in columns],
               "preview_rows": []}
    canary_field_by_template = {"passwords": "login_url", "api_credentials": "api_endpoint"}
    canary_field = canary_field_by_template.get(settings.get("template"))
    canary_field_index = next((index for index, column in enumerate(columns)
                               if column["name"].casefold() == canary_field), None)
    canary_field_usable = (canary_field_index is not None
                           and columns[canary_field_index]["kind"] in ("domain", "text"))
    if url and canary_field_usable:
        row_index = secrets.randbelow(row_count)
        profile_name = {"passwords": "password_vault", "api_credentials": "api_credential_inventory"}[
            settings["template"]]
        placement_kind = "vault_field" if settings["template"] == "passwords" else "api_endpoint_field"
        summary["canary_placement"] = {
            "kind": placement_kind, "field": columns[canary_field_index]["name"],
            "record": row_index + 1,
        }
        summary["resolved_canary_context"] = {
            "profile": profile_name, "table": table,
            "field": columns[canary_field_index]["name"], "record": row_index + 1,
        }
        database_url = ""

        def data_rows():
            for index, row in enumerate(records(columns, row_count, language)):
                if index == row_index:
                    row[canary_field_index] = url
                yield row
    else:
        database_url = url
        if database_url:
            summary["tables"] = 2
            summary["canary_placement"] = {"kind": "connection_table"}
        data_rows = records(columns, row_count, language)
    source_rows = data_rows() if callable(data_rows) else data_rows

    def preview_rows():
        for index, row in enumerate(source_rows):
            if index < PREVIEW_ROW_LIMIT:
                summary["preview_rows"].append([
                    (("[URL hidden]" if language == "en" else "[URLは非表示]")
                     if isinstance(value, str) and value.casefold().startswith(("http://", "https://"))
                     else value)
                    for value in row
                ])
            yield row

    return Artifact(basename + ".db", "application/vnd.sqlite3",
                    sqlite_bytes(table, columns, preview_rows(), database_url, language=language), summary=summary)


def generate_web(settings: dict, language: str = "ja") -> Artifact:
    language = language if language in ("ja", "en") else "ja"
    scenario = settings.get("scenario", "operations")
    if scenario not in ("operations", "shared", "archive", "records"):
        raise ValueError("Invalid portal scenario")
    url = _canary_url(settings.get("canary_url", ""), language)
    def localized(pair):
        return pair[0] if language == "ja" else pair[1]

    records = [
        (("四半期レポート.pdf", "Quarterly_Report.pdf"), 0, ("利用可能", "Ready")),
        (("運用ハンドブック.pdf", "Operations_Handbook.pdf"), 1, ("確認中", "In review")),
        (("サービス台帳.xlsx", "Service_Inventory.xlsx"), 3, ("利用可能", "Ready")),
        (("アーカイブ索引.csv", "Archive_Index.csv"), 7, ("保管済み", "Archived")),
        (("アクセス権レビュー.xlsx", "Access_Review.xlsx"), 2, ("確認中", "In review")),
        (("復旧手順チェックリスト.pdf", "Recovery_Checklist.pdf"), 5, ("利用可能", "Ready")),
        (("取引先連絡先.xlsx", "Vendor_Contacts.xlsx"), 9, ("更新済み", "Updated")),
        (("エクスポート予定.csv", "Export_Schedule.csv"), 14, ("予定", "Scheduled")),
        (("変更管理台帳.xlsx", "Change_Register.xlsx"), 4, ("確認中", "In review")),
        (("当番引継ぎメモ.pdf", "On_Call_Handover.pdf"), 2, ("更新済み", "Updated")),
        (("月次サービス点検.csv", "Monthly_Service_Check.csv"), 11, ("完了", "Complete")),
        (("プロジェクト議事録.pdf", "Project_Meeting_Notes.pdf"), 1, ("更新済み", "Updated")),
        (("共有資料の確認表.xlsx", "Shared_Materials_Review.xlsx"), 6, ("確認中", "In review")),
        (("文書保管期限一覧.csv", "Document_Retention_Schedule.csv"), 18, ("保管済み", "Archived")),
        (("旧システム移行記録.pdf", "Legacy_Migration_Record.pdf"), 27, ("完了", "Complete")),
        (("承認履歴一覧.csv", "Approval_History.csv"), 3, ("更新済み", "Updated")),
        (("記録確認チェックリスト.xlsx", "Records_Review_Checklist.xlsx"), 0, ("確認中", "In review")),
    ]
    profiles = {
        "operations": (("運用ポータル", "Operations Portal"), ("運用ファイル一覧", "Operations files"),
                       ("運用記録", "Operations"), (0, 1, 2, 5, 4, 8, 9, 10)),
        "shared": (("共有ドキュメント", "Document Workspace"), ("共有ドキュメント一覧", "Shared documents"),
                   ("共有ファイル", "Shared files"), (0, 3, 6, 7, 5, 11, 12)),
        "archive": (("業務アーカイブ", "Business Archive"), ("アーカイブ一覧", "Archive index"),
                    ("アーカイブ", "Archives"), (0, 2, 3, 5, 6, 13, 14)),
        "records": (("記録管理", "Records Center"), ("業務記録一覧", "Business records"),
                    ("業務記録", "Business records"), (1, 4, 6, 7, 3, 15, 16)),
    }
    profile_title, profile_heading, profile_section, profile_record_ids = profiles[scenario]
    title = _text(settings.get("title", ""), "title", 80, language) or localized(profile_title)
    recent_records = secrets.SystemRandom().sample([records[index] for index in profile_record_ids], 6)
    recent_records.sort(key=lambda record: record[1])
    linked_record = secrets.choice(recent_records) if url else None
    preview_rows, deployment_rows = [], []
    for names, days_ago, statuses in recent_records:
        name = localized(names)
        status = localized(statuses)
        updated = (date.today() - timedelta(days=days_ago)).strftime("%Y年%m月%d日" if language == "ja" else "%b %d, %Y")
        escaped_name = html.escape(name)
        if linked_record is not None and (names, days_ago, statuses) == linked_record:
            file_name = f'<a class="file-link" href="{html.escape(url, quote=True)}" rel="noreferrer">{escaped_name}</a>'
            deployment_file_name = file_name
        else:
            file_name = escaped_name
            deployment_file_name = f'<a class="file-link" href="documents/{html.escape(name, quote=True)}">{escaped_name}</a>'
        for target, label in ((preview_rows, file_name), (deployment_rows, deployment_file_name)):
            target.append(f'<tr><td><span class="file-icon" aria-hidden="true">▤</span>{label}</td><td>{updated}</td><td><span class="status">{html.escape(status)}</span></td></tr>')
    heading = localized(profile_heading)
    section = localized(profile_section)
    recent_label = "最近のファイル" if language == "ja" else "Recent files"
    file_label = "ファイル" if language == "ja" else "File"
    count_value = str(secrets.randbelow(801) + 120)
    showing_label = (f"最近の6件を表示（登録済み{count_value}件）" if language == "ja"
                     else f"Showing 6 recent files of {count_value} indexed.")
    updated_label = "最終更新" if language == "ja" else "Last updated"
    status_label = "状態" if language == "ja" else "Status"
    count_label = "登録済みファイル" if language == "ja" else "Files indexed"
    scroll_hint = "表は左右にスクロールできます。" if language == "ja" else "Scroll horizontally to see all columns."
    def make_page(rows):
        return f"""<!doctype html>
<html lang="{language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
{STATIC_HTML_SECURITY_META}
<title>{html.escape(title)}</title>
<style>
:root{{color-scheme:light;--ink:#203447;--muted:#607486;--line:#dbe4eb;--surface:#fff;--canvas:#f3f6f9;--accent:#245b78}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--canvas);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}}
header{{background:var(--surface);border-bottom:1px solid var(--line)}}
.bar{{max-width:1040px;margin:auto;padding:1rem 1.5rem;font-weight:700;letter-spacing:.01em}}
main{{max-width:1040px;margin:2.5rem auto;padding:0 1.5rem}}
h1{{margin:0 0 .4rem;font-size:clamp(1.6rem,3vw,2.15rem);letter-spacing:-.025em}}
.intro{{margin:.25rem 0 1.5rem;color:var(--muted)}}
.summary{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem;margin:1.25rem 0}}
.card,.panel{{background:var(--surface);border:1px solid var(--line);border-radius:12px;box-shadow:0 3px 12px #1d34440a}}
.card{{padding:1rem 1.2rem}}
.card small{{display:block;color:var(--muted);font-size:.82rem}}
.card strong{{display:block;margin-top:.2rem;font-size:1.45rem;font-variant-numeric:tabular-nums}}
.panel{{overflow:hidden}}
.panel-head{{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:1rem 1.2rem;border-bottom:1px solid var(--line)}}
.panel-head h2{{margin:0;font-size:1.1rem}}
a{{color:var(--accent)}}
.file-link{{font-weight:600;text-decoration:underline;text-decoration-color:#9bb3c0;text-underline-offset:3px}}
.file-link:hover{{color:#17445d;text-decoration-color:currentColor}}
.file-link:focus-visible,.table-scroll:focus-visible{{outline:3px solid #e0a928;outline-offset:3px}}
.table-scroll{{max-width:100%;overflow-x:auto}}
.table-scroll-hint{{display:none;margin:.6rem 1.2rem;color:var(--muted);font-size:.82rem}}
table{{width:100%;border-collapse:collapse;text-align:left}}
caption{{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}}
th,td{{padding:.8rem 1.2rem;border-bottom:1px solid var(--line);white-space:nowrap}}
th{{color:var(--muted);font-size:.8rem;font-weight:650;background:#f9fbfc}}
tbody tr:last-child td{{border-bottom:0}}
.file-icon{{display:inline-block;width:1.6rem;color:#668399}}
.status{{display:inline-block;padding:.16rem .55rem;border-radius:999px;background:#edf4f7;color:#355b6d;font-size:.82rem}}
.table-meta{{margin:0;padding:.75rem 1.2rem;border-top:1px solid var(--line);color:var(--muted);font-size:.84rem}}
footer{{padding:1.25rem .1rem;color:var(--muted);font-size:.82rem}}
@media(max-width:620px){{main{{margin:1.4rem auto;padding:0 1rem}}.bar{{padding:.85rem 1rem}}.panel-head{{align-items:flex-start;flex-direction:column}}.table-scroll-hint{{display:block}}th,td{{padding:.7rem .8rem}}}}
 </style>
</head><body><header><div class="bar"><span class="brand">{html.escape(title)}</span></div></header><main><h1>{html.escape(heading)}</h1><p class="intro">{section}</p><div class="summary"><div class="card"><small>{count_label}</small><strong>{count_value}</strong></div><div class="card"><small>{updated_label}</small><strong>{date.today().strftime("%Y/%m/%d" if language == "ja" else "%b %d")}</strong></div></div><section class="panel"><div class="panel-head"><h2>{recent_label}</h2></div><p id="scroll-hint" class="table-scroll-hint">{html.escape(scroll_hint)}</p><div class="table-scroll" role="region" tabindex="0" aria-label="{recent_label}" aria-describedby="table-summary scroll-hint"><table><caption>{recent_label}</caption><thead><tr><th scope="col">{file_label}</th><th scope="col">{updated_label}</th><th scope="col">{status_label}</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div><p id="table-summary" class="table-meta">{showing_label}</p></section><footer>{html.escape(title)} · {section}</footer></main></body></html>
"""
    markup = make_page(preview_rows)
    basename = (filename(settings["filename"], language) if settings.get("filename")
                else plausible_filename("html", extension="html", context=scenario))
    artifact_name = basename + ".html"
    package_name = basename + "_site.zip"
    portal_templates = {"operations": "cloud", "shared": "customers",
                        "archive": "invoices", "records": "tickets"}
    template_id = portal_templates[scenario]
    template = DATABASE_TEMPLATES[template_id]
    columns = _template_columns_with_labels(template_id, language)
    package = io.BytesIO()
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        write_archive_member(archive, "index.html", make_page(deployment_rows).encode("utf-8"), language=language)
        for names, _days_ago, _statuses in recent_records:
            name = localized(names)
            extension = name.rsplit(".", 1)[-1].casefold()
            fmt = {"pdf": "pdf", "xlsx": "xlsx", "csv": "csv"}.get(extension)
            if fmt is None:
                continue
            sample_rows = list(database_records(columns, 3, language))
            document = render(fmt, name.rsplit(".", 1)[0], "", sample_rows,
                              language, columns=columns, table=template["table"])
            write_archive_member(archive, "documents/" + name, document, language=language)
    summary = {"kind": "web", "documents": len(recent_records)}
    if linked_record is not None:
        canary_label = localized(linked_record[0])
        summary["canary_locations"] = [
            {"artifact": artifact_name, "element": "file_list_entry", "label": canary_label},
            {"artifact": package_name + "!/index.html", "element": "file_list_entry", "label": canary_label},
        ]
    deployment = Artifact(package_name, "application/zip", package.getvalue(), role="deployment")
    return Artifact(artifact_name, "text/html; charset=utf-8", markup.encode("utf-8"),
                    [deployment], summary)


def generate_fake_trap(settings: dict, language: str = "ja") -> tuple[str, str, bytes]:
    """Create a standalone, inert warning or waiting page; no telemetry is embedded."""
    variant = settings.get("variant", "warning")
    if variant not in ("warning", "reported", "waiting"):
        raise ValueError("Invalid fake trap variant")
    messages = {
        "ja": {"warning": ("異常なアクセスを検知しました", "この操作は監視対象です。"),
               "reported": ("アクセスが通報されました", "この操作はセキュリティ担当者に通報されました。"),
               "waiting": ("認証しています", "確認が完了するまでお待ちください。")},
        "en": {"warning": ("Unusual access detected", "This activity is subject to monitoring."),
               "reported": ("Access reported", "This activity has been reported to the security team."),
               "waiting": ("Authenticating", "Please wait while verification is in progress.")},
    }
    lang = language if language in messages else "ja"
    title, message = messages[lang][variant]
    spinner = '<div class="spinner" aria-hidden="true"></div>' if variant == "waiting" else ""
    markup = f'''<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
{STATIC_HTML_SECURITY_META}<title>{html.escape(title)}</title>
<style>body{{font-family:system-ui,sans-serif;background:#f3f6fa;color:#203047;margin:0;padding:12vh 1rem}}
main{{max-width:580px;margin:auto;padding:2rem;background:white;border:1px solid #cbd5df;border-radius:12px}}
.spinner{{width:36px;height:36px;border:4px solid #d9e3ee;border-top-color:#295d91;border-radius:50%;animation:spin 1s linear infinite}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}@media(prefers-reduced-motion:reduce){{.spinner{{animation:none}}}}</style>
</head><body><main>{spinner}<h1>{html.escape(title)}</h1><p>{html.escape(message)}</p></main></body></html>'''
    basename = (filename(settings["filename"], language) if settings.get("filename")
                else plausible_filename("fake_trap"))
    return basename + ".html", "text/html; charset=utf-8", markup.encode("utf-8")


GENERATORS = {"env": generate_env, "database": generate_database, "web": generate_web, "nest": generate_nest, "fake_trap": generate_fake_trap,
              "ransomware_tripwire": generate_ransomware_tripwire}
GENERATORS.update(directory_maze=generate_directory_maze, encoding_maze=generate_encoding_maze, stream=generate_stream_sample)
GENERATORS.update(path_maze=generate_path_maze, sparse_decoy=generate_sparse_decoy)

# Keep the API surface aligned with the settings assembled by web/app.js.
# Silently ignored keys are easy to mistype and would otherwise be copied into
# the operator inventory even though they had no effect on the generated file.
SETTING_KEYS = {
    "env": {"format", "canary_url", "canary_link_style", "canary_context", "canary_field", "canary_label",
            "env_layout", "env_suffix", "env_variable", "env_dev_url",
            "env_dev_url_authorized", "env_dev_comment", "env_prod_comment", "title", "rows", "filename"},
    "database": {"template", "email_domain", "email_domain_authorized", "vault_domain",
                 "vault_domain_authorized", "rows", "table", "columns", "canary_url", "filename"},
    "web": {"scenario", "title", "canary_url", "filename"},
    "fake_trap": {"variant", "filename"},
    "ransomware_tripwire": {"files"},
    "path_maze": {"depth", "branches", "files"},
    "sparse_decoy": {"size_gib", "files"},
    "nest": {"scenario", "vault_domain", "vault_domain_authorized", "layers", "branches", "decoys",
             "directory_depth", "rows", "format", "varied_formats", "directories", "canary_urls",
             "canary_url", "canary_percent", "filename", "password_policy"},
    "directory_maze": {"scenario", "vault_domain", "vault_domain_authorized", "title", "depth", "branches",
                        "files_per_directory", "cross_links", "canary_urls", "canary_url", "format", "filename"},
    "encoding_maze": {"scenario", "vault_domain", "vault_domain_authorized", "format", "layers",
                       "candidates", "canary_urls", "canary_url", "codecs", "filename"},
    "stream": {"path", "format", "port", "rate_kib", "max_streams", "filename"},
}


def generate(kind: object, settings: object, language: str = "ja") -> Artifact:
    if not isinstance(kind, str) or kind not in GENERATORS or not isinstance(settings, dict):
        raise ValueError(translate("select_method", language))
    language = language if language in ("ja", "en") else "ja"
    if any(not isinstance(key, str) for key in settings) or settings.keys() - SETTING_KEYS[kind]:
        raise ValueError(translate("unknown_settings", language))
    reject_unsafe_text_tree(settings, language)
    # Dedicated owned-domain inputs are exempt from generic endpoint scanning
    # so canary values remain byte-for-byte intact. Validate them even when a
    # caller supplies an otherwise unused optional field.
    for domain_key in ("vault_domain", "email_domain"):
        if domain_key in settings:
            vault_decoy_domain(settings[domain_key],
                               settings.get("vault_domain_authorized"
                                            if domain_key == "vault_domain"
                                            else "email_domain_authorized", False),
                               language)
    result = GENERATORS[kind](settings, language)
    asset = result if isinstance(result, Artifact) else Artifact(*result)
    # The top-level artifact is the deployable decoy. Companion artifacts keep
    # their own roles (operator-only by default, or deployment when applicable).
    asset.role = "deployment"
    return attach_inventory(asset, kind, settings, language)
