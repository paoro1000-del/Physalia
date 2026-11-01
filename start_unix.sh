#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
cd "$SCRIPT_DIR"

if [ ! -x ".venv/bin/python" ]; then
  PYTHON=""
  for CANDIDATE in python3.14 python3.13 python3.12 python3.11 python3 python; do
    if command -v "$CANDIDATE" >/dev/null 2>&1 \
      && "$CANDIDATE" -c 'import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] <= (3,14) else 1)' >/dev/null 2>&1; then
      PYTHON=$CANDIDATE
      break
    fi
  done
  if [ -z "$PYTHON" ]; then
    echo "Python 3.11, 3.12, 3.13 or 3.14 is required. Make python3.11, python3.12, python3.13, python3.14, python3 or python available, then run this script again." >&2
    echo "On Linux, install one of these Python versions using your distribution's package manager." >&2
    echo "For macOS, download a supported Python 3.11-3.14 version: https://www.python.org/downloads/" >&2
    echo "See docs/quickstart_en.md or docs/quickstart_ja.md for guidance." >&2
    exit 1
  fi
  if ! "$PYTHON" -m venv .venv; then
    echo "Could not create the Python virtual environment (.venv)." >&2
    echo "Some Linux distributions install venv support separately (for example, python3-venv or python3.13-venv)." >&2
    echo "Install the package matching your Python version with your distribution's package manager, and check that this folder is writable." >&2
    echo "Then run this script again." >&2
    exit 1
  fi
fi

if ! .venv/bin/python -c 'import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] <= (3,14) else 1)' >/dev/null 2>&1; then
  echo "The Python version in .venv is outside the supported 3.11-3.14 range." >&2
  echo "Rename or remove .venv after confirming it contains no files you need, then try again." >&2
  exit 1
fi

REQUIREMENTS_HASH=$(.venv/bin/python -c 'import hashlib,pathlib; print(hashlib.sha256(pathlib.Path("requirements.txt").read_bytes()).hexdigest())')
INSTALLED_HASH=""
if [ -f ".venv/.requirements.sha256" ]; then
  INSTALLED_HASH=$(cat ".venv/.requirements.sha256")
fi

if [ "$REQUIREMENTS_HASH" != "$INSTALLED_HASH" ]; then
  echo "Installing hash-verified, pinned dependencies. First setup may need internet access."
  if ! .venv/bin/python -m pip install --disable-pip-version-check --no-input --require-hashes --no-deps --only-binary=:all: -r requirements.txt; then
    echo "Dependency setup failed. Read the messages above and try again." >&2
    echo "Check internet access and confirm this is a supported Python 3.11-3.14 installation." >&2
    echo "If it still fails, save the error messages when asking for help; do not remove the version or hash checks." >&2
    exit 1
  fi
  printf '%s' "$REQUIREMENTS_HASH" > ".venv/.requirements.sha256"
fi

if ! .venv/bin/python -m pip check; then
  echo "Installed packages are inconsistent. Review the messages above." >&2
  echo "If needed, recreate .venv after confirming it contains no files you need." >&2
  exit 1
fi

echo "Starting AiDeceptionGuard. Press Ctrl+C in this terminal to stop it."
if .venv/bin/python app.py --open "$@"; then
  echo "AiDeceptionGuard stopped."
else
  APP_STATUS=$?
  echo "AiDeceptionGuard exited with an error (status $APP_STATUS). Review the message above." >&2
  echo "If the message says the port is already in use, rerun this script with --port 8766." >&2
  exit "$APP_STATUS"
fi
