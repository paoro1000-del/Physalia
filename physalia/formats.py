"""Real document formats with inert content and optional HTTPS hyperlinks."""
import csv
import html
import io
import json
import logging
import re
import secrets
import time
import unicodedata
from urllib.parse import urlsplit

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from pptx import Presentation
from pptx.util import Inches, Pt
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

from physalia.database import (
    DATABASE_TEMPLATES, DEFAULT_COLUMNS, _template_columns_with_labels,
    ensure_canary_endpoint_column, records, sqlite_bytes,
)
from physalia.i18n import translate
from physalia.naming import plausible_filename
from physalia.validation import canary_url, identifier, integer, is_public_host, is_reserved_example_url, text

LOGGER = logging.getLogger("physalia")

FORMATS = {
    "env": ("env", "text/plain; charset=utf-8"), "txt": ("txt", "text/plain; charset=utf-8"),
    "json": ("json", "application/json"), "csv": ("csv", "text/csv; charset=utf-8"),
    "html": ("html", "text/html; charset=utf-8"), "pdf": ("pdf", "application/pdf"),
    "xlsx": ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    "pptx": ("pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
    "sqlite": ("db", "application/vnd.sqlite3"),
}
PREVIEW_ROW_LIMIT = 10

STATIC_HTML_SECURITY_META = """<meta name="referrer" content="no-referrer"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; object-src 'none'; base-uri 'none'; form-action 'none'">"""

ENV_COMMENT_PRESETS = {
    "ja": (
        ("開発環境用URL（ローカルAPI接続）", "本番環境用URL（リリース設定）"),
        ("開発用サービス接続先", "本番サービス接続先（本番スロット）"),
        ("開発環境の接続先", "本番環境の接続先（本番リリース用）"),
        ("現在の開発環境URL", "本番用URL（運用環境）"),
    ),
    "en": (
        ("Development URL (local API)", "Production URL (release configuration)"),
        ("Development service endpoint", "Production service endpoint (production slot)"),
        ("Development environment endpoint", "Production environment endpoint (release)"),
        ("Current development URL", "Production URL (live environment)"),
    ),
}

CONTEXTS = {
    "service": {"field": "service_portal_url", "ja": "サービス管理画面", "en": "Service portal", "table": "service_links",
                "title_ja": "サービス接続台帳", "title_en": "Service connection register"},
    "billing": {"field": "billing_portal_url", "ja": "請求情報の確認", "en": "Billing portal", "table": "billing_links",
                "title_ja": "請求・入金照合", "title_en": "Billing and payment reconciliation"},
    "support": {"field": "support_portal_url", "ja": "サポート窓口", "en": "Support portal", "table": "support_links",
                "title_ja": "サポート対応一覧", "title_en": "Support request register"},
    "reports": {"field": "report_portal_url", "ja": "関連レポート", "en": "Related reports", "table": "report_links",
                "title_ja": "業務レポート", "title_en": "Operations report"},
}
CONTEXT_DATA_TEMPLATES = {
    "service": "cloud",
    "billing": "invoices",
    "support": "tickets",
    "reports": "sales",
}

DOCUMENT_AUTHORS = {
    "ja": ("業務運用チーム", "情報システム部", "顧客管理部", "事業企画室", "データ管理担当"),
    "en": ("Operations Team", "Information Systems", "Customer Operations", "Business Planning", "Data Services"),
}
PDF_PROFILES = (
    ("Microsoft Excel", "Microsoft Excel"),
    ("Microsoft Word", "Microsoft Word"),
    ("LibreOffice Calc", "LibreOffice"),
    ("LibreOffice Writer", "LibreOffice"),
    ("Microsoft Edge", "Skia/PDF"),
)


def document_author(language):
    """Choose a restrained, plausible author label without library fingerprints."""
    return secrets.choice(DOCUMENT_AUTHORS.get(language, DOCUMENT_AUTHORS["ja"]))


def resolve_context(settings, language):
    """Resolve presentation only. Never rewrite the provider-issued URL."""
    mode = settings.get("canary_context", "legacy")
    if not isinstance(mode, str) or mode not in (*CONTEXTS, "auto", "legacy"):
        raise ValueError(translate("invalid_input", language))
    if mode == "legacy":
        return None
    profile_name = secrets.choice(tuple(CONTEXTS)) if mode == "auto" else mode
    profile = CONTEXTS[profile_name]
    field = identifier(settings.get("canary_field") or profile["field"], language)
    context_columns = _template_columns_with_labels(CONTEXT_DATA_TEMPLATES[profile_name], language)
    reserved = ({"app_env", "archive_reference", "title", "reference", "records"}
                | {c["name"].lower() for c in DEFAULT_COLUMNS}
                | {c["name"].lower() for c in context_columns})
    if field.lower() in reserved:
        raise ValueError(translate("canary_field_conflict", language))
    label = text(settings.get("canary_label") or profile[language], "canary_label", 80, language) or profile[language]
    return {"profile": profile_name, "field": field, "label": label, "table": profile["table"]}


def spreadsheet_text(cell, value):
    cell.value = value
    # User-provided titles/values must remain text, including strings starting '='.
    if isinstance(value, str):
        cell.data_type = "s"


def spreadsheet_csv_value(value):
    """Keep custom CSV text inert when opened in spreadsheet applications."""
    if isinstance(value, str):
        # Check compatibility forms too (for example full-width formula
        # prefixes) while preserving the operator's original cell text.
        probe = unicodedata.normalize("NFKC", value).lstrip()
        # Some parsers ignore leading control and formatting characters too.
        while probe and unicodedata.category(probe[0]) in ("Cc", "Cf", "Cs", "Zl", "Zp"):
            probe = probe[1:]
        if probe.startswith(("=", "+", "-", "@")):
            return "'" + value
    return value


def localized_sheet_title(table, language):
    """Return the localized display name for a known synthetic database table."""
    for template in DATABASE_TEMPLATES.values():
        if template["table"].casefold() == str(table).casefold():
            return template.get(language, template["en"])[0]
    return str(table).replace("_", " ").title()


def render_switchable_env(settings, title, url, language, environment=None):
    """A commented production alternative; neither URL is fetched or executed."""
    key = identifier(settings.get("env_variable") or "URL", language)
    if key.upper() == "APP_ENV":
        raise ValueError(translate("canary_field_conflict", language))
    if environment is None:
        environment = settings.get("env_suffix") or "development"
    environment = text(environment, "env_suffix", 32, language)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}", environment):
        raise ValueError(translate("env_suffix_error", language))
    environment_key = environment.casefold()
    endpoint_defaults = {
        "development": "http://dev.example.invalid:8080",
        "staging": "https://staging.example.invalid",
        "test": "http://test.example.invalid:8080",
        "production": "https://api.example.invalid",
    }
    host = re.sub(r"[^a-z0-9-]+", "-", environment_key).strip("-") or "app"
    default_endpoint = endpoint_defaults.get(environment_key, f"http://{host}.example.invalid:8080")
    raw_dev_url = settings.get("env_dev_url", "")
    dev_url = default_endpoint if raw_dev_url == "" else text(raw_dev_url, "dev_url", 2048, language)
    if raw_dev_url != "" and raw_dev_url != dev_url:
        raise ValueError(translate("env_url_error", language))
    try:
        parsed = urlsplit(dev_url)
        host = parsed.hostname.rstrip(".").casefold() if parsed.hostname else ""
        valid = (parsed.scheme in ("http", "https") and host
                 and parsed.username is None and parsed.password is None
                 and is_public_host(parsed.hostname) and "#" not in dev_url and not parsed.netloc.endswith(":")
                 and (parsed.port is None or 1 <= parsed.port <= 65535)
                 and not any(ord(char) <= 32 or ord(char) == 127 or char in '\\"`$' for char in dev_url))
    except ValueError:
        host = ""
        valid = False
    if not valid:
        raise ValueError(translate("env_url_error", language))
    placeholder_host = host.endswith(".invalid")
    if is_reserved_example_url(dev_url) and not placeholder_host:
        raise ValueError(translate("env_url_error", language))
    if not placeholder_host and settings.get("env_dev_url_authorized") is not True:
        raise ValueError(translate("env_dev_url_authorization", language))
    default_dev_comment, default_prod_comment = secrets.choice(ENV_COMMENT_PRESETS.get(language, ENV_COMMENT_PRESETS["ja"]))
    dev_comment = text(settings.get("env_dev_comment") or default_dev_comment, "env_comment", 160, language)
    prod_comment = text(settings.get("env_prod_comment") or default_prod_comment, "env_comment", 160, language)
    token = url or "https://example.invalid/replace-me"
    if any(ord(char) <= 32 or ord(char) == 127 or char in '\\"`$' for char in token):
        raise ValueError(translate("env_token_error", language))
    profiles = {
        "service": ("operations-api", "operations"),
        "billing": ("billing-api", "billing"),
        "support": ("support-api", "support"),
        "reports": ("reporting-api", "reports"),
    }
    service_name, database_name = profiles.get(settings.get("canary_context"), profiles["service"])
    # Nested scenarios provide a purpose-specific environment key instead of
    # a standalone context selection; use that key to keep names coherent.
    key_prefix = re.sub(r"(?:_API)?_URL$", "", key.upper()).strip("_")
    if key_prefix and key.upper() not in ("URL", "SERVICE_URL"):
        service_name = key_prefix.lower().replace("_", "-") + "-service"
        database_name = key_prefix.lower()
    service_name = text(service_name, "title", 80, language)
    database_name = re.sub(r"[^a-z0-9_]+", "_", database_name.lower()).strip("_") or "operations"
    request_comment = "リクエスト処理" if language == "ja" else "Request handling"
    app_settings = (
        f"# {title}\nAPP_ENV={environment}\nAPP_NAME={service_name}\nLOG_LEVEL=info\nPORT=8080\n\n"
        f"# {dev_comment}\n{key}=\"{dev_url}\"\n"
        "DATABASE_HOST=postgres.dev.example.invalid\nDATABASE_PORT=5432\n"
        f"DATABASE_NAME={database_name}_{environment_key}\n"
        "REDIS_HOST=redis.dev.example.invalid\nREDIS_PORT=6379\n\n"
        f"# {request_comment}\nREQUEST_TIMEOUT_SECONDS=15\nMAX_RETRIES=3\n"
    )
    production_settings = (
        f"# {prod_comment}\n# APP_ENV=production\n# {key}=\"{token}\"\n"
        "# DATABASE_HOST=postgres.prod.example.invalid\n"
        f"# DATABASE_NAME={database_name}_production\n"
    )
    return (app_settings + "\n" + production_settings).encode("utf-8")


def dotenv_value(value, language):
    """Quote a supported URL in the constrained single-quoted dotenv form."""
    # Dotenv parsers differ on interpolation; a single-quoted value does not
    # reliably protect `${NAME}` from expansion across implementations.
    if "'" in value or "$" in value or any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(translate("dotenv_quote_error", language))
    return "'" + value + "'"


def render(fmt, title, url, data, language="ja", reference=None, context=None, app_env="production",
           columns=None, table="customers", canary_cell=None, sheet_title=None, canary_link_style="text",
           canary_display_value=None):
    """Render without fetching URLs, macros, scripts, external images or formulas."""
    columns = DEFAULT_COLUMNS if columns is None else columns
    headers = [column["name"] for column in columns]
    display_headers = [column.get("label") or column["name"] for column in columns]
    owned_login_index = next((index for index, column in enumerate(columns)
                              if column["name"].casefold() == "login_url"
                              and column.get("vault_decoy_domain")), None)
    email_columns = {index for index, column in enumerate(columns) if column.get("kind") == "email"}
    ref = reference or secrets.token_hex(6).upper()
    field = context["field"] if context else "archive_endpoint"
    label = context["label"] if context else translate("web_link", language)
    csv_link_label = label if context else ("アーカイブ接続先" if language == "ja" else "Archive endpoint")
    csv_link_header = f"{csv_link_label} ({field})"
    reference_label = "参照番号" if language == "ja" else "Reference"
    if fmt == "env":
        if app_env not in ("production", "staging", "development", "test"):
            raise ValueError(translate("invalid_input", language))
        env_url = dotenv_value(url or "https://example.invalid/replace-me", language)
        env_field = field.upper() if context else "SERVICE_URL"
        content = f"# {title}\nAPP_ENV={app_env}\nARCHIVE_REFERENCE={ref}\n{env_field}={env_url}\n"
        return content.encode("utf-8")
    if fmt == "txt":
        content = (f"{title}\n{reference_label}: {ref}\n\n" + " | ".join(display_headers) + "\n"
                   + "\n".join(" | ".join(map(str, row)) for row in data))
        endpoint_label = label if context else csv_link_label
        return (content + (f"\n\n{endpoint_label}: {url}\n"
                           if url and canary_cell is None else "\n")).encode("utf-8")
    if fmt == "json":
        payload = {"title": title, "reference": ref, "records": [dict(zip(headers, r)) for r in data]}
        if url and canary_cell is None:
            payload[field] = url
        return json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    if fmt == "csv":
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        safe_headers = [spreadsheet_csv_value(value) for value in display_headers]
        writer.writerow(safe_headers + ([spreadsheet_csv_value(csv_link_header)] if url and canary_cell is None else []))
        for index, row in enumerate(data):
            safe_row = [spreadsheet_csv_value(value) for value in row]
            writer.writerow(safe_row + ([url if index == 0 else ""] if url and canary_cell is None else []))
        return stream.getvalue().encode("utf-8-sig")
    if fmt == "sqlite":
        return sqlite_bytes(table, columns, data, url if canary_cell is None else "",
                            connection_table=f'{context["table"]}_connections' if context else None,
                            connection_name=field if context else "archive", language=language)
    if fmt == "html":
        if canary_link_style not in ("text", "button", "image", "email", "next", "pagination", "fullpage"):
            raise ValueError(translate("invalid_input", language))
        fullpage_link = bool(url and canary_cell is None and canary_link_style == "fullpage")
        table_scroll_hint = ("表を左右にスクロールできます。" if language == "ja"
                             else "Scroll the table horizontally to see all columns.")
        def cell_markup(value, row_index, column_index):
            if (url and canary_link_style in ("image", "next")
                    and canary_cell == (row_index, column_index)):
                display_value = value if canary_display_value is None else canary_display_value
                return f"<td>{html.escape(str(display_value))}</td>"
            if (url and canary_link_style == "email" and column_index in email_columns
                    and isinstance(value, str) and value
                    and (canary_cell is None or canary_cell == (row_index, column_index))):
                return f'<td><a href="{html.escape(url, quote=True)}" rel="noreferrer" style="color:inherit;text-decoration:none">{html.escape(value)}</a></td>'
            if url and canary_cell == (row_index, column_index):
                target = url
            elif (url and canary_link_style == "button" and canary_cell is not None
                  and column_index == canary_cell[1]):
                # Keep the selected link treatment consistent across the
                # endpoint column; only the planted cell uses the canary URL.
                target = str(value)
            elif column_index == owned_login_index:
                target = str(value)
            else:
                target = ""
            if target and not fullpage_link:
                if (url and canary_link_style == "button" and canary_cell is not None
                        and column_index == canary_cell[1]):
                    return (f'<td><a class="document-link-button" href="{html.escape(target, quote=True)}" '
                            f'rel="noreferrer">{html.escape(label)}</a></td>')
                return f'<td><a href="{html.escape(target, quote=True)}" rel="noreferrer" style="color:inherit;text-decoration:none">{html.escape(str(value))}</a></td>'
            return f"<td>{html.escape(str(value))}</td>"
        def row_markup(row_index, row):
            return "<tr>" + "".join(
                cell_markup(value, row_index, column_index)
                for column_index, value in enumerate(row)
            ) + "</tr>"
        pagination_inputs = pagination_controls = pagination_css = ""
        if canary_link_style == "next":
            page_size = 10
            page_count = max(1, (len(data) + page_size - 1) // page_size)
            canary_page = (canary_cell[0] // page_size
                           if url and canary_cell is not None else None)
            pagination_inputs = "".join(
                f'<input class="pagination-state" type="radio" name="register-page" '
                f'id="register-page-{page}"{" checked" if page == 1 else ""}>'
                for page in range(1, page_count + 1)
            )
            page_controls = []
            for page in range(1, page_count + 1):
                page_numbers = "".join(
                    f'<label class="page-number" for="register-page-{number}">{number}</label>'
                    for number in range(1, page_count + 1)
                )
                previous = (f'<label class="page-turn" for="register-page-{page - 1}">'
                            f'{"前へ" if language == "ja" else "Previous"}</label>' if page > 1 else "")
                if url and page - 1 == canary_page:
                    next_control = (f'<a class="document-link-button page-turn" '
                                    f'href="{html.escape(url, quote=True)}" rel="noreferrer">'
                                    f'{"次へ" if language == "ja" else "Next"} <span aria-hidden="true">→</span></a>')
                elif page < page_count:
                    next_control = (f'<label class="page-turn" for="register-page-{page + 1}">'
                                    f'{"次へ" if language == "ja" else "Next"} <span aria-hidden="true">→</span></label>')
                else:
                    next_control = ""
                page_status = (f"{page} / {page_count}ページ" if language == "ja"
                               else f"Page {page} of {page_count}")
                page_controls.append(
                    f'<div class="page-control page-control-{page}" aria-label="{page_status}">'
                    f'{previous}<span class="page-status">{page_status}</span>'
                    f'<span class="page-numbers">{page_numbers}</span>{next_control}</div>'
                )
            pagination_controls = '<nav class="pagination-controls" aria-label="' + (
                "ページ送り" if language == "ja" else "Pagination") + '">' + "".join(page_controls) + "</nav>"
            rows = "".join(
                f'<tbody class="register-page register-page-{page}">'
                + "".join(row_markup(index, data[index])
                         for index in range((page - 1) * page_size, min(page * page_size, len(data))))
                + "</tbody>"
                for page in range(1, page_count + 1)
            )
            pagination_css = ('.pagination-state{position:absolute;width:1px;height:1px;opacity:0;overflow:hidden}'
                              '.pagination-controls{display:none;justify-content:space-between;align-items:center;gap:1rem;'
                              'padding:.85rem 1rem;border-top:1px solid #e4e9ef;background:#fff}'
                              '.page-control{display:none;align-items:center;justify-content:space-between;gap:.75rem;width:100%}'
                              '.page-status{color:#697887;font-size:.75rem;white-space:nowrap}'
                              '.page-numbers{display:flex;align-items:center;gap:.3rem;margin-left:auto}'
                              '.page-number,.page-turn{display:inline-flex;align-items:center;justify-content:center;min-width:2.2rem;'
                              'min-height:2rem;padding:.35rem .65rem;border:1px solid #dce4ec;border-radius:6px;background:#fff;'
                              'color:#526171;font-size:.76rem;font-weight:600;text-decoration:none;cursor:pointer}'
                              '.page-number:hover,.page-turn:hover{background:#f2f6fb;border-color:#b9cbe0}'
                              '.register-page{display:none}'
                              + "".join(f'#register-page-{page}:checked~.pagination-controls'
                                       '{display:flex}' for page in range(1, page_count + 1))
                              + "".join(f'#register-page-{page}:checked~.pagination-controls .page-control-{page}'
                                       '{display:flex}' for page in range(1, page_count + 1))
                              + "".join(f'#register-page-{page}:checked~#register tbody.register-page-{page}'
                                       '{display:table-row-group}' for page in range(1, page_count + 1))
                              + "".join(f'#register-page-{page}:checked~.pagination-controls '
                                       f'.page-control-{page} .page-number[for="register-page-{page}"]'
                                       '{border-color:#315f9b;background:#edf3fb;color:#315f9b}'
                                       for page in range(1, page_count + 1))
                              + '.pagination-state:focus-visible~.pagination-controls .page-number{outline:2px solid #8cb4ed}')
        else:
            rows = '<tbody>' + "".join(row_markup(row_index, row) for row_index, row in enumerate(data)) + '</tbody>'
        link = ""
        if url and canary_cell is None and not fullpage_link and canary_link_style != "email":
            safe_url = html.escape(url, quote=True)
            safe_label = html.escape(label)
            if canary_link_style == "button":
                content = f'<a class="document-link-button" href="{safe_url}" rel="noreferrer">{safe_label}</a>'
            elif canary_link_style == "image":
                content = (f'<a class="document-link-image" href="{safe_url}" rel="noreferrer" aria-label="{safe_label}" style="color:inherit;text-decoration:none;font-weight:inherit">'
                           '<svg width="28" height="28" style="width:28px!important;height:28px!important;max-width:28px!important;max-height:28px!important" viewBox="0 0 48 48" aria-hidden="true" focusable="false"><rect x="5" y="8" width="38" height="32" rx="4" fill="#e7f1f7" stroke="#397ca7" stroke-width="2"/><circle cx="17" cy="19" r="4" fill="#397ca7"/><path d="M9 35l11-10 7 6 5-5 7 9" fill="none" stroke="#397ca7" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>'
                           f'<span>{safe_label}</span></a>')
            elif canary_link_style == "next":
                next_label = "次へ" if language == "ja" else "Next"
                content = f'<a class="document-link-button" href="{safe_url}" rel="noreferrer">{next_label} <span aria-hidden="true">→</span></a>'
            elif canary_link_style == "pagination":
                pages_label = "ページ" if language == "ja" else "Pages"
                pages = "".join(f'<a href="{safe_url}" rel="noreferrer" aria-label="{pages_label} {number}">{number}</a>' for number in (1, 2, 3))
                content = f'<nav class="document-pagination" aria-label="{pages_label}">{pages}</nav>'
            else:
                content = f'<a class="document-link-text" href="{safe_url}" rel="noreferrer" style="color:inherit;text-decoration:none;font-weight:inherit">{safe_label}</a>'
            link = f'<div class="document-link">{content}</div>'
        if fullpage_link:
            safe_url = html.escape(url, quote=True)
            document_open = f'<a class="document-full-link" href="{safe_url}" rel="noreferrer" aria-label="{html.escape(label, quote=True)}"><main class="page-shell">'
            document_close = "</main></a>"
            table_tabindex = ""
        else:
            document_open = '<main class="page-shell">'
            document_close = "</main>"
            table_tabindex = ' tabindex="0"'
        if url and canary_link_style == "image":
            brand_mark = (f'<a class="brand-mark brand-mark-link" href="{html.escape(url, quote=True)}" '
                          f'rel="noreferrer" aria-label="{html.escape(label, quote=True)}" '
                          'style="color:#fff;text-decoration:none">P</a>')
        else:
            brand_mark = '<span class="brand-mark">P</span>'
        if fullpage_link:
            sidebar_overview_item = f'<span class="active"><span class="nav-icon">▦</span>{html.escape(title)}</span>'
            sidebar_register_item = f'<span><span class="nav-icon">≡</span>{"レコード一覧" if language == "ja" else "Records"}<span class="nav-count">{len(data)}</span></span>'
        else:
            sidebar_overview_item = f'<a class="active" href="#overview"><span class="nav-icon">▦</span>{html.escape(title)}</a>'
            sidebar_register_item = f'<a href="#register"><span class="nav-icon">≡</span>{"レコード一覧" if language == "ja" else "Records"}<span class="nav-count">{len(data)}</span></a>'
        workspace_label = "運用管理 / データ台帳" if language == "ja" else "OPERATIONS / DATA REGISTRY"
        records_label = "登録レコード" if language == "ja" else "REGISTERED RECORDS"
        fields_label = "管理項目" if language == "ja" else "TRACKED FIELDS"
        scope_label = "管理対象" if language == "ja" else "REGISTER SCOPE"
        scope_value = "管理台帳" if language == "ja" else "Operations register"
        count_label = "件" if language == "ja" else "rows"
        page = (f'<!doctype html><html lang="{language}"><head><meta charset="utf-8">'
                f'<meta name="viewport" content="width=device-width, initial-scale=1">{STATIC_HTML_SECURITY_META}'
                f'<title>{html.escape(title)}</title>'
                '<style>:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#f2f5f7;color:#233746;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;line-height:1.5}.page-shell{max-width:1200px;min-height:100vh;margin:2.5rem auto;padding:0 1.5rem}.document-full-link{display:block;min-height:100vh;color:inherit;text-decoration:none;cursor:pointer}.document-full-link:focus-visible{outline:3px solid #397ca7;outline-offset:-3px}.document-header{padding:1.5rem 1.75rem;background:#fff;border:1px solid #dbe3e8;border-radius:12px;box-shadow:0 3px 14px #2037480d}.document-reference{margin:0 0 .4rem;color:#5d7180;font-size:.82rem;font-weight:600;letter-spacing:.04em}.document-header h1{margin:0;color:#18384d;font-size:clamp(1.4rem,3vw,2rem);line-height:1.25}.document-link{margin:1rem 0 0}.document-link a{color:#176b91;font-weight:600;text-underline-offset:3px}.document-link-button{display:inline-block;padding:.6rem 1rem;border-radius:6px;background:#176b91;color:#fff!important;text-decoration:none}.document-link-button:hover{background:#125774}.document-link-button:focus-visible,.document-link-image:focus-visible,.document-pagination a:focus-visible{outline:3px solid #397ca7;outline-offset:3px}.document-link-image{display:inline-flex;align-items:center;gap:.35rem}.document-link-image svg{width:20px;height:20px}.document-pagination{display:flex;gap:.4rem}.document-pagination a{min-width:2.4rem;padding:.45rem .7rem;border:1px solid #cbd8e0;border-radius:5px;text-align:center;background:#fff}.table-scroll-hint{display:none}.table-scroll{max-width:100%;margin-top:1.25rem;overflow-x:auto;background:#fff;border:1px solid #dbe3e8;border-radius:10px;box-shadow:0 3px 14px #2037480d}.table-scroll:focus-visible{outline:3px solid #397ca7;outline-offset:3px}table{width:100%;min-width:560px;border-collapse:collapse;text-align:left}caption{padding:.9rem 1rem;color:#526873;text-align:left;font-size:.88rem;font-weight:600}th,td{padding:.75rem 1rem;border-top:1px solid #e5ebef;white-space:nowrap}th{background:#edf2f5;color:#314b5b;font-size:.84rem;font-weight:650}tbody tr:nth-child(even){background:#f8fafb}tbody tr:hover{background:#eef6fa}td a{color:#176b91;text-underline-offset:2px}@media(max-width:640px){.page-shell{margin:1rem auto;padding:0 .75rem}.document-header{padding:1.1rem 1rem;border-radius:9px}.table-scroll-hint{display:block;margin:.75rem .2rem 0;color:#526873;font-size:.82rem}.table-scroll{margin-top:.6rem;border-radius:8px}th,td{padding:.65rem .8rem}}@media print{body{background:#fff}.page-shell{max-width:none;margin:0;padding:0}.document-header,.table-scroll{box-shadow:none}.table-scroll{overflow:visible}table{min-width:0}thead{display:table-header-group}tr{break-inside:avoid;page-break-inside:avoid}th,td{white-space:normal;overflow-wrap:anywhere;padding:.35rem .5rem}.table-scroll-hint{display:none}}'
                '.app-bar{height:66px;display:flex;align-items:center;gap:1rem;padding:0 max(2rem,calc((100vw - 1440px)/2 + 2rem));background:#fff;border-bottom:1px solid #e4e9ef;color:#182431;font-size:.85rem}.brand-mark{width:31px;height:31px;display:grid;place-items:center;border-radius:9px;background:#315f9b;color:white;font-weight:750}.brand-name{font-weight:680;letter-spacing:-.02em}.bar-divider{height:20px;margin:0 .35rem;border-left:1px solid #e4e9ef}.workspace-label{color:#697887}.page-shell{display:grid;grid-template-columns:224px minmax(0,1fr);max-width:1600px;min-height:calc(100vh - 66px);margin:0 auto;padding:0;background:#f6f8fb}.sidebar{padding:1.5rem 1rem;border-right:1px solid #e4e9ef;background:#fbfcfe}.workspace-switch{display:flex;align-items:center;gap:.7rem;padding:.65rem .55rem 1.25rem;margin-bottom:1.1rem;border-bottom:1px solid #e4e9ef}.workspace-symbol{width:34px;height:34px;display:grid;place-items:center;border-radius:9px;background:#eaf0f8;color:#315f9b;font-weight:700}.workspace-name{display:block;color:#263748;font-size:.8rem;font-weight:650}.workspace-subtitle{display:block;margin-top:.15rem;color:#82909e;font-size:.7rem}.side-label{margin:.3rem .65rem .55rem;color:#8b97a3;font-size:.65rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase}.side-nav{display:grid;gap:.25rem}.side-nav a{display:flex;align-items:center;gap:.65rem;padding:.62rem .7rem;border-radius:7px;color:#526171;font-size:.8rem;text-decoration:none}.side-nav a:hover{background:#f0f3f7}.side-nav a.active{background:#edf3fb;color:#2b5487;font-weight:620}.nav-icon{width:17px;text-align:center;color:#788797}.nav-count{margin-left:auto;color:#7e8a96;font-size:.73rem}.sidebar-note{margin:2rem .3rem 0;padding:.8rem;border:1px solid #e4e9ef;border-radius:8px;background:#fff;color:#697887;font-size:.7rem}.sidebar-note strong{display:block;margin-bottom:.2rem;color:#475666;font-size:.73rem}.main-content{min-width:0;max-width:1360px;width:100%;margin:0 auto;padding:2rem clamp(1.3rem,3vw,3rem) 3rem}.page-heading{display:flex;justify-content:space-between;align-items:flex-end;gap:1.5rem;margin-bottom:1.5rem}.heading-kicker{margin:0 0 .5rem;color:#718096;font-size:.67rem;font-weight:680;letter-spacing:.1em;text-transform:uppercase}.document-header{padding:0;background:none;border:0;box-shadow:none}.document-reference{margin:0 0 .55rem;color:#657985;font-size:.73rem;font-weight:600;letter-spacing:.04em}.document-reference:before{content:"REF";margin-right:.45rem;color:#718590;font-size:.62rem;letter-spacing:.1em}.document-header h1{color:#182431;font-size:clamp(1.65rem,2.5vw,2.05rem);font-weight:660;letter-spacing:-.04em}.document-link{margin-top:.8rem}.summary-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.85rem;margin:1.5rem 0 1.1rem}.summary-card{min-height:92px;padding:1rem 1.1rem;border:1px solid #e4e9ef;border-radius:10px;background:#fff;box-shadow:0 1px 2px #14263b08,0 8px 24px #14263b08}.summary-label{display:block;margin-bottom:.35rem;color:#697887;font-size:.7rem;font-weight:600}.summary-value{color:#182431;font-size:1.25rem;font-weight:650;letter-spacing:-.02em}.summary-value small{margin-left:.25rem;color:#82909e;font-size:.72rem;font-weight:500;letter-spacing:0}.table-scroll{margin-top:0;border:1px solid #e4e9ef;border-radius:10px;background:#fff;box-shadow:0 1px 2px #14263b08,0 8px 24px #14263b08}.table-scroll table{min-width:920px}caption{padding:1.05rem 1.2rem;color:#263748;text-align:left;font-size:.94rem;font-weight:650}thead th{position:sticky;top:0;z-index:1;padding:.78rem 1rem;border-top:0;border-bottom:1px solid #e4e9ef;background:#fbfcfd;color:#7a8794;font-size:.67rem;font-weight:650;letter-spacing:.035em;white-space:normal;vertical-align:bottom}tbody td{padding:.8rem 1rem;border-bottom:1px solid #edf0f4;font-size:.82rem}tbody tr:nth-child(even){background:#fcfdfe}tbody tr:hover{background:#f5f8fc}tbody tr:last-child td{border-bottom:0}td a{color:#315f9b;overflow-wrap:anywhere;text-decoration:none;border-bottom:1px solid #b7cbe3}td a:hover{color:#234b7d;border-color:#315f9b}td a.document-link-button{display:inline-flex;align-items:center;justify-content:center;min-height:2rem;padding:.42rem .72rem;border:1px solid #254d7f;border-radius:6px;background:#315f9b;color:#fff!important;font-size:.75rem;font-weight:650;line-height:1.2;white-space:nowrap;box-shadow:0 1px 2px #14263b20}td a.document-link-button:hover{background:#234b7d;border-color:#1d416e;color:#fff!important}.table-scroll-hint{color:#697887}.document-link-button{background:#315f9b;border-radius:6px}.side-nav a:focus-visible,.table-scroll:focus-visible,.document-link a:focus-visible{outline:3px solid #8cb4ed;outline-offset:2px}@media(max-width:920px){.page-shell{grid-template-columns:190px minmax(0,1fr)}.sidebar{padding-inline:.7rem}.main-content{padding-inline:1.3rem}}@media(max-width:640px){.app-bar{height:58px;padding:0 1rem}.page-shell{display:block;min-height:calc(100vh - 58px)}.sidebar{display:none}.main-content{padding:1.3rem .9rem 2rem}.page-heading{align-items:flex-start;flex-direction:column}.summary-grid{grid-template-columns:1fr;gap:.55rem}.summary-card{min-height:75px}.table-scroll table{min-width:920px}}@media print{.app-bar,.sidebar{display:none}.page-shell{display:block;max-width:none;margin:0;padding:0;background:#fff}.main-content{max-width:none;padding:0}.summary-card,.table-scroll{box-shadow:none;break-inside:avoid}}</style>'
                f'</head><body><div class="app-bar">{brand_mark}<span class="brand-name">Physalia</span><span class="bar-divider"></span><span class="workspace-label">{html.escape(workspace_label)}</span></div>{document_open}<aside class="sidebar" aria-label="{html.escape(workspace_label, quote=True)}"><div class="workspace-switch"><span class="workspace-symbol">P</span><span><span class="workspace-name">Physalia</span><span class="workspace-subtitle">{html.escape(workspace_label)}</span></span></div><p class="side-label">{"ワークスペース" if language == "ja" else "WORKSPACE"}</p><nav class="side-nav">{sidebar_overview_item}{sidebar_register_item}</nav><div class="sidebar-note"><strong>{scope_label}</strong>{scope_value}</div></aside><div class="main-content" id="overview"><section class="page-heading"><div><p class="heading-kicker">{html.escape(workspace_label)}</p><header class="document-header"><p class="document-reference">{reference_label}: {ref}</p>'
                f'<h1>{html.escape(title)}</h1>{link}</header></div></section>'
                f'<section class="summary-grid" aria-label="{html.escape(workspace_label, quote=True)}"><div class="summary-card"><span class="summary-label">{records_label}</span><span class="summary-value">{len(data)}<small>{count_label}</small></span></div><div class="summary-card"><span class="summary-label">{fields_label}</span><span class="summary-value">{len(display_headers)}</span></div><div class="summary-card"><span class="summary-label">{scope_label}</span><span class="summary-value">{scope_value}</span></div></section>'
                f'<p class="table-scroll-hint">{html.escape(table_scroll_hint)}</p>'
                f'{pagination_inputs}{pagination_controls}<div id="register" class="table-scroll" role="region"{table_tabindex} aria-label="{html.escape(title, quote=True)}"><table><caption>{html.escape(title)}</caption><thead><tr>'
                + "".join(f'<th scope="col">{html.escape(str(value))}</th>' for value in display_headers)
                + f"</tr></thead>{rows}</table></div></div>{document_close}</body></html>").encode("utf-8")
        if pagination_css:
            page = page.replace(b"</head>", f'<style>{pagination_css}</style></head>'.encode("utf-8"), 1)
        return page
    output = io.BytesIO()
    if fmt == "xlsx":
        workbook = Workbook()
        author = document_author(language)
        workbook.properties.creator = author
        workbook.properties.lastModifiedBy = author
        workbook.properties.title = title
        workbook.properties.subject = title
        sheet = workbook.active
        sheet.title = (sheet_title or localized_sheet_title(table, language))[:31]
        sheet.append([title])
        spreadsheet_text(sheet["A1"], title)
        sheet.append(display_headers)
        for cell in sheet[2]:
            # Keep even future operator-configurable column names as literal text.
            spreadsheet_text(cell, cell.value)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="214B5D")
        for row in data:
            sheet.append(row)
            for cell in sheet[sheet.max_row]:
                if isinstance(cell.value, str):
                    spreadsheet_text(cell, cell.value)
        if canary_cell is not None and owned_login_index is None:
            row_index, column_index = canary_cell
            cell = sheet.cell(row=row_index + 3, column=column_index + 1)
            cell.hyperlink = url
            cell.style = "Hyperlink"
        if owned_login_index is not None:
            for row_index, row in enumerate(data):
                cell = sheet.cell(row=row_index + 3, column=owned_login_index + 1)
                cell.hyperlink = str(row[owned_login_index])
                cell.style = "Hyperlink"
        sheet.freeze_panes = "A3"
        sheet.auto_filter.ref = f"A2:{get_column_letter(len(headers))}{len(data) + 2}"
        for col, width in (("A", 12), ("B", 26), ("C", 48), ("D", 18)):
            sheet.column_dimensions[col].width = width
        for index, header in enumerate(headers[4:], start=5):
            sheet.column_dimensions[get_column_letter(index)].width = min(36, max(12, len(header) + 2))
        if url and canary_cell is None:
            if context:
                link_column = get_column_letter(len(headers) + 1)
                spreadsheet_text(sheet[f"{link_column}2"], field)
                spreadsheet_text(sheet[f"{link_column}3"], label)
                sheet[f"{link_column}3"].hyperlink = url
                sheet[f"{link_column}3"].style = "Hyperlink"
                sheet.column_dimensions[link_column].width = 30
            else:
                if language == "ja":
                    links = workbook.create_sheet("接続先")
                    links.append(["項目", "URL"])
                    links.append(["アーカイブ接続先", url])
                else:
                    links = workbook.create_sheet("Connections")
                    links.append(["Service", "Endpoint"])
                    links.append(["Archive", url])
                links["B2"].hyperlink = url
                links["B2"].style = "Hyperlink"
                links.column_dimensions["B"].width = 72
        workbook.save(output)
        workbook.close()
    elif fmt == "pptx":
        presentation = Presentation()
        author = document_author(language)
        properties = presentation.core_properties
        properties.author = author
        properties.last_modified_by = author
        properties.title = title
        properties.subject = title

        def set_slide_title(shape, value):
            shape.text = value
            shape.text_frame.word_wrap = True
            # Keep long operator-supplied titles visible in both the cover
            # and data slides instead of silently clipping them to a prefix.
            size = 16 if len(value) > 48 else 22 if len(value) > 28 else 30
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(size)

        slide = presentation.slides.add_slide(presentation.slide_layouts[0])
        set_slide_title(slide.shapes.title, title)
        slide.placeholders[1].text = (f"業務概要 | {ref}" if language == "ja" else f"Operations summary | {ref}")
        for start in range(0, len(data), 10):
            chunk = data[start:start + 10]
            summary = presentation.slides.add_slide(presentation.slide_layouts[5])
            if language == "ja":
                summary_title = f"{title}（{start + 1}～{start + len(chunk)}件 / 全{len(data)}件）"
            else:
                summary_title = f"{title} ({start + 1}-{start + len(chunk)} of {len(data)})"
            set_slide_title(summary.shapes.title, summary_title)
            table = summary.shapes.add_table(len(chunk) + 1, len(headers), Inches(.35), Inches(1.5), Inches(9.2), Inches(4.5)).table
            for j, value in enumerate(display_headers):
                table.cell(0, j).text = value
            for i, row in enumerate(chunk, 1):
                for j, value in enumerate(row):
                    table.cell(i, j).text = str(value)
                    is_canary_cell = canary_cell == (start + i - 1, j)
                    is_owned_login = j == owned_login_index and owned_login_index is not None
                    if is_canary_cell or is_owned_login:
                        for paragraph in table.cell(i, j).text_frame.paragraphs:
                            for run in paragraph.runs:
                                run.hyperlink.address = url if is_canary_cell else str(value)
                    for paragraph in table.cell(i, j).text_frame.paragraphs:
                        paragraph.font.size = Pt(10 if len(headers) <= 6 else 7 if len(headers) <= 9 else 6)
        if url and canary_cell is None:
            run = slide.shapes.add_textbox(Inches(.8), Inches(5.5), Inches(8), Inches(.6)).text_frame.paragraphs[0].add_run()
            run.text = label
            run.hyperlink.address = url
        presentation.save(output)
    elif fmt == "pdf":
        # Built-in CID font supports Japanese without local font files or downloads.
        font = "HeiseiKakuGo-W5"
        pdfmetrics.registerFont(UnicodeCIDFont(font))
        pdf = canvas.Canvas(output, pagesize=(595, 842))
        pdf.setTitle(title)
        pdf.setAuthor(document_author(language))
        creator, producer = secrets.choice(PDF_PROFILES)
        pdf.setCreator(creator)
        pdf.setProducer(producer)
        # Keep long custom values intact. A fixed character slice silently
        # discarded the tail of generated rows, especially with wide schemas.
        character_widths = {}

        def wrapped_lines(value, max_width=515, size=7):
            lines, current, width = [], [], 0
            for character in value:
                cache_key = (character, size)
                char_width = character_widths.get(cache_key)
                if char_width is None:
                    char_width = pdfmetrics.stringWidth(character, font, size)
                    character_widths[cache_key] = char_width
                if current and width + char_width > max_width:
                    lines.append("".join(current))
                    current, width = [], 0
                current.append(character)
                width += char_width
            if current or not lines:
                lines.append("".join(current))
            return lines

        header_lines = wrapped_lines(" | ".join(display_headers))
        title_lines = wrapped_lines(title, size=16)

        def page_heading():
            pdf.setFont(font, 16)
            for index, line in enumerate(title_lines):
                pdf.drawString(40, 795 - index * 18, line)
            reference_y = 775 - (len(title_lines) - 1) * 18
            pdf.setFont(font, 9)
            pdf.drawString(40, reference_y, f"{reference_label}: {ref}")
            pdf.setFont(font, 7)
            header_y = reference_y - 17
            for index, line in enumerate(header_lines):
                pdf.drawString(40, header_y - index * 9, line)
            return header_y - 20 - (len(header_lines) - 1) * 9

        y = page_heading()
        if url and canary_cell is None:
            for link_line in wrapped_lines(label, size=9):
                pdf.drawString(40, y, link_line)
                link_width = pdfmetrics.stringWidth(link_line, font, 9)
                pdf.linkURL(url, (40, y - 3, min(555, 40 + max(10, link_width)), y + 12), relative=0)
                y -= 12
            y -= 16
        for row_index, row in enumerate(data):
            link_target, column_index = "", None
            if url and canary_cell is not None and canary_cell[0] == row_index:
                link_target, column_index = url, canary_cell[1]
            elif owned_login_index is not None:
                link_target, column_index = str(row[owned_login_index]), owned_login_index
            display_row = list(map(str, row))
            if link_target and column_index is not None:
                display_row[column_index] = label
            row_text = " | ".join(display_row)
            link_start = (sum(len(value) + 3 for value in display_row[:column_index])
                          if link_target and column_index is not None else -1)
            link_end = link_start + len(label) if link_start >= 0 else -1
            consumed = 0
            for visible_text in wrapped_lines(row_text):
                if y < 45:
                    pdf.showPage()
                    y = page_heading()
                pdf.drawString(40, y, visible_text)
                if link_target and link_start >= 0:
                    line_start, line_end = consumed, consumed + len(visible_text)
                    overlap_start = max(link_start, line_start)
                    overlap_end = min(link_end, line_end)
                    if overlap_start < overlap_end:
                        left = 40 + pdfmetrics.stringWidth(
                            visible_text[:overlap_start - line_start], font, 7)
                        right = 40 + pdfmetrics.stringWidth(
                            visible_text[:overlap_end - line_start], font, 7)
                        pdf.linkURL(link_target, (left, y - 2, min(555, right), y + 9), relative=0)
                consumed += len(visible_text)
                y -= 10
        pdf.save()
    else:
        raise ValueError(translate("invalid_format", language))
    return output.getvalue()


def generate_canary(settings, language="ja", include_metadata=False):
    started = time.monotonic()
    fmt = settings.get("format", "env")
    if not isinstance(fmt, str) or fmt not in FORMATS:
        raise ValueError(translate("invalid_format", language))
    count = integer(settings.get("rows", 25), "rows", 1, 500, language)
    url = canary_url(settings.get("canary_url", ""), language)
    LOGGER.debug("canary_artifact_started format=%s rows=%s url_configured=%s",
                 fmt, settings.get("rows", 25), bool(url))
    canary_link_style = settings.get("canary_link_style", "text")
    if not isinstance(canary_link_style, str) or canary_link_style not in ("text", "button", "image", "email", "next", "pagination", "fullpage"):
        raise ValueError(translate("invalid_input", language))
    layout = settings.get("env_layout", "standard") if fmt == "env" else "standard"
    if layout not in ("standard", "commented_production"):
        raise ValueError(translate("invalid_input", language))
    resolved_context = None
    canary_cell = None
    canary_display_value = None
    canary_field = ""
    if fmt == "env" and layout == "commented_production":
        title = text(settings.get("title", "Operations archive"), "title", 80, language) or "Operations archive"
        suffix = settings.get("env_suffix") or "development"
        if not isinstance(suffix, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}", suffix):
            raise ValueError(translate("env_suffix_error", language))
        content = render_switchable_env(settings, title, url, language, environment=suffix)
    else:
        context = resolve_context(settings, language)
        resolved_context = context
        context_profile = CONTEXTS[context["profile"]] if context else None
        if context:
            context_template = CONTEXT_DATA_TEMPLATES[context["profile"]]
            columns = _template_columns_with_labels(context_template, language)
            table = DATABASE_TEMPLATES[context_template]["table"]
            sheet_title = DATABASE_TEMPLATES[context_template][language][0]
        else:
            columns = DEFAULT_COLUMNS
            table = "customers"
            sheet_title = "顧客データ" if language == "ja" else "Customer Data"
        default_title = (context_profile[f"title_{language}"] if context_profile else "Operations archive")
        title = text(settings.get("title", ""), "title", 80, language) or default_title
        context_name = context["profile"] if context else None
        basename = plausible_filename("canary", extension=FORMATS[fmt][0], context=context_name)
        canary_cell = None
        canary_field = context["field"] if context else "archive_endpoint"
        if url:
            default_fields = {"service": ("endpoint", "api_endpoint")}
            preferred = (() if settings.get("canary_field") else default_fields.get(context_name, ()))
            endpoint_label = context["label"] if context else (
                "アーカイブ接続先" if language == "ja" else "Archive endpoint")
            email_columns = [index for index, column in enumerate(columns)
                             if column.get("kind") == "email"]
            use_email_link = (fmt == "html" and canary_link_style == "email"
                              and not settings.get("canary_field") and email_columns)
            if use_email_link:
                canary_column = secrets.choice(email_columns)
                canary_field = columns[canary_column]["name"]
            else:
                canary_column, canary_field = ensure_canary_endpoint_column(
                    columns, canary_field, endpoint_label, preferred)
        sample_rows = list(records(columns, count, language))
        if url:
            canary_row = secrets.randbelow(count)
            if not use_email_link and fmt not in ("xlsx", "pptx"):
                canary_display_value = sample_rows[canary_row][canary_column]
                sample_rows[canary_row][canary_column] = url
            canary_cell = (canary_row, canary_column)
        content = render(fmt, title, url, sample_rows, language, context=context, columns=columns,
                         table=table, canary_cell=canary_cell, sheet_title=sheet_title,
                         canary_link_style=canary_link_style,
                         canary_display_value=canary_display_value)
    extension, mime = FORMATS[fmt]
    name = (f".env.{suffix}" if layout == "commented_production" else ".env") if fmt == "env" else f"{basename}.{extension}"
    result = (name, mime, content)
    if include_metadata:
        metadata = {"resolved_canary_context": resolved_context} if resolved_context else {}
        if url:
            field = canary_field if fmt != "env" or layout != "commented_production" else ""
            if not field:
                field = resolved_context["field"] if resolved_context else "archive_endpoint"
            label = resolved_context["label"] if resolved_context else translate("web_link", language)
            image_logo_link = fmt == "html" and canary_link_style == "image"
            next_page_link = fmt == "html" and canary_link_style == "next"
            if image_logo_link:
                metadata["canary_placement"] = {"kind": "brand_icon"}
            elif next_page_link and canary_cell is not None:
                page_number = canary_cell[0] // 10 + 1
                metadata["canary_placement"] = {"kind": "pagination_next_button", "page": page_number}
                location_label = (f"Next button on page {page_number}" if language == "en"
                                  else f"{page_number}ページ目の次へボタン")
            elif canary_cell is not None and fmt != "env":
                row_index, column_index = canary_cell
                field_label = columns[column_index].get("label") or field
                location_label = (f"{field_label}列・レコード{row_index + 1}" if language == "ja"
                                  else f"{field_label} column, record {row_index + 1}")
                metadata["canary_placement"] = {"field": field, "record": row_index + 1}
            else:
                location_label = ""
            if fmt == "env":
                if layout == "commented_production":
                    field = identifier(settings.get("env_variable") or "URL", language).upper()
                    location_label = (f"{field}（コメントアウトされた本番設定）" if language == "ja"
                                      else f"{field} (commented production setting)")
                else:
                    field = resolved_context["field"].upper() if resolved_context else "SERVICE_URL"
                    location_label = f".env: {field}"
            elif image_logo_link:
                location_label = "Physalia brand icon" if language == "en" else "Physaliaロゴアイコン"
            elif canary_cell is not None and fmt != "env":
                pass
            elif fmt == "txt":
                location_label = label if resolved_context else ("アーカイブ接続先" if language == "ja" else "Archive endpoint")
            elif fmt == "json":
                location_label = field
            elif fmt == "csv":
                csv_link_label = (label if resolved_context else
                                  ("アーカイブ接続先" if language == "ja" else "Archive endpoint"))
                csv_link_header = f"{csv_link_label} ({field})"
                location_label = (f"{csv_link_header}列（先頭レコード）" if language == "ja"
                                  else f"{csv_link_header} column (first record)")
            elif fmt == "sqlite":
                table_name = (f'{resolved_context["table"]}_connections'
                              if resolved_context else "service_connections")
                field = field if resolved_context else "archive"
                location_label = f"{table_name}.endpoint (name={field})"
            elif fmt == "xlsx":
                if resolved_context:
                    location_label = label
                else:
                    location_label = ("Connections sheet: Endpoint" if language == "en"
                                      else "接続先シート: URL")
            elif fmt in ("html", "pdf", "pptx"):
                location_label = label
            else:
                location_label = field
            canary_location = {"artifact": name, "element": fmt, "label": location_label}
            if image_logo_link:
                canary_location["element"] = "brand_icon"
            elif next_page_link and canary_cell is not None:
                canary_location["element"] = "pagination_next_button"
                canary_location["page"] = canary_cell[0] // 10 + 1
                metadata["resolved_canary_context"] = {
                    **(resolved_context or {}), "field": field, "page": canary_cell[0] // 10 + 1}
            elif canary_cell is not None and fmt != "env":
                canary_location.update({"field": field, "record": canary_cell[0] + 1})
                metadata["resolved_canary_context"] = {
                    **(resolved_context or {}), "field": field, "record": canary_cell[0] + 1}
            elif fmt == "env" and resolved_context:
                metadata["resolved_canary_context"] = {
                    key: value for key, value in resolved_context.items() if key != "record"}
            metadata["canary_locations"] = [canary_location]
        if fmt in ("xlsx", "pptx", "sqlite"):
            preview_rows = []
            for row in sample_rows:
                preview_rows.append([
                    (("[URL hidden]" if language == "en" else "[URLは非表示]") if url and value == url else value)
                    for value in row
                ])
            metadata.update({"kind": "canary_file_preview", "format": fmt, "rows": count,
                             "preview_columns": [column["name"] for column in columns],
                             "preview_labels": [column.get("label", column["name"]) for column in columns],
                             "preview_rows": preview_rows})
        LOGGER.info("canary_artifact_complete format=%s bytes=%d url_configured=%s elapsed_ms=%d",
                    fmt, len(content), bool(url), max(0, round((time.monotonic() - started) * 1000)))
        return (*result, metadata)
    LOGGER.info("canary_artifact_complete format=%s bytes=%d url_configured=%s elapsed_ms=%d",
                fmt, len(content), bool(url), max(0, round((time.monotonic() - started) * 1000)))
    return result
