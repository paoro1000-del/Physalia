"""Real document formats with inert content and optional HTTPS hyperlinks."""
import csv
import html
import io
import json
import re
import secrets
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

from aideceptionguard.database import DEFAULT_COLUMNS, records, sqlite_bytes
from aideceptionguard.i18n import translate
from aideceptionguard.naming import plausible_filename
from aideceptionguard.validation import canary_url, filename, identifier, integer, is_public_host, is_reserved_example_url, text

FORMATS = {
    "env": ("env", "text/plain; charset=utf-8"), "txt": ("txt", "text/plain; charset=utf-8"),
    "json": ("json", "application/json"), "csv": ("csv", "text/csv; charset=utf-8"),
    "html": ("html", "text/html; charset=utf-8"), "pdf": ("pdf", "application/pdf"),
    "xlsx": ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    "pptx": ("pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
    "sqlite": ("db", "application/vnd.sqlite3"),
}

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
    reserved = {"app_env", "archive_reference", "title", "reference", "records"} | {c["name"].lower() for c in DEFAULT_COLUMNS}
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
    return (f"# {title}\nAPP_ENV={environment}\n\n# {dev_comment}\n{key}=\"{dev_url}\"\n\n"
            f"# {prod_comment}\n# {key}=\"{token}\"\n").encode("utf-8")


def dotenv_value(value, language):
    """Quote a supported URL in the constrained single-quoted dotenv form."""
    # Dotenv parsers differ on interpolation; a single-quoted value does not
    # reliably protect `${NAME}` from expansion across implementations.
    if "'" in value or "$" in value or any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(translate("dotenv_quote_error", language))
    return "'" + value + "'"


def render(fmt, title, url, data, language="ja", reference=None, context=None, app_env="production",
           columns=None, table="customers", canary_cell=None):
    """Render without fetching URLs, macros, scripts, external images or formulas."""
    columns = DEFAULT_COLUMNS if columns is None else columns
    headers = [column["name"] for column in columns]
    owned_login_index = next((index for index, column in enumerate(columns)
                              if column["name"].casefold() == "login_url"
                              and column.get("vault_decoy_domain")), None)
    ref = reference or secrets.token_hex(6).upper()
    field = context["field"] if context else "archive_endpoint"
    label = context["label"] if context else translate("web_link", language)
    if fmt == "env":
        if app_env not in ("production", "staging", "development", "test"):
            raise ValueError(translate("invalid_input", language))
        env_url = dotenv_value(url or "https://example.invalid/replace-me", language)
        env_field = field.upper() if context else "SERVICE_URL"
        content = f"# {title}\nAPP_ENV={app_env}\nARCHIVE_REFERENCE={ref}\n{env_field}={env_url}\n"
        return content.encode("utf-8")
    if fmt == "txt":
        content = (f"{title}\nReference: {ref}\n\n" + " | ".join(headers) + "\n"
                   + "\n".join(" | ".join(map(str, row)) for row in data))
        return (content + (f"\n\n{label if context else 'Archive endpoint'}: {url}\n"
                           if url and canary_cell is None else "\n")).encode("utf-8")
    if fmt == "json":
        payload = {"title": title, "reference": ref, "records": [dict(zip(headers, r)) for r in data]}
        if url and canary_cell is None:
            payload[field] = url
        return json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    if fmt == "csv":
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        safe_headers = [spreadsheet_csv_value(value) for value in headers]
        writer.writerow(safe_headers + ([spreadsheet_csv_value(field)] if url and canary_cell is None else []))
        for index, row in enumerate(data):
            safe_row = [spreadsheet_csv_value(value) for value in row]
            writer.writerow(safe_row + ([url if index == 0 else ""] if url and canary_cell is None else []))
        return stream.getvalue().encode("utf-8-sig")
    if fmt == "sqlite":
        return sqlite_bytes(table, columns, data, url if canary_cell is None else "",
                            connection_table=context["table"] if context else None,
                            connection_name=field if context else "archive", language=language)
    if fmt == "html":
        def cell_markup(value, row_index, column_index):
            if url and canary_cell == (row_index, column_index):
                target = url
            elif column_index == owned_login_index:
                target = str(value)
            else:
                target = ""
            if target:
                return f'<td><a href="{html.escape(target, quote=True)}" rel="noreferrer">{html.escape(str(value))}</a></td>'
            return f"<td>{html.escape(str(value))}</td>"
        rows = "".join(
            "<tr>" + "".join(
                cell_markup(value, row_index, column_index)
                for column_index, value in enumerate(row)
            ) + "</tr>" for row_index, row in enumerate(data)
        )
        link = (f'<p><a href="{html.escape(url, quote=True)}" rel="noreferrer">{html.escape(label)}</a></p>'
                if url and canary_cell is None else "")
        return (f'<!doctype html><html lang="{language}"><head><meta charset="utf-8">'
                f'<meta name="viewport" content="width=device-width, initial-scale=1">{STATIC_HTML_SECURITY_META}'
                f'<title>{html.escape(title)}</title>'
                '<style>body{font-family:system-ui;margin:3rem;color:#203748}table{border-collapse:collapse}td,th{padding:10px;border:1px solid #ddd}</style>'
                f'</head><body><h1>{html.escape(title)}</h1><p>{ref}</p>{link}<table><tr>'
                + "".join(f"<th>{html.escape(str(value))}</th>" for value in headers)
                + f"</tr>{rows}</table></body></html>").encode("utf-8")
    output = io.BytesIO()
    if fmt == "xlsx":
        workbook = Workbook()
        author = document_author(language)
        workbook.properties.creator = author
        workbook.properties.lastModifiedBy = author
        workbook.properties.title = title
        workbook.properties.subject = title
        sheet = workbook.active
        sheet.title = table.replace("_", " ").title()[:31]
        sheet.append([title])
        spreadsheet_text(sheet["A1"], title)
        sheet.append(headers)
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
            for j, value in enumerate(headers):
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

        header_lines = wrapped_lines(" | ".join(headers))
        title_lines = wrapped_lines(title, size=16)

        def page_heading():
            pdf.setFont(font, 16)
            for index, line in enumerate(title_lines):
                pdf.drawString(40, 795 - index * 18, line)
            reference_y = 775 - (len(title_lines) - 1) * 18
            pdf.setFont(font, 9)
            pdf.drawString(40, reference_y, ref)
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
            for visible_text in wrapped_lines(" | ".join(display_row)):
                if y < 45:
                    pdf.showPage()
                    y = page_heading()
                pdf.drawString(40, y, visible_text)
                y -= 10
            if link_target and column_index is not None:
                link_text = f"{headers[column_index]}: {label}"
                if y < 55:
                    pdf.showPage()
                    y = page_heading()
                for link_line in wrapped_lines(link_text, max_width=503):
                    if y < 45:
                        pdf.showPage()
                        y = page_heading()
                    pdf.drawString(52, y, link_line)
                    link_width = pdfmetrics.stringWidth(link_line, font, 7)
                    pdf.linkURL(link_target, (52, y - 2, min(555, 52 + link_width), y + 9), relative=0)
                    y -= 10
                y -= 2
        pdf.save()
    else:
        raise ValueError(translate("invalid_format", language))
    return output.getvalue()


def generate_canary(settings, language="ja", include_metadata=False):
    fmt = settings.get("format", "env")
    if not isinstance(fmt, str) or fmt not in FORMATS:
        raise ValueError(translate("invalid_format", language))
    count = integer(settings.get("rows", 25), "rows", 1, 500, language)
    url = canary_url(settings.get("canary_url", ""), language)
    layout = settings.get("env_layout", "standard") if fmt == "env" else "standard"
    if layout not in ("standard", "commented_production"):
        raise ValueError(translate("invalid_input", language))
    resolved_context = None
    if fmt == "env" and layout == "commented_production":
        title = text(settings.get("title", "Operations archive"), "title", 80, language) or "Operations archive"
        basename = filename(settings["filename"], language) if settings.get("filename") else ""
        suffix = settings.get("env_suffix") or "development"
        if not isinstance(suffix, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}", suffix):
            raise ValueError(translate("env_suffix_error", language))
        content = render_switchable_env(settings, title, url, language, environment=suffix)
    else:
        context = resolve_context(settings, language)
        resolved_context = context
        context_profile = CONTEXTS[context["profile"]] if context else None
        default_title = (context_profile[f"title_{language}"] if context_profile else "Operations archive")
        title = text(settings.get("title", ""), "title", 80, language) or default_title
        context_name = context["profile"] if context else None
        basename = (filename(settings["filename"], language) if settings.get("filename") else
                    plausible_filename("canary", extension=FORMATS[fmt][0], context=context_name))
        content = render(fmt, title, url, list(records(DEFAULT_COLUMNS, count, language)), language, context=context)
    extension, mime = FORMATS[fmt]
    name = (f".env.{suffix}" if layout == "commented_production" else ".env") if fmt == "env" and not settings.get("filename") else f"{basename}.{extension}"
    result = (name, mime, content)
    return (*result, resolved_context) if include_metadata else result
