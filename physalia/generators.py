"""Generate inert decoy assets. No network access or deployment is performed."""

from __future__ import annotations

import html
import io
import logging
import os
import secrets
import zipfile
import time
from datetime import date, timedelta
from urllib.parse import urlsplit

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
LOGGER = logging.getLogger("physalia")
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
    # Database samples are plain customer tables; canary URLs are not embedded.
    url = ""
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
    scenario_content = {
        "operations": {
            "nav": ("サービス状況", "Service health"), "nav_icon": "◉",
            "panel_title": ("サービス運用状況", "Service operations"),
            "panel_copy": ("各サービスの稼働状況と次回メンテナンス", "Current service health and the next maintenance window"),
            "items": [("顧客API", "Customer API", "正常", "Operational"),
                      ("請求処理", "Billing jobs", "正常", "Operational"),
                      ("夜間エクスポート", "Nightly export", "確認予定", "Review scheduled")],
            "action": ("運用手順書を開く", "Open operations runbook"),
            "labels": {"workspace": ("サービス運用", "Service operations"), "folder": ("サービス記録", "Service records"),
                       "storage": ("運用環境", "Environment"), "storage_value": ("検証ワークスペース", "Review workspace"),
                       "people": ("担当チーム", "Owners"), "count": ("登録項目", "Items tracked"),
                       "ready": ("稼働中", "Operational"), "updated": ("最終確認", "Last check"),
                       "activity_added": ("運用項目を更新", "Operations item updated"), "activity_review": ("サービス確認を完了", "Service review completed")},
            "color": "#176b68", "soft": "#e9f5f3", "canvas": "#f2f8f7",
        },
        "shared": {
            "nav": ("メンバー", "Members"), "nav_icon": "♙",
            "panel_title": ("最近の共同作業", "Recent collaboration"),
            "panel_copy": ("共有フォルダーの担当とアクセス範囲", "Owners and access scope for shared folders"),
            "items": [("プロジェクト · 編集者", "Project files · Editor", "編集可能", "Can edit"),
                      ("部門資料 · 閲覧者", "Department files · Viewer", "閲覧のみ", "View only"),
                      ("共有領域 · オーナー", "Shared workspace · Owner", "管理可能", "Can manage")],
            "action": ("共有設定の記録", "Review sharing settings"),
            "labels": {"workspace": ("共有ワークスペース", "Shared workspace"), "folder": ("共有ファイル", "Shared files"),
                       "storage": ("共有領域", "Workspace"), "storage_value": ("部門ドキュメント", "Department documents"),
                       "people": ("メンバー", "Members"), "count": ("共有ファイル", "Shared files"),
                       "ready": ("利用可能", "Available"), "updated": ("最終更新", "Last activity"),
                       "activity_added": ("共有ファイルを追加", "File shared with workspace"), "activity_review": ("アクセス範囲を確認", "Access scope reviewed")},
            "color": "#4c58a6", "soft": "#eef0fb", "canvas": "#f5f6fc",
        },
        "archive": {
            "nav": ("保管期限", "Retention"), "nav_icon": "▣",
            "panel_title": ("保管ポリシー", "Retention policy"),
            "panel_copy": ("アーカイブ区分ごとの確認サイクル", "Review cycle by archive collection"),
            "items": [("契約・調達", "Contracts & procurement", "7年保管", "7-year retention"),
                      ("サービス運用", "Service operations", "年次確認", "Annual review"),
                      ("旧システム", "Legacy systems", "移行済み", "Migration complete")],
            "action": ("保管期限一覧を確認", "Review retention schedule"),
            "labels": {"workspace": ("業務アーカイブ", "Business archive"), "folder": ("保管コレクション", "Archive collections"),
                       "storage": ("保管区分", "Collection"), "storage_value": ("部門記録", "Department records"),
                       "people": ("管理担当", "Stewards"), "count": ("保管文書", "Documents archived"),
                       "ready": ("保管対象", "In retention scope"), "updated": ("最終収録", "Last archived"),
                       "activity_added": ("記録をアーカイブへ追加", "Record added to archive"), "activity_review": ("保管期限を確認", "Retention review completed")},
            "color": "#8a5a2f", "soft": "#f7efe6", "canvas": "#faf7f2",
        },
        "records": {
            "nav": ("確認キュー", "Review queue"), "nav_icon": "☷",
            "panel_title": ("確認待ちの記録", "Records awaiting review"),
            "panel_copy": ("監査証跡と承認状況の未処理項目", "Open items in the audit and approval trail"),
            "items": [("変更申請 CR-2841", "Change request CR-2841", "承認待ち", "Pending approval"),
                      ("アクセス審査 AR-1908", "Access review AR-1908", "担当確認", "Owner review"),
                      ("移行記録 MR-0732", "Migration record MR-0732", "照合済み", "Reconciled")],
            "action": ("承認履歴を確認", "Review approval history"),
            "labels": {"workspace": ("記録センター", "Records center"), "folder": ("監査・承認記録", "Audit and approval records"),
                       "storage": ("記録区分", "Record class"), "storage_value": ("変更・アクセス審査", "Change and access reviews"),
                       "people": ("確認担当", "Reviewers"), "count": ("管理記録", "Records indexed"),
                       "ready": ("確認可能", "Ready for review"), "updated": ("最終審査", "Last reviewed"),
                       "activity_added": ("記録を登録", "Record indexed"), "activity_review": ("承認履歴を照合", "Approval history reconciled")},
            "color": "#8b4054", "soft": "#f8edf0", "canvas": "#faf5f6",
        },
    }[scenario]
    labels = scenario_content["labels"]
    sidebar_href = html.escape(url, quote=True) if url else "#members"
    purpose_action_href = html.escape(url, quote=True) if url else "#files"
    sidebar_target_label = localized(scenario_content["nav"])
    context_rows = "".join(
        f'<div class="context-row"><span class="context-mark" aria-hidden="true"></span>'
        f'<span class="context-name">{html.escape(localized((ja_name, en_name)))}</span>'
        f'<span class="context-state">{html.escape(localized((ja_state, en_state)))}</span></div>'
        for ja_name, en_name, ja_state, en_state in scenario_content["items"]
    )
    action_rel = ' rel="noreferrer"' if url else ""
    context_panel = (
        f'<section class="purpose-card" aria-labelledby="purpose-heading">'
        f'<div class="purpose-heading"><div><p class="purpose-kicker">{html.escape(localized(profile_section))}</p>'
        f'<h2 id="purpose-heading">{html.escape(localized(scenario_content["panel_title"]))}</h2>'
        f'<p>{html.escape(localized(scenario_content["panel_copy"]))}</p></div>'
        f'<a class="purpose-action" href="{purpose_action_href}"{action_rel}>'
        f'{html.escape(localized(scenario_content["action"]))}</a></div>'
        f'<div class="context-list">{context_rows}</div></section>'
    )
    theme_style = (f' style="--accent:{scenario_content["color"]};'
                   f'--accent-soft:{scenario_content["soft"]};--canvas:{scenario_content["canvas"]}"')
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
    count_label = localized(labels["count"])
    type_label = "種類" if language == "ja" else "Type"
    workspace_label = localized(labels["workspace"])
    folder_label = localized(labels["folder"])
    overview_label = "概要" if language == "ja" else "Overview"
    files_label = "ファイル" if language == "ja" else "Files"
    activity_label = "アクティビティ" if language == "ja" else "Activity"
    people_label = localized(labels["people"])
    available_label = "利用可能" if language == "ja" else "Available"
    ready_label = localized(labels["ready"])
    activity_added_label = localized(labels["activity_added"])
    activity_review_label = localized(labels["activity_review"])
    storage_label = localized(labels["storage"])
    storage_value = localized(labels["storage_value"])
    filter_label = folder_label
    modified_label = localized(labels["updated"])
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
.portal-archive{{font-family:Georgia,"Yu Mincho",serif}}
.purpose-card{{margin:0 0 1.1rem;padding:1.1rem 1.25rem;border:1px solid var(--line);border-top:3px solid var(--accent);border-radius:10px;background:var(--surface);box-shadow:var(--shadow)}}
.purpose-heading{{display:flex;align-items:center;justify-content:space-between;gap:1.2rem}}
.purpose-kicker{{margin:0 0 .25rem;color:var(--accent);font-size:.66rem;font-weight:720;letter-spacing:.09em;text-transform:uppercase}}
.purpose-heading h2{{margin:0;font-size:1rem;font-weight:660}}
.purpose-heading p:not(.purpose-kicker){{margin:.25rem 0 0;color:var(--muted);font-size:.76rem}}
.purpose-action{{flex:0 0 auto;padding:.55rem .75rem;border:1px solid var(--accent);border-radius:7px;color:var(--accent);font-size:.73rem;font-weight:620}}
.purpose-action:hover{{background:var(--accent-soft)}}
.context-list{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.6rem;margin-top:.9rem}}
.context-row{{display:flex;align-items:center;gap:.55rem;min-width:0;padding:.62rem .7rem;border:1px solid var(--line);border-radius:7px;background:var(--canvas);font-size:.72rem}}
.context-mark{{width:7px;height:7px;flex:0 0 auto;border-radius:50%;background:var(--accent)}}
.context-name{{overflow:hidden;color:#435365;text-overflow:ellipsis;white-space:nowrap}}
.context-state{{margin-left:auto;color:var(--accent);font-size:.65rem;white-space:nowrap}}
.portal-shared .context-mark{{width:25px;height:25px;border-radius:50%;background:var(--accent-soft);color:var(--accent)}}
.portal-shared .context-mark::after{{display:block;content:"•";text-align:center;line-height:25px}}
.portal-archive .purpose-card{{border-top:0;border-left:4px solid var(--accent);border-radius:3px 10px 10px 3px}}
.portal-archive .context-row{{border-style:dashed;background:#fffdf9}}
.portal-records .context-row{{border-left:3px solid var(--accent);border-radius:4px}}
@media(max-width:640px){{.purpose-heading{{align-items:flex-start;flex-direction:column}}.context-list{{grid-template-columns:1fr}}.purpose-action{{align-self:flex-start}}}}
@media(max-width:920px){{.topbar{{padding:0 1.3rem}}.brand{{min-width:auto}}.topnav{{gap:1rem}}.app-layout{{grid-template-columns:190px minmax(0,1fr)}}.sidebar{{padding-inline:.7rem}}.main{{padding-inline:1.3rem}}.heading-row{{align-items:flex-start;flex-direction:column}}.heading-actions{{align-self:flex-end}}}}
@media(max-width:640px){{.topbar{{height:58px;gap:1rem;padding:0 1rem}}.topnav{{display:none}}.top-right{{gap:.6rem}}.workspace-status{{display:none}}.app-layout{{display:block;min-height:calc(100vh - 58px)}}.sidebar{{display:none}}.main{{padding:1.2rem .85rem 2rem}}.breadcrumbs{{margin-bottom:1.1rem}}.heading-row{{gap:1rem;margin-bottom:1.2rem}}.heading-actions{{width:100%;justify-content:space-between}}.metrics{{gap:.55rem}}.metric{{align-items:flex-start;flex-direction:column;gap:.45rem;padding:.75rem}}.metric-icon{{width:30px;height:30px}}.metric strong{{font-size:1rem}}.panel-head{{align-items:flex-start;flex-direction:column;padding:.9rem}}.panel-tools{{width:100%}}th,td{{padding:.7rem .8rem}}.table-scroll-hint{{display:block}}.file-cell{{min-width:205px}}.file-link{{max-width:240px}}.detail-grid{{grid-template-columns:1fr}}.footer{{flex-direction:column}}}}
@media(prefers-reduced-motion:reduce){{*,*::before,*::after{{scroll-behavior:auto!important;transition:none!important}}}}
 </style>
</head><body class="portal-{scenario}"{theme_style}>
<header class="topbar"><a class="brand" href="#overview"><span class="brand-mark" aria-hidden="true">{html.escape(title[:1].upper())}</span><span>{html.escape(title)}</span></a>
<nav class="topnav" aria-label="{localized(("ワークスペース", "Workspace"))}"><a href="#overview">{overview_label}</a><a class="active" href="#files">{files_label}</a><a href="#activity">{activity_label}</a></nav>
<div class="top-right"><span class="workspace-status">{workspace_label}</span><span class="avatar" aria-label="{people_label}">OP</span></div></header>
<div class="app-layout"><aside class="sidebar" aria-label="{localized(("ナビゲーション", "Navigation"))}">
<div class="workspace-switch"><span class="workspace-symbol" aria-hidden="true">{scenario_content["nav_icon"]}</span><span><span class="workspace-name">{html.escape(title)}</span><span class="workspace-subtitle">{workspace_label}</span></span></div>
<p class="side-label">{localized(("ワークスペース", "Workspace"))}</p><nav class="side-nav"><a href="#overview"><span class="nav-icon" aria-hidden="true">⌂</span>{overview_label}</a><a class="active" href="#files"><span class="nav-icon" aria-hidden="true">▤</span>{files_label}<span class="nav-count">{count_value}</span></a><a href="#activity"><span class="nav-icon" aria-hidden="true">◷</span>{activity_label}</a><a href="{sidebar_href}"{action_rel}><span class="nav-icon" aria-hidden="true">{scenario_content["nav_icon"]}</span>{sidebar_target_label}</a></nav>
<div class="sidebar-note"><strong>{storage_label}</strong>{storage_value}</div></aside>
<main class="main" id="overview"><div class="breadcrumbs"><span>{localized(("ワークスペース", "Workspace"))}</span><span class="separator">/</span><strong>{folder_label}</strong></div>
<div class="heading-row"><div><span class="eyebrow">{html.escape(title)}</span><h1>{heading}</h1><p class="intro">{section}</p></div><div class="heading-actions"><span class="sync-state"><span class="sync-dot" aria-hidden="true"></span>{available_label}</span><span class="updated-pill">{modified_label}: {date.today().strftime("%Y/%m/%d" if language == "ja" else "%b %d, %Y")}</span></div></div>
<div class="metrics" aria-label="{workspace_label}"><div class="metric"><span class="metric-icon" aria-hidden="true">▤</span><span><small>{count_label}</small><strong>{count_value}</strong></span></div><div class="metric"><span class="metric-icon" aria-hidden="true">✓</span><span><small>{ready_label}</small><strong>{available_count} / 6</strong></span></div><div class="metric"><span class="metric-icon" aria-hidden="true">◷</span><span><small>{modified_label}</small><strong>{date.today().strftime("%Y/%m/%d" if language == "ja" else "%b %d")}</strong></span></div></div>
{context_panel}
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
    if url:
        summary.setdefault("canary_locations", []).extend([
            {"artifact": artifact_name, "element": "purpose_sidebar_link", "label": sidebar_target_label},
            {"artifact": package_name + "!/index.html", "element": "purpose_sidebar_link", "label": sidebar_target_label},
            {"artifact": artifact_name, "element": "purpose_panel_action", "label": localized(scenario_content["action"])},
            {"artifact": package_name + "!/index.html", "element": "purpose_panel_action", "label": localized(scenario_content["action"])},
        ])
    deployment = Artifact(package_name, "application/zip", package.getvalue(), role="deployment")
    return Artifact(artifact_name, "text/html; charset=utf-8", markup.encode("utf-8"),
                    [deployment], summary)


def _generate_polished_fake_trap(settings: dict, language: str = "ja") -> Artifact:
    """Build a convincing but entirely static access review portal."""
    variant = settings.get("variant", "warning")
    if variant not in ("warning", "reported", "waiting", "maintenance", "device_review", "access_request", "sync_status", "policy_update"):
        raise ValueError("Invalid fake trap variant")
    lang = language if language in ("ja", "en") else "ja"
    ja = lang == "ja"
    copy = {
        "brand": "社内ポータル" if ja else "Internal workspace", "product": "アカウント管理" if ja else "Account management",
        "crumb": "セキュリティ" if ja else "Security",
        "titles": {"warning": "追加の確認が必要です" if ja else "Additional verification required",
                   "reported": "確認リクエストを受け付けました" if ja else "Review request received",
                   "waiting": "セッションを確認しています" if ja else "Reviewing your session",
                   "maintenance": "サービスのメンテナンス中です" if ja else "Scheduled service maintenance",
                   "device_review": "新しいデバイスを確認してください" if ja else "Review your new device",
                   "access_request": "アクセス申請を確認しています" if ja else "Access request under review",
                   "sync_status": "アカウント情報を同期しています" if ja else "Account sync in progress",
                   "policy_update": "セキュリティ設定が更新されました" if ja else "Security settings updated"},
        "messages": {"warning": "通常と異なるサインインが検出されたため、このセッションを一時的に保留しています。" if ja else "We detected a sign-in that differs from your usual activity. This session is temporarily on hold.",
                     "reported": "リクエストは確認キューに追加されました。確認が完了するまで、この画面を閉じずにお待ちください。" if ja else "Your request has been added to the review queue. Keep this page open until the review is complete.",
                     "waiting": "セキュリティ情報を確認しています。通常、この処理には数秒かかります。" if ja else "We are checking your security information. This usually takes a few seconds.",
                     "maintenance": "一部のアカウント機能を一時的に利用できません。しばらくしてから、もう一度ご確認ください。" if ja else "Some account features are temporarily unavailable. Please check again shortly.",
                     "device_review": "このデバイスのサインイン情報がアカウントに反映されるまで、確認処理に数分かかる場合があります。" if ja else "It may take a few minutes for this device's sign-in details to appear in your account.",
                     "access_request": "アクセス権限のリクエストを担当チームが確認しています。更新があるまで、このページを開いたままにしてください。" if ja else "The responsible team is reviewing this access request. Keep this page open for updates.",
                     "sync_status": "最近のアカウント情報を読み込んでいます。同期が完了するまでこの画面を表示してください。" if ja else "Recent account information is being loaded. Keep this page open while sync completes.",
                     "policy_update": "組織のセキュリティ ポリシーに基づき、アカウント設定を再確認してください。" if ja else "Review your account settings in line with your organization's security policy."},
        "status": {"warning": "確認が必要" if ja else "Action required", "reported": "確認中" if ja else "In review", "waiting": "処理中" if ja else "Processing",
                   "maintenance": "メンテナンス" if ja else "Maintenance", "device_review": "デバイス確認" if ja else "Device review",
                   "access_request": "申請確認中" if ja else "Request review", "sync_status": "同期中" if ja else "Syncing",
                   "policy_update": "設定の確認" if ja else "Review settings"},
        "activity": "サインインの詳細" if ja else "Sign-in details", "when": "日時" if ja else "Date and time",
        "location": "おおよその場所" if ja else "Approximate location", "device": "デバイス" if ja else "Device",
        "browser": "ブラウザー" if ja else "Browser", "review": "確認の状況" if ja else "Review progress",
        "help": "この操作に心当たりがない場合は、組織の IT 管理者にお問い合わせください。" if ja else "If you do not recognize this activity, contact your organization's IT administrator.",
    }
    title, message = copy["titles"][variant], copy["messages"][variant]
    now = date.today().strftime("%Y年%m月%d日" if ja else "%b %d, %Y")
    ref = "IR-" + secrets.token_hex(5).upper()
    embed_canary = settings.get("embed_canary", bool(settings.get("canary_url")))
    url = _canary_url(settings.get("canary_url", ""), lang) if embed_canary else ""
    if embed_canary and not url:
        raise ValueError(translate("invalid_url", lang))
    canary_beacon = (f'<img class="contact-marker" src="{html.escape(url, quote=True)}" '
                     'width="1" height="1" alt="" aria-hidden="true" referrerpolicy="no-referrer">') if url else ""
    canary_security_meta = STATIC_HTML_SECURITY_META
    if url:
        parsed_canary = urlsplit(url)
        canary_origin = f"{parsed_canary.scheme}://{parsed_canary.netloc}"
        canary_security_meta = canary_security_meta.replace(
            "default-src 'none';",
            f"default-src 'none'; img-src {html.escape(canary_origin, quote=True)};",
        )
    icon = '<span class="spin"></span>' if variant in ("waiting", "maintenance", "device_review", "access_request", "sync_status") else '<span class="check">✓</span>'
    e = html.escape
    eyebrow = "サインインの確認" if ja else "SIGN-IN REVIEW"
    if variant == "maintenance":
        eyebrow = "サービス状況" if ja else "SERVICE STATUS"
        copy["activity"] = "サービス情報" if ja else "Service details"
        details = [("対象" if ja else "Service", "アカウント ワークスペース" if ja else "Account workspace"),
                   ("状態" if ja else "Status", "メンテナンス中" if ja else "Maintenance"),
                   ("開始日" if ja else "Started", now), ("影響" if ja else "Impact", "一部機能" if ja else "Some features")]
    elif variant == "device_review":
        eyebrow = "デバイスの確認" if ja else "DEVICE REVIEW"
        copy["activity"] = "デバイスの詳細" if ja else "Device details"
        details = [("デバイス" if ja else "Device", "Windows デバイス" if ja else "Windows device"),
                   ("ブラウザー" if ja else "Browser", "デスクトップ ブラウザー" if ja else "Desktop browser"),
                   ("おおよその場所" if ja else "Approximate location", "東京都" if ja else "Tokyo, Japan"),
                   ("最初のサインイン" if ja else "First sign-in", now)]
    elif variant == "access_request":
        eyebrow = "アクセス管理" if ja else "ACCESS MANAGEMENT"
        copy["activity"] = "申請の詳細" if ja else "Request details"
        details = [("対象" if ja else "Resource", "Workspace ドキュメント" if ja else "Workspace documents"),
                   ("アクセス レベル" if ja else "Access level", "閲覧" if ja else "Read only"),
                   ("申請日" if ja else "Requested", now), ("状態" if ja else "Status", "確認中" if ja else "Under review")]
    elif variant == "sync_status":
        eyebrow = "アカウント同期" if ja else "ACCOUNT SYNC"
        copy["activity"] = "同期の詳細" if ja else "Sync details"
        details = [("アカウント" if ja else "Account", "Workspace プロファイル" if ja else "Workspace profile"),
                   ("最終同期" if ja else "Last sync", now), ("同期対象" if ja else "Items", "プロファイル情報" if ja else "Profile information"),
                   ("状態" if ja else "Status", "処理中" if ja else "In progress")]
    elif variant == "policy_update":
        eyebrow = "セキュリティ設定" if ja else "SECURITY SETTINGS"
        copy["activity"] = "更新の詳細" if ja else "Update details"
        details = [("設定" if ja else "Setting", "サインイン ポリシー" if ja else "Sign-in policy"),
                   ("適用範囲" if ja else "Scope", "組織アカウント" if ja else "Organization accounts"),
                   ("更新日" if ja else "Updated", now), ("確認" if ja else "Review", "設定を確認してください" if ja else "Review your settings")]
    else:
        details = [(copy["when"], now), (copy["location"], "東京都" if ja else "Tokyo, Japan"),
                   (copy["device"], "Windows デバイス" if ja else "Windows device"),
                   (copy["browser"], "デスクトップ ブラウザー" if ja else "Desktop browser")]
    details_html = "".join(f"<div><dt>{e(label)}</dt><dd>{e(value)}</dd></div>" for label, value in details)
    panel_content = {
        "warning": (("確認の状況" if ja else "Review progress"), [("完了" if ja else "Complete", "サインイン情報" if ja else "Sign-in details", True), ("処理中" if ja else "In progress", "追加確認" if ja else "Additional review", False), ("次の手順" if ja else "Next", "確認を完了" if ja else "Complete review", False)]),
        "reported": (("受付状況" if ja else "Request status"), [("受付済み" if ja else "Received", "リクエスト" if ja else "Request", True), ("確認中" if ja else "In review", "担当チーム" if ja else "Review team", False), ("次の更新" if ja else "Next update", "確認後に表示" if ja else "After review", False)]),
        "waiting": (("処理の状況" if ja else "Process status"), [("完了" if ja else "Complete", "セッション情報" if ja else "Session details", True), ("確認中" if ja else "Checking", "セキュリティ情報" if ja else "Security details", False), ("保留" if ja else "Pending", "結果の反映" if ja else "Apply result", False)]),
        "maintenance": (("メンテナンス情報" if ja else "Maintenance information"), [("対象" if ja else "Affected", "一部機能" if ja else "Some features", True), ("現在の状態" if ja else "Current status", "作業中" if ja else "In progress", False), ("次回確認" if ja else "Next check", "時間をおいて再確認" if ja else "Check again later", False)]),
        "device_review": (("デバイス確認" if ja else "Device review"), [("登録情報" if ja else "Device details", "受信済み" if ja else "Received", True), ("ポリシー確認" if ja else "Policy check", "確認中" if ja else "In review", False), ("アカウント反映" if ja else "Account update", "保留" if ja else "Pending", False)]),
        "access_request": (("申請の状況" if ja else "Request progress"), [("申請内容" if ja else "Request details", "受付済み" if ja else "Received", True), ("権限確認" if ja else "Access review", "担当チームが確認中" if ja else "With review team", False), ("結果" if ja else "Decision", "確認後に表示" if ja else "After review", False)]),
        "sync_status": (("同期の状況" if ja else "Sync status"), [("対象の確認" if ja else "Scope check", "完了" if ja else "Complete", True), ("プロファイル同期" if ja else "Profile sync", "処理中" if ja else "In progress", False), ("最終確認" if ja else "Final check", "保留" if ja else "Pending", False)]),
        "policy_update": (("設定の更新" if ja else "Settings update"), [("ポリシー確認" if ja else "Policy review", "完了" if ja else "Complete", True), ("設定の適用" if ja else "Apply settings", "確認が必要" if ja else "Review required", False), ("反映状況" if ja else "Update status", "保留" if ja else "Pending", False)]),
    }
    panel_title, panel_steps = panel_content[variant]
    steps_html = "".join(
        f'<li class="step{" done" if complete else ""}"><span class="dot" aria-hidden="true">{"✓" if complete else index}</span><div><strong>{e(label)}</strong><small>{e(value)}</small></div></li>'
        for index, (label, value, complete) in enumerate(panel_steps, 1))
    side_html = f'''<aside class="card side" aria-labelledby="status-heading"><h2 id="status-heading">{panel_title}</h2><ol class="progress-list">{steps_html}</ol><p class="reference">{'参照 ID' if ja else 'Reference ID'} <code>{ref}</code></p></aside>'''
    context_content = {
        "warning": (("関連する確認項目" if ja else "Related checks"), ("項目" if ja else "Check", "状態" if ja else "Status", "更新" if ja else "Updated"), [("サインイン情報" if ja else "Sign-in details", "確認済み" if ja else "Reviewed", now), ("追加認証" if ja else "Additional verification", "対応が必要" if ja else "Action required", now), ("セッション状態" if ja else "Session status", "保留中" if ja else "On hold", now)]),
        "reported": (("受付内容" if ja else "Request summary"), ("項目" if ja else "Item", "内容" if ja else "Details", "状態" if ja else "Status"), [("受付番号" if ja else "Reference", ref, "受付済み" if ja else "Received"), ("申請区分" if ja else "Request type", "アカウント確認" if ja else "Account review", "確認中" if ja else "In review"), ("担当窓口" if ja else "Review queue", "情報システム" if ja else "IT operations", "割当済み" if ja else "Assigned")]),
        "waiting": (("処理の内訳" if ja else "Processing details"), ("処理" if ja else "Process", "結果" if ja else "Result", "所要時間" if ja else "Duration"), [("端末情報の照合" if ja else "Device check", "完了" if ja else "Complete", "1秒未満" if ja else "Under 1 sec"), ("ポリシー確認" if ja else "Policy review", "処理中" if ja else "In progress", "—"), ("セッション更新" if ja else "Session update", "待機中" if ja else "Queued", "—")]),
        "maintenance": (("機能別の状況" if ja else "Service availability"), ("機能" if ja else "Service", "状態" if ja else "Status", "影響" if ja else "Impact"), [("プロフィール" if ja else "Profile", "一時停止" if ja else "Paused", "変更" if ja else "Updates"), ("監査ログ" if ja else "Audit log", "利用可能" if ja else "Available", "なし" if ja else "None"), ("アカウント設定" if ja else "Account settings", "遅延" if ja else "Delayed", "反映" if ja else "Changes")]),
        "device_review": (("デバイス一覧" if ja else "Registered devices"), ("デバイス" if ja else "Device", "最終利用" if ja else "Last active", "状態" if ja else "Status"), [("Windows デスクトップ" if ja else "Windows desktop", now, "確認中" if ja else "Reviewing"), ("モバイル端末" if ja else "Mobile device", "前回の利用" if ja else "Previous session", "登録済み" if ja else "Registered"), ("ブラウザー セッション" if ja else "Browser session", "現在" if ja else "Current", "保留中" if ja else "Pending")]),
        "access_request": (("アクセス申請の内訳" if ja else "Access request details"), ("リソース" if ja else "Resource", "権限" if ja else "Permission", "状態" if ja else "Status"), [("共有ドキュメント" if ja else "Shared documents", "閲覧" if ja else "Read", "申請済み" if ja else "Requested"), ("運用レポート" if ja else "Operations reports", "閲覧" if ja else "Read", "対象外" if ja else "Not requested"), ("アカウント設定" if ja else "Account settings", "変更" if ja else "Manage", "許可なし" if ja else "Not granted")]),
        "sync_status": (("同期対象" if ja else "Sync scope"), ("データ" if ja else "Data", "状態" if ja else "Status", "最終更新" if ja else "Last update"), [("プロフィール" if ja else "Profile", "同期済み" if ja else "Synced", now), ("通知設定" if ja else "Preferences", "処理中" if ja else "Processing", now), ("デバイス一覧" if ja else "Devices", "待機中" if ja else "Queued", "—")]),
        "policy_update": (("変更された設定" if ja else "Changed settings"), ("設定" if ja else "Setting", "適用値" if ja else "Value", "状態" if ja else "Status"), [("多要素認証" if ja else "Multi-factor authentication", "必須" if ja else "Required", "確認が必要" if ja else "Review required"), ("セッション有効期間" if ja else "Session duration", "標準" if ja else "Standard", "適用済み" if ja else "Applied"), ("信頼済みデバイス" if ja else "Trusted devices", "再確認" if ja else "Recheck", "保留中" if ja else "Pending")]),
    }
    context_title, context_columns, context_rows = context_content[variant]
    table_head = "".join(f'<th scope="col">{e(column)}</th>' for column in context_columns)
    table_rows = "".join("<tr>" + "".join(f"<td>{e(value)}</td>" for value in row) + "</tr>" for row in context_rows)
    context_section = f'''<section class="card section records" id="related" aria-labelledby="related-heading"><h2 id="related-heading">{context_title}</h2><div class="table-scroll"><table><thead><tr>{table_head}</tr></thead><tbody>{table_rows}</tbody></table></div><p class="table-note">{'表示内容は現在の状態に基づくサマリーです。反映に時間がかかる場合があります。' if ja else 'This summary reflects the current status. Updates may take additional time to appear.'}</p></section>'''
    markup = f'''<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
{canary_security_meta}<meta name="application-name" content="{e(copy['brand'])}"><meta name="theme-color" content="#f3f6fa"><meta name="description" content="{e(message)}"><title>{e(title)} | {e(copy['brand'])}</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f3f6fa;color:#172b4d;font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}.skip-link{{position:absolute;left:-10000px;top:auto}}.skip-link:focus{{left:12px;top:12px;z-index:10;background:#fff;padding:8px 12px}}
header{{height:66px;background:#fff;border-bottom:1px solid #dfe4ec;display:flex;align-items:center;padding:0 max(24px,calc((100vw - 1060px)/2));gap:12px}}
.logo{{display:grid;place-items:center;width:34px;height:34px;border-radius:8px;background:#173e68;color:white;font-weight:700;font-size:19px}}header strong{{font-size:17px}}header small{{color:#5e6c84}}
main{{max-width:920px;margin:30px auto;padding:0 20px}}nav{{color:#5e6c84;font-size:13px;margin:0 0 22px}}nav span{{padding:0 9px;color:#9aa5b5}}.layout{{display:grid;grid-template-columns:1.6fr 1fr;gap:18px;align-items:start}}
.card{{background:white;border:1px solid #dfe4ec;border-radius:9px;box-shadow:0 2px 5px #172b4d08}}.hero{{padding:26px 29px;border-top:3px solid #d49b22}}.eyebrow{{font-size:11px;color:#5e6c84;font-weight:700;letter-spacing:.08em}}
h1{{font-size:25px;line-height:1.35;margin:8px 0}}p{{color:#44546a}}.pill{{display:inline-flex;align-items:center;gap:8px;background:#fff7e0;color:#815b00;border-radius:18px;padding:5px 10px;font-size:12px;font-weight:650;margin-top:8px}}
.check{{color:#18865b;background:#e9f5ef;border-radius:50%;width:20px;height:20px;text-align:center}}.spin{{width:16px;height:16px;border:2px solid #eadba9;border-top-color:#976d00;border-radius:50%;animation:rotate .9s linear infinite}}@keyframes rotate{{to{{transform:rotate(360deg)}}}}
.section,.side{{padding:21px 23px;margin-top:14px}}h2{{font-size:15px;margin:0 0 15px}}.details{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}dt{{color:#5e6c84;font-size:12px}}dd{{margin:2px 0 0;font-size:13px;font-weight:550}}
.workspace-nav{{display:flex;gap:22px;overflow-x:auto;border-bottom:1px solid #dfe4ec;margin:0 0 8px;padding:0 2px}}.workspace-nav a{{padding:10px 2px;color:#344563;text-decoration:none;white-space:nowrap;font-size:13px}}.workspace-nav a:focus,.workspace-nav a:hover{{color:#1769aa;text-decoration:underline}}.records{{overflow:hidden}}.table-scroll{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;text-align:left;font-size:12px}}th{{color:#5e6c84;font-weight:600;background:#f7f8fa}}th,td{{padding:10px 12px;border-bottom:1px solid #e8ebf0;white-space:nowrap}}tbody tr:last-child td{{border-bottom:0}}.table-note{{margin:13px 0 0;font-size:12px;color:#6b778c}}
.progress-list{{list-style:none;margin:0;padding:0}}.step{{display:flex;gap:11px;position:relative;padding-bottom:19px}}.step:not(:last-child):before{{content:"";position:absolute;left:10px;top:22px;bottom:0;width:1px;background:#dfe4ec}}.dot{{z-index:1;display:grid;place-items:center;flex:none;width:21px;height:21px;border:1px solid #cbd3df;border-radius:50%;background:white;font-size:11px}}.done .dot{{background:#e9f5ef;color:#18865b}}.step strong{{font-size:12px}}.step small{{display:block;color:#5e6c84;font-size:11px}}.reference{{font-size:12px;border-top:1px solid #dfe4ec;padding-top:12px}}.reference code{{display:inline;border:0;padding:0;color:#344563;font-size:12px}}.action{{display:inline-block;margin-top:18px;background:#1769aa;color:#fff;text-decoration:none;border-radius:5px;padding:9px 15px;font-size:13px;font-weight:600}}.action:hover{{background:#12598f}}.help{{color:#6b778c;font-size:12px}}@media(max-width:680px){{.layout{{grid-template-columns:1fr}}main{{margin:20px auto;padding:0 14px}}.hero{{padding:22px}}h1{{font-size:22px}}}}@media(prefers-reduced-motion:reduce){{.spin{{animation:none}}}}
</style></head><body><header><strong>{copy['brand']}</strong><small>{copy['product']}</small></header><main><nav aria-label="{'パンくずリスト' if ja else 'Breadcrumb'}">{copy['brand']}<span aria-hidden="true">›</span>{copy['product']}<span aria-hidden="true">›</span>{copy['crumb']}</nav><nav class="workspace-nav" aria-label="{'関連セクション' if ja else 'Related sections'}"><a href="#main-content">{'概要' if ja else 'Overview'}</a><a href="#activity-panel">{copy['activity']}</a><a href="#related">{context_title}</a><a href="#status-heading">{panel_title}</a></nav><div class="layout"><div>
<a class="skip-link" href="#main-content">{'本文へ移動' if ja else 'Skip to content'}</a><section class="card hero" id="main-content" aria-labelledby="page-title"><div class="eyebrow">{eyebrow}</div><h1 id="page-title">{e(title)}</h1><p>{e(message)}</p><span class="pill" role="status">{icon}{e(copy['status'][variant])}</span></section>
<section class="card section" id="activity-panel" aria-labelledby="activity-heading"><h2 id="activity-heading">{copy['activity']}</h2><dl class="details">{details_html}</dl></section>{context_section}<p class="help">{copy['help']}</p></div>
{side_html}</div>{canary_beacon}</main></body></html>'''
    basename = plausible_filename("fake_trap") + ".html"
    summary = {"kind": "fake_trap"}
    if url:
        summary["canary_locations"] = [{"artifact": basename, "element": "img", "label": "page_open_contact"}]
    return Artifact(basename, "text/html; charset=utf-8", markup.encode("utf-8"), summary=summary)


generate_fake_trap = _generate_polished_fake_trap


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
    "database": {"template", "rows", "table", "columns"},
    "web": {"scenario", "canary_url"},
    "fake_trap": {"variant", "embed_canary", "canary_url"},
    "ransomware_tripwire": {"files"},
    "path_maze": {"os_type", "depth", "branches", "files"},
    "sparse_decoy": {"size_gib", "extension"},
    "nest": {"scenario", "layers", "branches", "decoys",
             "directory_depth", "rows", "directories", "password_policy"},
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
    if kind == "fake_trap":
        # The fake-trap panel has evolved independently from older cached UI
        # clients. Ignore stale fields from that panel (for example, a prior
        # canary toggle flag) while retaining every setting this generator uses.
        settings = {key: value for key, value in settings.items()
                    if key in SETTING_KEYS[kind]}
    if any(not isinstance(key, str) for key in settings) or settings.keys() - SETTING_KEYS[kind]:
        LOGGER.warning("generator_rejected kind=%s reason=unknown_setting_keys", kind)
        raise ValueError(translate("unknown_settings", language))
    if kind == "fake_trap":
        embed_canary = settings.get("embed_canary", bool(settings.get("canary_url")))
        if not isinstance(embed_canary, bool):
            raise ValueError(translate("invalid_input", language))
        if not embed_canary and "canary_url" in settings:
            settings = {key: value for key, value in settings.items() if key != "canary_url"}
    LOGGER.debug("generator_validation_started kind=%s setting_keys=%s",
                 kind, ",".join(sorted(settings)))
    validation_started = time.monotonic()
    reject_unsafe_text_tree(settings, language)
    LOGGER.debug("generator_text_validation_complete kind=%s elapsed_ms=%d",
                 kind, max(0, round((time.monotonic() - validation_started) * 1000)))
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
    generation_started = time.monotonic()
    LOGGER.debug("generator_function_started kind=%s language=%s", kind, language)
    try:
        result = GENERATORS[kind](settings, language)
    except Exception as exc:
        LOGGER.error("generator_function_failed kind=%s error_type=%s", kind, type(exc).__name__)
        LOGGER.debug("generator_function_traceback kind=%s", kind, exc_info=True)
        raise
    asset = result if isinstance(result, Artifact) else Artifact(*result)
    # The top-level artifact is the deployable decoy. Companion artifacts keep
    # their own roles (operator-only by default, or deployment when applicable).
    asset.role = "deployment"
    inventory_started = time.monotonic()
    asset = attach_inventory(asset, kind, settings, language)
    LOGGER.debug("generator_complete kind=%s name=%s mime=%s in_memory_bytes=%d companions=%d elapsed_ms=%d inventory_ms=%d",
                 kind, asset.name, asset.mime, len(asset.content), len(asset.companions),
                 max(0, round((time.monotonic() - generation_started) * 1000)),
                 max(0, round((time.monotonic() - inventory_started) * 1000)))
    return asset
