"""Verify generated artifacts against a separately stored ADG inventory."""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat
import sys


SAFE_BASENAME = re.compile(r"(?:\.env(?:\.[A-Za-z0-9_-]+)*|[A-Za-z0-9][A-Za-z0-9_.-]{0,254})\Z")
WINDOWS_DEVICE_NAME = re.compile(r"(?i)(?:CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])\Z")
SHA256_HEX = re.compile(r"[0-9a-f]{64}\Z")
MAX_INVENTORY_BYTES = 8 * 1024 * 1024
MAX_ARTIFACT_BYTES = 128 * 1024 * 1024
MAX_BROWSER_RENAMED_CANDIDATES = 100
MAX_DIRECTORY_ENTRIES = 100_000


def safe_display(value):
    """Escape controls and bidi formatting before writing untrusted names to a terminal."""
    printable = "".join(
        character if character.isprintable() else
        (f"\\u{ord(character):04x}" if ord(character) <= 0xFFFF else f"\\U{ord(character):08x}")
        for character in str(value))
    return json.dumps(printable, ensure_ascii=False)[1:-1]


def unique_object(pairs):
    result = {}
    keys = set()
    for key, value in pairs:
        normalized = key.casefold()
        if normalized in keys:
            raise ValueError("Duplicate JSON key in inventory")
        keys.add(normalized)
        result[key] = value
    return result


def reject_non_json_constant(value):
    raise ValueError(f"Invalid JSON constant: {value}")


def safe_basename(value):
    if (not isinstance(value, str) or len(value) > 255
            or not SAFE_BASENAME.fullmatch(value) or value.endswith(".")):
        return False
    # Windows reserves device names even when an extension is present.
    stem = value.split(".", 1)[0]
    return not WINDOWS_DEVICE_NAME.fullmatch(stem)


def readonly_flags():
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    # These protect against final-component links and blocking special files
    # on platforms that provide the corresponding open flags.
    return flags | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)


def file_identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def read_inventory(path):
    path_initial = os.stat(path, follow_symlinks=False)
    if not stat.S_ISREG(path_initial.st_mode):
        raise ValueError("Inventory must be a regular file")
    descriptor = os.open(path, readonly_flags())
    with os.fdopen(descriptor, "rb") as source:
        initial = os.fstat(source.fileno())
        if (not stat.S_ISREG(initial.st_mode)
                or file_identity(path_initial) != file_identity(initial)):
            raise ValueError("Inventory path changed while opening")
        if initial.st_size > MAX_INVENTORY_BYTES:
            raise ValueError(f"Inventory exceeds {MAX_INVENTORY_BYTES} bytes")
        raw = source.read(MAX_INVENTORY_BYTES + 1)
        final = os.fstat(source.fileno())
        path_final = os.stat(path, follow_symlinks=False)
        if len(raw) > MAX_INVENTORY_BYTES:
            raise ValueError(f"Inventory exceeds {MAX_INVENTORY_BYTES} bytes")
        if (file_identity(initial) != file_identity(final)
                or file_identity(final) != file_identity(path_final)):
            raise ValueError("Inventory changed during reading")
    inventory = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                           parse_constant=reject_non_json_constant)
    if not isinstance(inventory, dict) or inventory.get("schema") != "adg-deployment-v1":
        raise ValueError("Unsupported inventory schema")
    return inventory


def expected_artifacts(inventory, include_packages):
    artifact = inventory.get("artifact")
    if not isinstance(artifact, dict):
        raise ValueError("Inventory is missing the primary artifact")
    operator_files = inventory.get("operator_files")
    operator_artifacts = inventory.get("operator_artifacts")
    if (not isinstance(operator_files, list) or any(not isinstance(name, str) for name in operator_files)
            or not isinstance(operator_artifacts, list)
            or operator_files != [record.get("name") for record in operator_artifacts
                                  if isinstance(record, dict)]
            or len(operator_files) != len(operator_artifacts)):
        raise ValueError("Inventory operator file list does not match its artifact records")
    expected = [("deployment", artifact)]
    for key, category in (("deployment_packages", "deployment package"),
                          ("operator_artifacts", "operator-only artifact")):
        records = inventory.get(key)
        if not isinstance(records, list):
            raise ValueError(f"Inventory field {key} must be an array")
        if any(not isinstance(record, dict) for record in records):
            raise ValueError(f"Inventory field {key} contains an invalid record")
        if category != "deployment package" or include_packages:
            expected.extend((category, record) for record in records)

    names = set()
    # Validate every record, including optional packages, before deciding which
    # directories to inspect. An omitted package directory must not hide a
    # malformed or ambiguous inventory entry.
    all_records = [("deployment", artifact)]
    for key, category in (("deployment_packages", "deployment package"),
                          ("operator_artifacts", "operator-only artifact")):
        records = inventory.get(key)
        all_records.extend((category, record) for record in records)
    for category, record in all_records:
        name = record.get("name")
        digest = record.get("sha256")
        size = record.get("bytes")
        if (not safe_basename(name)
                or not isinstance(digest, str) or not SHA256_HEX.fullmatch(digest)):
            raise ValueError("Inventory contains an invalid artifact name or SHA-256")
        if (isinstance(size, bool) or not isinstance(size, int)
                or size < 0 or size > MAX_ARTIFACT_BYTES):
            raise ValueError(f"Inventory has an invalid size for {name}")
        if name.casefold() in names:
            raise ValueError(f"Inventory lists {name} more than once")
        names.add(name.casefold())
    inventory_file = inventory.get("inventory_file")
    if inventory_file is not None:
        primary_name = artifact.get("name")
        if not safe_basename(primary_name):
            raise ValueError("Inventory primary artifact has no valid name")
        expected_inventory_file = primary_name + ".inventory.json"
        if inventory_file != expected_inventory_file:
            raise ValueError("Inventory filename does not match the primary artifact")
        if inventory_file.casefold() in names:
            raise ValueError("Inventory filename collides with a listed artifact")
    return expected


def hash_file(path, expected_size=None, base=None, expected_resolved=None):
    digest = hashlib.sha256()
    size = 0
    # Compare the path entry with the opened descriptor. This closes the
    # resolve-then-open gap on platforms where O_NOFOLLOW is unavailable and
    # detects a final-component replacement while hashing.
    path_initial = os.stat(path, follow_symlinks=False)
    if not stat.S_ISREG(path_initial.st_mode):
        return None, path_initial.st_size
    resolved_initial = Path(path).resolve(strict=True)
    if ((base is not None and not resolved_initial.is_relative_to(base))
            or (expected_resolved is not None and resolved_initial != expected_resolved)):
        return None, path_initial.st_size
    descriptor = os.open(path, readonly_flags())
    with os.fdopen(descriptor, "rb") as source:
        initial = os.fstat(source.fileno())
        initial_size = initial.st_size
        resolved_open = Path(path).resolve(strict=True)
        if (not stat.S_ISREG(initial.st_mode) or initial_size > MAX_ARTIFACT_BYTES
                or file_identity(path_initial) != file_identity(initial)
                or resolved_open != resolved_initial
                or (base is not None and not resolved_open.is_relative_to(base))
                or (expected_size is not None and initial_size != expected_size)):
            return None, initial_size
        while chunk := source.read(min(1024 * 1024, MAX_ARTIFACT_BYTES + 1 - size)):
            digest.update(chunk)
            size += len(chunk)
            if size > MAX_ARTIFACT_BYTES:
                return None, size
        final = os.fstat(source.fileno())
        path_final = os.stat(path, follow_symlinks=False)
        resolved_final = Path(path).resolve(strict=True)
        if (size != final.st_size or file_identity(initial) != file_identity(final)
                or file_identity(final) != file_identity(path_final)
                or resolved_final != resolved_initial
                or (base is not None and not resolved_final.is_relative_to(base))):
            return None, size
    return digest.hexdigest(), size


def inspect_artifact(path, base, record):
    if path.is_symlink():
        return False, "missing or not a regular file"
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError:
        return None, "missing"
    except (OSError, RuntimeError):
        return False, "missing or not a regular file"
    if not resolved.is_relative_to(base) or not resolved.is_file():
        return False, "missing, outside directory, or not a regular file"
    try:
        digest, size = hash_file(path, record.get("bytes"), base=base, expected_resolved=resolved)
    except OSError:
        return False, "unreadable or changed during verification"
    if digest is None:
        return False, "size mismatch, changed during verification, or exceeds 128 MiB limit"
    size_matches = size == record["bytes"]
    if hmac.compare_digest(digest, record["sha256"]) and size_matches:
        return True, "verified"
    return False, "hash or size mismatch"


def directory_entry_names(base):
    names = []
    with os.scandir(base) as entries:
        for entry in entries:
            names.append(entry.name)
            if len(names) > MAX_DIRECTORY_ENTRIES:
                raise ValueError("Verification directory has too many entries; narrow the directory")
    return names


def resolve_plain_directory(path, label):
    """Resolve a real directory while rejecting symlink and reparse-point roots."""
    path = Path(path)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

    def require_plain_directory(info):
        attributes = getattr(info, "st_file_attributes", 0)
        return (stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode)
                and not attributes & reparse_flag)

    before = os.stat(path, follow_symlinks=False)
    if not require_plain_directory(before):
        raise ValueError(f"{label} must be a regular directory, not a link or reparse point")
    resolved = path.resolve(strict=True)
    after = os.stat(path, follow_symlinks=False)
    resolved_after = path.resolve(strict=True)
    if (not require_plain_directory(after) or file_identity(before) != file_identity(after)
            or resolved != resolved_after):
        raise ValueError(f"{label} changed while being resolved")
    return resolved


def directory_tree_entry_names(base):
    """List basenames and links without following them, bounded across the tree."""
    names = []
    links = []
    pending = [base]
    visited = {os.path.normcase(str(base))}
    while pending:
        current = pending.pop()
        with os.scandir(current) as entries:
            for entry in entries:
                names.append(entry.name)
                if len(names) > MAX_DIRECTORY_ENTRIES:
                    raise ValueError("Deployment tree has too many entries; narrow the directory")
                if entry.is_symlink():
                    links.append(str(Path(entry.path).relative_to(base)))
                    continue
                is_junction = getattr(entry, "is_junction", None)
                if is_junction and is_junction():
                    links.append(str(Path(entry.path).relative_to(base)))
                    continue
                if entry.is_dir(follow_symlinks=False):
                    try:
                        resolved = Path(entry.path).resolve(strict=True)
                    except (OSError, RuntimeError):
                        continue
                    resolved_key = os.path.normcase(str(resolved))
                    if resolved.is_relative_to(base) and resolved_key not in visited:
                        visited.add(resolved_key)
                        pending.append(Path(entry.path))
    return names, links


def browser_renamed_candidates(base, names, entry_names):
    expected = {name.casefold(): name for name in names}
    candidates = {name: [] for name in expected.values()}
    pattern = re.compile(r"(.+) \(([1-9][0-9]*)\)(\.[^.]+)?\Z", re.IGNORECASE)
    for entry_name in entry_names:
        match = pattern.fullmatch(entry_name)
        if not match:
            continue
        original_name = expected.get((match.group(1) + (match.group(3) or "")).casefold())
        if original_name is not None:
            candidates[original_name].append((int(match.group(2)), base / entry_name))
            if len(candidates[original_name]) > MAX_BROWSER_RENAMED_CANDIDATES:
                raise ValueError("Too many browser-renamed candidates; narrow the verification directory")
    return {name: [path for _, path in sorted(matches)] for name, matches in candidates.items()}


def verify(inventory_path, directory=None, operator_directory=None, package_directory=None):
    inventory_path = Path(inventory_path)
    if inventory_path.is_symlink():
        raise ValueError("Do not use a symbolic link as the inventory file")
    inventory = read_inventory(inventory_path)
    expected = expected_artifacts(inventory, include_packages=package_directory is not None)
    deployment_base = resolve_plain_directory(
        Path(directory) if directory else inventory_path.parent, "Deployment directory")
    operator_base = resolve_plain_directory(
        Path(operator_directory) if operator_directory else inventory_path.parent, "Operator directory")
    package_base = (resolve_plain_directory(Path(package_directory), "Package directory")
                    if package_directory else None)
    results = []
    if deployment_base == operator_base:
        results.append((False, "directory separation", str(operator_base),
                        "deployment and operator directories are identical; separation cannot be verified"))
    missing_by_directory = {}
    for category, record in expected:
        name = record["name"]
        if category == "operator-only artifact":
            base = operator_base
        elif category == "deployment package":
            base = package_base
        else:
            base = deployment_base
        path = base / name
        # Resolve candidates and require them to remain inside their designated
        # directory. This also rejects directory junctions/reparse points that
        # escape a base directory without making the final component a symlink.
        passed, detail = inspect_artifact(path, base, record)
        if passed is None:
            missing_by_directory.setdefault(base, []).append((len(results), name, record))
        results.append((passed, category, name, detail))
    for base, missing in missing_by_directory.items():
        candidates = browser_renamed_candidates(
            base, [name for _, name, _ in missing], directory_entry_names(base))
        for result_index, name, record in missing:
            renamed = []
            for candidate in candidates[name]:
                candidate_passed, _ = inspect_artifact(candidate, base, record)
                if candidate_passed:
                    renamed.append(candidate.name)
            if renamed:
                detail = f"verified after browser rename: {', '.join(renamed)}"
                passed = True
            else:
                detail = "missing or not a regular file"
                passed = False
            _previous, category, result_name, _previous_detail = results[result_index]
            results[result_index] = (passed, category, result_name, detail)

    # Do not allow the deployment tree to expose content through links.
    tree_names, deployment_links = directory_tree_entry_names(deployment_base)
    for link_name in deployment_links:
        results.append((False, "deployment link", link_name,
                        "symbolic links and directory junctions are not allowed in the deployment tree"))

    # A valid private copy does not prove the operator companions were kept out
    # of the public deployment root. Check the public root for the exact names
    # recorded by the trusted inventory, and reject a private directory nested
    # under the deployment tree.
    if deployment_base != operator_base:
        if operator_base.is_relative_to(deployment_base):
            results.append((False, "operator directory", str(operator_base),
                            "inside the deployment directory tree"))
        try:
            inventory_resolved = inventory_path.resolve(strict=True)
        except OSError as exc:
            raise ValueError("Inventory path changed during verification") from exc
        inventory_inside_deployment = inventory_resolved.is_relative_to(deployment_base)
        if inventory_inside_deployment:
            results.append((False, "operator-only artifact", inventory_resolved.name,
                            "inventory file is inside the deployment directory tree"))
        deployed_names = {name.casefold() for name in tree_names}
        private_names = list(inventory.get("operator_files", []))
        inventory_name = inventory.get("inventory_file")
        if inventory_name:
            private_names.append(inventory_name)
        private_name_keys = {name.casefold() for name in private_names}
        renamed_private_names = set()
        renamed_pattern = re.compile(r"(.+) \(([1-9][0-9]*)\)(\.[^.]+)?\Z", re.IGNORECASE)
        for deployed_name in deployed_names:
            match = renamed_pattern.fullmatch(deployed_name)
            if match:
                original_name = (match.group(1) + (match.group(3) or "")).casefold()
                if original_name in private_name_keys:
                    renamed_private_names.add(original_name)
        for name in private_names:
            name_key = name.casefold()
            if ((name_key in deployed_names or name_key in renamed_private_names)
                    and not (inventory_inside_deployment and isinstance(inventory_name, str)
                             and name_key == inventory_name.casefold())):
                results.append((False, "operator-only artifact", name,
                                "also present (possibly browser-renamed) in the deployment directory tree"))
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Verify generated files against a separately protected ADG inventory.")
    parser.add_argument("inventory", type=Path, help="Path to the private *.inventory.json file")
    parser.add_argument("--directory", type=Path,
                        help="Deployment-file directory (defaults to the inventory directory; must differ from --operator-directory)")
    parser.add_argument("--operator-directory", type=Path,
                        help="Operator-only file directory (defaults to the inventory directory; must differ from --directory)")
    parser.add_argument("--package-directory", type=Path,
                        help="Optional directory containing original deployment ZIP packages to verify")
    args = parser.parse_args()
    try:
        inventory_parent = args.inventory.resolve(strict=False).parent
        deployment_directory = (args.directory.resolve(strict=False)
                                if args.directory else inventory_parent)
        operator_directory = (args.operator_directory.resolve(strict=False)
                              if args.operator_directory else inventory_parent)
        if deployment_directory == operator_directory:
            print("WARNING: Deployment and operator directories are the same; verification will fail because separation cannot be confirmed.",
                  file=sys.stderr)
        results = verify(args.inventory, args.directory, args.operator_directory, args.package_directory)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, RecursionError, RuntimeError) as exc:
        print(f"Cannot verify inventory: {safe_display(exc)}", file=sys.stderr)
        return 2

    for passed, category, name, detail in results:
        state = "OK" if passed else "FAIL"
        print(f"{state} [{safe_display(category)}] {safe_display(name)}: {safe_display(detail)}")
    failures = sum(not passed for passed, *_ in results)
    print(f"Passed {len(results) - failures}/{len(results)} checks")
    print("NOTICE: The inventory was trusted as the reference; its own integrity is not verified by this command.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
