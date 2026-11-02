@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" goto :venv_ready
set "PYTHON_LAUNCHER="
for %%V in (3.14 3.13 3.12 3.11) do (
  if not defined PYTHON_LAUNCHER (
    py -%%V --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_LAUNCHER=py -%%V"
  )
)
if defined PYTHON_LAUNCHER goto :launcher_ready
python -c "import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] <= (3,14) else 1)" >nul 2>&1
if not errorlevel 1 set "PYTHON_LAUNCHER=python"
if defined PYTHON_LAUNCHER goto :launcher_ready
python3 -c "import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] <= (3,14) else 1)" >nul 2>&1
if not errorlevel 1 set "PYTHON_LAUNCHER=python3"
if not defined PYTHON_LAUNCHER goto :no_python

:launcher_ready
%PYTHON_LAUNCHER% -m venv .venv
if errorlevel 1 goto :venv_creation_failed

:venv_ready
.venv\Scripts\python.exe -c "import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] <= (3,14) else 1)"
if errorlevel 1 goto :unsupported_python

.venv\Scripts\python.exe -c "import hashlib,pathlib,sys; p=pathlib.Path('.venv/.requirements.sha256'); current=hashlib.sha256(pathlib.Path('requirements.txt').read_bytes()).hexdigest(); sys.exit(0 if p.is_file() and p.read_text(encoding='ascii')==current else 1)"
if errorlevel 1 (
  echo Installing hash-verified, pinned dependencies. First setup requires internet access.
  .venv\Scripts\python.exe -m pip install --disable-pip-version-check --no-input --require-hashes --no-deps --only-binary=:all: -r requirements.txt
  if errorlevel 1 goto :failed
  .venv\Scripts\python.exe -c "import hashlib,pathlib; pathlib.Path('.venv/.requirements.sha256').write_text(hashlib.sha256(pathlib.Path('requirements.txt').read_bytes()).hexdigest(), encoding='ascii')"
  if errorlevel 1 goto :failed
)

.venv\Scripts\python.exe -m pip check
if errorlevel 1 goto :dependency_check_failed

echo Starting Physalia. Press Ctrl+C in this window to stop it.
.venv\Scripts\python.exe app.py --open %*
if errorlevel 1 goto :app_failed
echo Physalia has stopped.
pause
exit /b 0

:no_python
echo Python 3.11-3.14 is not installed yet.
echo.
echo Open this official Python 3.14 download page:
echo https://www.python.org/downloads/release/python-31410/
echo Download and run Windows installer (64-bit), then choose Install Now.
echo After installation finishes, double-click this file again.
echo See docs/quickstart_ja.md for step-by-step guidance.
pause
exit /b 1

:unsupported_python
echo The Python version in .venv is outside the supported 3.11-3.14 range.
echo Rename or remove .venv after confirming it contains no files you need, then run this file again.
pause
exit /b 1

:venv_creation_failed
echo Could not create the Python virtual environment (.venv).
echo Check that the selected Python installation includes the venv module and that this folder is writable.
echo Repair or reinstall the supported Python version, then run this file again.
pause
exit /b 1

:dependency_check_failed
echo Installed packages are inconsistent. Review the messages above.
echo If needed, recreate .venv after confirming it contains no files you need.
pause
exit /b 1

:failed
echo Setup or startup failed. Read the messages above before trying again.
echo Check that you have internet access for dependency downloads and write access to this folder.
pause
exit /b 1

:app_failed
echo Physalia could not start or exited with an error. Review the messages above.
echo If the local port is already in use, run this file with --port 8766.
pause
exit /b 1
