# Create your first sample

## 1. Start the app

The launcher checks for Python 3.14, 3.13, 3.12 and 3.11, in that order. Python 3.15 and later are not currently supported. For a first Windows setup, open the [official Python 3.14.10 download page](https://www.python.org/downloads/release/python-31410/), download **Windows installer (64-bit)** near the bottom of the page, run it and choose **Install Now**. On macOS, choose a Python 3.14.x installer from the official page. On Linux, install Python 3.11–3.14 and the `venv` module using your distribution's package manager. If you need guidance, see the [official Python Linux installation guide](https://docs.python.org/3.14/using/unix.html#on-linux).

- Windows: double-click `start_windows.bat`.
- macOS / Linux: run `sh start_unix.sh` in a terminal.

The app runs on this computer only. Generated files are saved by your browser and are not published to a website automatically.

The launch script creates a dedicated virtual environment. First-time setup may need internet access to install the reviewed, pinned dependencies. Your browser opens when the local app starts. If it does not, enter the URL shown in the launch window (usually `http://127.0.0.1:8765/`) in your browser. Press `Ctrl+C` in the launch window to stop it. If the default port is already in use, pass another port, such as `sh start_unix.sh --port 8766` or `start_windows.bat --port 8766`.

If setup stops while installing packages, check that the computer is online and retry the launcher. It installs only the reviewed, hash-checked versions; do not remove version or hash requirements to work around an install error. If the error remains, keep the full message from the launch window and ask your administrator or the project maintainer for help.

## 2. Understand a method before generating a sample

Select a method and review how it works before creating an artifact.

1. Open **Generate samples** in the left navigation.
2. Select one method card.
3. Read **Learn this method**: its mechanism, target attacks, conditions that weaken it, detection and response preparation, and legal notes.
4. Review and adjust its settings, then select **Generate file** at the bottom.
5. Preview the download and confirm its contents and deployment location.

Set formats and record counts in the selected method's settings. Enter only a canary URL issued by your monitoring provider. The generator never contacts it. Opening a file alone does not normally create an alert; the monitor records an event when the URL is actually requested after deployment. Your own click or a crawler may also create an event.

### Sample types

- **Canary files:** choose a supported format such as HTML, PDF, TXT, JSON, CSV, Excel, PowerPoint, SQLite or `.env`, then set context and fictional record count. `.env` does not use a count.
- **Static decoy portal:** set the context and title. The deployment ZIP contains HTML and fictional documents, with no login feature.
- **Decoy database:** select a preset such as customers, sales or user management, then review its rows and fields. It contains no real card numbers or CVVs; password and API key examples cannot authenticate. It never connects to an existing database.
- **Encrypted Deep Nest, Directory Maze and Encoding Maze:** review the explanation and estimates, then adjust size, depth and counts. Keep operator-only files separate from deployment artifacts.
- **Explanation-only methods:** these explain a technique but do not generate a sample or change production.

Artifacts contain fictional data and are saved by your browser. The app does not publish or deploy them. Do not load them into production; inspect them in an isolated environment you control.

### Reviewing ZIPs and databases

Extract a ZIP and open `index.html` to inspect it. Deploy manually to a test environment you control. Review databases with a SQLite viewer you trust. Keep the Encrypted Deep Nest deployment ZIP separate from its operator-only JSON; never place the latter in a public directory.

The default `.env.development` uses reserved `example.invalid` placeholders in both active and commented URLs. Review any URLs or notes in Detailed settings before generation. Do not load the sample into a real application; use it only in an isolated environment.

## 3. Review the downloaded file

The tool chooses a plausible filename for the selected sample. Where detailed settings provide a filename field, you can change it; leaving it blank is fine.

Files are saved to your browser's download location. If the browser does not save the file automatically, click its filename link in the results area. Select **Preview HTML in a new tab** or **Preview PDF in a new tab** to view the output. The standalone HTML is for appearance preview. For the portal, extract the deployment ZIP; it contains a linked `index.html` and a `documents` folder. Deploy both in the same website directory. Without a monitoring URL, all six sample documents open from the page. With one, one list entry points to the monitor and the other five documents open locally. Opening the standalone HTML preview does not contact the canary URL; clicking a canary link may be recorded or reported by the monitoring service. The app does not deploy files to a website. Generated database, Excel and PowerPoint previews show at most the first 10 records. To inspect every database row, open the downloaded SQLite file with a SQLite viewer you already trust. To use the `.env` ZIP, right-click it and select **Extract All** on Windows, or double-click it on macOS. Review the extracted `.env.development` file.

If you temporarily keep outputs inside the project, put them in the repository's top-level `generated/` folder; Git ignores that folder. Do not rely on ignore rules alone: review `git status --short` before publishing.

### Opening an Encrypted Deep Nest sample

Save both `*_deployment.zip` and `*.operator.json` from the browser downloads. Extract the deployment ZIP to get the encrypted archive, then look up its password in the operator JSON. Open it with an archive utility that supports AES-encrypted ZIP files; repeat for any nested ZIPs. The operator JSON contains passwords and placement details for every layer. Do not publish or deploy it; store it separately in a restricted location. If you lose the operator JSON, you may no longer be able to open the encrypted archives.

## 4. If you deploy a sample

Start on a test website or separate server that you control, not in production. Keep it separate from your production website, databases and user accounts; do not put real credentials or production data there. Deploy only files intended for serving. Keep `.operator.json`, `.inventory.json` and other operator-only files outside the folder that website visitors can download from. Generated artifacts may contain canary URLs you entered; do not commit them to a public GitHub repository. Configure login restrictions, HTTPS, access logging and alert delivery on the hosting side.

Detailed deployment, monitoring and retirement instructions: `/guide/en`
