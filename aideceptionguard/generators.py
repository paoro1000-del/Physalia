"""Generate inert decoy assets. No network access or deployment is performed."""

from __future__ import annotations

import html
import io
import os
import secrets
import zipfile

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from aideceptionguard.archive_metadata import write_archive_member
from aideceptionguard.i18n import translate
from aideceptionguard.validation import (text as _text, canary_url as _canary_url,
                                         filename, reject_unsafe_text_tree,
                                         vault_decoy_domain)
from aideceptionguard.database import database_settings, records, sqlite_bytes
from aideceptionguard.formats import STATIC_HTML_SECURITY_META, generate_canary
from aideceptionguard.nesting import MAX_LAYERS, Artifact, generate_nest
from aideceptionguard.mazes import generate_directory_maze, generate_encoding_maze, generate_stream_sample
from aideceptionguard.naming import plausible_filename
from aideceptionguard.inventory import attach_inventory

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
    name, mime, content, resolved_context = generate_canary(settings, language, include_metadata=True)
    summary = {"resolved_canary_context": resolved_context} if resolved_context else {}
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
    basename = (filename(settings["filename"], language) if settings.get("filename")
                else plausible_filename("database", extension="sqlite", profile=settings.get("template", "customers")))
    url = _canary_url(settings.get("canary_url", ""), language)
    summary = {}
    login_url_index = next((index for index, column in enumerate(columns)
                            if column["name"].casefold() == "login_url"), None)
    login_url_usable = (login_url_index is not None
                        and columns[login_url_index]["kind"] in ("domain", "text"))
    if url and settings.get("template") == "passwords" and login_url_usable:
        row_index = secrets.randbelow(row_count)
        summary["resolved_canary_context"] = {
            "profile": "password_vault", "table": table,
            "field": columns[login_url_index]["name"], "record": row_index + 1,
        }
        database_url = ""

        def data_rows():
            for index, row in enumerate(records(columns, row_count, language)):
                if index == row_index:
                    row[login_url_index] = url
                yield row
    else:
        database_url = url
        data_rows = records(columns, row_count, language)
    return Artifact(basename + ".db", "application/vnd.sqlite3",
                    sqlite_bytes(table, columns, data_rows, database_url, language=language), summary=summary)


def generate_web(settings: dict, language: str = "ja") -> tuple[str, str, bytes]:
    language = language if language in ("ja", "en") else "ja"
    title = _text(settings.get("title", "Operations Portal"), "title", 80, language) or "Operations Portal"
    url = _canary_url(settings.get("canary_url", ""), language)
    action = (f'<p><a href="{html.escape(url, quote=True)}" rel="noreferrer">{translate("web_link", language)}</a></p>'
              if url else f'<p>{translate("web_no_link", language)}</p>')
    markup = f"""<!doctype html>
<html lang="{language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
{STATIC_HTML_SECURITY_META}
<title>{html.escape(title)}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:850px;margin:4rem auto;padding:0 1rem;color:#263445}}
main{{border:1px solid #d7e1ea;border-radius:12px;padding:2rem}}a{{color:#155eaa}}</style>
</head><body><main><h1>{html.escape(title)}</h1><p>{translate("web_intro", language)}</p>{action}</main></body></html>
"""
    basename = filename(settings["filename"], language) if settings.get("filename") else plausible_filename("html", extension="html")
    return basename + ".html", "text/html; charset=utf-8", markup.encode("utf-8")


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
    basename = filename(settings["filename"], language) if settings.get("filename") else "security_notice"
    return basename + ".html", "text/html; charset=utf-8", markup.encode("utf-8")


GENERATORS = {"env": generate_env, "database": generate_database, "web": generate_web, "nest": generate_nest, "fake_trap": generate_fake_trap}
GENERATORS.update(directory_maze=generate_directory_maze, encoding_maze=generate_encoding_maze, stream=generate_stream_sample)

# Keep the API surface aligned with the settings assembled by web/app.js.
# Silently ignored keys are easy to mistype and would otherwise be copied into
# the operator inventory even though they had no effect on the generated file.
SETTING_KEYS = {
    "env": {"format", "canary_url", "canary_context", "canary_field", "canary_label",
            "env_layout", "env_suffix", "env_variable", "env_dev_url",
            "env_dev_url_authorized", "env_dev_comment", "env_prod_comment", "title", "rows", "filename"},
    "database": {"template", "email_domain", "email_domain_authorized", "vault_domain",
                 "vault_domain_authorized", "rows", "table", "columns", "canary_url", "filename"},
    "web": {"title", "canary_url", "filename"},
    "fake_trap": {"variant", "filename"},
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
