"""Ensure the audit-log KQL covers every operation classified by the GUI."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
KQL_PATH = ROOT / "examples" / "entra-audit-changes.kql"
sys.path.insert(0, str(ROOT))

from aideceptionguard.cloud_review import AUDIT_RULES, audit_activity


def main():
    try:
        source = KQL_PATH.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(f"Cannot read audit KQL: {exc}", file=sys.stderr)
        return 2

    start_marker = "ActivityDisplayName in~ ("
    end_marker = "| project TimeGenerated"
    if start_marker not in source or end_marker not in source:
        print("Cannot find the audit operation list in the KQL", file=sys.stderr)
        return 2
    operation_block = source.split(start_marker, 1)[1].split(end_marker, 1)[0]
    labels = re.findall(r'"([^"]+)"', operation_block)
    if not labels:
        print("The audit KQL operation list is empty", file=sys.stderr)
        return 2

    gui_operations = set(AUDIT_RULES)
    kql_operations = {audit_activity(label) for label in labels}
    missing = sorted(gui_operations - kql_operations)
    unclassified = sorted(kql_operations - gui_operations)
    if missing or unclassified:
        if missing:
            print("GUI audit operations missing from entra-audit-changes.kql:", file=sys.stderr)
            print("\n".join(f"- {operation}" for operation in missing), file=sys.stderr)
        if unclassified:
            print("KQL operations not classified by the GUI analyzer:", file=sys.stderr)
            print("\n".join(f"- {operation}" for operation in unclassified), file=sys.stderr)
        return 1

    required_scope = ("AuditLogs", "| where TimeGenerated >= ago(",
                      '| where Result =~ "success"')
    absent_scope = [fragment for fragment in required_scope if fragment not in source]
    if absent_scope:
        print("Audit KQL is missing expected scope filters: " + ", ".join(absent_scope),
              file=sys.stderr)
        return 1

    print(f"Audit KQL covers all {len(gui_operations)} GUI operation labels "
          f"({len(labels)} listed spellings after normalization).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
