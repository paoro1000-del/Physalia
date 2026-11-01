# AiDeceptionGuard

English | [日本語](README.md)

AiDeceptionGuard is a local tool for generating fictional decoy files and samples for security testing. It does not deploy generated artifacts or provide production authentication, monitoring, or notifications. Evaluate its effectiveness in your own environment.

## Setup and launch

Install Python 3.11–3.14, then open a terminal and download the source:

```sh
git clone https://github.com/paoro1000-del/AiDeceptionGuard.git
cd AiDeceptionGuard
```

Start the app from the downloaded folder using the instructions for your operating system.

**Windows (PowerShell)**

For your first setup, install Python once:

1. Open the [official Python 3.14.10 download page](https://www.python.org/downloads/release/python-31410/).
2. Download and run **Windows installer (64-bit)** near the bottom of the page.
3. Select **Install Now**. Once installation is complete, start the app.

To start the app, double-click `start_windows.bat` or run this command in PowerShell:

```powershell
.\start_windows.bat
```

**macOS / Linux (terminal)**

```sh
sh ./start_unix.sh
```

On Linux, install Python 3.11–3.14 and ensure `venv` is available before starting. Some distributions provide `venv` as a separate package, such as `python3-venv`. The launch script looks for a supported Python version and displays guidance if it cannot find one. See the [quick-start guide](docs/quickstart_en.md) for installation help.

The launch script creates a virtual environment, installs the pinned dependencies on first launch, and starts the app in your browser. First-time installation requires internet access to download the packages.

## What you can do

The tool explains the purpose, workings, and considerations for each security measure and generates sample files and code. Use these materials to decide whether a measure is suitable for your organization's environment and operations.

The generated samples support evaluation and adoption decisions. You arrange deployment and monitoring service integration in your own environment.

## Note

Do not upload generated decoy files or settings to a public Git repository. If generated decoys or their patterns become public, someone could compare them with deployed files and identify the decoys. Keep generated files private and use them in an isolated testing environment.

## Documentation

- [First sample](docs/quickstart_en.md)
- [Deployment and response](docs/deployment_en.md)
- [Log review](docs/log-review-guide_en.md)
- [Evaluation](docs/deception_evaluation.md)
- [Security policy](SECURITY.md)

License: [Apache License 2.0](LICENSE)

The version number is maintained in [VERSION](VERSION). Restart the app after changing it to update the display.
