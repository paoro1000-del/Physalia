"""Check that Nginx connection limits use and log an explicit rejection status."""
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
CONFIGS = ("nginx-decoy.conf", "nginx-stream-proxy.conf")


def main():
    errors = []
    for name in CONFIGS:
        path = ROOT / "examples" / name
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"{name}: cannot read configuration ({exc})")
            continue
        if "limit_conn_status 429;" not in source:
            errors.append(f"{name}: connection-limit rejections must return HTTP 429")
        if "$limit_conn_status" not in source:
            errors.append(f"{name}: access log must record the connection-limit status")
        if "limit_conn " not in source:
            errors.append(f"{name}: no connection limit directive found")

    if errors:
        print("Connection-limit status propagation problems:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    print(f"Both Nginx examples return and log connection-limit rejections ({len(CONFIGS)} files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
