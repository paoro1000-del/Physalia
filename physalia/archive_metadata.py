"""Metadata helpers for plausible, locally generated ZIP artifacts."""
from datetime import datetime, timedelta
import re
import secrets
import unicodedata
import zipfile

from physalia.i18n import translate

_WINDOWS_DEVICE_NAME = re.compile(
    r"(?i)(?:CON|PRN|AUX|NUL|COM[1-9\u00b9\u00b2\u00b3]|LPT[1-9\u00b9\u00b2\u00b3])(?:\..*)?\Z")


def _validate_member_name(name, language):
    """Reject traversal and non-portable paths before writing a ZIP member."""
    if (not isinstance(name, str) or not name or len(name) > 1024 or name.startswith("/")
            or "\\" in name or any(
                unicodedata.category(character) in ("Cc", "Cf", "Cs", "Zl", "Zp")
                or character in '<>:"|?*'
                for character in name
            )):
        raise ValueError(translate("invalid_input", language))
    parts = name.split("/")
    if any(not part or len(part) > 255 or part in (".", "..") or part.endswith((".", " "))
           or _WINDOWS_DEVICE_NAME.fullmatch(part) for part in parts):
        raise ValueError(translate("invalid_input", language))
    return name


def write_archive_member(archive, name, content, info_type=zipfile.ZipInfo, language="ja"):
    """Write a ZIP member with a recent, varied timestamp.

    ZipFile.writestr(name, content) otherwise assigns the DOS epoch
    (1980-01-01), which makes generated archives conspicuous to an offline
    reviewer. Timestamps are bounded to the previous 180 days and never
    intentionally set in the future.
    """
    name = _validate_member_name(name, language)
    now = datetime.now().astimezone().replace(tzinfo=None)
    modified = now - timedelta(seconds=secrets.randbelow(180 * 24 * 60 * 60 + 1))
    modified = modified.replace(second=(modified.second // 2) * 2, microsecond=0)
    info = info_type(name, date_time=modified.timetuple()[:6])
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, content)
