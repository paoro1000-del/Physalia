# AiDeceptionGuard

AiDeceptionGuard is a local tool for creating fictional decoy files and reviewing exported security logs. It does not deploy generated files.

Generated artifacts may contain the canary URL you provide, and operator-only files may contain passwords or deployment details. Do not publish generated output or rely on `.gitignore` alone; review `git status` before committing.

## Choose a language

- [English documentation](READM.md)
- [日本語のドキュメント](README_ja.md)

## Create your first sample

1. On GitHub, select **Code → Download ZIP** and extract the archive, or clone the repository. Open the extracted project folder.
2. Install Python 3.11–3.14 if it is not already available. See the [first-sample guide](docs/quickstart_en.md) for installation help, including Windows Python Install Manager setup.
3. In the repository folder, double-click `start_windows.bat` on Windows. On macOS or Linux, run `sh start_unix.sh` in a terminal.
4. When the local page opens, the defaults create one standalone HTML file for Service management with 25 fictional records. Create it and preview it from the results area. To make a site you can deploy, choose **Create sample web page (HTML + deployment ZIP)**. Its ZIP contains `index.html` and six fictional PDF, Excel and CSV files; extract the ZIP and place its files together on a web server. The page has no login and is not published automatically. The `.env` sample is decoy-only; do not load it into a real application or production configuration. First launch may need internet access to install pinned, hash-verified packages.

The monitoring URL is optional for creating a sample. A real canary alert requires a URL issued by your monitoring service; the generator never contacts that URL.

- [First sample guide (English)](docs/quickstart_en.md)
- [初回サンプル作成ガイド（日本語）](docs/quickstart_ja.md)
