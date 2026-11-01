"""Validate the checked-in integration-kit allowlist without building the ZIP."""
import ast
import operator
from pathlib import Path, PurePosixPath
import sys


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
FORBIDDEN_PARTS = {
    ".env", ".secrets", "generated", "tests", "__pycache__", ".venv", "venv",
}
FORBIDDEN_SUFFIXES = {
    ".operator.json", ".inventory.json", ".pem", ".key", ".p12", ".pfx",
}
REQUIRED_FILES = {
    "LICENSE", "README.md", "READM.md", "README_ja.md",
    "docs/deployment_ja.md", "docs/deployment_en.md",
    "docs/log-review-guide_ja.md", "docs/log-review-guide_en.md",
    "docs/legal_ja.md", "docs/legal_en.md",
    "examples/nginx-decoy.conf", "examples/decoy-contact-sample.jsonl",
    "examples/nginx-stream-proxy.conf", "examples/nginx-stream-token.conf.example",
    "examples/verify_inventory.py",
}


def assignments(module):
    found = {}
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found[target.id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            found[node.target.id] = node.value
    return found


def integer_constant(node):
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in (ast.Add, ast.Mult):
        operation = operator.add if isinstance(node.op, ast.Add) else operator.mul
        return operation(integer_constant(node.left), integer_constant(node.right))
    raise ValueError("size limit must be an integer literal or a simple +/* expression")


def main():
    try:
        module = ast.parse(APP.read_text(encoding="utf-8"), filename=str(APP))
        values = assignments(module)
        files = ast.literal_eval(values["INTEGRATION_BUNDLE_FILES"])
        size_limit = integer_constant(values["MAX_INTEGRATION_BUNDLE_BYTES"])
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError) as exc:
        print(f"Cannot inspect integration bundle manifest: {exc}", file=sys.stderr)
        return 2

    if not isinstance(files, tuple) or not files or type(size_limit) is not int or size_limit <= 0:
        print("Integration bundle manifest must be a non-empty tuple with a positive size limit",
              file=sys.stderr)
        return 2

    errors = []
    seen = set()
    total_size = 0
    for item in files:
        if not isinstance(item, str):
            errors.append(f"non-string bundle path: {item!r}")
            continue
        path = PurePosixPath(item)
        normalized = path.as_posix()
        if (path.is_absolute() or not path.parts or normalized != item
                or any(part in ("", ".", "..") for part in path.parts)):
            errors.append(f"non-portable or unsafe bundle path: {item!r}")
            continue
        key = normalized.casefold()
        if key in seen:
            errors.append(f"duplicate bundle path: {item}")
        seen.add(key)
        if any(part.casefold() in FORBIDDEN_PARTS for part in path.parts):
            errors.append(f"operator, generated, or development path in bundle: {item}")
        if path.name.casefold().startswith(".env") or path.name.casefold().endswith(
                tuple(suffix.casefold() for suffix in FORBIDDEN_SUFFIXES)):
            errors.append(f"sensitive artifact type in bundle: {item}")

        candidate = ROOT.joinpath(*path.parts)
        try:
            current = ROOT
            for part in path.parts:
                current = current / part
                if current.is_symlink():
                    errors.append(f"symbolic link in bundle path: {item}")
                    break
            resolved = candidate.resolve(strict=True)
            if not resolved.is_relative_to(ROOT):
                errors.append(f"bundle path escapes project root: {item}")
            elif not resolved.is_file():
                errors.append(f"bundle entry is not a regular file: {item}")
            else:
                total_size += resolved.stat().st_size
        except OSError as exc:
            errors.append(f"missing or unreadable bundle entry {item}: {exc}")

    if total_size > size_limit:
        errors.append(f"bundle source total {total_size} exceeds {size_limit} bytes")
    missing_required = sorted(path for path in REQUIRED_FILES if path.casefold() not in seen)
    if missing_required:
        errors.append("required user guidance or integration examples missing from bundle: "
                      + ", ".join(missing_required))

    if errors:
        print("Integration bundle manifest problems:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1

    print(f"Integration bundle allowlist is safe: {len(files)} unique files, "
          f"{total_size} source bytes (limit {size_limit}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
