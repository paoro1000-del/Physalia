"""Heuristically flag common executable HTML/JavaScript sinks in browser code."""
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCES = (ROOT / "web" / "app.js", ROOT / "web" / "json_utils.js")
FORBIDDEN = {
    "HTML assignment": re.compile(
        r"(?:\.\s*(?:innerHTML|outerHTML)\b|\[\s*['\"](?:innerHTML|outerHTML)['\"]\s*\])\s*="),
    "HTML insertion": re.compile(
        r"(?:\.\s*insertAdjacentHTML\b|\[\s*['\"]insertAdjacentHTML['\"]\s*\])\s*\("),
    "document.write": re.compile(
        r"(?:\bdocument\s*\.\s*write\b|\bdocument\s*\[\s*['\"]write['\"]\s*\])\s*\("),
    "dynamic evaluation": re.compile(r"\b(?:eval|Function)\s*\("),
}


def main():
    findings = []
    for source in SOURCES:
        try:
            text = source.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            print(f"Cannot inspect browser source {source}: {exc}", file=sys.stderr)
            return 2
        for label, pattern in FORBIDDEN.items():
            for match in pattern.finditer(text):
                line_number = text.count("\n", 0, match.start()) + 1
                findings.append(f"{source.relative_to(ROOT)}:{line_number}: {label}")
    if findings:
        print("Unsafe browser DOM or code execution sinks require review:", file=sys.stderr)
        print("\n".join(f"- {finding}" for finding in findings), file=sys.stderr)
        return 1
    print(f"No listed unsafe sink patterns found in {len(SOURCES)} browser sources; "
          "this heuristic does not prove DOM safety or detect indirect aliases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
