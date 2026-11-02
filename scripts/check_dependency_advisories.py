"""Check exact project pins against PyPI's release-specific advisory list.

This uses only the standard library and does not install or upgrade packages.
It detects published advisories, not malicious or compromised package files.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import json
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from check_dependency_pins import REQUIRED_FILES, pinned_requirements


ROOT = Path(__file__).resolve().parents[1]
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
TIMEOUT_SECONDS = 20
USER_AGENT = "Physalia-dependency-advisory-check/1.0"


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def pinned_dependencies():
    dependencies = {}
    files = sorted(ROOT.glob("requirements*.txt"), key=lambda item: item.name)
    present = {path.name for path in files}
    missing = REQUIRED_FILES - present
    if missing:
        raise ValueError("Required dependency file missing: " + ", ".join(sorted(missing)))

    for path in files:
        for name, version in pinned_requirements(path):
            normalized = re.sub(r"[-_.]+", "-", name.lower())
            if normalized in dependencies:
                raise ValueError(f"{path.name}: duplicate package pin: {name}")
            dependencies[normalized] = (name, version)
    return sorted(dependencies.values(), key=lambda item: item[0].casefold())


def inspect_release(dependency):
    name, version = dependency
    url = f"https://pypi.org/pypi/{quote(name, safe='')}/{quote(version, safe='')}/json"
    request = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Could not check {name}=={version}: {exc}") from exc
    if len(raw) > MAX_RESPONSE_BYTES:
        raise RuntimeError(f"PyPI response exceeded the size limit for {name}=={version}")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"Invalid PyPI response for {name}=={version}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("vulnerabilities"), list):
        raise RuntimeError(f"PyPI response lacks release advisory data for {name}=={version}")
    active = []
    for item in data["vulnerabilities"]:
        if not isinstance(item, dict):
            raise RuntimeError(f"Invalid advisory entry for {name}=={version}")
        withdrawn = item.get("withdrawn")
        if withdrawn not in (None, ""):
            if not isinstance(withdrawn, str):
                raise RuntimeError(f"Invalid advisory withdrawal value for {name}=={version}")
            try:
                withdrawn_at = datetime.fromisoformat(withdrawn.replace("Z", "+00:00"))
            except ValueError as exc:
                raise RuntimeError(f"Invalid advisory withdrawal date for {name}=={version}") from exc
            if withdrawn_at.tzinfo is None:
                raise RuntimeError(f"Invalid advisory withdrawal timezone for {name}=={version}")
        else:
            active.append(item)
    return name, version, active


def main():
    try:
        dependencies = pinned_dependencies()
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Cannot read pinned dependencies: {exc}", file=sys.stderr)
        return 2

    results = []
    errors = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(inspect_release, dependency): dependency for dependency in dependencies}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except RuntimeError as exc:
                errors.append(str(exc))

    if errors:
        print("Advisory scan could not verify every pinned release:", file=sys.stderr)
        for error in sorted(errors):
            print(f"- {error}", file=sys.stderr)
        return 2

    findings = []
    for name, version, advisories in sorted(results, key=lambda item: item[0].casefold()):
        for advisory in advisories:
            advisory_id = advisory.get("id", "unknown advisory")
            if not isinstance(advisory_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", advisory_id):
                advisory_id = "invalid advisory identifier"
            findings.append(f"{name}=={version}: {advisory_id}")
    if findings:
        print("Known, non-withdrawn PyPI advisories affect pinned releases:", file=sys.stderr)
        print("\n".join(f"- {finding}" for finding in findings), file=sys.stderr)
        return 1

    print(f"No active PyPI advisories found for {len(dependencies)} exact dependency pins.")
    print("This check does not detect malware, compromised files, or vulnerabilities in native libraries outside PyPI advisory data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
