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

- **Canary files:** choose a format such as HTML, PDF, TXT, JSON, CSV, Excel, PowerPoint, SQLite or `.env` and select a context. The filename and document title are chosen automatically, and documents contain 25 fictional records. `.env` does not use a count.
- **Ransomware Decoy Flood:** creates 4–8 synthetic files and a separate operator-only script that replenishes changed or deleted decoys. The host needs Python 3.11 or later. Replenishment is unlimited by default. It does not stop encryption or restore data.
- **Path Maze:** creates a finite ZIP of ordinary folders with synthetic files. Processing decoys adds work; parallel encryption may reach real files first.
- **Sparse Decoy:** generates a script that creates synthetic files with a large logical size at the destination. Copies, backups and synchronization may consume the full logical size and substantial time.
- **Static decoy portal:** set the context and title. The deployment ZIP contains HTML and fictional documents, with no login feature.
- **Decoy database:** select a preset such as customers, sales or user management, then review its rows and fields. It contains no real card numbers or CVVs; password and API key examples cannot authenticate. It never connects to an existing database.
- **Encrypted Deep Nest, Directory Maze and Encoding Maze:** review the explanation and estimates, then adjust size, depth and counts. Keep operator-only files separate from deployment artifacts.
- **Explanation-only methods:** these explain a technique but do not generate a sample or change production.

Artifacts contain fictional data and are saved by your browser. The app does not publish or deploy them. Do not load them into production; inspect them in an isolated environment you control.

### Reviewing ZIPs and databases

Extract the ZIP to inspect its contents. For the Static Decoy Portal or Directory Maze, open the extracted `index.html` to inspect the pages. Deploy manually to a test environment you control. Review databases with a SQLite viewer you trust. Keep the Encrypted Deep Nest deployment ZIP separate from its operator-only JSON; never place the latter in a public directory.

### Using Path Maze and Sparse Decoy

Extract the Path Maze ZIP at the destination. Keep the separate operator-only JSON inventory to identify and remove its files. It contains ordinary folders and synthetic files, with no links or background service. Searches and backups can encounter the extra files.

The Sparse Decoy ZIP contains a creation script and README. Extract it, then run `py -3 create_sparse_decoy.py <existing-destination>` on Windows or `python3 create_sparse_decoy.py <existing-destination>` on macOS/Linux with Python 3.11 or later. Generation does not run the script. The created names and logical sizes appear on stdout and in the separate operator JSON. Existing files are never overwritten, and creation stops when sparse allocation is unavailable.

Each file has a logical size of 1–32 GiB. Initial physical allocation is small, but copying, backup, synchronization or encrypted output can consume the logical size. Review available space and consider excluding decoys from normal backups. Partial encryption, size exclusions and parallel execution may reduce the delay.

### Using Ransomware Decoy Flood

Extract the deployment ZIP into the root directory you want to monitor. Save the monitor script in a separate operator-only directory; do not put it in a public directory or inside the deployment ZIP. On the monitored host, run it with Python 3.11 or later and pass the extracted directory (`py -3 ransomware_tripwire_monitor.py <extracted-directory>` on Windows; `python3 ransomware_tripwire_monitor.py <extracted-directory>` on macOS/Linux). It checks the listed file contents about once per second and records changes, deletion and replacement in `tripwire-alerts.jsonl`. Monitoring and logging run only while the script is running; no events are recorded while it is stopped. Keep the log with the script in a protected location.

On a detected change, the script creates a new synthetic file under a different name in the same directory. Replacements and their total content bytes are unlimited by default. Optionally pass `--max-files 100` or `--max-bytes 1048576` at startup. Limits apply only to replacements created in that run, excluding pre-existing and encrypted files. Counters reset on restart, and files replenished during a previous run are not tracked after restart.

A full disk can disrupt applications, logging and recovery. Existing files may still be overwritten. One-time file enumeration or parallel processing may eliminate the delay. Stopping the script or deleting a decoy directory prevents replenishment.

The monitor does not detect reads or exfiltration, stop processes, isolate a device or restore data. It can miss changes made and reverted between checks. At startup it compares the original files to their generated contents; it does not reconstruct events that occurred while stopped. Choose a location ordinary applications do not update to reduce false alarms. Data with no recoverable copy or history cannot be restored after destruction.

The default `.env.development` uses reserved `example.invalid` placeholders in both active and commented URLs. Review any URLs or notes in Detailed settings before generation. Do not load the sample into a real application; use it only in an isolated environment.

## 2. Review the downloaded file

The tool chooses a plausible filename for the selected sample. Where detailed settings provide a filename field, you can change it; leaving it blank is fine.

Files are saved to your browser's download location. If the browser does not save the file automatically, click its filename link in the results area. Select **Preview HTML in a new tab** or **Preview PDF in a new tab** to view the output. The standalone HTML is for appearance preview. For HTML canary files, choose a text link, button-style link, icon image, Next button, page numbers or the entire page. All require a click; with the entire-page option, clicking anywhere in the page opens the canary. For the portal, extract the deployment ZIP; it contains a linked `index.html` and a `documents` folder. Deploy both in the same website directory. Without a monitoring URL, all six sample documents open from the page. With one, one list entry points to the monitor and the other five documents open locally. Opening the standalone HTML preview does not contact the canary URL; clicking a canary link may be recorded or reported by the monitoring service. The app does not deploy files to a website. Generated database, Excel and PowerPoint previews show at most the first 10 records. To inspect every database row, open the downloaded SQLite file with a SQLite viewer you already trust. To use the `.env` ZIP, right-click it and select **Extract All** on Windows, or double-click it on macOS. Review the extracted `.env.development` file.

If you temporarily keep outputs inside the project, put them in the repository's top-level `generated/` folder; Git ignores that folder. Do not rely on ignore rules alone: review `git status --short` before publishing.

### Opening an Encrypted Deep Nest sample

Save both `*_deployment.zip` and `*.operator.json` from the browser downloads. Extract the deployment ZIP to get the encrypted archive, then look up its password in the operator JSON. Open it with an archive utility that supports AES-encrypted ZIP files; repeat for any nested ZIPs. The operator JSON contains passwords and placement details for every layer. Do not publish or deploy it; store it separately in a restricted location. If you lose the operator JSON, you may no longer be able to open the encrypted archives.

## 3. If you deploy a sample

Start on a test website or separate server that you control, not in production. Keep it separate from your production website, databases and user accounts; do not put real credentials or production data there. Deploy only files intended for serving. Keep `.operator.json`, `.inventory.json` and other operator-only files outside the folder that website visitors can download from. Generated artifacts may contain canary URLs you entered; do not commit them to a public GitHub repository. Configure login restrictions, HTTPS, access logging and alert delivery on the hosting side.

Detailed deployment, monitoring and retirement instructions: `/guide/en`
