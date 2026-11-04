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
                                         reject_unsafe_text_tree,
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
    basename = plausible_filename("database", extension="sqlite", profile=template_id)
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
            for index, row in enumerate(database_records(columns, row_count, language)):
                if index == row_index:
                    row[canary_field_index] = url
                yield row
    else:
        database_url = url
        if database_url:
            summary["tables"] = 2
            summary["canary_placement"] = {"kind": "connection_table"}
        data_rows = database_records(columns, row_count, language)
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
        updated_date = date.today() - timedelta(days=days_ago)
        updated = (f"{updated_date.year}年{updated_date.month:02d}月{updated_date.day:02d}日"
                   if language == "ja" else updated_date.strftime("%b %d, %Y"))
        escaped_name = html.escape(name)
        if linked_record is not None and (names, days_ago, statuses) == linked_record:
            file_name = f'<a class="file-link" href="{html.escape(url, quote=True)}" rel="noreferrer">{escaped_name}</a>'
            deployment_file_name = file_name
        else:
            file_name = escaped_name
            deployment_file_name = f'<a class="file-link" href="documents/{html.escape(name, quote=True)}">{escaped_name}</a>'
        extension = name.rsplit(".", 1)[-1].casefold()
        status_key = {"Ready": "ready", "In review": "review", "Archived": "archived",
                      "Complete": "complete", "Updated": "updated", "Scheduled": "scheduled"}.get(status, "default")
        modified = date.today() - timedelta(days=days_ago)
        for target, label in ((preview_rows, file_name), (deployment_rows, deployment_file_name)):
            target.append(f'<tr><td><div class="file-cell"><span class="file-icon file-{extension}" aria-hidden="true">{extension.upper()}</span><span>{label}<small class="file-meta">{html.escape(localized(profile_section))}</small></span></div></td><td><time class="date" datetime="{modified.isoformat()}">{updated}</time></td><td><span class="status status-{status_key}">{html.escape(status)}</span></td><td class="type">{extension.upper()}</td></tr>')
    heading = localized(profile_heading)
    section = localized(profile_section)
    recent_label = "最近のファイル" if language == "ja" else "Recent files"
    file_label = "ファイル名" if language == "ja" else "Name"
    count_value = str(secrets.randbelow(801) + 120)
    available_count = sum(1 for record in recent_records if record[2][1] == "Ready")
    showing_label = (f"{count_value}件中 6件を表示" if language == "ja"
                     else f"Showing 6 of {count_value} files")
    updated_label = "更新日時" if language == "ja" else "Last modified"
    status_label = "状態" if language == "ja" else "Status"
    count_label = "登録ファイル" if language == "ja" else "Files indexed"
    type_label = "種類" if language == "ja" else "Type"
    workspace_label = "共有ワークスペース" if language == "ja" else "Shared workspace"
    folder_label = "すべてのファイル" if language == "ja" else "All files"
    overview_label = "概要" if language == "ja" else "Overview"
    files_label = "ファイル" if language == "ja" else "Files"
    activity_label = "アクティビティ" if language == "ja" else "Activity"
    people_label = "メンバー" if language == "ja" else "Members"
    available_label = "利用可能" if language == "ja" else "Available"
    ready_label = "利用可能なファイル" if language == "ja" else "Available files"
    activity_added_label = "ファイルを登録" if language == "ja" else "Files added to workspace"
    activity_review_label = "ワークスペースを確認" if language == "ja" else "Workspace review completed"
    storage_label = "ストレージ" if language == "ja" else "Storage"
    storage_value = "共有ドキュメント" if language == "ja" else "Shared documents"
    filter_label = "すべてのファイル" if language == "ja" else "All files"
    modified_label = "最終更新" if language == "ja" else "Last updated"
    scroll_hint = "表は左右にスクロールできます。" if language == "ja" else "Scroll horizontally to see all columns."
    def make_page(rows):
        return f"""<!doctype html>
<html lang="{language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
{STATIC_HTML_SECURITY_META}
<title>{html.escape(title)}</title>
<style>
:root{{color-scheme:light;--ink:#182431;--muted:#697887;--line:#e4e9ef;--surface:#fff;--canvas:#f6f8fb;--accent:#315f9b;--accent-soft:#edf3fb;--shadow:0 1px 2px #14263b08,0 8px 24px #14263b08}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--canvas);color:var(--ink);font:14px/1.5 Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}}
a{{color:inherit;text-decoration:none}}
.topbar{{height:66px;display:flex;align-items:center;gap:2.25rem;padding:0 4.2vw;background:var(--surface);border-bottom:1px solid var(--line)}}
.brand{{display:flex;align-items:center;gap:.7rem;min-width:220px;font-weight:680;letter-spacing:-.02em}}
.brand-mark{{display:grid;place-items:center;width:31px;height:31px;border-radius:9px;background:#315f9b;color:white;font-size:.85rem;font-weight:750}}
.topnav{{display:flex;align-self:stretch;align-items:center;gap:1.8rem;color:var(--muted);font-size:.9rem}}
.topnav a{{display:flex;height:100%;align-items:center;border-bottom:2px solid transparent;padding-top:2px}}
.topnav a.active{{color:var(--ink);border-bottom-color:var(--accent);font-weight:600}}
.top-right{{margin-left:auto;display:flex;align-items:center;gap:1rem;color:var(--muted);font-size:.84rem}}
.avatar{{display:grid;place-items:center;width:32px;height:32px;border-radius:50%;background:#e8eef7;color:#36597f;font-size:.72rem;font-weight:700}}
.app-layout{{display:grid;grid-template-columns:232px minmax(0,1fr);max-width:1600px;min-height:calc(100vh - 66px);margin:0 auto}}
.sidebar{{padding:1.5rem 1rem;border-right:1px solid var(--line);background:#fbfcfe}}
.workspace-switch{{display:flex;align-items:center;gap:.7rem;padding:.7rem .65rem 1.35rem;margin-bottom:1.1rem;border-bottom:1px solid var(--line)}}
.workspace-symbol{{display:grid;place-items:center;width:34px;height:34px;border-radius:9px;background:#eaf0f8;color:#315f9b;font-weight:700}}
.workspace-name{{display:block;font-size:.82rem;font-weight:650}}
.workspace-subtitle{{display:block;margin-top:.12rem;color:var(--muted);font-size:.73rem}}
.side-label{{margin:.3rem .7rem .5rem;color:#8b97a3;font-size:.67rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase}}
.side-nav{{display:grid;gap:.25rem}}
.side-nav a{{display:flex;align-items:center;gap:.7rem;padding:.62rem .7rem;border-radius:7px;color:#526171;font-size:.84rem}}
.side-nav a:hover{{background:#f0f3f7}}
.side-nav a.active{{background:var(--accent-soft);color:#2b5487;font-weight:620}}
.nav-icon{{width:17px;text-align:center;color:#788797;font-size:.9rem}}
.nav-count{{margin-left:auto;color:#7e8a96;font-size:.75rem;font-variant-numeric:tabular-nums}}
.sidebar-note{{margin:2rem .35rem 0;padding:.85rem;border:1px solid var(--line);border-radius:8px;background:white;color:var(--muted);font-size:.74rem}}
.sidebar-note strong{{display:block;margin-bottom:.25rem;color:#475666;font-size:.76rem}}
.main{{min-width:0;max-width:1320px;width:100%;margin:0 auto;padding:1.7rem clamp(1.25rem,3.5vw,3.5rem) 3rem}}
.breadcrumbs{{display:flex;align-items:center;gap:.55rem;margin-bottom:1.6rem;color:#82909e;font-size:.77rem}}
.breadcrumbs .separator{{color:#bbc4cd}}
.breadcrumbs strong{{color:#506070;font-weight:550}}
.heading-row{{display:flex;align-items:flex-end;justify-content:space-between;gap:1.5rem;margin-bottom:1.65rem}}
.eyebrow{{display:block;margin-bottom:.45rem;color:#718096;font-size:.68rem;font-weight:680;letter-spacing:.1em;text-transform:uppercase}}
h1{{margin:0;font-size:clamp(1.6rem,2.5vw,2.05rem);font-weight:660;letter-spacing:-.045em;line-height:1.2}}
.intro{{max-width:680px;margin:.55rem 0 0;color:var(--muted);font-size:.9rem}}
.heading-actions{{display:flex;align-items:center;gap:1rem;flex-shrink:0}}
.sync-state{{display:flex;align-items:center;gap:.45rem;color:#697887;font-size:.76rem;white-space:nowrap}}
.sync-dot{{width:7px;height:7px;border-radius:50%;background:#35a574;box-shadow:0 0 0 3px #35a57418}}
.updated-pill{{padding:.52rem .75rem;border:1px solid #dfe5ec;border-radius:7px;background:#fff;color:#536273;font-size:.74rem;white-space:nowrap}}
.metrics{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem;margin-bottom:1.4rem}}
.metric,.panel,.detail-card{{border:1px solid var(--line);border-radius:10px;background:var(--surface);box-shadow:var(--shadow)}}
.metric{{display:flex;align-items:center;gap:.85rem;padding:1rem 1.15rem}}
.metric-icon{{display:grid;place-items:center;width:37px;height:37px;border-radius:9px;background:#edf3fb;color:#466b9a;font-size:1rem}}
.metric small{{display:block;color:var(--muted);font-size:.73rem}}
.metric strong{{display:block;margin-top:.12rem;font-size:1.15rem;font-weight:650;font-variant-numeric:tabular-nums;letter-spacing:-.02em}}
.panel{{overflow:hidden}}
.panel-head{{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:1.05rem 1.25rem;border-bottom:1px solid var(--line)}}
.panel-head h2{{margin:0;font-size:.98rem;font-weight:650;letter-spacing:-.015em}}
.panel-subtitle{{margin:.2rem 0 0;color:var(--muted);font-size:.75rem}}
.panel-tools{{display:flex;align-items:center;gap:.55rem}}
.filter-pill{{padding:.38rem .67rem;border:1px solid #e0e6ed;border-radius:6px;background:#fff;color:#536273;font-size:.73rem}}
.filter-pill.active{{border-color:#d9e5f5;background:#f1f6fc;color:#315b91;font-weight:600}}
.table-scroll{{max-width:100%;overflow-x:auto}}
.table-scroll-hint{{display:none;margin:.6rem 1.2rem;color:var(--muted);font-size:.78rem}}
table{{width:100%;border-collapse:collapse;text-align:left}}
caption{{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}}
th,td{{padding:.78rem 1.15rem;border-bottom:1px solid #edf0f4;white-space:nowrap}}
th{{background:#fbfcfd;color:#7a8794;font-size:.68rem;font-weight:650;letter-spacing:.035em}}
tbody tr{{transition:background .12s ease}}
tbody tr:hover{{background:#fafbfd}}
tbody tr:last-child td{{border-bottom:0}}
.file-cell{{display:flex;align-items:center;gap:.72rem;min-width:245px}}
.file-icon{{display:grid;place-items:center;width:33px;height:37px;flex:0 0 auto;border:1px solid #e1e7ee;border-radius:6px;background:linear-gradient(145deg,#fff,#f7f9fb);color:#60778f;font-size:.62rem;font-weight:730;letter-spacing:-.04em}}
.file-pdf{{color:#bd5a55;background:#fff8f7;border-color:#f0e2df}}
.file-xlsx{{color:#31815e;background:#f5fbf7;border-color:#dceee2}}
.file-csv{{color:#987a35;background:#fffaf0;border-color:#efe6d0}}
.file-link{{display:block;max-width:390px;overflow:hidden;color:#263a50;font-size:.81rem;font-weight:570;text-overflow:ellipsis}}
.file-link:hover{{color:var(--accent);text-decoration:underline;text-decoration-color:#9cb4d0;text-underline-offset:3px}}
.file-link:focus-visible,.table-scroll:focus-visible{{outline:3px solid #8cb4ed;outline-offset:2px}}
.file-meta{{display:block;margin-top:.16rem;color:#8a96a2;font-size:.68rem}}
.date{{color:#526171;font-size:.77rem;font-variant-numeric:tabular-nums}}
.status{{display:inline-flex;align-items:center;gap:.36rem;padding:.25rem .52rem;border-radius:999px;background:#f0f4f7;color:#607080;font-size:.68rem;font-weight:570}}
.status::before{{width:6px;height:6px;border-radius:50%;background:#9aa7b4;content:""}}
.status-ready{{background:#edf7f1;color:#33714f}}.status-ready::before{{background:#42a36d}}
.status-review{{background:#fff7e9;color:#8b6926}}.status-review::before{{background:#d4a33b}}
.status-archived{{background:#f1f2f5;color:#707987}}.status-archived::before{{background:#8c95a0}}
.status-complete{{background:#eef3fb;color:#49688e}}.status-complete::before{{background:#6d8fbe}}
.type{{color:#6f7d8b;font-size:.74rem}}
.table-meta{{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:.75rem 1.15rem;border-top:1px solid var(--line);color:#7b8895;font-size:.72rem}}
.detail-grid{{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(240px,1fr);gap:1rem;margin-top:1rem}}
.detail-card{{padding:1rem 1.15rem}}
.detail-title{{margin:0 0 .85rem;font-size:.82rem;font-weight:650}}
.activity-row{{display:flex;align-items:center;gap:.7rem;padding:.5rem 0;color:#596777;font-size:.74rem}}
.activity-row+.activity-row{{border-top:1px solid #f0f2f5}}
.activity-mark{{width:7px;height:7px;flex:0 0 auto;border-radius:50%;background:#84a3cc}}
.activity-row time{{margin-left:auto;color:#8a96a2;font-size:.68rem;white-space:nowrap}}
.info-line{{display:flex;justify-content:space-between;gap:.7rem;padding:.48rem 0;color:#778492;font-size:.73rem}}
.info-line+.info-line{{border-top:1px solid #f0f2f5}}
.info-line strong{{color:#465666;font-size:.73rem;font-weight:560;text-align:right}}
.footer{{display:flex;justify-content:space-between;gap:1rem;margin-top:1.3rem;color:#8b97a3;font-size:.68rem}}
@media(max-width:920px){{.topbar{{padding:0 1.3rem}}.brand{{min-width:auto}}.topnav{{gap:1rem}}.app-layout{{grid-template-columns:190px minmax(0,1fr)}}.sidebar{{padding-inline:.7rem}}.main{{padding-inline:1.3rem}}.heading-row{{align-items:flex-start;flex-direction:column}}.heading-actions{{align-self:flex-end}}}}
@media(max-width:640px){{.topbar{{height:58px;gap:1rem;padding:0 1rem}}.topnav{{display:none}}.top-right{{gap:.6rem}}.workspace-status{{display:none}}.app-layout{{display:block;min-height:calc(100vh - 58px)}}.sidebar{{display:none}}.main{{padding:1.2rem .85rem 2rem}}.breadcrumbs{{margin-bottom:1.1rem}}.heading-row{{gap:1rem;margin-bottom:1.2rem}}.heading-actions{{width:100%;justify-content:space-between}}.metrics{{gap:.55rem}}.metric{{align-items:flex-start;flex-direction:column;gap:.45rem;padding:.75rem}}.metric-icon{{width:30px;height:30px}}.metric strong{{font-size:1rem}}.panel-head{{align-items:flex-start;flex-direction:column;padding:.9rem}}.panel-tools{{width:100%}}th,td{{padding:.7rem .8rem}}.table-scroll-hint{{display:block}}.file-cell{{min-width:205px}}.file-link{{max-width:240px}}.detail-grid{{grid-template-columns:1fr}}.footer{{flex-direction:column}}}}
@media(prefers-reduced-motion:reduce){{*,*::before,*::after{{scroll-behavior:auto!important;transition:none!important}}}}
 </style>
</head><body>
<header class="topbar"><a class="brand" href="#overview"><span class="brand-mark" aria-hidden="true">{html.escape(title[:1].upper())}</span><span>{html.escape(title)}</span></a>
<nav class="topnav" aria-label="{localized(("ワークスペース", "Workspace"))}"><a href="#overview">{overview_label}</a><a class="active" href="#files">{files_label}</a><a href="#activity">{activity_label}</a></nav>
<div class="top-right"><span class="workspace-status">{workspace_label}</span><span class="avatar" aria-label="{people_label}">OP</span></div></header>
<div class="app-layout"><aside class="sidebar" aria-label="{localized(("ナビゲーション", "Navigation"))}">
<div class="workspace-switch"><span class="workspace-symbol" aria-hidden="true">W</span><span><span class="workspace-name">{html.escape(title)}</span><span class="workspace-subtitle">{workspace_label}</span></span></div>
<p class="side-label">{localized(("ワークスペース", "Workspace"))}</p><nav class="side-nav"><a href="#overview"><span class="nav-icon" aria-hidden="true">⌂</span>{overview_label}</a><a class="active" href="#files"><span class="nav-icon" aria-hidden="true">▤</span>{files_label}<span class="nav-count">{count_value}</span></a><a href="#activity"><span class="nav-icon" aria-hidden="true">◷</span>{activity_label}</a><a href="#members"><span class="nav-icon" aria-hidden="true">♙</span>{people_label}</a></nav>
<div class="sidebar-note"><strong>{storage_label}</strong>{storage_value}</div></aside>
<main class="main" id="overview"><div class="breadcrumbs"><span>{localized(("ワークスペース", "Workspace"))}</span><span class="separator">/</span><strong>{folder_label}</strong></div>
<div class="heading-row"><div><span class="eyebrow">{html.escape(title)}</span><h1>{heading}</h1><p class="intro">{section}</p></div><div class="heading-actions"><span class="sync-state"><span class="sync-dot" aria-hidden="true"></span>{available_label}</span><span class="updated-pill">{modified_label}: {date.today().strftime("%Y/%m/%d" if language == "ja" else "%b %d, %Y")}</span></div></div>
<div class="metrics" aria-label="{workspace_label}"><div class="metric"><span class="metric-icon" aria-hidden="true">▤</span><span><small>{count_label}</small><strong>{count_value}</strong></span></div><div class="metric"><span class="metric-icon" aria-hidden="true">✓</span><span><small>{ready_label}</small><strong>{available_count} / 6</strong></span></div><div class="metric"><span class="metric-icon" aria-hidden="true">◷</span><span><small>{modified_label}</small><strong>{date.today().strftime("%Y/%m/%d" if language == "ja" else "%b %d")}</strong></span></div></div>
<section class="panel" id="files"><div class="panel-head"><div><h2>{recent_label}</h2><p class="panel-subtitle">{folder_label} · {showing_label}</p></div><div class="panel-tools"><span class="filter-pill active">{filter_label}</span><span class="filter-pill">{section}</span></div></div>
<p id="scroll-hint" class="table-scroll-hint">{html.escape(scroll_hint)}</p><div class="table-scroll" role="region" tabindex="0" aria-label="{recent_label}" aria-describedby="table-summary scroll-hint"><table><caption>{recent_label}</caption><thead><tr><th scope="col">{file_label}</th><th scope="col">{updated_label}</th><th scope="col">{status_label}</th><th scope="col">{type_label}</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div><div id="table-summary" class="table-meta"><span>{showing_label}</span><span>{available_label}</span></div></section>
<div class="detail-grid"><section class="detail-card" id="activity"><h2 class="detail-title">{activity_label}</h2><div class="activity-row"><span class="activity-mark" aria-hidden="true"></span><span>{activity_added_label}</span><time>{date.today().strftime("%b %d" if language == "en" else "%m/%d")}</time></div><div class="activity-row"><span class="activity-mark" aria-hidden="true"></span><span>{activity_review_label}</span><time>{date.today().strftime("%b %d" if language == "en" else "%m/%d")}</time></div></section><section class="detail-card" id="members"><h2 class="detail-title">{workspace_label}</h2><div class="info-line"><span>{storage_label}</span><strong>{storage_value}</strong></div><div class="info-line"><span>{people_label}</span><strong>12</strong></div><div class="info-line"><span>{status_label}</span><strong>{available_label}</strong></div></section></div>
<footer class="footer"><span>{html.escape(title)} · {workspace_label}</span><span>{folder_label} · {count_value}</span></footer></main></div></body></html>
"""
    markup = make_page(preview_rows)
    basename = plausible_filename("html", extension="html", context=scenario)
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
    basename = plausible_filename("fake_trap")
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
            "env_dev_url_authorized", "env_dev_comment", "env_prod_comment", "title", "rows"},
    "database": {"template", "email_domain", "email_domain_authorized", "vault_domain",
                 "vault_domain_authorized", "rows", "table", "columns", "canary_url"},
    "web": {"scenario", "title", "canary_url"},
    "fake_trap": {"variant"},
    "ransomware_tripwire": {"files"},
    "path_maze": {"depth", "branches", "files"},
    "sparse_decoy": {"size_gib", "files"},
    "nest": {"scenario", "vault_domain", "vault_domain_authorized", "layers", "branches", "decoys",
             "directory_depth", "rows", "format", "varied_formats", "directories", "canary_urls",
             "canary_url", "canary_percent", "password_policy"},
    "directory_maze": {"scenario", "vault_domain", "vault_domain_authorized", "title", "depth", "branches",
                        "files_per_directory", "cross_links", "canary_urls", "canary_url", "format"},
    "encoding_maze": {"scenario", "vault_domain", "vault_domain_authorized", "format", "layers",
                       "candidates", "canary_urls", "canary_url", "codecs"},
    "stream": {"path", "format", "port", "rate_kib", "max_streams"},
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
