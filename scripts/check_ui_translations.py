"""Check that every HTML translation key has an English UI translation."""
from html.parser import HTMLParser
import ast
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]


class TranslationKeyParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.app_keys = set()
        self.cloud_keys = set()

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in ("data-i18n", "data-i18n-aria") and value:
                self.app_keys.add(value)
            elif name == "data-cloud-i18n" and value:
                self.cloud_keys.add(value)

    handle_startendtag = handle_starttag


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
    return keys


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


def backend_review_rule_keys(source):
    module = ast.parse(source)
    for node in module.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "FINDING_PRIORITY"
                for target in node.targets):
            if isinstance(node.value, ast.Dict):
                return {key.value for key in node.value.keys
                        if isinstance(key, ast.Constant) and isinstance(key.value, str)}
    raise ValueError("Could not inspect backend review rule priorities")


def cloud_render_rule_keys(source):
    keys = set()
    for body in re.findall(r"rules\s*:\s*\{([^}]*)\}", source):
        keys.update(re.findall(r"(?:^|,)\s*([A-Za-z_$][\w$]*)\s*:\s*\[", body))
    keys.update(re.findall(r"copy\.(?:ja|en)\.rules\.([A-Za-z_$][\w$]*)\s*=", source))
    keys.update(re.findall(r"finding\.rule\s*===\s*['\"]([A-Za-z_$][\w$]*)['\"]", source))
    return keys


def main():
    parser = TranslationKeyParser()
    parser.feed((ROOT / "web" / "index.html").read_text(encoding="utf-8"))
    app_source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    cloud_source = (ROOT / "web" / "cloud_review.js").read_text(encoding="utf-8")
    backend_source = (ROOT / "aideceptionguard" / "cloud_review.py").read_text(encoding="utf-8")
    try:
        app_english = english_translation_keys(
            app_source, "const translations = {", "  en: {", "translations.en")
        cloud_english = english_translation_keys(
            cloud_source, "const copy = {", "    en: {", "copy.en")
        app_keys = parser.app_keys | literal_translation_calls(app_source, "t")
        cloud_keys = parser.cloud_keys | literal_translation_calls(cloud_source, "tr")
        missing_app = sorted(app_keys - app_english)
        missing_cloud = sorted(cloud_keys - cloud_english)
        backend_rules = backend_review_rule_keys(backend_source)
        missing_rules = sorted(backend_rules - cloud_render_rule_keys(cloud_source))
    except (ValueError, IndexError) as exc:
        print(f"Cannot inspect English translations: {exc}", file=sys.stderr)
        return 2
    if missing_app or missing_cloud or missing_rules:
        if missing_app:
            print("Missing English translations for app UI keys:", file=sys.stderr)
            print("\n".join(f"- {key}" for key in missing_app), file=sys.stderr)
        if missing_cloud:
            print("Missing English translations for cloud-panel keys:", file=sys.stderr)
            print("\n".join(f"- {key}" for key in missing_cloud), file=sys.stderr)
        if missing_rules:
            print("Backend review rules without a cloud-panel translation or explicit fallback:", file=sys.stderr)
            print("\n".join(f"- {key}" for key in missing_rules), file=sys.stderr)
        return 1
    print(f"English translations cover all {len(app_keys)} app UI and {len(cloud_keys)} cloud-panel keys; "
          f"all {len(backend_rules)} backend review rules have a panel description or fallback.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
