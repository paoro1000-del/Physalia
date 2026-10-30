"""Reject floating or indirect dependency declarations in project requirements."""
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = {"requirements.txt", "requirements-dev.txt"}
PIN = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[A-Za-z0-9._,-]+\])?=="
    r"(?P<version>[A-Za-z0-9][A-Za-z0-9.!+_-]*)$"
)
HASH = re.compile(r"--hash=sha256:(?P<digest>[0-9a-f]{64})$")
BASE_INCLUDE = "-r requirements.txt"


def parse_file(path):
    errors = []
    pins = []
    includes = 0
    current = None
    hashes = set()
    continuation = False

    def finish(number):
        nonlocal current, hashes
        if current is not None:
            if not hashes:
                errors.append(f"{path.name}:{number}: dependency has no SHA-256 hashes")
            pins.append(current)
            current, hashes = None, set()

    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.partition("#")[0].strip()
        if not line:
            continue
        continued = line.endswith("\\")
        if continued:
            line = line[:-1].rstrip()
        if line.startswith("--hash="):
            if current is None or not continuation:
                errors.append(f"{path.name}:{number}: SHA-256 hash is not attached to a dependency")
                continuation = continued
                continue
            match = HASH.fullmatch(line)
            if not match:
                errors.append(f"{path.name}:{number}: use a full SHA-256 requirement hash")
            elif match.group("digest") in hashes:
                errors.append(f"{path.name}:{number}: duplicate SHA-256 hash")
            else:
                hashes.add(match.group("digest"))
            continuation = continued
            if not continuation:
                finish(number)
            continue
        if continuation:
            errors.append(f"{path.name}:{number}: dependency continuation must contain a SHA-256 hash")
            current, hashes, continuation = None, set(), False
        if path.name == "requirements-dev.txt" and line == BASE_INCLUDE:
            includes += 1
            continue
        match = PIN.fullmatch(line)
        if not match:
            errors.append(f"{path.name}:{number}: use an exact name==version pin followed by SHA-256 hashes: {line}")
            continue
        current = (match.group("name"), match.group("version"))
        continuation = continued
        if not continuation:
            errors.append(f"{path.name}:{number}: dependency must continue to at least one SHA-256 hash")
            finish(number)
    if current is not None:
        errors.append(f"{path.name}: dependency hash list ends with an incomplete continuation")
        finish("EOF")
    return pins, errors, includes


def check_file(path, pins_seen_in_other_files=None):
    pins_seen_in_other_files = pins_seen_in_other_files if pins_seen_in_other_files is not None else set()
    pins, errors, includes = parse_file(path)
    seen = set()
    for name, _version in pins:
        normalized = re.sub(r"[-_.]+", "-", name.lower())
        if normalized in seen:
            errors.append(f"{path.name}: duplicate dependency: {name}")
        if normalized in pins_seen_in_other_files:
            errors.append(f"{path.name}: dependency is also pinned in another requirements file: {name}")
        seen.add(normalized)
        pins_seen_in_other_files.add(normalized)
    if not pins:
        errors.append(f"{path.name}: no pinned dependencies found")
    if path.name == "requirements-dev.txt" and includes != 1:
        errors.append(f"{path.name}: include requirements.txt exactly once with {BASE_INCLUDE}")
    return errors


def pinned_requirements(path):
    pins, errors, _includes = parse_file(path)
    if errors:
        raise ValueError("; ".join(errors))
    return pins


def main():
    errors = []
    files = sorted(ROOT.glob("requirements*.txt"))
    present = {path.name for path in files}
    for missing in sorted(REQUIRED_FILES - present):
        errors.append(f"{missing}: required dependency file is missing")
    pins_seen_in_other_files = set()
    # Process the base set first so a conflicting development pin is reported
    # at the development-file entry that introduced the duplicate.
    for path in sorted(files, key=lambda item: (item.name != "requirements.txt", item.name)):
        errors.extend(check_file(path, pins_seen_in_other_files))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Dependency versions are exact and every pin has SHA-256 distribution hashes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
