"""Check that browser generation settings and the backend API allowlist agree."""
import ast
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
MULTI_URL_LEGACY_KEYS = {"canary_url"}
DOMAIN_HELPER_KEYS = {"vault_domain", "vault_domain_authorized"}
PROPERTY = re.compile(r"^\s*([A-Za-z_$][\w$]*)\s*:")
BUILDER = re.compile(r"^\s*([A-Za-z_$][\w$]*)\s*:\s*\(\)\s*=>\s*\(\s*\{", re.S)


def matching_brace(source, opening):
    depth = 0
    quote = None
    escaped = False
    line_comment = block_comment = False
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
                return index
        index += 1
    raise ValueError("Could not find matching JavaScript object brace")


def split_top_level(source):
    depths = {"{": 0, "[": 0, "(": 0}
    closing = {"}": "{", "]": "[", ")": "("}
    quote = None
    escaped = False
    line_comment = block_comment = False
    parts = []
    last = 0
    index = 0
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
        elif char in depths:
            depths[char] += 1
        elif char in closing:
            depths[closing[char]] -= 1
        elif char == "," and not any(depths.values()):
            parts.append(source[last:index])
            last = index + 1
        index += 1
    parts.append(source[last:])
    return parts


def backend_allowlist(source):
    module = ast.parse(source)
    for node in module.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "SETTING_KEYS"
                for target in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError("Could not inspect backend SETTING_KEYS")


def browser_builders(source):
    marker = "settings = {"
    if marker not in source:
        raise ValueError("Could not find browser settings builder")
    opening = source.index("{", source.index(marker))
    end = matching_brace(source, opening)
    segments = split_top_level(source[opening + 1:end])
    builders = {}
    for segment in segments:
        match = BUILDER.match(segment)
        if not match:
            continue
        kind = match.group(1)
        object_opening = segment.index("{", match.start())
        object_end = matching_brace(segment, object_opening)
        emitted = set()
        for prop in split_top_level(segment[object_opening + 1:object_end]):
            property_match = PROPERTY.match(prop)
            if property_match:
                emitted.add(property_match.group(1))
            elif prop.lstrip().startswith("..."):
                if "vaultDomainSettings()" in prop:
                    emitted.update(DOMAIN_HELPER_KEYS)
                # Conditional filename object spreads use this literal key.
                if re.search(r"\bfilename\s*:", prop):
                    emitted.add("filename")
        builders[kind] = emitted
    if not builders:
        raise ValueError("No browser generation settings builders found")
    return builders


def main():
    try:
        backend = backend_allowlist(
            (ROOT / "physalia" / "generators.py").read_text(encoding="utf-8"))
        browser = browser_builders((ROOT / "web" / "app.js").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, SyntaxError, ValueError, TypeError) as exc:
        print(f"Cannot inspect generation setting parity: {exc}", file=sys.stderr)
        return 2

    errors = []
    if set(backend) != set(browser):
        errors.append("generator kinds differ: backend=" + ", ".join(sorted(backend))
                      + "; browser=" + ", ".join(sorted(browser)))
    for kind in sorted(set(backend) & set(browser)):
        accepted = set(backend[kind])
        emitted = browser[kind]
        rejected_by_backend = sorted(emitted - accepted)
        absent_from_ui = sorted(accepted - emitted - (
            MULTI_URL_LEGACY_KEYS if kind in ("nest", "directory_maze", "encoding_maze") else set()))
        if rejected_by_backend:
            errors.append(f"{kind}: browser sends backend-rejected keys: " + ", ".join(rejected_by_backend))
        if absent_from_ui:
            errors.append(f"{kind}: accepted settings missing from browser builder: " + ", ".join(absent_from_ui))

    if errors:
        print("Generation setting parity problems:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    print(f"Browser settings match the backend allowlist for {len(backend)} generation methods.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
