"""Shared validation for bounded, local asset generation."""
import functools
import ipaddress
import logging
import math
import re
import secrets
import time
import unicodedata
from urllib.parse import urlsplit

from physalia.i18n import translate

LOGGER = logging.getLogger("physalia")

def _logged_validation(function):
    """Trace shared validation stages without recording supplied values."""
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        started = time.monotonic()
        LOGGER.debug("validation_started name=%s", function.__name__)
        try:
            result = function(*args, **kwargs)
        except Exception as exc:
            LOGGER.info("validation_rejected name=%s error_type=%s elapsed_ms=%d",
                        function.__name__, type(exc).__name__,
                        max(0, round((time.monotonic() - started) * 1000)))
            raise
        LOGGER.debug("validation_complete name=%s elapsed_ms=%d",
                     function.__name__, max(0, round((time.monotonic() - started) * 1000)))
        return result
    return wrapped

MAX_CANARY_URLS = 400
MAX_CANARY_URL_LENGTH = 2048
MAX_SETTING_TEXT_LENGTH = MAX_CANARY_URL_LENGTH
MAX_SETTING_NODES = 10_000
MAX_SETTING_DEPTH = 32
_RESERVED_EXAMPLE_SUFFIXES = (
    ".invalid", ".example", ".test",
    ".example.com", ".example.net", ".example.org",
)
_RESERVED_EXAMPLE_HOSTS = {"example.com", "example.net", "example.org"}
_SPECIAL_USE_SUFFIXES = (".arpa", ".onion", ".alt")
_BIDI_DISPLAY_CONTROLS = frozenset("\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\u206a\u206b\u206c\u206d\u206e\u206f")
_EMAIL_DOMAIN = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@((?:[^\W_](?:[^\W_-]{0,61}[^\W_])?\.)+[^\W\d_](?:[^\W_-]{0,61}[^\W\d_]))(?![\w.-])"
)
_URL_VALUE = re.compile(r"(?i)\b[a-z][a-z0-9+.-]{1,15}://[^\s<>'\"]+|\bmailto:[^\s<>'\"]+")
_DOMAIN_VALUE = re.compile(
    r"(?<![\w@.-])((?:[^\W_](?:[^\W_-]{0,61}[^\W_])?\.)+[^\W\d_](?:[^\W_-]{0,61}[^\W\d_]))"
    r"(?=$|[\s/:?#,;!)}\]]|\.$)"
)
_NON_DOMAIN_SUFFIXES = frozenset({
    "7z", "avif", "bak", "backup", "bat", "bin", "bz2", "cfg", "class",
    "conf", "config", "crt", "csv", "db", "dll", "doc", "docx", "env",
    "gif", "go", "gz", "htm", "html", "ini", "java", "jpeg", "jpg", "js",
    "json", "key", "lock", "log", "md", "mov", "mp3", "mp4", "patch", "pdf",
    "pem", "php", "p12", "pfx", "png", "ppt", "pptx", "properties", "ps1",
    "py", "r", "rar", "rb", "rs", "sh", "sql", "sqlite", "svg", "tar", "toml",
    "ts", "txt", "war", "webp", "xls", "xlsx", "xml", "yaml", "yml", "zip",
})
_IPV4_VALUE = re.compile(r"(?<![0-9.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9.])")
_IPV6_VALUE = re.compile(r"(?<![A-Za-z0-9:])(?:[0-9A-Fa-f]{0,4}:){2,}[0-9A-Fa-f:.]+(?:%[A-Za-z0-9_.-]+)?(?![A-Za-z0-9:])")
_DOCUMENTATION_NETWORKS = tuple(ipaddress.ip_network(value) for value in (
    "192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "2001:db8::/32",
))
_CREDENTIAL_MARKERS = re.compile(
    r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"
    r"|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"
    r"|\bgithub_pat_[A-Za-z0-9_]{20,}\b"
    r"|\bgh[pousr]_[A-Za-z0-9]{20,}\b"
    r"|\bxox[baprs]-[A-Za-z0-9-]{10,}\b"
    r"|\bAIza[0-9A-Za-z_-]{30,}\b"
    r"|\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"
    r"|\b(?:sk|rk)_live_[A-Za-z0-9]{12,}\b"
    r"|\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*[^\s,;]+",
    re.IGNORECASE,
)
_JWT_VALUE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
_CARD_NUMBER = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")


def _unsafe_text_character(character):
    return (unicodedata.category(character) in ("Cc", "Zl", "Zp")
            or character in _BIDI_DISPLAY_CONTROLS
            or 0xD800 <= ord(character) <= 0xDFFF)


@_logged_validation
def reject_unsafe_text_tree(value, language="ja"):
    """Reject unsafe text, recognizable secrets and unapproved endpoints."""
    pending = [(value, False, 0)]
    seen = set()
    visited = 0
    while pending:
        item, skip_sensitive, depth = pending.pop()
        visited += 1
        if visited > MAX_SETTING_NODES or depth > MAX_SETTING_DEPTH:
            raise ValueError(translate("invalid_input", language))
        if isinstance(item, str):
            # Bound normalization and several regex scans before field-level
            # validation. All supported single-value inputs are <= 2048 chars;
            # larger settings can only be malformed or unused payload.
            if len(item) > MAX_SETTING_TEXT_LENGTH:
                raise ValueError(translate("setting_text_limit", language,
                                           maximum=MAX_SETTING_TEXT_LENGTH))
            if any(_unsafe_text_character(character) for character in item):
                raise ValueError(translate("invalid_input", language))
            if not skip_sensitive:
                if _has_sensitive_pattern(item):
                    raise ValueError(translate("synthetic_value_sensitive_error", language))
                if _has_unapproved_endpoint(item, ignore_dotted_file_names=True):
                    raise ValueError(translate("synthetic_value_endpoint_error", language))
        elif isinstance(item, float) and not math.isfinite(item):
            # JSON's 1e999 parses to infinity even though NaN/Infinity tokens
            # are rejected by the HTTP parser. Catch it before settings are
            # copied into strict operator inventory JSON.
            raise ValueError(translate("invalid_input", language))
        elif isinstance(item, dict):
            marker = (id(item), skip_sensitive)
            if marker in seen:
                continue
            seen.add(marker)
            for key, child in item.items():
                pending.append((key, skip_sensitive, depth + 1))
                # Values in dedicated endpoint fields are validated by their
                # own validators below; canary URLs must retain their exact bytes.
                dedicated_endpoint = isinstance(key, str) and key.casefold() in (
                    "canary_url", "canary_urls", "vault_domain", "email_domain")
                pending.append((child, skip_sensitive or dedicated_endpoint, depth + 1))
        elif isinstance(item, list):
            marker = (id(item), skip_sensitive)
            if marker in seen:
                continue
            seen.add(marker)
            pending.extend((child, skip_sensitive, depth + 1) for child in item)


def text(value, label, maximum=200, language="ja"):
    if (not isinstance(value, str) or len(value) > maximum
            or any(_unsafe_text_character(character) for character in value)):
        raise ValueError(translate("single_line", language, label=translate(label, language), maximum=maximum))
    return value.strip()


def _safe_synthetic_host(host):
    if is_reserved_example_url("https://" + host):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(address.version == network.version and address in network
               for network in _DOCUMENTATION_NETWORKS)


def _luhn_valid(value):
    digits = [int(character) for character in value if character.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def _has_sensitive_pattern(value):
    inspection = "".join(
        character for character in unicodedata.normalize("NFKC", value)
        if unicodedata.category(character) != "Cf"
    )
    return (_CREDENTIAL_MARKERS.search(inspection) is not None
            or _JWT_VALUE.search(inspection) is not None
            or any(_luhn_valid(match.group(0)) for match in _CARD_NUMBER.finditer(inspection)))


def _has_unapproved_endpoint(value, ignore_dotted_file_names=True):
    # IDNA treats these Unicode full stops as label separators.
    inspection = "".join(
        character for character in unicodedata.normalize("NFKC", value)
        if unicodedata.category(character) != "Cf"
    )
    inspection = inspection.translate(str.maketrans({"\u3002": ".", "\uff0e": ".", "\uff61": "."}))
    for match in _URL_VALUE.finditer(inspection):
        url = match.group(0).rstrip(".,;!?)")
        try:
            host = urlsplit(url).hostname or ""
        except ValueError:
            host = ""
        if not _safe_synthetic_host(host):
            return True
    for match in _EMAIL_DOMAIN.finditer(inspection):
        if not _safe_synthetic_host(match.group(1)):
            return True
    for match in _DOMAIN_VALUE.finditer(inspection):
        host = match.group(1).rstrip(".")
        # Dotted file names such as report.csv and backup.db are common in
        # titles and notes, but are not hostnames or clickable endpoints.
        if (ignore_dotted_file_names
                and host.rsplit(".", 1)[-1].casefold() in _NON_DOMAIN_SUFFIXES):
            continue
        if not _safe_synthetic_host(host):
            return True
    for match in _IPV4_VALUE.finditer(inspection):
        try:
            ipaddress.ip_address(match.group(0))
        except ValueError:
            continue
        if not _safe_synthetic_host(match.group(0)):
            return True
    for match in _IPV6_VALUE.finditer(inspection):
        literal = match.group(0).split("%", 1)[0]
        try:
            ipaddress.IPv6Address(literal)
        except ValueError:
            continue
        if not _safe_synthetic_host(literal):
            return True
    return False


def synthetic_candidate(value, language="ja"):
    """Reject live endpoints and recognizable secrets in custom synthetic rows."""
    candidate = text(value, "sample_value", 120, language)
    if _has_sensitive_pattern(candidate):
        raise ValueError(translate("synthetic_value_sensitive_error", language))
    if _has_unapproved_endpoint(candidate):
        raise ValueError(translate("synthetic_value_endpoint_error", language))
    return candidate


def integer(value, label, minimum, maximum, language="ja"):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(translate("integer_range", language, label=translate(label, language), minimum=minimum, maximum=maximum))
    return value


def is_public_host(host):
    """Return whether a URL host is syntactically public and non-local.

    DNS is intentionally not resolved here. Callers must still ensure a
    supplied hostname resolves only to addresses they control and expect.
    """
    if not isinstance(host, str) or not host:
        return False
    try:
        ascii_host = host.encode("idna").decode("ascii")
    except UnicodeError:
        return False
    # IPv6 zone identifiers (for example, %25eth0 in a URL literal) are
    # interface-scoped and are not valid public destinations. Python's
    # ipaddress module can still report a global base address as is_global.
    if "%" in ascii_host:
        return False
    if ascii_host.endswith(".."):
        return False
    normalized_host = ascii_host[:-1] if ascii_host.endswith(".") else ascii_host
    try:
        address = ipaddress.ip_address(normalized_host)
    except ValueError:
        address = None
    if address is not None:
        return address.is_global and (getattr(address, "ipv4_mapped", None) is None
                                      or address.ipv4_mapped.is_global)

    normalized_host = normalized_host.lower()
    labels = normalized_host.split(".")
    numeric_label = re.compile(r"(?:0x[0-9a-f]+|0[0-7]*|[0-9]+)")
    if all(numeric_label.fullmatch(label) for label in labels):
        # WHATWG URL parsers accept legacy IPv4 forms such as 127.1,
        # 0177.0.0.1, and 0x7f.0.0.1, which Python's ipaddress rejects.
        return False
    local_host = (normalized_host in ("localhost", "localhost.localdomain", "ip6-localhost")
                  or normalized_host.endswith((".localhost", ".local", ".internal", ".lan", ".home", ".test")))
    if normalized_host.endswith(_SPECIAL_USE_SUFFIXES):
        return False
    return (len(normalized_host) <= 253 and len(labels) >= 2 and not local_host
            and all(label and len(label) <= 63
                    and re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", label)
                    for label in labels))


def is_reserved_example_url(value):
    """Return whether a URL uses a reserved documentation/test domain."""
    if not isinstance(value, str):
        return False
    try:
        raw_host = urlsplit(value).hostname or ""
        host = raw_host.encode("idna").decode("ascii").rstrip(".").lower()
    except (TypeError, ValueError):
        return False
    return host in _RESERVED_EXAMPLE_HOSTS or any(host.endswith(suffix) for suffix in _RESERVED_EXAMPLE_SUFFIXES)


@_logged_validation
def canary_url(value, language="ja"):
    original_value = value
    value = text(value, "canary_url", MAX_CANARY_URL_LENGTH, language)
    if not value:
        return ""
    # Never silently rewrite an operator-issued token URL. In particular,
    # text() strips surrounding whitespace for ordinary text fields, so reject
    # that normalization here to keep the embedded value identical to input.
    if original_value != value:
        raise ValueError(translate("invalid_url", language))
    # Fragments are never sent in HTTP requests. Accepting one can make an
    # operator believe that the fragment itself is part of the canary token.
    if any(character.isspace() for character in value) or "\\" in value or "#" in value:
        raise ValueError(translate("invalid_url", language))
    try:
        parsed = urlsplit(value)
        host, port = parsed.hostname, parsed.port
    except ValueError as exc:
        raise ValueError(translate("invalid_url", language)) from exc
    local_canary = (parsed.scheme == "http" and host == "127.0.0.1"
                    and parsed.path.startswith("/canary/")
                    and re.fullmatch(r"/canary/[A-Za-z0-9_-]{32,64}", parsed.path)
                    and not parsed.query)
    if (parsed.scheme != "https" and not local_canary) or not host or parsed.username is not None or parsed.password is not None:
        raise ValueError(translate("https_url", language))
    if port is not None and not 1 <= port <= 65535:
        raise ValueError(translate("invalid_url", language))
    # A generated lure may later be opened by a crawler or an AI agent.
    if not local_canary and not is_public_host(host):
        raise ValueError(translate("invalid_url", language))
    return value


@_logged_validation
def canary_url_list(settings, language="ja"):
    """Validate a per-file URL list while retaining the legacy single-URL input."""
    raw = settings.get("canary_urls")
    if raw is None:
        value = canary_url(settings.get("canary_url", ""), language)
        return [value] if value else []
    if not isinstance(raw, list) or any(not isinstance(value, str) for value in raw):
        raise ValueError(translate("invalid_url", language))
    if len(raw) > MAX_CANARY_URLS:
        raise ValueError(translate("too_many_canary_urls", language))
    values = [canary_url(value, language) for value in raw if value.strip()]
    if len(values) != len(set(values)):
        raise ValueError(translate("duplicate_canary_urls", language))
    return values


@_logged_validation
def vault_decoy_domain(value, authorized, language="ja"):
    """Validate an operator-owned domain for isolated synthetic login URLs.

    This performs no DNS lookup. Ownership and decoy-only routing are an
    explicit operator attestation because they cannot be established locally.
    """
    # The longest generated service label is 48 characters, plus a dot.
    value = text(value, "vault_domain", 204, language)
    if not value:
        return ""
    if not isinstance(authorized, bool) or not authorized:
        raise ValueError(translate("vault_domain_authorization", language))
    if any(character in value for character in "/\\?#@:[]"):
        raise ValueError(translate("vault_domain_error", language))
    try:
        host = value.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ValueError(translate("vault_domain_error", language)) from exc
    try:
        ipaddress.ip_address(host)
        is_ip = True
    except ValueError:
        is_ip = False
    if (is_ip or len(host.rstrip(".")) > 204 or not is_public_host(host)
            or is_reserved_example_url(f"https://{host}/")):
        raise ValueError(translate("vault_domain_error", language))
    return host.rstrip(".")


class CanaryURLCycle:
    """Assign supplied URLs once each, then repeat the shuffled list."""

    def __init__(self, values):
        self._values = list(values)
        secrets.SystemRandom().shuffle(self._values)
        self._index = 0

    def next(self):
        if not self._values:
            return ""
        value = self._values[self._index % len(self._values)]
        self._index += 1
        return value


def identifier(value, language="ja"):
    if (not isinstance(value, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,47}", value)
            or value.lower().startswith("sqlite_")):
        raise ValueError(translate("identifier_error", language))
    return value


def filename(value, language="ja"):
    value = text(value, "filename", 64, language)
    # Extensions are assigned by the renderer; paths and device names are not allowed.
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value)
            or re.fullmatch(r"(?i:CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])", value)):
        raise ValueError(translate("filename_error", language))
    return value
