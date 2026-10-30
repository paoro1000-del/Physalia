"""Check that Nginx connection-limit outcomes survive conversion and review."""
from pathlib import Path
import json
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ("PASSED", "REJECTED", "REJECTED_DRY_RUN")
FILES = {
    "decoy Nginx config": "examples/nginx-decoy.conf",
    "stream Nginx config": "examples/nginx-stream-proxy.conf",
    "log converter": "examples/access_events.py",
    "backend analyzer": "aideceptionguard/cloud_review.py",
    "browser panel": "web/cloud_review.js",
    "fictional review sample": "examples/cloud-review-sample.json",
    "Japanese deployment guide": "docs/deployment_ja.md",
    "English deployment guide": "docs/deployment_en.md",
}


def main():
    sources = {}
    for label, relative in FILES.items():
        try:
            sources[label] = (ROOT / relative).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            print(f"Cannot inspect {label} ({relative}): {exc}", file=sys.stderr)
            return 2

    errors = []
    for label in ("decoy Nginx config", "stream Nginx config"):
        source = sources[label]
        for fragment in ("$limit_conn_status", "limit_conn_status 429", "1.17.6"):
            if fragment not in source:
                errors.append(f"{label} is missing {fragment}")

    for label in ("log converter", "backend analyzer", "browser panel"):
        source = sources[label]
        if "connection_limit_status" not in source:
            errors.append(f"{label} does not propagate connection_limit_status")

    converter = sources["log converter"]
    if 'record.get("limit_conn_status")' not in converter or 'result["connection_limit_status"]' not in converter:
        errors.append("log converter does not map Nginx's source field to the review field")
    backend = sources["backend analyzer"]
    if ('field(row, "connection_limit_status")' not in backend
            or 'finding["connection_limit_status"]' not in backend):
        errors.append("backend analyzer does not validate and preserve the review field")

    value_sets = {
        "log converter": re.findall(
            r'connection_status\s+in\s+\(([^)]*)\)', converter),
        "backend analyzer": re.findall(
            r'connection_limit_status\s+in\s+\(([^)]*)\)', backend),
    }
    browser = sources["browser panel"]
    branch_start = browser.find('normalizedKey === "connection_limit_status"')
    branch_end = browser.find("} else if", branch_start)
    branch = browser[branch_start:branch_end] if branch_start >= 0 and branch_end >= 0 else ""
    value_sets["browser panel"] = re.findall(r'\[([^\]]+)\]\.includes\(value\)', branch)
    for label, candidates in value_sets.items():
        if not candidates:
            errors.append(f"{label} has no explicit connection-limit status allowlist")
            continue
        found = set(re.findall(r'"([A-Z_]+)"', candidates[0]))
        if found != set(EXPECTED):
            errors.append(f"{label} allows {sorted(found)}, expected {sorted(EXPECTED)}")

    try:
        sample = json.loads(sources["fictional review sample"])
        sample_events = [row for row in sample if isinstance(row, dict)
                         and row.get("event") == "decoy_contact"]
    except (TypeError, json.JSONDecodeError):
        sample_events = []
    if not any(row.get("connection_limit_status") in EXPECTED for row in sample_events):
        errors.append("fictional review sample does not demonstrate a connection-limit status")

    if browser.count("connection_limit_status:") < 2:
        errors.append("browser panel is missing a Japanese or English field label")
    if '"connection_limit_status", "connection_limit_status"' not in browser:
        errors.append("browser panel does not render the connection status field")

    for label in ("Japanese deployment guide", "English deployment guide"):
        source = sources[label]
        if "connection_limit_status" not in source or "1.17.6" not in source:
            errors.append(f"{label} is missing the status field or Nginx version requirement")

    if errors:
        print("Connection-limit status parity problems:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1

    print("Connection-limit outcomes are wired through Nginx, conversion, backend review, UI and guides.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
