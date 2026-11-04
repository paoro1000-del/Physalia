"""Check that every HTML translation key has an English UI translation."""
from html.parser import HTMLParser
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
# These two helpers are rebuilt by the final compact .env copy below; the
# earlier detail-oriented text is intentionally superseded.
FINAL_TRANSLATION_OVERRIDES = {"ja.quick_env_help", "en.quick_env_help"}


class TranslationKeyParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.app_keys = set()
        self.corrupt_text = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if isinstance(value, str) and ("???" in value or "\ufffd" in value):
                self.corrupt_text.append(f"{name}={value[:80]!r}")
            if name in ("data-i18n", "data-i18n-aria", "data-i18n-placeholder") and value:
                self.app_keys.add(value)

    handle_startendtag = handle_starttag

    def handle_data(self, data):
        if "???" in data or "\ufffd" in data:
            sample = " ".join(data.split())
            if sample:
                self.corrupt_text.append(sample[:100])


def english_translation_keys(source, container_marker, english_marker, assignment_prefix):
    marker_start = source.index(english_marker, source.index(container_marker))
    start = marker_start + len(english_marker)

    depth = 1
    quote = None
    escaped = False
    line_comment = False
    block_comment = False
    end = None
    index = start
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if line_comment:
            if char in "\r\n":
                line_comment = False
        elif block_comment:
            if char == "*" and following == "/":
                block_comment = False
                index += 1
        elif quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char == "/" and following == "/":
            line_comment = True
            index += 1
        elif char == "/" and following == "*":
            block_comment = True
            index += 1
        elif char in "'\"`":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = index
                break
        index += 1
    if end is None:
        raise ValueError("Could not find the end of the English translation object")

    body = source[start:end]
    keys = set()
    depth = 0
    quote = None
    escaped = False
    line_comment = False
    block_comment = False
    last = 0
    parts = []
    index = 0
    while index < len(body):
        char = body[index]
        following = body[index + 1] if index + 1 < len(body) else ""
        if line_comment:
            if char in "\r\n":
                line_comment = False
        elif block_comment:
            if char == "*" and following == "/":
                block_comment = False
                index += 1
        elif quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char == "/" and following == "/":
            line_comment = True
            index += 1
        elif char == "/" and following == "*":
            block_comment = True
            index += 1
        elif char in "'\"`":
            quote = char
        elif char in "{[(":
            depth += 1
        elif char in "}])":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(body[last:index])
            last = index + 1
        index += 1
    parts.append(body[last:])

    for part in parts:
        match = re.match(r"\s*([A-Za-z_$][\w$]*)\s*:", part)
        if match:
            keys.add(match.group(1))
    keys.update(re.findall(rf"{re.escape(assignment_prefix)}\.([A-Za-z_$][\w$]*)\s*=", source))
    # Several translation groups are appended with Object.assign rather than
    # direct property assignments. Parse their top-level keys while ignoring
    # commas and braces inside strings, so translated UI keys are not reported
    # as missing merely because they use that common JavaScript pattern.
    marker = f"Object.assign({assignment_prefix}, {{"
    cursor = 0
    while True:
        call = source.find(marker, cursor)
        if call < 0:
            break
        opening = call + len(marker) - 1
        keys.update(top_level_object_keys(source, opening))
        cursor = opening + 1
    return keys


def overwritten_translation_appends(source):
    """Find appended UI text that a later direct or object assignment replaces."""
    events = {}
    pattern = re.compile(r"\btranslations\.(ja|en)\.([A-Za-z_$][\w$]*)\s*(\+=|=(?!=))")
    for match in pattern.finditer(source):
        events.setdefault((match.group(1), match.group(2)), []).append(
            (match.group(3), match.start()))
    object_assign = re.compile(r"Object\.assign\(translations\.(ja|en),\s*\{")
    for match in object_assign.finditer(source):
        opening = match.end() - 1
        for key in top_level_object_keys(source, opening):
            events.setdefault((match.group(1), key), []).append(("=", match.start()))
    overwritten = []
    for (language, key), assignments in events.items():
        if f"{language}.{key}" in FINAL_TRANSLATION_OVERRIDES:
            continue
        for index, (operator, position) in enumerate(assignments):
            later_overwrite = any(next_operator == "=" and next_position > position
                                  for next_operator, next_position in assignments[index + 1:])
            # Some startup text is rebuilt from a concise prefix plus a suffix
            # retained from the earlier localized copy. That is not a lost append.
            next_assignment = next((next_position for next_operator, next_position
                                    in assignments[index + 1:]
                                    if next_operator == "=" and next_position > position), None)
            preserves_suffix = next_assignment is not None and re.search(
                rf"translations\.{language}\.{re.escape(key)}\s*=\s*[^\n]*"
                rf"translations\.{language}\.{re.escape(key)}\.slice\(",
                source[next_assignment:])
            if operator == "+=" and later_overwrite and not preserves_suffix:
                overwritten.append(f"{language}.{key}")
                break
    return sorted(overwritten)


def top_level_object_keys(source, opening):
    """Read property names from a JavaScript object literal at opening."""
    depth = 0
    quote = None
    escaped = False
    line_comment = False
    block_comment = False
    last = opening + 1
    parts = []
    index = opening
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if line_comment:
            if char in "\r\n":
                line_comment = False
        elif block_comment:
            if char == "*" and following == "/":
                block_comment = False
                index += 1
        elif quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char == "/" and following == "/":
            line_comment = True
            index += 1
        elif char == "/" and following == "*":
            block_comment = True
            index += 1
        elif char in "'\"`":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                parts.append(source[last:index])
                break
        elif char == "," and depth == 1:
            parts.append(source[last:index])
            last = index + 1
        index += 1
    return {match.group(1) for part in parts
            if (match := re.match(r"\s*([A-Za-z_$][\w$]*)\s*:", part))}


def literal_translation_calls(source, function_name):
    """Return literal keys passed to t(...) or tr(...)."""
    keys = set()
    call = re.compile(rf"\b{re.escape(function_name)}\s*\(")
    for match in call.finditer(source):
        index = match.end()
        while index < len(source) and source[index].isspace():
            index += 1
        if index >= len(source) or source[index] not in "'\"":
            continue
        quote = source[index]
        end = source.find(quote, index + 1)
        if end < 0:
            continue
        after = end + 1
        while after < len(source) and source[after].isspace():
            after += 1
        if after >= len(source) or source[after] not in "),":
            continue
        key = source[index + 1:end]
        if re.fullmatch(r"[A-Za-z_$][\w$]*", key):
            keys.add(key)
    return keys


def main():
    parser = TranslationKeyParser()
    parser.feed((ROOT / "web" / "index.html").read_text(encoding="utf-8"))
    app_source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    corrupt_scripts = {
        name: [marker for marker in ("???", "\ufffd") if marker in source]
        for name, source in (("web/app.js", app_source),)
    }
    corrupt_scripts = {name: markers for name, markers in corrupt_scripts.items() if markers}
    try:
        app_english = english_translation_keys(
            app_source, "const translations = {", "  en: {", "translations.en")
        app_keys = parser.app_keys | literal_translation_calls(app_source, "t")
        missing_app = sorted(app_keys - app_english)
        overwritten_appends = overwritten_translation_appends(app_source)
    except (ValueError, IndexError) as exc:
        print(f"Cannot inspect English translations: {exc}", file=sys.stderr)
        return 2
    if (missing_app or overwritten_appends or parser.corrupt_text or corrupt_scripts):
        if missing_app:
            print("Missing English translations for app UI keys:", file=sys.stderr)
            print("\n".join(f"- {key}" for key in missing_app), file=sys.stderr)
        if overwritten_appends:
            print("App translation text appended before a later overwrite:", file=sys.stderr)
            print("\n".join(f"- {key}" for key in overwritten_appends), file=sys.stderr)
        if parser.corrupt_text:
            print("Suspicious placeholder or replacement characters in the HTML UI:", file=sys.stderr)
            print("\n".join(f"- {text!r}" for text in parser.corrupt_text), file=sys.stderr)
        if corrupt_scripts:
            print("Suspicious placeholder or replacement characters in UI scripts:", file=sys.stderr)
            for name, markers in corrupt_scripts.items():
                print(f"- {name}: {', '.join(markers)}", file=sys.stderr)
        return 1
    print(f"English translations cover all {len(app_keys)} app UI keys.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
