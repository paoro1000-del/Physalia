# Getting started

The app is already running. Start with **Methods & sample generation** in the left navigation.

## 1. Understand a method before generating a sample

Select a method and review how it works before creating an artifact.

1. Open **Methods & sample generation** in the left navigation.
2. Choose a concern to filter the options, then select a method card.
3. Read **About this method**: its mechanism, target attacks, conditions that weaken it, detection and response preparation, and legal notes.
4. Review and adjust its settings, then select **Generate file** at the bottom.
5. Preview the download and confirm its contents and deployment location.

Choose a format in the selected method's settings. Some methods also let you set a record count. Canary File starts with a local URL for this PC; you can replace it with a URL issued by your monitoring provider. The generator never contacts it. Opening a file alone does not normally create an alert; a monitoring provider or the local contact log records an event when the URL is requested. Your own click or a crawler may also create an event.

For a same-PC check, use the URL already set in Canary File. While Physalia is running, open **Canary contacts** in the left menu to see each request's time, HTTP method and identifier, along with the source IP, User-Agent, language, browser client hints and other request metadata when supplied. Clients can omit or falsify these values. The URL uses `127.0.0.1` and works only on the same PC; the source IP is normally `127.0.0.1`, and a file placed on another PC cannot reach this instance. Samples created in the same session share the URL, so the log cannot identify which file was contacted. Up to 500 events stay in memory and are cleared at shutdown; the URL changes on restart and earlier URLs no longer work. For a different host, use a monitoring endpoint reachable from that environment.

When a browser opens the canary page and runs JavaScript, it can also report screen and viewport dimensions, time zone, languages, available logical processors, approximate memory, touch and automation flags, browser-exposed plugins and GPU information, and client hints to the same local server. Browser support, settings or blocking can prevent collection. A script or agent that does not run JavaScript produces only the HTTP contact record. Browser and OS labels are estimates from the User-Agent; automation flags and GPU information alone cannot identify a sandbox or attacker.

The canary page also requests location permission. If permitted, the browser can report latitude, longitude, accuracy and timestamp, plus altitude, heading and speed when available, to the same local server. A previously granted permission may avoid a new prompt. HTTP contacts are still logged when permission is denied, unsupported, times out or JavaScript does not run. Some browsers may require clicking **Send location** on the page. Browser or OS location services may use network services, and returned values may be approximate or falsified; they do not establish an attacker's real location.

Each recorded header and string is limited to 512 characters. Authorization headers, cookies, arbitrary request bodies sent to the canary, referrer URLs and query strings are not retained in the log. Browser reports use JSON with a fixed list of environment fields. Access information may identify a person when combined with other data. Use this feature only in an environment where you have permission, and review your organization's rules and applicable law for purpose, access and retention. Collecting communications content or tracking third parties without authorization requires a separate legal assessment. [Japan's PPC guidelines](https://www.ppc.go.jp/personalinfo/legal/guidelines_tsusoku/)

### Sample types

- **Canary files:** choose a format such as HTML, PDF, TXT, JSON, CSV, Excel, PowerPoint, SQLite or `.env` and select a context. Download names use a method-specific `Physalia_*` pattern; document titles are also chosen automatically. Documents contain 25 fictional records. `.env` does not use a count. The result shows the placement: field and record number for record formats, or the setting key for `.env`. For composite artifacts, review the placement examples and operator inventory.
- **Ransomware Decoy Flood:** creates 4–8 synthetic files and a separate operator-only script that replenishes changed or deleted decoys. The host needs Python 3.11 or later. Replenishment is unlimited by default. It does not stop encryption or restore data.
- **Path Maze:** creates a finite ZIP of ordinary folders with synthetic files. Processing decoys adds work; parallel encryption may reach real files first.
- **Sparse Decoy:** The app creates a sparse file directly in the specified folder. Actual allocation is usually small. The selected size is nominal; the actual logical size varies by up to about 0.5%, only downward near the 1 TiB ceiling. A supporting filesystem is required; creation stops if sparse allocation is unavailable. Copies, sync, backups or encrypted output may use the full logical size. The extension is for appearance only; the content does not match that format.
- **Static decoy portal:** each purpose changes the palette, layout, information panel and page content. A supplied canary URL is placed in a file-list entry, a purpose-specific sidebar link and an information-panel link. Clicking may create a contact; opening the page alone does not. The deployment ZIP contains HTML and fictional documents, with no login feature.
- **Decoy database:** create a fictional B2C customer table with the default name `customers`. Choose 1,000, 10,000 or 100,000 rows. Postal code, prefecture and city are selected as matching real localities; street numbers are generated randomly. Older registration dates have a higher chance of a sparse soft-delete flag. It never connects to an existing database and contains no canary URL.
- **Encrypted Deep Nest, Directory Maze and Encoding Maze:** review the explanation and estimates, then adjust size, depth and counts. Keep operator-only files separate from deployment artifacts.
- **Explanation-only methods:** these explain a technique but do not generate a sample or change production.

Artifacts contain fictional data and are saved by your browser. The app does not publish or deploy them. Do not load them into production; inspect them in an isolated environment you control.

### Reviewing ZIPs and databases

Extract ZIPs to inspect their contents. For the Static Decoy Portal or Directory Maze, open the extracted `index.html` to inspect the pages. Deploy manually to a test environment you control. Review databases with a SQLite viewer you trust. The Encrypted Deep Nest ZIP is encrypted itself; store its verification password list separately and never place that list in a public directory.

### Using Path Maze and Sparse Decoy

Choose a Windows, Unix-like or macOS profile and extract the Path Maze ZIP to a dedicated destination. It uses platform-oriented folder names and relative path budgets, but destination-path and filesystem limits still apply. HTML index links remain inside the archive; it creates no filesystem symlinks or background service. Keep the separate operator-only JSON inventory to identify and remove its files.

For Sparse Decoy, the destination defaults to the Downloads folder, or the user folder if Downloads is unavailable; you can change it to another existing folder, then select a nominal size (1-1,024 GiB, up to 1 TiB) and extension. Generation creates one sparse file there without overwriting existing files; its logical size varies by up to about 0.5% from the selected value, only downward near the 1 TiB ceiling. The app stops if the filesystem does not support sparse allocation. Save the separate operator-only file list. The extension is for appearance only; the content does not match that format. Copies, synchronization, backups and encrypted output may use the full logical size.

To create the file on a Unix-like host from Windows, select **Download sparse TAR for Unix** instead of direct creation. The uncompressed TAR uses GNU PAX sparse format 1.0: it stores the logical file length and a map of the ranges that contain data, rather than filling the gaps with zero bytes. On the target host, extract it with GNU tar or bsdtar (for example, `tar -xf Physalia_…tar`). Extraction creates the named file with holes for the omitted ranges. Check `ls -lh` for the logical size and `du -h` for allocated space. TAR support alone does not guarantee sparse extraction; older or non-sparse-aware extractors may allocate the full logical size. Keep the TAR and operator-only file list separate from public deployment files.

Partial encryption, size exclusions and parallel execution may reduce the delay.

### Using Ransomware Decoy Flood

Extract the deployment ZIP into the root directory you want to monitor. Save the monitor script in a separate operator-only directory; do not put it in a public directory or inside the deployment ZIP. On the monitored host, run it with Python 3.11 or later and pass the extracted directory (`py -3 ransomware_tripwire_monitor.py <extracted-directory>` on Windows; `python3 ransomware_tripwire_monitor.py <extracted-directory>` on macOS/Linux). It checks the listed file contents about once per second and records changes, deletion and replacement in `tripwire-alerts.jsonl`. Monitoring and logging run only while the script is running; no events are recorded while it is stopped. Keep the log with the script in a protected location.

On a detected change, the script creates a new synthetic file under a different name in the same directory. Replacements and their total content bytes are unlimited by default. Optionally pass `--max-files 100` or `--max-bytes 1048576` at startup. Limits apply only to replacements created in that run, excluding pre-existing and encrypted files. Counters reset on restart, and files replenished during a previous run are not tracked after restart.

A full disk can disrupt applications, logging and recovery. Existing files may still be overwritten. One-time file enumeration or parallel processing may eliminate the delay. Stopping the script or deleting a decoy directory prevents replenishment.

The monitor does not detect reads or exfiltration, stop processes, isolate a device or restore data. It can miss changes made and reverted between checks. At startup it compares the original files to their generated contents; it does not reconstruct events that occurred while stopped. Choose a location ordinary applications do not update to reduce false alarms. Data with no recoverable copy or history cannot be restored after destruction.

`.env.development` includes common operational settings such as an app name, log level, port, database and Redis endpoints, timeout and retry count. Endpoints use fictional hosts under the reserved `example.invalid` domain, and the file contains no credentials. The canary URL is in a comment and is not requested just by opening the file. Do not load the sample into a real application; use it only in an isolated environment.

## 2. Review the downloaded file

Download names use a method-specific `Physalia_*` pattern. Rename files after saving if needed. Files inside deployment ZIPs retain names required by their formats, such as `.env`.

Files are saved to your browser's download location. If the browser does not save the file automatically, click its filename link in the results area. Select **Preview HTML in a new tab** or **Preview PDF in a new tab** to view the output. Excel and PowerPoint canary files keep a fictional endpoint visible in the selected table cell and store the canary URL only as that cell's hyperlink destination. To inspect it without contacting the monitor, use Excel's Edit Hyperlink command instead of clicking; clicking may trigger a request. The standalone HTML is for appearance preview. For HTML canary files, choose a text link, button-style link, icon image, Next button, page numbers or the entire page. All require a click; with the entire-page option, clicking anywhere in the page opens the canary. For the portal, extract the deployment ZIP; it contains a linked `index.html` and a `documents` folder. Deploy both in the same website directory. Without a monitoring URL, all six sample documents open from the page. With one, one list entry points to the monitor and the other five documents open locally. Opening the standalone HTML preview does not contact the canary URL; clicking a canary link may be recorded or reported by the monitoring service. The app does not deploy files to a website. The canary-file preview shows 10 records per page and opens on the canary record when present; use the page controls to review all generated records. The database method preview shows the first 10 records. To inspect every database row, open the downloaded SQLite file with a SQLite viewer you already trust. To use the `.env` ZIP, right-click it and select **Extract All** on Windows, or double-click it on macOS. Review the extracted `.env.development` file.

With the email address style, one selected email cell keeps its displayed address and links to the canary URL. Clicking it opens the URL in a browser; it does not send email.

If you temporarily keep outputs inside the project, put them in the repository's top-level `generated/` folder; Git ignores that folder. Do not rely on ignore rules alone: review `git status --short` before publishing.

### Opening an Encrypted Deep Nest sample

The downloaded `Physalia_*.zip` is itself the first AES-encrypted archive; there is no ordinary ZIP wrapper to extract first. Open it with an archive utility that supports AES-encrypted ZIP files and enter the matching path's password from `*_zip_passwords.txt`. Use the same list for nested archives. The password list is only for sample verification; it contains passwords, so keep it private and never deploy or publish it with the decoys.

## 3. If you deploy a sample

Start on a test website or separate server that you control, not in production. Keep it separate from your production website, databases and user accounts; do not put real credentials or production data there. Deploy only files intended for serving. Keep `.operator.json`, `.inventory.json` and other operator-only files outside the folder that website visitors can download from. Generated artifacts may contain canary URLs you entered; do not commit them to a public GitHub repository. Configure login restrictions, HTTPS, access logging and alert delivery on the hosting side.

Detailed deployment, monitoring and retirement instructions: `/guide/en`
