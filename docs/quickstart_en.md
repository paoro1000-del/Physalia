# Getting started

## Configure the local port

Set `port` in the project root `app_config.json` to an available port from 1 to 65535. The default is 8765. Save the file and restart Physalia for the change to take effect. A `--port` command-line option overrides this setting; `--port 0` asks the operating system to choose an available port for that run.

The app is already running. Start with **Methods & sample generation** in the left navigation.

## 1. Generate a sample

Each method's page explains how it works, its expected effects and its configuration. This guide covers only the basic steps.

1. Open **Methods & sample generation** in the left navigation.
2. Choose a concern to filter the options, then select a method card.
3. Review the description and settings shown for that method.
4. Set the options you need and select **Generate file**.
5. To review the saved files, continue to **2. Review the downloaded file**.

Methods marked **In development** cannot be selected or generated in the initial release. Methods marked **Explanation only** describe a concept and do not generate files or change production systems.

Generated data is fictional, and files are saved by your browser. The app does not deploy them to a website. Do not put them in production; inspect them in an isolated environment you control.

## 2. Review the downloaded file

Download names use a method-specific `Physalia_*` pattern. Rename them after saving if needed. Files inside deployment ZIPs keep names required by their format, such as `.env`.

### Save and preview

- Files go to your browser's download folder. If a file is not saved automatically, click its filename in the results area.
- Use **Preview HTML in a new tab** or **Preview PDF in a new tab** to inspect those formats. A standalone HTML preview is for display only; the app does not deploy it to a website.
- HTML canary files can use text links, buttons, icons, page navigation or the whole page as a link. A canary request occurs only after a click. With the whole-page option, clicking anywhere opens the link. Opening the preview alone does not contact the canary URL.

### Check each format

- **Excel and PowerPoint:** The selected cell displays a fictional ordinary URL; the canary URL is stored only as the hyperlink destination. To inspect it without contacting the monitor, do not click the cell. Right-click and edit the link instead. Clicking may send a request.
- **Email address style:** The selected cell displays an ordinary email address and links to the canary URL. Clicking opens that URL in a browser; it does not send email.
- **Decoy portal:** The deployment ZIP contains `index.html` and a `documents` folder. To try it as a website, extract the ZIP and manually place both in the same directory. Without a monitoring URL, all six fictional documents open locally. With one, one list entry points to the monitor and the other five open documents.
- **File and database previews:** Canary files show 10 records per page and open on the canary record when present; use the page controls to inspect all records. The database preview shows the first 10 rows. To inspect every row, open the downloaded SQLite file with a viewer you trust.
- **`.env`:** Extract the ZIP. On Windows, right-click and select **Extract All**; on macOS, double-click it. Review the extracted `.env.development` file.

### Encrypted Deep Nest ZIP

1. The downloaded `Physalia_*.zip` is itself the first AES-encrypted ZIP. There is no ordinary ZIP wrapper to extract first. Open it with a utility that supports AES-encrypted ZIP files.
2. Find the matching path's password in `*_zip_passwords.txt` and enter it. This list is for sample verification only. It contains passwords, so keep it separate from the decoys and never deploy or publish it.
3. ZIP encryption protects file contents, not filenames or folder structure. It is normal for 7-Zip to show the current archive's listing. Inner ZIP listings remain hidden until you open those archives with their passwords. This tool does not support 7z header encryption, which can hide the listing.

If you temporarily store outputs inside the project, use the top-level `generated/` folder; Git ignores it. Before publishing, review `git status --short` instead of relying on ignore rules alone.

## 3. If you deploy a sample

Start on a test website or separate server that you control, not in production. Keep it separate from your production website, databases and user accounts; do not put real credentials or production data there. Deploy only files intended for serving. Keep `.operator.json`, `.inventory.json` and other operator-only files outside the folder that website visitors can download from. Generated artifacts may contain canary URLs you entered; do not commit them to a public GitHub repository. Configure login restrictions, HTTPS, access logging and alert delivery on the hosting side.

Detailed deployment, monitoring and retirement instructions: `/guide/en`
