"""Check local document links and reject invalid UTF-8, replacement and C1 characters."""

from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = (
    ROOT / ".github" / "README.md",
    ROOT / "README_ja.md",
    ROOT / "README.md",
    ROOT / "READM.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "SECURITY.md",
    *sorted((ROOT / "docs").glob("*.md")),
    *sorted((ROOT / "docs").glob("*.html")),
)
UI_SOURCE_FILES = (
    ROOT / "web" / "index.html",
    ROOT / "web" / "app.js",
    ROOT / "aideceptionguard" / "i18n.py",
)
CODE_SOURCE_FILES = (
    ROOT / "app.py",
    ROOT / "decrypt.py",
    *(source for directory in ("aideceptionguard", "examples", "scripts", "tests")
      for source in sorted((ROOT / directory).glob("*.py"))),
)
PUBLIC_FORM_FILES = tuple(sorted((ROOT / ".github" / "ISSUE_TEMPLATE").glob("*.yml")))
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)")
MARKDOWN_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
INLINE_MARKUP = re.compile(r"[`*_~]|!?\[([^\]]*)\]\([^)]*\)|<[^>]*>")
FENCE_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
FENCE_CLOSE = re.compile(r"^ {0,3}(`+|~+)[ \t]*$")


def read_utf8(source: Path) -> str:
    """Read a source file and report invalid UTF-8 with a useful line number."""
    raw = source.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        line_number = raw[:error.start].count(b"\n") + 1
        raise ValueError(f"{source}: invalid UTF-8 at line {line_number}, byte {error.start}") from error


class HTMLDocument(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.links = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.add(attributes["id"])
        if tag.lower() == "a" and attributes.get("name"):
            self.ids.add(attributes["name"])
        if attributes.get("href"):
            self.links.append(attributes["href"])


def local_target(source: Path, value: str) -> Path | None:
    value = unescape(value.strip().strip("<>"))
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc:
        return None
    if not parsed.path:
        return source if parsed.fragment else None
    return source.parent / unquote(parsed.path)


def github_slug(heading: str) -> str:
    heading = INLINE_MARKUP.sub(lambda match: match.group(1) or "", heading)
    heading = unescape(heading).strip().lower()
    heading = re.sub(r"[^\w -]", "", heading, flags=re.UNICODE)
    return re.sub(r"\s+", "-", heading).strip("-")


def outside_fenced_code(lines):
    """Yield source lines outside CommonMark fenced code blocks.

    A closing fence must use the same marker and at least as many characters
    as its opener. In particular, a triple-backtick line inside a four-backtick
    example must not hide the remainder of the document from link checking.
    """
    fence_character = None
    fence_length = 0
    for line_number, line in enumerate(lines, 1):
        if fence_character is None:
            match = FENCE_OPEN.match(line)
            if match:
                marker, info = match.groups()
                if marker[0] != "`" or "`" not in info:
                    fence_character = marker[0]
                    fence_length = len(marker)
                    continue
            yield line_number, line
            continue

        match = FENCE_CLOSE.match(line)
        if match:
            marker = match.group(1)
            if marker[0] == fence_character and len(marker) >= fence_length:
                fence_character = None
                fence_length = 0


def markdown_ids(source: Path) -> set[str]:
    identifiers = set()
    for _, line in outside_fenced_code(read_utf8(source).splitlines()):
        match = MARKDOWN_HEADING.match(line)
        if not match:
            continue
        base = github_slug(match.group(1))
        slug, suffix = base, 0
        while slug in identifiers:
            suffix += 1
            slug = f"{base}-{suffix}"
        identifiers.add(slug)
    parser = HTMLDocument()
    parser.feed(read_utf8(source))
    identifiers.update(parser.ids)
    return identifiers


def markdown_targets(source: Path):
    for line_number, line in outside_fenced_code(read_utf8(source).splitlines()):
        for match in MARKDOWN_LINK.finditer(line):
            target = local_target(source, match.group(1))
            if target is not None:
                yield line_number, target, unquote(urlsplit(match.group(1)).fragment)


def html_targets(source: Path):
    parser = HTMLDocument()
    parser.feed(read_utf8(source))
    for value in parser.links:
        target = local_target(source, value)
        if target is not None:
            yield 0, target, unquote(urlsplit(value).fragment)


def document_encoding_issues(source: Path):
    """Report replacement and C1 control characters left by mojibake."""
    for line_number, line in enumerate(read_utf8(source).splitlines(), 1):
        for character in line:
            codepoint = ord(character)
            if character == "\ufffd" or 0x80 <= codepoint <= 0x9F:
                yield line_number, f"U+{codepoint:04X}"


def main() -> int:
    missing = []
    encoding_issues = []
    for source in DOCUMENTS:
        if not source.is_file():
            missing.append((source, 0, source))
            continue
        try:
            encoding_issues.extend((source, line_number, codepoint)
                                   for line_number, codepoint in document_encoding_issues(source))
            extractor = html_targets if source.suffix.lower() == ".html" else markdown_targets
            for line_number, target, fragment in extractor(source):
                if not target.exists():
                    missing.append((source, line_number, target))
                elif fragment and fragment not in markdown_ids(target):
                    missing.append((source, line_number, target.with_name(f"{target.name}#{fragment}")))
        except ValueError as error:
            print(error, file=sys.stderr)
            return 1
    text_sources = tuple(dict.fromkeys((*UI_SOURCE_FILES, *CODE_SOURCE_FILES, *PUBLIC_FORM_FILES)))
    for source in text_sources:
        if source.is_file():
            try:
                encoding_issues.extend((source, line_number, codepoint)
                                       for line_number, codepoint in document_encoding_issues(source))
            except ValueError as error:
                print(error, file=sys.stderr)
                return 1
        else:
            missing.append((source, 0, source))

    if missing or encoding_issues:
        for source, line_number, target in missing:
            print(f"{source.relative_to(ROOT)}:{line_number}: missing local target {target}")
        for source, line_number, codepoint in encoding_issues:
            print(f"{source.relative_to(ROOT)}:{line_number}: suspicious document character {codepoint}")
        return 1
    print(f"Checked local links in {len(DOCUMENTS)} documents and text integrity in "
          f"{len(UI_SOURCE_FILES)} UI sources, {len(CODE_SOURCE_FILES)} Python sources and "
          f"{len(PUBLIC_FORM_FILES)} public forms.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
