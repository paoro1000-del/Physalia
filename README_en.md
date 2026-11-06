# Physalia

English | [日本語](README.md)

Physalia is a local tool for generating fictional decoy files and samples for security testing. It does not deploy generated artifacts or integrate with production authentication or network monitoring services. Ransomware Decoy Flood includes a separately started script that replenishes changed synthetic files to potentially increase attacker work. Replenishment is unlimited by default.

## Setup and launch

Install Python 3.11–3.14, then open a terminal and download the source:

```sh
git clone https://github.com/paoro1000-del/Physalia.git
cd Physalia
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

On Windows, the app opens in a separate window. Press `Ctrl+C` in that window to stop it; the app exits without a batch-job confirmation prompt.

**macOS / Linux (terminal)**

```sh
sh ./start_unix.sh
```

On Linux, install Python 3.11–3.14 and ensure `venv` is available before starting. Some distributions provide `venv` as a separate package, such as `python3-venv`. The launch script looks for a supported Python version and displays guidance if it cannot find one. See the [quick-start guide](docs/quickstart_en.md) for installation help.

The launch script creates a virtual environment, installs the pinned dependencies on first launch, and starts the app in your browser. First-time installation requires internet access to download the packages.

Application logs are written daily to `logs/YYYYMMDD_app.log` under the project folder. At startup, logs that are at least seven days old are deleted. Set `log_level` in the root `app_config.json` to `DEBUG`, `INFO`, `WARNING` or `ERROR`; the default is `INFO`. `DEBUG` also records route categories and exception details. Request bodies, URL paths and canary tokens are not logged.

## What you can do

The tool explains the purpose, workings, and considerations for each security measure and generates sample files and code. Use these materials to decide whether a measure is suitable for your organization's environment and operations.

Ransomware Decoy Flood includes a standard-library-only script that replenishes changed synthetic files. The host needs Python 3.11 or later. Replenishment count and bytes are unlimited by default, with optional startup limits. A full disk can disrupt work and recovery and may not stop encryption.

Path Maze creates a finite tree of ordinary folders and synthetic files. Sparse Decoy generates a script to create large logical-size synthetic files manually at the destination. Copies, backups, synchronization and encrypted output may consume their full logical size. Both aim to add work when an attack selects and processes decoys.

Path Maze creates a finite tree of ordinary folders and synthetic files. Sparse Decoy generates a script to create large logical-size synthetic files manually at the destination. Copies, backups, synchronization and encrypted output may consume their full logical size. Both aim to add work when an attack selects and processes decoys.

The generated samples support evaluation and adoption decisions. You arrange deployment and monitoring service integration in your own environment.

Physalia automatically prepares a local canary page URL at startup for same-PC checks. The **Canary page** displays contacts and request metadata such as the source IP and browser information; up to 500 events stay in memory. The URL uses `127.0.0.1`, so another PC cannot contact this instance and the source IP is normally `127.0.0.1`. The log is cleared when the app stops. Samples in the same session share the initial URL; a restart creates a new one. For production use, publish a canary page over HTTPS at a location reachable from external networks, then use that page's URL in your samples.

When a browser opens the canary page, it can also report screen size, time zone, available processors, GPU information and automation flags. Requests that do not run JavaScript have only HTTP metadata. These values can be missing or falsified and cannot identify a sandbox or attacker. Use the feature only in an environment where you have permission, and review applicable laws and organizational rules.

The canary page also requests browser permission to access location. If allowed, the contact log records the reported coordinates, accuracy and other available position data. A previously granted permission may avoid a new prompt. The HTTP contact is still recorded if permission is denied or location is unavailable. Browser or OS location services may use network services.

To host your own canary destination in an isolated environment, download the homepage kit at the bottom of the Canary page. It contains an HTML/CSS/JavaScript page, a Python standard-library logging server, and Japanese and English setup guides. Use an HTTPS reverse proxy with access controls for external hosting.

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
