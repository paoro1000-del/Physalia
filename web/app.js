"use strict";
const $ = selector => document.querySelector(selector);
document.querySelectorAll(".cards .card-foot").forEach(label => label.remove());
document.querySelector(".category-guide")?.remove();
document.querySelectorAll(".method-tag.ai").forEach(tag => tag.remove());
const MAX_GENERATION_REQUEST_BYTES = Number($('meta[name="adg-generation-request-limit"]').content);
const form = $("#generator"), result = $("#result"), button = $("#submit"), languageSelect = $("#language");
let language = "ja";
const CANARY_DEFAULT_ROWS = 25;
let activeWorkspacePage = "intro";
let activeKind = document.querySelector('input[name="kind"]:checked')?.value || "env";
let downloadUrls = [];
let generatedAsset = null;
let settingsRevision = 0;
let fieldErrorSequence = 0;
document.addEventListener("click", event => {
  const control = event.target.closest?.("[data-page-target]");
  if (control) showWorkspacePage(control.dataset.pageTarget);
});
function markInvalid(input) {
  input.setAttribute("aria-invalid", "true");
  input.setAttribute("aria-errormessage", "result");
  let error = input.nextElementSibling;
  if (!error?.classList.contains("field-error")) {
    error = document.createElement("small");
    error.className = "field-error";
    const baseId = input.id ? `${input.id}-field-error` : "field-error";
    error.id = baseId;
    while (document.getElementById(error.id)) error.id = `${baseId}-${++fieldErrorSequence}`;
    input.insertAdjacentElement("afterend", error);
  }
  error.textContent = result.textContent;
  const describedBy = new Set((input.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean));
  describedBy.add(error.id);
  input.setAttribute("aria-describedby", [...describedBy].join(" "));
}
function clearInvalid(input) {
  const hadError = input.getAttribute("aria-invalid") === "true";
  input.removeAttribute("aria-invalid");
  input.removeAttribute("aria-errormessage");
  const error = input.nextElementSibling;
  if (error?.classList.contains("field-error")) {
    const describedBy = new Set((input.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean));
    describedBy.delete(error.id);
    if (describedBy.size) input.setAttribute("aria-describedby", [...describedBy].join(" "));
    else input.removeAttribute("aria-describedby");
    error.remove();
  }
  if (hadError) result.textContent = "";
}
let databaseTemplates = [];
let databaseTemplatesLanguage = "";
let generationInProgress = false;
const japanese = {};
for (const root of [document, $("#column-template").content]) {
  root.querySelectorAll("[data-i18n]").forEach(element => { japanese[element.dataset.i18n] = element.textContent; });
}
const translations = {
  ja: {...japanese, intro: "手法を選び、仕組みや対象となる攻撃を確認してから生成します。", notice: "\u521d\u671f\u8a2d\u5b9a\u306e\u307e\u307e\u30b5\u30f3\u30d7\u30eb\u3092\u4f5c\u6210\u3067\u304d\u307e\u3059\u3002\u751f\u6210\u30c7\u30fc\u30bf\u306f\u67b6\u7a7a\u3067\u3001\u4f7f\u3048\u308b\u8a8d\u8a3c\u60c5\u5831\u306f\u542b\u307f\u307e\u305b\u3093\u3002\u30d5\u30a1\u30a4\u30eb\u306f\u81ea\u52d5\u914d\u7f6e\u3055\u308c\u307e\u305b\u3093\u3002\u4e0a\u90e8\u3068\u8a73\u7d30\u8a2d\u5b9a\u306eURL\u6b04\u304c\u3069\u3061\u3089\u3082\u7a7a\u306a\u3089\u901a\u77e5\u306f\u767a\u751f\u3057\u307e\u305b\u3093\u3002", database_template: "用途別テンプレート", database_help: "\u9867\u5ba2\u30fb\u30ab\u30fc\u30c9\u53f0\u5e33\u30fb\u4f1a\u793e\u30fb\u30d1\u30b9\u30ef\u30fc\u30c9\u4fdd\u7ba1\u30fb\u6ce8\u6587\u30fb\u8acb\u6c42\u30fb\u30e6\u30fc\u30b6\u30fc\u7ba1\u7406\u30fbAPI\u8a8d\u8a3c\u60c5\u5831\u30fb\u5f93\u696d\u54e1\u30fb\u53d6\u5f15\u5148\u30fb\u30b5\u30dd\u30fc\u30c8\u30fb\u8cc7\u7523\u30fb\u30af\u30e9\u30a6\u30c9\u306e\u96db\u5f62\u304c\u3042\u308a\u307e\u3059\u3002\u9805\u76ee\u306f\u6700\u592730\u500b\u307e\u3067\u7de8\u96c6\u3067\u304d\u307e\u3059\u3002\u5408\u6210\u306e\u8a8d\u8a3c\u60c5\u5831\u898b\u672c\u306f\u5b9f\u30b5\u30fc\u30d3\u30b9\u3067\u4f7f\u3048\u307e\u305b\u3093\u3002\u5b9f\u5728\u306e\u500b\u4eba\u60c5\u5831\u3084\u5b9f\u63a5\u7d9a\u5148\u306f\u4f7f\u308f\u306a\u3044\u3067\u304f\u3060\u3055\u3044\u3002\u30e1\u30fc\u30eb\u30fb\u30c9\u30e1\u30a4\u30f3\u578b\u306fexample.invalid\u3092\u4f7f\u3044\u307e\u3059\u3002", template_loading: "読込中…", template_custom: "カスタム（項目を自由に編集）", context_title_auto: "選択した用途に合わせて自動設定", context_title_generic: "空欄時の既定タイトル：Operations archive", template_help: "テンプレート選択後に項目を編集できます。実在の個人情報や実接続先は使わないでください。", kind_phone: "\u5317\u7c73\u306e\u67b6\u7a7a\u4e88\u7d04\u96fb\u8a71\u756a\u53f7\uff08\u975e\u7a3c\u50cd\uff09", kind_domain: "example.invalid ドメイン", kind_card_reference: "無効カード参照値", kind_card_expiry: "カード期限", kind_test_postal: "テスト用郵便番号", kind_credential_preview: "\u8a8d\u8a3c\u306b\u4f7f\u3048\u306a\u3044\u5408\u6210\u8a8d\u8a3c\u60c5\u5831\u306e\u898b\u672c", kind_currency: "通貨", kind_documentation_ip: "文書用IPアドレス", method_explainer: "この手法を知る", explain_how: "どういう対策か", explain_target: "どの攻撃を想定するか", explain_limit: "できないこと・限界", generating: "\u751f\u6210\u3057\u3066\u3044\u307e\u3059\u3002\u5927\u304d\u306a\u30d5\u30a1\u30a4\u30eb\u306f\u5c11\u3057\u6642\u9593\u304c\u304b\u304b\u308b\u3053\u3068\u304c\u3042\u308a\u307e\u3059\u3002\u3053\u306e\u753b\u9762\u3092\u9589\u3058\u305a\u306b\u304a\u5f85\u3061\u304f\u3060\u3055\u3044\u3002", generated: "{name} を生成しました。", failed: "生成に失敗しました。",
    estimate: "暗号化ZIP {archives}個 / ダミーファイル {documents}個（上限40 ZIP・生成内容32MiB・暗号化ZIP累積64MiB）", over_limit: "分岐・階層を減らしてください。暗号化ZIPの上限は40個です。", number_input_invalid: "数値欄に、表示された範囲内の整数を入力してください。",
    download_again: "生成ファイルを保存", operator_download: "運用情報を保存（配置しない）", inventory_download: "運用台帳を保存（生成ファイルと分けて保管）", summary: "生成結果：ZIP {archives}個 / デコイファイル {documents}個 / カナリア入り {canaries}個", format_breakdown: "形式内訳",
    monitoring_not_placed: "カナリアページURLは今回の生成ファイルに入りませんでした。設定を確認して再生成してください。",
    monitoring_placeholder: "例示用URLは監視通知に使えません。運用時は監視サービスが発行したURLを指定してください。",
    schema_limit: "項目は1〜30個にしてください。", invalid_options: "数値範囲は最小,最大（例: 0,100000）で、最小値は最大値以下にしてください。整数項目では小数を使えません。"},
  en: {
    skip_to_content: "Skip to main content",
    scenario_label: "Decoy scenario", scenario_crm: "Customer account register", scenario_migration: "Customer data migration", scenario_archive: "Customer data archive", scenario_cards: "Payment card inventory", scenario_companies: "Company directory", scenario_passwords: "Credential vault", scenario_invoices: "Invoice and payment register", scenario_employees: "Employee and department register", scenario_vendors: "Vendor and partner register", scenario_orders: "Order and sales ledger", scenario_tickets: "Support ticket queue", scenario_assets: "IT asset inventory", scenario_cloud: "Cloud resource inventory", scenario_api_credentials: "API credential inventory", scenario_help: "Match the synthetic data schema, file names, titles and URL context to the selected business use. No real personal data is used.", directory_title_help: "Leave blank to use the title for the selected scenario.",
    env_zip_download: "Save ZIP with exact .env filename", env_direct_download: "Save file directly (browser may remove leading dot)", env_zip_note: "The ZIP contains the exact filename. Some browsers remove a leading dot from direct downloads; extract the ZIP before deployment.",
    env_layout_title: ".env layout", env_layout_label: "Configuration pattern", env_layout_switch: "Development/production switch note (production URL commented)", env_layout_standard: "Standard URL setting", env_suffix: "Environment suffix", env_variable: "Setting key", env_dev_url: "Active URL for this environment (optional)", env_dev_url_authorized: "I control this host and route it only to an isolated test endpoint without production authentication. It may receive requests from anyone who follows the URL.", env_dev_comment_label: "Development comment (optional)", env_prod_comment_label: "Production switch note (optional)", env_switch_help: "With a blank filename this creates .env.development. The development URL is active and the canary URL is a commented production alternative. The default uses example.invalid. For a custom host, confirm ownership and route it only to an isolated test endpoint without production authentication. A crawler or agent may request this active URL. The generator does not resolve or contact it. Do not enter internal or production endpoints or load the file in production configuration.",
    canary_context: "URL context", context_profile: "Purpose", context_service: "Service administration", context_billing: "Billing", context_support: "Support", context_reports: "Reports", context_auto: "Choose automatically", context_title_auto: "Automatic for selected purpose", context_title_generic: "Blank title defaults to Operations archive", context_field: "URL field name (optional; ASCII letters, digits, _) ", context_label: "Visible link label (optional)", context_help: "The selected purpose changes the generated record fields, title and default canary field or label. Blank document filenames and titles follow the selected purpose. Standard .env files use it for the title and URL key; the development/production note layout uses its environment settings instead. CSV places the URL in the first record; Excel puts a link on the data sheet. The URL is not modified or fetched. Its domain and hyperlink target can still be inspected.",
    legal_title: "Japanese legal assessment for implementing countermeasures (Unauthorized Computer Access Act)", legal_normal: "Normal use:", legal_risk: "Conduct that may violate the Act:", legal_scope: "General assessment for assets you are authorized to manage. The actual authority and actions matter; other laws can also apply.", legal_more: "Basis and method-by-method details", legal_police: "National Police Agency guidance",
    method_explainer: "About this method", explain_how: "How it works", explain_target: "Attacks it addresses", explain_limit: "Limitations",
    database_template: "Use case template", template_loading: "Loading…", template_custom: "Custom (edit columns)", template_help: "Edit the columns after selecting a template. Replacing company, department, status and text candidates with fictional values from your business context can make records more credible. Do not use real personal data or live endpoints. To provide candidate names or emails, change the kind to Text.",
    kind_phone: "Reserved non-working NANP sample number", kind_domain: "example.invalid domain", kind_card_reference: "Nonfunctional card reference", kind_card_expiry: "Card expiry", kind_test_postal: "Test postal label", kind_credential_preview: "Synthetic credential placeholder (cannot authenticate)", kind_currency: "Currency", kind_documentation_ip: "Documentation IP address",
    save_settings: "Save settings (exclude URLs and ownership confirmations)", load_settings: "Load settings",
    settings_privacy_help: "Dedicated URL fields and ownership confirmations are not saved. Domain values and ordinary settings may remain in the JSON. URLs or secrets in free-text fields are not automatically removed, so do not enter real data or secrets, and store the JSON securely.",
    config_saved: "Saved settings. URLs and domain-ownership confirmations are not carried over.", config_loaded: "Loaded settings. Re-enter URLs in their URL fields and reconfirm ownership before using a decoy domain.", config_invalid: "Select valid settings JSON exported by this tool (up to 1 MiB, nesting depth at most 64); duplicate keys are rejected.",
    unsafe_setting_text: "Settings contain control or bidirectional formatting characters. Remove them before saving or loading.",
    monitoring_placeholder: "At least one configured URL uses a reserved example/test domain. That URL cannot produce a live canary alert; use a URL issued by your monitoring service for deployment.",
    monitoring_not_placed: "A canary URL was provided, but random placement put it in none of the files. Increase placement or adjust the settings before deployment.",
    workspace: "Workspace", create: "Methods and sample generation",
    language: "Language", intro: "Choose a file type, configure it, and generate your decoy.",
    getting_started: "Getting started", notice: "Select a method and review its mechanism and target attacks before generating. Artifacts contain fictional data and are not deployed automatically. No canary alert occurs without a monitoring URL.",
    select_method: "Select a method", file_type: "Choose by intended role", settings: "Settings", method_settings: "Configure the selected method",
    canary_file: "Canary file", canary_card: "Detect suspicious contact when a monitoring URL is used", canary_formats_foot: "MULTIPLE FORMATS", nest_title: "Encrypted Deep Nest",
    nest_card: "Layer encrypted decoys to slow exploration", database_title: "Decoy Database", database_card: "Use a synthetic database to confuse selection",
    web_title: "Static Decoy Portal", web_card: "Draw exploration into a static decoy portal", canary_desc: "Choose a format, file name and title for a document containing your monitoring URL.",
    stream_title: "Infinite Stream", stream_card: "Prolong downloads with an endless response",
    directory_title: "Directory Maze", directory_card: "Add exploration through directories and decoy files",
    encoding_title: "Encoding Maze", encoding_card: "Use layered encoding to add candidate inspection",
    stream_desc: "Generate a ZIP containing a streaming server and configuration. Generation does not start the server.",
    stream_format: "Stream content format", stream_path: "Download path", stream_port: "Local listening port", stream_rate: "Aggregate bandwidth (KiB/s)", stream_concurrency: "Concurrent streams",
    stream_help: "No total size or duration cutoff while connected, but the backend closes a connection after five seconds without socket activity, including when a write stalls because the client is not reading. Disconnects, operator stop and failures also end the response. Use a short client-side timeout when testing. The bandwidth limit is not a cumulative quota.",
    stream_note: "Python standard library only. Listens on 127.0.0.1 with Bearer authentication and emits secret-free JSON start/end events to stdout. Authenticated HEAD probes return headers without streaming and emit a stream_probe event. payload_bytes_sent counts payload blocks only after the complete block write and flush succeed. It omits partial writes from failed blocks and HTTP/TCP framing; it does not confirm client receipt. Configure protected log collection and alerting separately. Access/admin tokens stay in operator JSON, never the deployment ZIP. See the README for proxy setup.",
    directory_desc: "Generate ordinary directories, index.html pages and decoy files. Extract for static hosting.",
    maze_depth: "Additional directory levels below the root folder", maze_files: "Decoy files per directory", maze_cross_links: "Link to other branches and parents to create browsing paths", maze_format: "Single file format for all decoys",
    directory_note: "All decoy files use the single selected format. Up to 400 directories and 16 MiB of content. Cycles are HTML links, without filesystem symlinks or recursive extraction. Crawlers that deduplicate URLs can stop revisiting pages. Canary URLs are assigned up to the number of generated files and mapped to paths in the private operator JSON. Surplus URLs remain unused. Reused URLs cannot identify the exact file.",
    encoding_desc: "Generate independent fictional candidates that match a selected business scenario, then apply layered encodings. File names, titles and schemas follow the scenario. For .env, candidates use common dotenv filenames and APP_ENV matches each filename.", decoded_format: "Decoded file format", encoding_layers: "Encoding steps", encoding_candidates: "Candidate files", encoding_codecs: "Available encodings for each layer",
    encoding_note: "Each layer is JSON with encoding and payload fields. This is not encryption. Operator JSON records the scenario, decode order, URL-to-candidate assignments and final SHA-256. Content limit: 16 MiB. A short script can decode all layers, so evaluate delay in your exploration and verification workflow. URLs beyond the candidate count remain unused. Reused URLs cannot identify the exact candidate.",
    encoding_estimate: "Estimated transform operations: {operations} ({candidates} candidates × {layers} layers). This does not predict output size. Generation limit: 16 MiB.",
    canary_url: "Canary URL", canary_urls: "Canary URLs (one per line)", optional: "Optional", canary_help: "Enter the HTTPS URL issued by your monitoring service. If supplied, the URL is included in the generated file; do not publish that file in a public repository. Without a URL, no real canary alert can occur; .env samples use the reserved example.invalid address. The generator never contacts the URL.",
    canary_note: "Reading a file alone does not trigger an alert; the provider may alert when the URL is accessed. Scanners or link previews may access it automatically. An alert alone cannot identify who viewed the file or caused the request.", canary_advanced_summary: "URL format and input details", canary_advanced_help: "To receive alerts, use a publicly reachable monitoring endpoint. Private IPs and local-only hostnames are rejected, but DNS destinations are not checked. With no URL, only .env samples include the reserved example.invalid placeholder; other formats omit it. Standard .env wraps URLs in single quotes, so choose another format if the URL contains a single quote. URLs containing $ cannot be used in .env. The development/production note layout has separate input restrictions. PowerPoint includes every requested record, split into slides of up to 10 rows.",
    csv_safety_note: "CSV has no cell-type metadata. Text that could be interpreted as a formula is prefixed with an apostrophe to reduce risk. The apostrophe remains in the CSV, and spreadsheet import behavior varies; verify it in the application you use before deployment.",
    format: "File format", filename: "File name (start with a letter or number; letters, numbers, - or _ only; no extension; blank = automatic)", document_title: "Document title", document_rows: "Records in document",
    nest_desc: "Generate a policy-based password for each branching archive containing decoy files. Choose a primary format and optionally mix in occasional alternatives. Duplicates are detected and replaced as needed to keep every password unique.", nest_layers: "ZIP levels (including the first)",
    nest_branches: "Child ZIPs per archive", branches: "Subfolders per folder", decoys: "Decoy files per ZIP", directory_depth: "Maximum folder depth within each ZIP", nest_rows: "Records per document / database",
    directories: "Folder name candidates (scenario-based default; editable, ASCII comma-separated)", nest_format: "Primary decoy file format",
    nest_varied_formats: "Keep this format common and occasionally mix other formats",
    nest_varied_formats_help: "About 75% of decoys use the selected format. Weighted alternatives such as Excel, SQLite and .env appear among documents inside the encrypted nest.",
    password_policy: "Automatically generated password policy", password_mode: "Generation mode", memorable: "Words + digits / symbols", random: "Fully random",
    hints: "Include recovery-note decoys", hints_early: "First two layers", hints_all: "Every layer", hints_none: "No notes",
    min_length: "Minimum length", max_length: "Maximum length", lowercase: "Lowercase", uppercase: "Uppercase", digits: "Digits", symbols: "Symbols",
    hint_characters: "Trailing characters the recovery note claims are stored elsewhere", password_words: "Word candidates (ASCII, comma-separated; blank for defaults)",
    progressive: "Start shorter and increase length in deeper layers",
    password_help: "Maintenance notes are designed to make an attacker look for a separate key register. They contain no password characters; the stated withheld-character count is part of the decoy, not a usable hint. Passwords remain in the operator-only file. Progressive length starts at 9 characters in the default 9–13 range and increases in deeper layers. Archives can be attacked offline and in parallel after download, so a successful guess and delay are not guaranteed. A memorable candidate may fall back to a random value if it repeats. Even a 9–13 character password may be impractical to crack; solve time depends on the archive format and attacker resources.",
    canary_percent: "Canary probability per decoy (%)", canary_probability: "Sampled independently per file. 0% means none; 100% means all decoys. Up to 400 URLs are accepted. Selected files receive different URLs before one is reused. URLs beyond the number of selected files remain unused; the selected count varies with the per-file probability. Reused URLs cannot identify the exact file from an alert. A blank URL list inserts no monitoring URL.",
    nest_note: "Use an AES-compatible ZIP tool. Source content is limited to 32 MiB and cumulative encrypted archives to 64 MiB. Save the deployment ZIP and all operator-only JSON files separately. The password/layout file and the lifecycle inventory can contain passwords, URLs, settings and hashes; never deploy or publish either.",
    database_desc: "Choose a preset to create a SQLite file with fictional data in a main table. You can customize its columns if needed. A supplied canary URL may add a separate connection table; the file does not connect to an existing database.", rows: "Number of records", database_rows_help: "Default: 100 rows. SQLite files are limited to 32 MiB. If generation reaches the limit, reduce the row count or number of columns.", table_name: "Table name", schema: "Column definitions", add_column: "+ Add column",
    database_help: "Choose a customer, card inventory, company, password vault, orders, sales transactions, invoices, employees, user management, vendors, support tickets, assets or cloud inventory template. Edit up to 30 columns. Replacing company, department, status and text candidates with fictional values from your business context can make the records more credible. To provide candidate names or emails, change the kind to Text. Do not use real personal data or live endpoints. Company-associated email/domain values use company-matched subdomains under reserved example.invalid; rows without a company use example.invalid. By default, password vault login_url values use the reserved example.invalid domain and cannot reach real services.",
    database_note: "Card data uses a clearly invalid reference only; no PAN or CVV. Phone fields use the reserved fictional +1-202-555-0100–0199 range, including in Japanese-language samples. Password fields contain random synthetic strings that are not linked to real accounts or services; no real credentials or hashes are imported. Reading a database alone does not alert. The Password Vault template places the canary URL in one login_url record when that column exists; otherwise it uses a connection table. Other templates also use a connection table. The monitoring service alerts only if the URL is requested.",
    column_name: "Column name", data_kind: "Data generator", data_options: "Candidate values / numeric range", remove_column: "Remove",
    kind_id: "Sequence (INTEGER)", kind_name: "Full name (TEXT)", kind_username: "Login name (TEXT)", kind_invoice_reference: "Invoice number (TEXT)", kind_order_reference: "Order number (TEXT)", kind_sale_reference: "Sales reference (TEXT)", kind_email: "Email (TEXT)", kind_company: "Company (TEXT)", kind_department: "Department (TEXT)",
    kind_integer: "Integer (INTEGER)", kind_decimal: "Decimal (REAL)", kind_date: "Date (TEXT)", kind_datetime: "Date and time (TEXT)", kind_status: "Status (TEXT)", kind_uuid: "UUID (TEXT)", kind_text: "Text (TEXT)",
    web_desc: "Generate a static archive page.", page_title: "Page title",
    web_help: "The results include an HTML preview and a deployment ZIP. The ZIP contains index.html and six fictional files. Without a monitoring URL, all six open from the page. With one, a list entry links to the monitor instead of opening its matching document; the other five open locally. Opening the page alone does not request the monitoring URL; its link must be clicked.",
    web_note: "This is static HTML. Login, configuration changes, access monitoring, and infinite streaming require a separate server.",
    generate: "Generate file",
    generating: "Generating. Larger files may take a little while. Keep this page open until generation finishes.", generated: "Generated {name}.", failed: "Generation failed.", generation_settings_changed: "Settings changed during generation, so the result was discarded. Generate again with the current settings.", number_input_invalid: "Enter a whole number within the range shown for the selected method.",
    estimate: "{archives} encrypted ZIPs / {documents} decoy files (limit: 40 ZIPs, 32 MiB of source content, and 64 MiB cumulative encrypted archives)", over_limit: "Reduce depth or branching. The limit is 40 encrypted ZIPs.",
    download_again: "Save generated file", operator_download: "Save operator information (do not deploy)", inventory_download: "Save operations inventory separately from generated files", summary: "Generated: {archives} ZIPs / {documents} decoy files / {canaries} with canary URLs", format_breakdown: "Formats",
    schema_limit: "Use 1–30 columns.", invalid_options: "Enter the numeric range as min,max (for example 0,100000), with minimum no greater than maximum. Integer fields do not accept decimals.",
  },
};
translations.ja.filename_error = "ファイル名は64文字以内の英数字・ハイフン・アンダースコアで入力し、英数字で始めてください。拡張子やパス、OSの予約名は使えません。";
translations.en.filename_error = "Use up to 64 ASCII letters, digits, hyphens or underscores, starting with a letter or digit. Extensions, paths and device names are not allowed.";
Object.assign(translations.ja, {
  intro_concept_scope:"手法には、従来の考え方を使うものや、AIが普及した環境に合わせたものがあります。効果は配置や攻撃者の行動によって異なります。", intro_inspiration:"完全に防げるかだけでなく、**攻撃者の手間を増やし、対応の機会を作れるか**も対策を考える軸です。紹介する手法が、その検討のヒントになればと考えています。",
  quick_db_customers: "顧客管理",
  quick_db_failed_fallback: "プリセット一覧を読み込めません。既定の顧客DBは作成できます。他のプリセットは再読込後に選べます。",
  quick_db_failed_custom: "プリセット一覧を読み込めません。編集した項目はこのボタンか「ファイルを生成」から作成できます。他の用途別テンプレートは再読込後に選べます。",
  quick_db_customer_fallback_help: "既定の顧客テーブルを作成します。項目は詳細設定で確認・編集できます。",
  quick_html_scenario_help: "一覧の見出しとファイル例を用途に合わせます。",
  web_scenario_label: "サイトの用途",
  web_scenario_operations: "運用ポータル",
  web_scenario_shared: "共有ドキュメント",
  web_scenario_archive: "業務アーカイブ",
  web_scenario_records: "記録管理",
});
Object.assign(translations.en, {
  intro_concept_scope:"Methods include established approaches and adaptations for environments shaped by AI. Their effects depend on placement and attacker behavior.", intro_inspiration:"Complete prevention is not the only measure of value: a defense may also add work for an attacker or create a chance to respond. We hope these methods help you consider options for your environment.",
  quick_db_customers: "Customers",
  quick_db_failed_fallback: "Could not load presets. You can still create the default customer database; retry to choose other presets.",
    quick_db_failed_custom: "Could not load presets. You can create the edited schema with this button or Generate file; retry to load the other templates.",
  quick_db_customer_fallback_help: "Creates the default customer table. Review or edit its fields in the detailed settings below.",
  quick_html_scenario_help: "Matches the portal heading and sample files to this purpose.",
  quick_db_purpose: "No database server is needed. This creates one SQLite file with fictional data and never connects to or changes an existing database. It contains no payment card numbers or usable passwords. Phone fields use the reserved fictional +1-202-555-0100–0199 range, including in Japanese-language samples. Files are limited to 32 MiB; if generation exceeds the limit, reduce the row count. A supplied canary URL is included in the file.",
  web_scenario_label: "Portal purpose",
  web_scenario_operations: "Operations portal",
  web_scenario_shared: "Shared documents",
  web_scenario_archive: "Business archive",
  web_scenario_records: "Records management",
});
translations.en.workspace_create = "WORKSPACE / CREATE";
translations.ja.hint_characters = "復元メモが「別管理」と装う末尾文字数（実際のパスワード文字は含まない）";
translations.ja.hints = "復元メモのデコイを配置";
translations.ja.hints_none = "配置しない";
translations.ja.password_help = "保守メモは、別の鍵台帳を探させるためのデコイです。実際のパスワード文字は含まず、伏せ字の文字数も利用可能な手掛かりではありません。パスワード本体は管理者専用ファイルにのみ保存されます。既定の9〜13文字では、段階設定により序盤を短くし、深い階層ほど長くします。ZIP取得後はオフラインで並列試行できるため、解読成功や遅延は保証されません。単語形式の候補が重複した場合はランダム値に切り替わります。9〜13文字でも解読困難な場合があり、所要時間はZIP形式や攻撃設備に左右されます。";
translations.en.assets_eyebrow = "DECEPTION ASSETS";
translations.ja.maze_estimate = "ディレクトリ{directories}個・デコイファイル{documents}個（上限400ディレクトリ）";
translations.en.maze_estimate = "{directories} directories · {documents} files (limit: 400 directories)";
translations.ja.maze_over_limit = "上限400ディレクトリを超えています。階層数か分岐数を減らしてください。";
translations.en.maze_over_limit = "This exceeds the 400-directory limit. Reduce depth or branching.";
translations.ja.maze_limit_adjust = "上限内にするには、{options}のいずれかにしてください。";
translations.en.maze_limit_adjust = "To stay within the limit, reduce {options}.";
translations.ja.maze_reduce_depth_to = "階層数を{value}以下";
translations.en.maze_reduce_depth_to = "depth to {value}";
translations.ja.maze_reduce_branches_to = "分岐数を{value}以下";
translations.en.maze_reduce_branches_to = "branching to {value}";
translations.ja.maze_or = "または";
translations.en.maze_or = "or";
translations.ja.nest_limit_adjust = "上限40個以内にするには、{options}にしてください。";
translations.en.nest_limit_adjust = "To stay within 40 ZIPs, reduce {options}.";
translations.ja.nest_reduce_layers_to = "ZIP階層数を{value}以下";
translations.en.nest_reduce_layers_to = "ZIP layers to {value}";
translations.ja.nest_reduce_branches_to = "各ZIPの子ZIP数を{value}以下";
translations.ja.explain_deception = "本物らしさを高める要素";
translations.ja.explain_delay = "攻撃者を遅らせる可能性";
Object.assign(translations.en, {
  tag_detect:"Detects attacks", tag_delay:"Adds work", tag_leak:"Harder to sort after theft", tag_lure:"Leads to fictional data",
  flow_title:"How it works", flow_details:"More about this method", explain_deception:"What makes it look genuine", explain_delay:"How it can delay an attacker",
  explain_measurement:"Plausibility and delay depend on the deployment environment and attacker behavior.",
  legal_disclaimer:"This is a general view of Japanese law, not a determination for a particular case. Consult a legal professional familiar with the applicable jurisdiction before deployment.", legal_us_disclaimer:"This is a general view of US law, not a determination for a particular case. Consult a legal professional familiar with the applicable jurisdiction before deployment.",
  legal_us_title:"US legal considerations for implementing countermeasures (federal and state law)", legal_us_risk:"Specific considerations", legal_us_scope:"Federal and state law and contracts may apply. The contents and storage of communications and the locations of those involved can affect the assessment; monitoring is not automatically permitted even on systems you control.", legal_us_more:"US legal background and details",
  email_domain:"Email domain for an isolated decoy (optional)", email_domain_help:"By default, company names use matching addresses under the reserved example.invalid domain; other rows use example.invalid. Use a domain you own only for an isolated decoy, without production mailboxes. This tool does not perform DNS lookups or send email. Direct any mail to an isolated monitoring sink.",
  email_domain_authorized:"I own this domain and will use it only for an isolated decoy without production mailboxes.",
  column_options_help:"For numeric fields, enter minimum,maximum (for example 0,100000). Separate text or status candidates with | (for example active|pending). Blank ranges default to 1–100 for quantities, 25–2500 for unit prices, and 0–100000 for other numeric fields.",
  candidate_values_safety:"Candidate values cannot contain real domains, IP addresses, URLs or email addresses. Use reserved examples such as example.invalid, and use the dedicated fields for monitoring URLs and owned domains.",
  vault_domain:"Domain for the isolated decoy (optional)", vault_domain_help:"Used only for fictional login_url fields in the Password Vault scenario. Applies to the standalone database and non-.env files in Encrypted Deep Nest, Directory Maze and Encoding Maze; .env files use environment variables. A supplied domain creates an HTTPS URL that may be reachable. The generator does not resolve or contact it. Use a domain you own, and point wildcard DNS and TLS only at an isolated decoy without production authentication. This is not a monitoring token; use DNS or web-server logs to observe requests. Leave blank to use example.invalid.",
  vault_domain_authorized:"I control this domain and direct it only to an isolated decoy without production authentication."
});
translations.en.nest_reduce_branches_to = "child ZIPs per archive to {value}";
const methodExplanations = {
  ja: {
    env: {title:"カナリアファイル", how:"もっともらしい文書や設定ファイルに、運用者が指定した監視URLを埋め込みます。", target:"攻撃者がカナリアファイル（罠ファイル）を盗み出し、そこに書かれたURLへアクセスする場面を想定します。接続先の設定に応じて、通報やリクエスト情報の記録などを行い、侵害後の調査につなげます。", limit:"単体のカナリア生成ではURLを1つ使います。暗号化ネスト、ディレクトリ・メイズ、エンコーディング・メイズはURL一覧からファイルごとに割り当て、台帳に対応を記録します。ファイルの取得・閲覧だけではURL型トークンは発火しません。通信遮断やURLを試さない手順では通知されず、発火してもAIによるアクセスかは判定できません。"},
    database: {title:"デコイ・データベース", how:"実在人物を含まない、もっともらしいテーブルと架空レコードのDBを作ります。指定項目から最大10,000件を生成します。パスワード管理テンプレートでは、カナリアURLをランダムに選んだ1件のlogin_urlへ配置し、password値は保ちます。", target:"`.db`を探して顧客・注文情報を持ち出す攻撃者と、盗んだ後に本物らしさを検証する攻撃者を想定します。", limit:"本ツールは単独テーブルと架空データを作ります。本番DBへの自動接続・読み取り監視はありません。実データや再現し過ぎたスキーマを使わず、本物も同時に漏れ得る前提で運用します。関連技術のデータ・ディルーションは、本番DBに大量の合成レコードを混ぜ、流出後の選別と利用を難しくする構想です。本ツールでは技術紹介のみを行い、本番DBへの混在は実装しません。"},
    web: {title:"スタティック・デコイ・ポータル", how:"アーカイブや管理ポータルに見える静的HTMLを作ります。", target:"公開URLや管理画面らしいサブディレクトリを探索し、リンクやファイルをたどる攻撃を想定します。", limit:"静的ページです。認証、ログイン状態、設定変更、アクセス制御、通知処理は実装しません。画面を開くだけではリンク先のカナリアURLにアクセスしません。"},
    fake_trap: {title:"フェイクトラップ", how:"警告、通報済み表示、認証中スピナーのいずれかを示す静的HTMLを作ります。画面表示だけで、通報・認証・情報収集や接続の維持は行いません。", target:"デコイ経路に到達し、表示を読む人やAIエージェントが、検知された可能性を考えて再確認する状況を想定します。", limit:"表示を無視するスクリプトや、別経路を並列に探索する攻撃者には働きません。ログ記録や通知は配置先で別途設定してください。遅延効果は保証されません。"},
    ransomware_tripwire: {title:"ランサムウェア・デコイフラッド", how:"架空の業務ファイル一式と、指定ファイルの内容変更・削除・差し替えをローカル記録するPython標準ライブラリ製の監視スクリプトを生成します。配置ZIPと監視スクリプトは別々に保存します。", target:"ランサムウェアなどが監視対象のファイルを暗号化・削除・置換する状況を想定します。", limit:"監視スクリプトは約1秒間隔の確認で、読み取りだけのアクセスは検知しません。検知前に実データが損なわれる可能性があり、プロセス停止・端末隔離・復元は行いません。監視対象の差し替えや監視停止にも弱く、見逃し・誤検知があります。"},
    nest: {title:"エンクリプテッド・ディープ・ネスト", how:"暗号化ZIPを分岐・多層化し、各層に文書や次のアーカイブを混在させます。選択形式を中心に、Excel・SQLite・.envなども時々混ぜられます。パスワードと復元メモの対応は管理者専用ファイルに分けます。復元メモは別の鍵台帳があるよう示しますが、実際のパスワード文字は含みません。ファイルごとに異なるカナリアURLを割り当てると接触先を識別でき、URLを再利用した場合はグループまでの識別になります。認証情報保管庫シナリオでは、.envにシナリオ別環境変数、その他の形式に架空login_url項目を使い、password値は変えません。", target:"バックアップや設定を急いで一括回収する攻撃者と、候補を順に展開して秘密を探す攻撃者を想定します。", limit:"持ち出した後に並列・オフラインで解析する攻撃者は、現場の時間を使いません。強いパスワードなら解読不能で、反対にヒントが露骨なら罠と見抜かれます。通常データの暗号化やバックアップの代替ではありません。"},
    stream: {title:"インフィニット・ストリーム", how:"認証付きの隔離配信経路で、接続中は総容量・総時間で終わらない応答を返します。帯域と同時接続を抑え、管理者が停止できます。", target:"ファイル取得を完了するまで待つ、全量ダウンロード型の攻撃者を想定します。短時間で撤収したい攻撃者の時間と注意を拘束する狙いです。", limit:"バックエンドは無通信が5秒続くと接続を終了します。受信側が読み取らず書き込みが詰まった場合も対象です。部分取得、並列探索、明示的な切断でも迂回され、接続自体が罠と疑われることがあります。GUIはサーバーを起動せず、認証付き隔離経路・開始検知・負荷管理は配置側で必要です。"},
    directory_maze: {title:"ディレクトリ・メイズ", how:"実際のフォルダーとHTMLリンクで有限の階層・分岐を作り、文書や設定ファイルを配置します。認証情報保管庫シナリオでは、.envにシナリオ別環境変数、その他の形式に架空login_url項目を使い、password値は変えません。", target:"サブディレクトリ名を総当たりし、見つかったファイルを広く収集するクローラやAI生成ツールを想定します。", limit:"階層・ファイル数は有限で、URL重複排除や並列化で探索は速くなります。HTMLを全走査するだけの攻撃者には遅滞効果がなく、重要情報の見落としを保証しません。"},
    encoding_maze: {title:"エンコーディング・メイズ", how:"選択した業務シナリオに合わせ、候補ごとに独立した架空レコード・ファイル名・タイトルを作ってから多段変換します。認証情報保管庫では、.envにシナリオ別環境変数、その他の形式に架空login_url項目を使い、password値は変えません。", target:"取得後に複数候補を復元・正規化し、どれが価値ある情報か見極めようとする攻撃者を想定します。", limit:"暗号化ではありません。一括デコードは容易で、データベース自体が読むだけで通知するわけでもありません。"},
  },
  en: {
    env: {title:"Canary File", how:"Embeds a monitoring URL supplied by the operator in a plausible document or configuration file.", target:"An intruder steals a canary file and visits the URL inside it. Depending on the destination's configuration, it can report the contact or record request details for follow-up investigation.", limit:"A standalone canary file uses one URL. Encrypted Deep Nest, Directory Maze and Encoding Maze accept up to 400 URLs and record file assignments in their private operator inventory. If a URL is reused, an alert cannot identify the exact file. Reading or downloading a file alone does not trigger an HTTP token. Network blocking or workflows that never test URLs prevent alerts. An alert does not identify whether a human or AI caused it."},
    database: {title:"Decoy Database", how:"Creates a plausible schema populated only with synthetic records, up to 10,000 rows. The Password Vault template puts its canary URL in one randomly selected login_url record and leaves the password value unchanged.", target:"Intruders collecting .db files for customer or order data, including those who validate stolen data later.", limit:"This creates a standalone database; it does not connect to production or monitor reads. Avoid importing real data. A real database can still leak alongside decoys. The related Data Dilution concept mixes many synthetic records into a production database to make leaked data harder to select and use. This tool introduces the concept but does not mix records into production."},
    web: {title:"Static Decoy Portal", how:"Creates a static page that resembles an archive or operations portal.", target:"Attacks that enumerate public URLs and admin-like subdirectories, then follow links or collect files.", limit:"Static HTML has no authentication, session, setting changes, access control or alert delivery. Opening the page does not fetch its canary link."},
    fake_trap: {title:"Fake Trap", how:"Creates static HTML with a warning, a reported-message display or an authentication spinner. The page does not report, authenticate, collect information or keep a connection open.", target:"A person or AI agent reaches a decoy path, reads the display and may reconsider whether access has been detected.", limit:"This has no effect on scripts that ignore the display or attackers exploring other paths in parallel. Configure hosting logs and alerts separately; delay is not guaranteed."},
    ransomware_tripwire: {title:"Ransomware Decoy Flood", how:"Generates fictional business files and a Python standard-library monitor that locally records content changes, deletion or replacement of those specific files. The deployment ZIP and monitor script are separate downloads.", target:"Ransomware or another process encrypts, deletes or replaces a monitored tripwire file.", limit:"The monitor polls about once per second and does not detect read-only access. Real data may be damaged before an alert; it does not stop processes, isolate a device or restore data. It can miss brief changes and may produce false alarms."},
    nest: {title:"Encrypted Deep Nest", how:"Builds branching layers of encrypted ZIP files containing decoy files and more archives. The selected primary format stays common; weighted occasional alternatives can include Excel, SQLite and .env. Passwords and the mapping to recovery-note files stay in the operator-only file. The notes imply a separate key register but disclose no password characters. A distinct canary URL per file can identify which assigned file was contacted; reused URLs identify only a group. In the Password Vault scenario, .env files use the scenario's environment variable and other formats use the synthetic login_url field; password values stay unchanged.", target:"Intruders rapidly collecting backups/configuration and those who open candidate archives to find secrets.", limit:"The selected primary format is used for about 75% of decoys when format mixing is enabled. Parallel/offline analysis after exfiltration adds no on-site delay. Strong passwords can be infeasible to crack; obvious clues reveal the trap. This does not replace normal encryption or backups."},
    stream: {title:"Infinite Stream", how:"An authenticated, isolated endpoint returns data without a total size or duration cutoff while connected, with bandwidth/concurrency caps and operator stop.", target:"Bulk-download workflows that wait for the file to finish, occupying a rushed intruder's time and attention.", limit:"The backend closes a connection after five seconds without socket activity, including when a stalled write blocks delivery. Partial downloads, parallel discovery and intentional disconnects also bypass it; an endless response may itself look suspicious. The GUI does not start it; deployment, authentication, start-event monitoring and capacity limits belong in the host environment."},
    directory_maze: {title:"Directory Maze", how:"Creates finite real directories and HTML links with branches, documents and configuration files. In the Password Vault scenario, .env files use the scenario's environment variable and other formats put the canary in a synthetic login_url field without changing password values.", target:"Crawlers and AI-generated tools that enumerate subdirectory names and download discovered files.", limit:"The tree is finite. URL deduplication and parallelism speed exploration; a crawler that only indexes links gains little delay. It cannot guarantee that important files are missed."},
    encoding_maze: {title:"Encoding Maze", how:"Creates independent synthetic records, file names and titles for the selected business scenario, then applies layered encodings. In the Password Vault scenario, .env files use the scenario's environment variable and other formats put the canary in a synthetic login_url field without changing password values.", target:"Intruders who restore and inspect multiple candidates after collection to identify useful information.", limit:"This is not encryption; batch decoding is easy. It does not alert when read."},
  },
};
const usLegal = {
 ja: {
  env:["権限のある環境に監視URL付きの偽ファイルを置く通常利用は、それ自体が第三者システムへの無断アクセスとは限りません。","URLの接触ログや監視事業者への転送を確認します。他人の認証情報を使って無断アクセスすればCFAAが問題となり得ます。"],
  database:["権限のある環境に合成データの偽DBを作る通常利用は、それ自体が第三者システムへの無断アクセスとは限りません。","第三者DBから無断でデータを取得する行為はCFAAが問題となり得ます。実在者情報や接触ログにはプライバシー法等も関係します。"],
  web:["権限のある自組織の経路で静的な偽画面を提供する行為は、それ自体が第三者システムへの無断アクセスとは限りません。","第三者サービスへのなりすましや資格情報収集、通信内容の傍受には別の法的問題が生じ得ます。"],
  fake_trap:["権限のある自組織の経路で静的な警告画面を提供する行為は、それ自体が第三者システムへの無断アクセスとは限りません。","実在機関へのなりすまし、誤接触による損害、通信内容の収集は別途検討します。生成画面は実際の通報や情報収集を行いません。"],
  nest:["権限のある環境で架空の暗号化アーカイブを生成・配置する行為は、それ自体が第三者システムへの無断アクセスとは限りません。","他人の認証情報を使った無断ログインや第三者システムへの侵入はCFAAが問題となり得ます。"],
  stream:["権限のある隔離環境で配信を行う行為は、それ自体が第三者システムへの無断アクセスとは限りません。","正規利用者や第三者の資源に損害を与えた場合、行為・損害や契約に応じ別の責任が問題となり得ます。"],
  directory_maze:["権限のある場所に架空の階層とファイルを配置する行為は、それ自体が第三者システムへの無断アクセスとは限りません。","配置や調査のために他人のアクセス制御を無断で突破する行為はCFAAが問題となり得ます。"],
  encoding_maze:["権限のある場所で架空データを変換・配置する行為は、それ自体が第三者システムへの無断アクセスとは限りません。","他人の認証情報を使った無断ログインはCFAAが問題となり得ます。"],
  data_dilution:["権限のあるDBに合成レコードを混在させる構想は、それ自体が第三者システムへの無断アクセスとは限りません。","第三者情報の混入、誤送信、個人情報の取扱い、契約や州法を検討します。ツールはこの構想を実装しません。"],
  honeyword:["自組織が管理する認証で偽一致を隔離環境へ分岐する構想は、それ自体が第三者システムへの無断アクセスとは限りません。","入力された資格情報や通信内容の収集、第三者になりすます画面、監視の範囲を検討します。ツールは認証に組み込みません。"]
 },
 en: {
  env:["Placing a decoy file with a monitoring URL in an authorized environment is not, by itself, necessarily unauthorized access to someone else's system.","Review contact logs and transfers to the monitoring provider. Unauthorized access using another person's credentials may implicate the CFAA."],
  database:["Creating a synthetic decoy database in an authorized environment is not, by itself, necessarily unauthorized access to someone else's system.","Unauthorized retrieval from another database may implicate the CFAA. Privacy laws may separately apply to real personal data and contact logs."],
  web:["Hosting a static decoy page on an authorized path is not, by itself, necessarily unauthorized access to someone else's system.","Impersonating a third-party service, collecting credentials or intercepting communications may raise separate legal issues."],
  fake_trap:["Hosting a static warning on an authorized path is not, by itself, necessarily unauthorized access to someone else's system.","Consider impersonation of real agencies, harm from accidental access and collection of communications. Generated pages do not actually report or collect information."],
  nest:["Creating and placing synthetic encrypted archives in an authorized environment is not, by itself, necessarily unauthorized access to another system.","Unauthorized login using another person's credentials or intrusion into a third-party system may implicate the CFAA."],
  stream:["Serving data from an authorized isolated environment is not, by itself, necessarily unauthorized access to someone else's system.","Harm to legitimate users or third-party resources can raise separate liability or contractual issues depending on the conduct and damage."],
  directory_maze:["Placing fictional files and directories in an authorized location is not, by itself, necessarily unauthorized access to another system.","Bypassing a third party's access controls without authority to deploy or investigate may implicate the CFAA."],
  encoding_maze:["Encoding and placing synthetic data in an authorized location is not, by itself, necessarily unauthorized access to another system.","Unauthorized login with another person's credentials may implicate the CFAA."],
  data_dilution:["The concept of mixing synthetic records into an authorized database is not, by itself, necessarily unauthorized access to another system.","Consider third-party information, accidental messages, personal-data handling, contracts and state laws. The tool does not implement this concept."],
  honeyword:["The concept of routing a decoy match in an organization's own authentication system to an isolated environment is not, by itself, necessarily unauthorized access to another system.","Consider credential or communication content collection, impersonation and monitoring scope. The tool does not integrate with authentication."]
 }
};
// These are conditional examples, not guarantees or live deployment status.

const methodFlows = {ja: {}, en: {}};
Object.assign(translations.ja, {flow_if:"効果が期待できる場合", flow_else:"効果が弱まる条件", flow_response:"ポイント"});
Object.assign(translations.en, {flow_if:"When it may help", flow_else:"When the effect may be reduced", flow_response:"Key points"});
Object.assign(methodFlows.ja, {
 env:{context:"例：運用者が発行済みの監視URLを、設定ファイルや業務文書に埋め込みます。",steps:[["1. 偽ファイルを配置","秘密情報に見える文書を、権限のある探索経路に置きます。"],["2. 攻撃者が取得","設定ファイルを回収し、記載されたURLを接続先として調べます。"],["3. URLを試す","攻撃者やスキャナーが監視URLへHTTPリクエストを送ります。"],["4. 通知して対応","監視サービスが要求を受ければ通知し、担当者がログを調査します。"]],ifCase:["内部ネットワークから監視URLへアクセスされると、そのリクエストを攻撃の兆候として検知できます。","通知を受けて早期対応に移る手掛かりになります（内部からURLへ到達でき、通知設定が必要です）。"],elseCase:["カナリアページが正規利用者もアクセスしやすい場所にあると、誤接触による通知が発生し、攻撃の兆候と区別しにくくなります。","ファイルを読んだだけ、URLを試さない、通信が遮断される場合はURL通知が発生しません。"],response:"監視URLの発行・通知先と、ファイル取得を記録するWeb／OS監査を別々に設定します。",note:"通知は設定されたサービスからの要求記録であり、攻撃者本人の特定や対応前の遮断を保証しません。"},
 database:{context:"例：顧客台帳に見える、合成レコードのみのSQLiteを独立したデコイ領域に置きます。",steps:[["1. 偽DBを用意","架空の顧客や注文を含む単一テーブルを生成します。"],["2. 本物らしく配置","業務のバックアップに見える名前や経路で、権限のある場所に置きます。"],["3. 攻撃者が回収","発見したDBを持ち帰り、本物の候補と比較します。"],["4. 真偽を確認","候補ごとに内容や関連性を確認すると、選別に時間がかかる可能性があります。"]],ifCase:"偽物を本物と誤認したり、確認の途中で本物を見落としたりする可能性があります。",elseCase:"偽DBを無視する、本物を別途取得する、全候補を一括で持ち出す行動も可能です。",response:"配信ログやOS・DB監査を別途設定します。カナリアURLを試された場合の通知も別のイベントです。",note:"本番DBと混ぜる方式ではありません。DBの閲覧だけで自動通知されず、本物の流出も防げません。"},
 web:{context:"例：アーカイブや管理ポータルに見える静的ページをデコイ用の経路に配置します。",steps:[["1. ページを用意","タイトルと、必要なら運用者が指定したカナリアURLへのリンクを設定します。"],["2. 攻撃者が探索","管理画面やバックアップを探す途中で、ページにたどり着きます。"],["3. 内容を調べる","表示されたページやリンクを確認し、実際の管理情報か判断します。"],["4. 接触を記録","配信側にアクセスログを設定していればページへの要求を確認できます。"]],ifCase:"ページやリンクを調べる場合は、偽の候補を確認する作業が増える可能性があります。",elseCase:"ページを無視する、直接別経路に進む、リンクを試さない場合もあります。",response:"ページ要求の監視と、リンク先のカナリアサービスの通知を別々に設定します。",note:"生成物は静的HTMLです。ログイン機能や状態保持はなく、開いただけではリンク先へアクセスしません。"},
 nest:{context:"例：バックアップ風のZIP内に、偽文書とさらに別の暗号化ZIPを分岐させて置きます。",steps:[["1. 階層を作る","暗号化ZIPの各層に、偽文書と次のZIPを混在させます。"],["2. 対応を保管","各ZIPのパスワードと構成情報は運用者専用ファイルに分けます。"],["3. 攻撃者が探索","候補ごとにパスワードを探し、開けたものの内容を確認します。"],["4. 判断を繰り返す","複数の分岐を確認する場合、候補の選択と展開に時間を使い得ます。"]],ifCase:"途中の候補が本物と見分けられず、未確認の枝にも有用な情報があり得る場合、調査を続けるほど手間が増え、打ち切れば本物も見落とす可能性があります。偽文書を1つ見つけても、未確認の枝まで全て偽物とは断定できません。",elseCase:"途中で不自然な名前・構造や既知の本番情報との矛盾が見つかれば、罠だと疑われることがあります。ただし、それだけで未確認の内容まで確定するとは限りません。また、見破らなくても全体を持ち出して後で並列解析すれば現場での展開時間は減りますが、持ち出し後の選別作業は残り得ます。本物を別経路で得る場合も、この罠の影響は小さくなります。",response:"アクセス監査や、使用されたカナリアURLの通知を別途設定します。管理者専用の鍵台帳は公開しません。",note:"最後まで見分けられないことは保証できません。ZIPを開くだけでは自動通知されず、実際の効果は比較試験で確認します。"},
 stream:{context:"例：隔離された配信経路を、取得完了まで待つバックアップに見立てます。",steps:[["1. 専用サーバーを用意","生成されたサンプルを隔離先に設置し、認証・帯域・同時接続数を設定します。"],["2. 要求を受ける","認証された要求に対して、サーバーがダミーデータの配信を始めます。"],["3. 配信が続く","接続中は総容量・総時間で終わらず、完了を待つ相手の時間を使わせます。"],["4. 開始を把握","サーバーの開始イベントを収集し、担当者が確認・停止できます。"]],ifCase:"全量のダウンロードが終わるまで待つ相手には、対応する時間を得られる可能性があります。",elseCase:"部分取得、切断、並列探索や無通信タイムアウトで、待たずに別の行動を取れます。",response:"サーバーの起動、ログ収集・通知、接続・帯域制限と停止手順を配信側で設定します。",note:"ツールはサーバーを自動起動しません。無通信が5秒続く接続は終了し、攻撃者の拘束は保証されません。"},
 directory_maze:{context:"例：archive／reports／backupなどの階層に偽ファイルを分散させます。",steps:[["1. 階層を生成","有限のディレクトリと偽文書を作り、必要なら別の枝へHTMLリンクを張ります。"],["2. 隔離先に配置","静的配信先で正規利用者の経路と分け、アクセスログを設定します。"],["3. 攻撃者が探索","ディレクトリやリンクを巡り、見つけたファイルを取得します。"],["4. 候補を確認","複数の文書の中から目的の情報を選ぶ場合、追加の確認が生じ得ます。"]],ifCase:"一つずつ巡り、各ファイルを確認する探索では、追加の要求や選別に時間を使い得ます。",elseCase:"並列探索やURLの重複排除、一括取得後のオフライン解析で、現場での遅れは小さくなります。",response:"配信ログの監視と、埋め込んだカナリアURLの通知を設定し、管理者用の対応表は別保管します。",note:"生成される階層は有限です。重要情報の見落としや通知の到達を保証しません。"},
 encoding_maze:{context:"例：架空の請求情報などを複数候補に分け、それぞれをBase64などで多段変換します。",steps:[["1. 候補を作る","業務シナリオに合わせて、異なる架空レコードやファイル名を用意します。"],["2. 多段変換","各候補を複数のエンコーディング層に包みます。暗号化ではありません。"],["3. 攻撃者が復元","取得後に形式を読み取り、各層をデコードします。"],["4. 内容を選別","復元した候補を比較して、価値がある情報かを判断します。"]],ifCase:"復元後の内容を個別に判断する場合、候補の確認作業が増える可能性があります。",elseCase:"既知の形式ならスクリプトで一括デコードでき、並列化すれば作業が短縮されます。",response:"取得を知るには配信側の監視が必要です。URLを試した場合のカナリア通知と区別します。",note:"オフラインでの復元・閲覧は自動検知できません。デコード順とURL対応は運用者用ファイルに保存します。"},
 fake_trap:{context:"例：通常使わないデコイ経路に『通報済み』の表示や認証中スピナーを置きます。",steps:[["1. 表示を選ぶ","警告、通報済み、認証中のいずれかの静的HTMLを生成します。"],["2. デコイ経路に配置","自組織の管理下に置き、正規利用者や監視ツールの誤接触を避けます。"],["3. 相手が表示を見る","画面を読むAIや人が、検知された可能性について再判断します。"],["4. 防御側が確認","アクセスログを別途監視していれば、経路への接触を確認できます。"]],ifCase:"警告を信じて調べ直す、待機を続けるなどの場合に、探索が遅れる可能性があります。",elseCase:"警告を読まないスクリプトや、別経路を並列に進む攻撃には、この表示だけでは働きません。",response:"配信側でログと内部通知を設定し、接触した正規利用者への対応も準備します。",note:"画面は実際に通報・認証・情報収集を行いません。スピナーも表示のみで接続を維持しません。"},
 ransomware_tripwire:{context:"例：普段の業務アプリが書き換えない共有フォルダーに、架空の運用ファイルを数個置きます。",steps:[["1. 架空ファイルを生成","業務らしい名前と合成データのファイルを4〜8個作ります。"],["2. 監視先へ配置","配置ZIPを展開し、通常のアプリが更新しない場所に置きます。"],["3. 監視を開始","運用者専用スクリプトを別の保護された場所に置き、配置先ルートを指定して起動します。"],["4. 変化を確認","変更・削除・差し替えをローカルログに記録し、担当者が初動を判断します。"]],ifCase:"攻撃プロセスが監視ファイルを書き換える・削除する場合、短い間隔で変化を記録できます。",elseCase:"読み取りや持ち出しだけでは反応しません。監視停止、差し替え、短い間に元へ戻す操作や並列実行で見逃す場合があります。",response:"ログを監視対象と別の保護された場所へ保存します。異常時は既存のEDRやOS保護機能で端末隔離を判断します。",note:"この仕組み自体は暗号化を止めず、データも復元しません。復元可能なコピーがない場合、破損した元データは戻せません。"},
 data_dilution:{context:"例：本物1万件と架空100万件を混ぜた場合、無作為に1件を選ぶと約99%は偽物です。",steps:[["1. 本物と偽物を混ぜる","関連する架空レコードも整え、同じ流出対象に大量の候補を用意する構想です。"],["2. 正規業務を維持","運用者は保護された判別機構を使い、本物だけを検索・集計します。"],["3. 混在データが流出","攻撃者が大量取得しても、個々の候補の真偽がすぐ分かるとは限りません。"],["4. 攻撃者が選別","外部情報と照合しても複数の説明が成り立つ場合、正解の判断が難しくなり得ます。"]],ifCase:"本物を高い精度で選別できなければ、流出データの利用・取引価値が下がる可能性があります。",elseCase:"選別せず全件を公開する、外部情報で絞る、判別機構も侵害する場合を別途評価します。",response:"判別台帳・アクセス権を分離し、DB読み取りや外部転送の監査と対応手順を設計します。",note:"技術紹介のみで実装はありません。99%は無作為抽出の割合で、被害軽減率ではなく、本物も流出します。"},
 honeyword:{context:"例：管理者アカウントの正規パスワードとは別に、認証側で検知用の偽パスワードを用意します。",steps:[["1. 認証側に偽候補を登録","対象アカウントに正規パスワードと区別できる偽パスワードを登録します。外部ファイルへの配置は必要ありません。"],["2. 攻撃者が試行","総当たりなどでログインを試みる場合や、流出したデータ・ディルーションの偽認証情報を試す場合を想定します。"],["3. 一致で分岐","登録済みの偽パスワードに一致した場合だけ、本番認証を成立させず独立した偽セッションへ誘導します。"],["4. 通知・操作観測","偽セッションへの移行を通知し、偽画面での操作を記録します。"]],ifCase:"試行された値が登録済みの偽パスワードに一致し、攻撃者が偽環境を調べれば、検知・遅滞につながる可能性があります。",elseCase:"偽候補に一致しなければ誘導されません。試行回数や偽候補の選び方によっては総当たりで一致しにくく、正規利用者の誤入力やMFAの差も課題です。",response:"正規認証とMFA、試行制限を維持し、偽セッションの権限・データ・ログを本番から隔離します。試行予算と誤発火を評価します。",note:"技術紹介のみで認証連携は未実装です。一般の誤パスワードすべてを誘導せず、総当たりの検知・阻止を保証しません。"}
});
Object.assign(methodFlows.en, {
 env:{context:"Example: place a monitoring-service URL supplied by the operator in a decoy configuration file or document.",steps:[["1. Place a decoy","Put a plausible-looking file on an authorized discovery path."],["2. Intruder collects it","The intruder finds the file and inspects the apparent endpoint."],["3. URL is requested","An intruder or scanner sends an HTTP request to the monitoring URL."],["4. Alert and investigate","If the monitoring service receives the request, it alerts the responder to inspect logs."]],ifCase:["An access to the monitoring URL from inside the network can be detected as a sign of suspicious activity.","The alert can prompt an early response (the URL must be reachable internally and alerting must be configured)."],elseCase:["If the canary page is easy for legitimate users to reach, accidental visits can trigger alerts and make attack activity harder to distinguish.","Reading alone, never testing the URL, or blocked outbound traffic produces no URL alert."],response:"Configure the monitoring service and alert destination separately from web or OS auditing of file retrieval.",note:"An alert records a request, not the identity of an attacker; timely response and containment are not guaranteed."},
 database:{context:"Example: place a SQLite file containing only synthetic customer records in a separate decoy area.",steps:[["1. Build the decoy","Generate a single table with fictional customer or order records."],["2. Place it plausibly","Use a backup-like name and authorized location relevant to the environment."],["3. Intruder collects candidates","The intruder takes the decoy and may compare it with other database files."],["4. Verify contents","Checking each candidate's records and context may add selection time."]],ifCase:"An intruder may mistake a decoy for real data or stop checking before finding a real candidate.",elseCase:"The intruder may ignore the decoy, obtain the real database elsewhere, or collect everything in bulk.",response:"Configure hosting logs, OS or DB read auditing separately; a canary URL request is a distinct event.",note:"This is a separate decoy database, not production-record mixing. Reading alone does not alert or prevent a real leak."},
 web:{context:"Example: put a static archive or operations portal lookalike on a dedicated decoy path.",steps:[["1. Prepare the page","Choose a title and optionally a link to an operator-supplied canary URL."],["2. Intruder explores","The page is encountered while looking for an administrative area or backup."],["3. Inspect contents","The intruder reviews the page or link and judges whether it leads to useful data."],["4. Record contact","Hosting access logs can record a request when separately configured."]],ifCase:"Inspecting the page and its link may add candidate-checking work.",elseCase:"The intruder may ignore the page, use another route, or never request the link.",response:"Configure monitoring for page requests and canary-service alerts as separate events.",note:"The generated page is static: no login or persistent state, and opening it does not request the linked URL."},
 nest:{context:"Example: a backup-like archive contains fictional documents and branching encrypted ZIPs.",steps:[["1. Build layers","Place decoy documents and nested ZIPs across multiple branches."],["2. Protect the mapping","Keep passwords and structure in a separate operator-only companion."],["3. Intruder explores","The intruder searches for passwords, opens candidates and inspects their contents."],["4. Repeat selection","Checking several branches may consume time for choosing and opening candidates."]],ifCase:"If candidates remain indistinguishable during exploration and unchecked branches may contain useful information, continuing adds work while stopping risks missing real data. Finding one fake document does not prove every unchecked branch is fake.",elseCase:"Unnatural names or structure, or a contradiction with independently known production information, may raise suspicion; this does not necessarily establish what is in unchecked branches. Without identifying a trap, an intruder can also collect everything and analyze it in parallel later, reducing on-site delay while potentially still facing selection work. Obtaining real data through a separate route can also reduce the effect.",response:"Configure access auditing or canary-use alerts separately. Never deploy the private password inventory.",note:"Indistinguishability through the final branch is not guaranteed. Opening a ZIP alone does not alert; assess actual effectiveness through controlled comparisons."},
 stream:{context:"Example: an isolated download endpoint resembles a backup that a client may wait to complete.",steps:[["1. Prepare a server","Deploy the generated sample in isolation; configure authentication, bandwidth and concurrency limits."],["2. Receive a request","The server begins delivering dummy data to an authenticated requester."],["3. Keep streaming","While connected, the response has no total size or duration cutoff."],["4. Observe the start","A separately collected start event can prompt investigation and operator stop."]],ifCase:"A client waiting for the full download may give responders additional time.",elseCase:"Partial retrieval, disconnecting, parallel exploration or an inactivity timeout ends or bypasses the wait.",response:"Start and monitor the server separately; set up logs, alerts, limits and an operator stop procedure.",note:"The tool does not start the server. A connection with five seconds of inactivity closes; attacker delay is not guaranteed."},
 directory_maze:{context:"Example: distribute decoy files across archive, reports and backup directories.",steps:[["1. Generate a tree","Create finite directories and fictional files, optionally linking branches with HTML."],["2. Host in isolation","Separate it from legitimate paths and configure hosting access logs."],["3. Intruder explores","The intruder follows directories or links and collects files."],["4. Check candidates","Finding useful-looking data may involve inspecting additional documents."]],ifCase:"Sequential traversal and inspection may add requests and selection work.",elseCase:"Parallel crawling, URL deduplication and bulk offline analysis may reduce on-site delay.",response:"Monitor hosting logs and canary URL use separately; retain the operator mapping privately.",note:"The tree is finite. Missing real information or receiving a timely alert is not guaranteed."},
 encoding_maze:{context:"Example: wrap several independent fictional invoice candidates in multiple encoding layers.",steps:[["1. Create candidates","Generate distinct fictional records and filenames for the chosen business scenario."],["2. Encode in layers","Wrap each candidate in multiple encodings; this is not encryption."],["3. Intruder decodes","After collection, the intruder reads the format and restores each layer."],["4. Assess content","The restored candidates are compared to identify useful information."]],ifCase:"Individual content assessment may add selection work after decoding.",elseCase:"Known formats can be decoded in bulk and parallelized to reduce the work.",response:"Use hosting-side monitoring for retrieval; distinguish it from alerts when a canary URL is requested.",note:"Offline decoding and reading are not automatically detected. Decode order and URL mappings are kept in the operator file."},
 fake_trap:{context:"Example: place a 'reported' warning or authentication spinner at an otherwise unused decoy path.",steps:[["1. Choose a display","Generate static HTML for an unusual-access warning, reported message or spinner."],["2. Deploy the page","Host it on an authorized path and avoid accidental access by legitimate users or monitors."],["3. A visitor reads it","An AI agent or person may reassess whether access has been detected."],["4. Defender observes","Separately configured hosting logs can record contact with the path."]],ifCase:"A visitor who investigates the warning or keeps waiting may spend additional time.",elseCase:"A script that ignores the display, or parallel exploration of another route, can bypass this effect.",response:"Configure hosting logs and internal alerts; prepare a response for legitimate users who encounter the page.",note:"The page does not actually report, authenticate or collect information. The spinner does not keep a server connection open."},
 ransomware_tripwire:{context:"Example: place a few fictional operations files in a directory that ordinary applications do not update.",steps:[["1. Generate synthetic files","Create four to eight plausible-looking files containing fictional data."],["2. Place the files","Extract the deployment ZIP somewhere visible to an attacker but outside normal application write paths."],["3. Start the monitor","Keep the operator-only script separate and run it against the extracted root."],["4. Review local events","Changes, deletion or replacement are logged locally for an operator to assess."]],ifCase:"If a process changes, deletes or replaces a monitored tripwire file, the monitor can record the change shortly afterward.",elseCase:"Reads or exfiltration alone do not trigger it. Stopping the monitor, replacing the tripwire, or changing and restoring a file between polls can evade detection.",response:"Keep logs in a protected location outside the watched directory. Use existing endpoint controls to decide whether to isolate a device.",note:"This does not stop encryption or restore data. Without a recoverable copy, destroyed original data cannot be reconstructed."},
 data_dilution:{context:"Example: among 10,000 genuine and 1,000,000 synthetic records, a uniformly random single record is about 99% synthetic.",steps:[["1. Mix candidates","The concept adds many plausible synthetic records and related data to the same leak target."],["2. Maintain legitimate use","Authorized operations rely on a protected mechanism to distinguish real records."],["3. Mixed data leaks","An intruder retrieves the dataset but may not immediately know which records are genuine."],["4. Select candidates","External comparisons can still leave multiple plausible explanations and uncertain answers."]],ifCase:"If real records cannot be selected accurately, leaked data may become less useful or valuable to a buyer.",elseCase:"Evaluate publication without selection, external matching, and compromise of the classification mechanism separately.",response:"Design separated classification data and permissions, database read/transfer auditing and incident response.",note:"Concept overview only: no implementation. The 99% is a random-sample proportion, not a damage-reduction rate; real records still leak."},
 honeyword:{context:"Example: configure a privileged account with decoy passwords separate from its real password.",steps:[["1. Register decoy candidates","Configure decoy passwords for the account in the authentication system. Placing them in an external file is not required."],["2. Attacker attempts login","Consider password guessing or use of decoy credentials leaked through a Data Dilution design."],["3. Branch on a match","Only a registered decoy-password match routes to an isolated session; production authentication remains unsuccessful."],["4. Alert and observe","Alert on the decoy session and record its subsequent actions."]],ifCase:"If an attempt matches a registered decoy password and the attacker explores the fake environment, detection and delay may result.",elseCase:"No decoy session is issued without a match. Match probability depends on the attempt budget and decoy selection; legitimate mistakes and MFA differences also matter.",response:"Preserve real authentication, MFA and rate limits; isolate decoy permissions, data and logs. Evaluate attempt budgets and false positives.",note:"Concept overview only; authentication integration is not implemented. Ordinary incorrect passwords do not all trigger a decoy, and detecting or stopping every guessing attack is not guaranteed."}
});
// State the compromise stage explicitly; no scenario guarantees containment.
// Keep decision-critical operating limits in the visible Key points section,
// even when the fuller explanation also appears in a note or method overview.
const methodKeyPointAdditions = {
  ja: {
    env:["このURL型カナリアは、ファイルを読む・開く・実行するだけでは発火せず、URLへの実際の要求が必要です。外部接続できても要求がなければ通知されません。送信元だけで攻撃者本人と断定できず、即時通知も保証されません。"],
    database:["DBファイルの作成・取得・閲覧だけでは通知されず、本番DBへのアクセス監視や流出防止もしません。配置先のアクセスログやDB監査は別途設定してください。"],
    web:["静的ページのため、ログイン・認証・状態保存・通知は行いません。ページを開いただけでは、埋め込んだカナリアURLにもアクセスしません。"],
    nest:["ZIPを開くだけでは通知されず、最後まで本物と区別できない保証もありません。持ち出し後の並列・オフライン解析では現場の遅滞が小さくなります。"],
    stream:["生成しただけでは配信サーバーは起動しません。無通信が5秒続くと接続が終了し、部分取得や並列接続でも待ち時間を迂回される場合があります。"],
    directory_maze:["ディレクトリとファイル数は有限です。並列巡回や一括取得後のオフライン解析で遅延は小さくなり、実データの見落としや即時通知を保証しません。"],
    encoding_maze:["エンコードは暗号化ではありません。取得後の一括デコードやオフライン閲覧は自動検知されないため、取得ログを別途監視してください。"],
    fake_trap:["表示だけの静的ページで、実際の通報・認証・情報収集は行いません。スピナーも接続を維持せず、表示を無視する自動処理には作用しません。"],
    ransomware_tripwire:["ファイル変更を記録する仕組みで、暗号化を止めたりデータを復元したりはしません。読み取りや持ち出しだけでは発火せず、監視停止や変更の復元で見逃す場合があります。"],
    data_dilution:["合成データを混ぜても本物のレコードは流出し得ます。ランダム抽出時の合成比率は、被害軽減率を示すものではありません。全件公開や外部情報との照合も防げません。"],
    honeyword:["登録済みの偽パスワードとの一致時だけ分岐します。このサンプルは認証連携・通知を実装せず、誤入力やMFAの違いによる誤検知にも注意が必要です。"],
    path_maze:["配置するフォルダーとファイルは有限です。対象を絞る攻撃や並列処理では実ファイルが先に処理される場合があり、遅滞や見落とし防止は保証されません。"],
    sparse_decoy:["部分暗号化やサイズによる除外では追加負荷が小さくなります。バックアップ・同期・コピーは論理サイズ分の容量を使う場合があるため、小規模に試して空き容量を監視してください."]
  },
  en: {
    env:["This URL canary triggers only when the URL is actually requested; reading, opening or running the file alone is not enough. External connectivity without a request produces no alert. A source address does not identify the attacker, and immediate delivery is not guaranteed."],
    database:["Creating, retrieving or viewing the database alone sends no alert. This does not monitor or prevent access to a production database or its leakage; configure hosting logs or database auditing separately."],
    web:["The page is static: it does not log in, authenticate, retain state or send alerts. Opening the page alone does not request its canary URL."],
    nest:["Opening a ZIP does not alert, and indistinguishability through the final branch is not guaranteed. Parallel or offline analysis after collection reduces on-site delay."],
    stream:["Generating the sample does not start its server. Five seconds without activity closes a connection, and partial retrieval or parallel connections may bypass the wait."],
    directory_maze:["The directory tree and file count are finite. Parallel crawling or offline analysis after bulk collection can reduce delay; the method does not guarantee missed real data or an immediate alert."],
    encoding_maze:["Encoding is not encryption. Bulk decoding and offline inspection after collection are not detected automatically; configure retrieval monitoring separately."],
    fake_trap:["This is a static display; it does not actually report, authenticate or collect information. The spinner does not keep a connection open, and automated processing that ignores the page is unaffected."],
    ransomware_tripwire:["This records file changes; it does not stop encryption or restore data. Reads and exfiltration alone do not trigger it, and stopping the monitor or restoring a file between checks may evade detection."],
    data_dilution:["Genuine records can still leak. The synthetic share in a random sample is not a measure of harm prevented; this does not stop publication of all records or matching against external information."],
    honeyword:["Diversion occurs only when a registered decoy password matches. This sample does not implement authentication integration or alerts, and legitimate mistakes or MFA differences can cause false positives."],
    path_maze:["The deployed folders and files are finite. Selective targeting or parallel processing can reach real files first; delay and prevention of missed data are not guaranteed."],
    sparse_decoy:["Partial encryption or size-based exclusions reduce the extra work. Backups, synchronization and copies may consume the full logical size, so start small and monitor free space."]
  }
};
function applyMethodKeyPointAdditions() {
  for (const [lang, methods] of Object.entries(methodKeyPointAdditions)) {
    for (const [method, points] of Object.entries(methods)) {
      const current = methodFlows[lang][method].response;
      methodFlows[lang][method].response = [...(Array.isArray(current) ? current : [current]), ...points];
    }
  }
}

const flowScenarios = {
 ja: {
  env:"想定：攻撃者が侵入後に偽ファイルを取得し、持ち出したURLを試す。侵害や流出の後でも接触を検知する狙いです。",
  database:"想定：侵入した攻撃者が偽DBを盗み出す。持ち出し後の真偽確認に手間を生じさせる狙いです。",
  web:"想定：攻撃者がサイトを探索、または侵入後に管理経路を探索して偽画面に接触する。探索中の検知・遅滞を狙います。",
  nest:"想定：攻撃者が侵入後にデコイZIPを盗み出す。持ち出し後も中身を復号・展開・選別する手間を生じさせる狙いです。",
  stream:"想定：侵入後、または配信経路に到達した攻撃者がバックアップを盗もうとする。取得中に時間を稼ぐ狙いです。",
  directory_maze:"想定：侵入した攻撃者や探索者が偽の階層を調べてファイルを盗み出す。探索と取得後の選別に手間を生じさせる狙いです。",
  encoding_maze:"想定：侵入した攻撃者が変換済みの偽候補を盗み出す。持ち出し後の復元・選別に手間を生じさせる狙いです。",
  fake_trap:"想定：攻撃者がサイトを探索、または侵入後にデコイ経路へ到達する。警告を読んだ場合の再判断と遅滞を狙います。",
  ransomware_tripwire:"想定：ランサムウェアなどがファイルを暗号化・削除・差し替える。架空ファイルの変化を手掛かりに初動を促します。",
  data_dilution:"想定：侵入した攻撃者が本物と大量の偽レコードをまとめて盗み出す。流出後の真偽選別と利用を難しくする構想です。",
  honeyword:"想定：攻撃者が総当たりでパスワードを試す、または流出したデータ・ディルーションの偽認証情報を試す。登録済みの偽パスワードに一致した場合に検知・誘導する構想です。"
 },
 en: {
  env:"Scenario: after an intrusion, an attacker steals a decoy file and tries its URL. The aim is to detect contact even after compromise or exfiltration.",
  database:"Scenario: an intruder steals a decoy database. The aim is to add verification work after exfiltration.",
  web:"Scenario: an attacker explores a site or its administrative paths after intrusion and reaches the decoy. The aim is detection and delay during exploration.",
  nest:"Scenario: an intruder steals the decoy ZIP. The aim is to add work decrypting, extracting and selecting its contents after exfiltration.",
  stream:"Scenario: after intrusion, or after reaching the delivery endpoint, an attacker tries to steal a backup. The aim is to buy time during retrieval.",
  directory_maze:"Scenario: an intruder or explorer traverses decoy directories and steals files. The aim is additional exploration and post-collection selection work.",
  encoding_maze:"Scenario: an intruder steals encoded decoy candidates. The aim is additional decoding and selection after exfiltration.",
  fake_trap:"Scenario: an attacker exploring the site or its paths after intrusion reaches the decoy. The aim is reassessment and delay if the display is read.",
  ransomware_tripwire:"Scenario: ransomware or another process encrypts, deletes or replaces files. Changes to synthetic files can prompt an initial response.",
  data_dilution:"Scenario: an intruder steals real records mixed with many decoys. The concept aims to make selection and use harder after a leak.",
  honeyword:"Scenario: an attacker guesses passwords or tries decoy credentials leaked through Data Dilution. The concept detects a registered decoy-password match and routes subsequent actions to an isolated decoy."
 }
};
methodFlows.ja.nest.steps[2] = ["3. 盗み出してファイル確認・解凍", "侵入した攻撃者がデコイZIPを持ち出し、パスワードの探索、解凍、内容確認を試みます。別途回収した本物の暗号化ファイルも候補に含まれる場合があります。"];
methodFlows.en.nest.steps[2] = ["3. Steal and inspect files", "An intruder takes the decoy ZIP and may attempt password discovery, extraction and inspection. Separately collected genuine encrypted files may also be among the candidates."];
methodFlows.ja.nest.steps[3] = ["4. 解凍するか判断", "他の候補も偽物かもしれないと疑えば、解凍や確認に労力をかけるか、価値があるか不明なまま捨てるか迷う可能性があります。"];
methodFlows.en.nest.steps[3] = ["4. Decide what to extract", "Suspicion may extend to other candidates, creating a choice between spending effort to inspect them and discarding files of uncertain value."];
methodFlows.ja.nest.ifCase = "本物と偽物を途中で見分けられない場合、デコイの確認だけでなく、別途回収した本物の暗号化ファイルも偽物かもしれないと疑う可能性があります。解凍・確認を続ければ作業が増え、打ち切れば本物を見落とし得ます。偽文書を1つ見つけても、未確認の枝や別ファイルがすべて偽物とは断定できません。";
methodFlows.en.nest.ifCase = "If genuine files and decoys cannot be distinguished during inspection, suspicion may extend to separately collected genuine encrypted files. Continuing to decrypt and inspect adds work; stopping can mean missing real data. Finding one fake document does not prove that unchecked branches or other files are fake.";
methodFlows.ja.nest.note = "生成するデコイZIPには本物の秘密を入れません。本物への疑いが生じるかは仮説で、最後まで判別できないことも保証できません。ZIPを開くだけでは自動通知されません。";
methodFlows.en.nest.note = "The generated decoy ZIP contains no real secrets. Suspicion extending to real files is a hypothesis, and indistinguishability is not guaranteed. Opening a ZIP alone does not trigger an alert.";
methodFlows.ja.env.ifCase = ["内部ネットワークから監視URLへアクセスされると、そのリクエストを攻撃の兆候として検知し、早期対応の手掛かりにできます。内部からURLへ到達でき、通知設定が必要です。", "盗まれたファイルのURLが後から外部接続可能な環境で試された場合も、監視先に要求が届けば検知できます。記録される時刻や接続元情報はサービスや設定によって異なります。"];
methodFlows.ja.env.elseCase = ["カナリアページが正規利用者もアクセスしやすい場所にあると、誤接触による通知が攻撃の兆候に紛れる可能性があります。", "踏み台・VPN・サンドボックス経由の接続元情報は攻撃者本人を示すとは限りません。ファイルが拡散すると、第三者やスキャナーのアクセスも混ざります。", "URLが試されない場合や通信が遮断された場合、通知されません。"];
methodFlows.ja.env.steps[2][0] = "3. URLにアクセス";
methodFlows.ja.env.response = ["正規利用者が通常アクセスしないURLにカナリアページを配置します。", "URLをファイル内の自然な文脈に埋め込み、カナリアだと気づかれにくくします。", "URLが露見したら無効化し、新しいURLのページに置き換えます。"];
methodFlows.ja.env.note = "";
methodFlows.en.env.ifCase = ["An access to the monitoring URL from inside the network can signal suspicious activity and create an opportunity for early response. The URL must be reachable internally and alerting must be configured.", "A later request to the URL in a stolen file can also trigger detection if it reaches the monitoring endpoint. Recorded timestamps and connection details depend on the service and its configuration."];
methodFlows.en.env.elseCase = ["If the canary page is easy for legitimate users to reach, accidental visits can blend with alerts for suspicious activity.", "A relay, VPN or sandbox may make connection details point to that intermediary rather than the attacker. If the file spreads, third parties or scanners may also visit the URL.", "No alert occurs if the URL is not requested or traffic is blocked."];
methodFlows.en.env.steps[2][0] = "3. Visit the URL";
methodFlows.en.env.response = ["Place the canary page at a URL legitimate users would not normally visit.", "Embed the URL naturally in the file so it is less obvious as a canary.", "If the URL is exposed, disable it and replace it with a page at a new URL."];
methodFlows.en.env.note = "";
methodFlows.ja.database.steps[3] = ["4. 真偽を確認・利用", "別の情報と照合しても正解が確定せず、時間や費用をかけても判断がつかない場合があります。偽DBを転売する可能性もあります。"];
methodFlows.en.database.steps[3] = ["4. Verify and use", "Comparison with other information may remain inconclusive despite time and expense. The decoy may also be resold as genuine."];
methodFlows.ja.database.ifCase = "DB間でユーザーが一致しない場合も、収録範囲や更新時点の違いなどがあり、それだけでは偽物と断定できません。確実な答え合わせができなければ確認が徒労に終わり、選別の負担が残ります。偽DBの転売後に買い手が偽物と判断して共有すれば、売り手の信用に影響する可能性もあります。";
methodFlows.en.database.ifCase = "A user absent from one database may reflect different coverage or snapshot dates; absence alone does not prove a fake. Without reliable ground truth, verification can consume resources yet remain inconclusive. If a buyer identifies a resold decoy and shares feedback, the seller's reputation may also suffer.";
methodFlows.ja.database.elseCase = "攻撃者が登録したユーザーが見当たらなくても、対象テーブル・収録範囲・更新時点を知らなければ判別できない場合があります。逆に、それらを確実に知る場合は手掛かりになり得ます。生成物は架空データだけであり、本物のユーザーを取り込んで検証を妨げる機能はありません。";
methodFlows.en.database.elseCase = "An attacker's own registered account may be absent because the table, scope or snapshot date is unknown; if those facts are reliably known, absence can be a useful clue. Generated decoys contain only synthetic data and do not import real accounts to defeat this check.";
methodFlows.ja.database.note = "攻撃者が偽DBを本物と見分ける可能性があります。データ・ディルーションは別の紹介用構想であり、組み合わせても判別不能を保証しません。読み取りだけでは通知されません。";
methodFlows.en.database.note = "An attacker may distinguish the decoy database from a genuine one. Data Dilution is a separate concept; combining it does not guarantee indistinguishability. Reading alone does not alert.";
methodFlows.ja.data_dilution.ifCase = "全件が公開されても、本物を選別できなければ、データの信頼性や利用・取引価値が下がる可能性があります。外部情報との照合にも作業が必要で、一致だけでは正解と断定できない場合があります。";
methodFlows.ja.data_dilution.elseCase = "判別台帳や照会権限も盗まれると、真偽を選別される可能性があります。また、真偽を選ばず大量に自動試行できる攻撃では、低い本物率でも成功が生じ得ます。流出元などが公開された候補の真偽を明らかにした場合も、その範囲では不確実性が減ります。";
methodFlows.ja.data_dilution.response = "判別台帳と照会権限を分離・監査します。偽パスワードを試したときだけ隔離・検知するハニーワードと、試行制限・MFAを組み合わせる構想も評価します。一般の総当たりを一律に検知・阻止する仕組みではありません。";
methodFlows.ja.data_dilution.note = "このツールでは技術紹介のみを行い、本番DBへの混在は実装しません。全件公開には本物も含まれますが、公開と本物の判別・悪用は別に評価します。漏えい時の法令・契約上の通知義務は別途確認します。";
methodFlows.en.data_dilution.ifCase = "Even if the full dataset is published, its reliability and resale or use value may fall if genuine records cannot be selected. External matching takes work, and a match alone may not establish ground truth.";
methodFlows.en.data_dilution.elseCase = "A stolen classification inventory or lookup privilege may reveal which records are genuine. Large-scale automated attempts without prior selection can still succeed despite a low genuine fraction. If the source or another party discloses which published candidates are genuine, uncertainty is reduced for those records.";
methodFlows.en.data_dilution.response = "Separate and audit the classification inventory and lookup privileges. Evaluate combining rate limits and MFA with honeywords that detect and isolate a specific decoy-password match; honeywords do not detect or stop all bulk attempts.";
methodFlows.en.data_dilution.note = "This tool explains the concept but does not mix records into production. Full publication includes genuine records, but publication and identifying or exploiting them are assessed separately. Review applicable legal and contractual breach-notification duties.";

const methodOutcomes = {
  ja: {
    env: {deception:"実際の設定ファイル名・キー・接続先の置き方に合わせます。example.invalidは安全ですが、罠だと見抜く手掛かりになります。", delay:"ファイル自体に大きな遅滞はありません。取得やURL試行を記録し、発火をすぐ対応へ結びつけた場合に限り、防御側の猶予を作れます。"},
    database: {deception:"周辺の実システムに合うスキーマ・列名・件数・業務語彙を使います。example.invalidは不自然さを示すため、必要なら所有する隔離デコイ専用ドメインを使います。", delay:"複数のDB候補の照合やデータの検証に時間を使わせます。単に読み取るだけでは通知されず、読み取り監査かカナリアURLへのアクセスが別途必要です。"},
    web: {deception:"実サイト内の自然なパス・画面名・リンク構成に合わせて配置します。単独の汎用ページでは疑われやすくなります。", delay:"クローラーにリンク先やファイルを順に確認させ、追加リクエストと選別時間を生みます。巡回は有限で、並列化すれば短縮できます。"},
    nest: {deception:"バックアップや移行資料に見合うファイル名・フォルダー・手掛かりを選びます。露骨な規則性や周辺環境と合わない内容は罠の兆候になります。", delay:"現場で層ごとに展開・確認する攻撃者には、各段のパスワード探索と内容判断が追加作業になります。持ち出し後の並列オフライン解析では現場の時間を使わせません。"},
    stream: {deception:"実在するバックアップ配信経路に似せ、認証付きの隔離経路として配置します。終端のない応答自体が不自然に見える可能性があります。", delay:"終端不明の取得を続けるか切るか判断させ、帯域制限中の時間を使わせます。開始検知と対応が取得より先に間に合う運用が必要です。"},
    directory_maze: {deception:"実サイトや共有領域の命名・階層に合うディレクトリとファイルを配置します。無関係な大量リンクは巡回パターンから疑われ得ます。", delay:"リンクをたどる巡回にリクエストと候補選別を追加します。深さ・件数には上限があり、URL重複排除や並列探索で短縮されます。"},
    encoding_maze: {deception:"候補ごとに異なる架空レコードと業務らしいファイル名を使い、どの候補にも共通の比較基準を置きません。変換形式や不自然なデータは罠の手掛かりになります。", delay:"複数の候補を復元して内容の有用性を個別に判断させます。復元は一括自動化でき、遅滞は候補の数と選別手順に依存します。"},
  },
  en: {
    env: {deception:"Match real configuration filenames, keys and endpoint placement. example.invalid is safe but also signals that the file is a decoy.", delay:"The file itself adds little delay. It buys response time only when downloads or URL attempts are logged and alerts reach responders promptly."},
    database: {deception:"Match surrounding schemas, column names, record counts and business vocabulary. example.invalid looks artificial; use an owned domain dedicated to an isolated decoy when appropriate.", delay:"Make the intruder spend time comparing database candidates or validating records. A read alone does not alert; separate read auditing or a canary URL request is required."},
    web: {deception:"Place it at a natural path within the real site and match page names and link structure. A generic standalone page is easier to dismiss.", delay:"Following links and checking files adds requests and selection work. The crawl is finite and can be shortened through parallelism."},
    nest: {deception:"Use filenames, folders and clues that fit backup or migration workflows. Obvious patterns or content that conflicts with the environment can reveal the decoy.", delay:"On-site exploration adds password-solving and inspection at each layer. Parallel offline analysis after collection consumes no on-site time."},
    stream: {deception:"Place it behind an authenticated isolated route that resembles a real backup download. An endless response may itself look suspicious.", delay:"An unknown completion point forces a decision to keep waiting or disconnect while bandwidth is capped. Start detection and response must beat useful data collection."},
    directory_maze: {deception:"Use directory and file names that fit the site's real naming and hierarchy. Large unrelated link sets can look suspicious to a crawler.", delay:"Following links adds requests and candidate-selection work. Depth and file counts are bounded; URL deduplication and parallel crawling reduce delay."},
    encoding_maze: {deception:"Give each candidate independent synthetic records and plausible filenames, with no shared baseline for direct comparison. Predictable encodings or implausible data can reveal the decoy.", delay:"Require recovery and individual assessment of multiple candidates. Decoding can be batched; delay depends on candidate count and selection workflow."},
  },
};

methodOutcomes.ja.database.delay = "偽DBの確認・選別に時間を使わせるほか、本物として転売された偽DBが買い手に見破られれば、売り手の信用や次の取引に影響する可能性があります。";
methodOutcomes.en.database.delay = "Besides selection time, a decoy resold as genuine may harm the seller's reputation and future business if the buyer recognizes it as fake.";

const methodLegal = {
  ja: {
    env: {normal:"自組織の偽ファイルに、正当に発行された監視用URLを入れること自体は、同法上の不正アクセスに通常は該当しません。", risk:"第三者の本物の識別符号を正当な理由なく第三者に提供したり、その符号で無断ログインしたりすると、同法第5条または第2条・第3条に抵触し得ます。"},
    database: {normal:"権限のある環境で架空データのDBを生成・配置すること自体は、同法上の不正アクセスに通常は該当しません。", risk:"偽DBの作成に際し、他人のID・パスワードを使って第三者のアクセス制御を無断で解除すると、同法第2条・第3条に該当し得ます。", other:"実際の個人データを使う場合は、個人情報保護法上の取扱いも別に問題となります。"},
    web: {normal:"管理権限のある場所で静的な偽画面を配信する通常利用は、同法上の不正アクセスに通常は該当しません。", risk:"他のアクセス管理者になりすまし、または利用者にその管理者であると誤認させ、識別符号の入力を求める情報を公衆閲覧可能にするか、利用権者へメール送信すると、第7条に抵触し得ます。実際に入力されたかは問いません。当該アクセス管理者の承諾を得た行為は同条の対象外ですが、他法令の評価は別です。"},
    nest: {normal:"権限のある環境で暗号化ZIPと架空文書を作ること自体は、同法上の不正アクセスに通常は該当しません。", risk:"配置や調査のために、他人の認証情報を使って保護されたサーバーへ無断ログインすると、第2条・第3条に該当し得ます。ZIPをオフラインで復号することだけで、直ちに同法違反になるわけではありません。"},
    stream: {normal:"権限のある自組織の配信サーバーから終端のない応答を返すこと自体は、同法上の不正アクセスに通常は該当しません。", risk:"その設置のため他人のアクセス制御を無断で突破する場合は、第2条・第3条に該当し得ます。", other:"無限配信が正当な第三者に損害を与えた場合などは、業務妨害や損害賠償等が別に問題となり得ます。認証の有無だけで結論は決まりません。"},
    directory_maze: {normal:"権限のある配信先に有限のディレクトリやリンクを作る通常利用は、同法上の不正アクセスに通常は該当しません。", risk:"第三者の管理する配信先に、権限なく認証を突破して迷路を配置する場合は、第2条・第3条に該当し得ます。"},
    encoding_maze: {normal:"架空ファイルをエンコードして配置する通常利用は、同法上の不正アクセスに通常は該当しません。", risk:"回収した他人の認証情報を用いて、権限なく他人のサービスへログインすると、第2条・第3条に該当し得ます。エンコードやオフライン復元自体は同法の不正アクセスではありません。"},
  },
  en: {
    env: {normal:"Embedding a legitimately issued monitoring URL in your own decoy file ordinarily does not constitute unauthorized access under the Act.", risk:"Providing another person's real credentials to others without a legitimate reason, or using them to log in without authority, can implicate Articles 5 or 2 and 3."},
    database: {normal:"Generating and deploying a synthetic database in an authorized environment ordinarily does not constitute unauthorized access under the Act.", risk:"Using another person's credentials to bypass access controls without authority when obtaining data can implicate Articles 2 and 3.", other:"Using actual personal data may also raise separate privacy-law issues."},
    web: {normal:"Hosting a static decoy page in an authorized environment ordinarily does not constitute unauthorized access under the Act.", risk:"Impersonating another access administrator or otherwise making users believe you are that administrator, then publicly displaying or emailing information asking authorized users to enter credentials, can implicate Article 7. Actual submission is not required. Article 7 excludes conduct consented to by the relevant access administrator; other legal duties still apply."},
    nest: {normal:"Creating encrypted ZIPs and synthetic documents in an authorized environment ordinarily does not constitute unauthorized access under the Act.", risk:"Using another person's credentials to enter a protected server without authority can implicate Articles 2 and 3. Offline ZIP decryption alone is not automatically a violation of this Act."},
    stream: {normal:"Serving an endless response from an authorized server ordinarily does not itself constitute unauthorized access under the Act.", risk:"Bypassing another party's access controls without authority to deploy it can implicate Articles 2 and 3.", other:"Harm to an authorized third party may raise separate obstruction or civil liability issues. Authentication alone does not settle those issues."},
    directory_maze: {normal:"Creating a finite directory and link structure in an authorized hosting area ordinarily does not constitute unauthorized access under the Act.", risk:"Bypassing another party's access controls without authority to deploy it can implicate Articles 2 and 3."},
    encoding_maze: {normal:"Encoding and deploying fictional files in an authorized environment ordinarily does not constitute unauthorized access under the Act.", risk:"Using another person's credentials to log in without authority can implicate Articles 2 and 3. Encoding or decoding files offline is not itself unauthorized access under this Act."},
  },
};
methodExplanations.ja.honeyword = {title:"プリビレッジ・ハニーワード・セッション", how:"特権アカウントに検知用の偽パスワードを用意し、一致した試行を本番から隔離された偽セッションへ誘導する構想です。", target:"攻撃者がパスワードを推測する場合や、流出した偽の認証情報を試す場合を想定します。", limit:"登録した偽パスワードに一致した場合だけ動作します。誤入力やMFAの差に注意が必要です。このツールは手法の紹介のみを行い、認証連携や通知は実装しません。"};
methodExplanations.en.honeyword = {title:"Privilege Honeyword Session", how:"The concept registers decoy passwords for a privileged account and routes a match to a session isolated from production.", target:"An attacker guessing passwords or trying leaked decoy credentials.", limit:"It triggers only on a registered decoy password. Consider legitimate mistakes and differences in MFA. This tool explains the method; authentication integration and alerts are not implemented."};
methodExplanations.ja.data_dilution = {title:"データ・ディルーション", how:"本物のデータに大量の架空レコードを混ぜ、流出後の真偽の選別を難しくする構想です。正規利用者には別の判別手段が必要です。", target:"攻撃者が本物と偽物をまとめて取得し、利用・売却しようとする状況を想定します。", limit:"本物も流出し、全件の公開や外部情報との照合、判別手段の侵害を防げません。このツールは手法の紹介のみを行い、本番データへの混在は実装しません。"};
methodExplanations.en.data_dilution = {title:"Data Dilution", how:"The concept mixes many synthetic records with real data to make selection after a leak harder. Legitimate users need a separate way to distinguish records.", target:"An attacker obtaining a mixed dataset and trying to use or sell it.", limit:"Genuine records also leak. The approach cannot prevent publishing all records, external matching or compromise of the classification mechanism. This tool explains the concept and does not mix records into production."};
methodOutcomes.ja.fake_trap = {deception:"配置先のデザインや文言に合う警告・認証中の画面にすると、表示を確認する攻撃者に運用中の画面として受け取られる可能性があります。", delay:"表示を見た攻撃者が検知された可能性を考えて操作を見直す場合、確認の手間が増えます。表示を読まないスクリプトには作用しません。"};
methodOutcomes.en.fake_trap = {deception:"A warning or authentication screen matching the deployment context may appear operational to an attacker who reads it.", delay:"An attacker who reviews the message and reconsiders their actions may spend extra time. Scripts that ignore the page are unaffected."};
methodLegal.ja.fake_trap = {normal:"自組織が管理する経路に架空の警告や待機画面を配置すること自体は、通常、第三者システムへの不正アクセスには当たりません。", risk:"実在機関へのなりすましや正規利用者の誤接触、アクセスログの収集方法を検討します。表示だけでは実際の通報は行いません。"};
methodLegal.en.fake_trap = {normal:"Placing a fictional warning or waiting page on a route you control is not, by itself, necessarily unauthorized access to another system.", risk:"Consider impersonation of real organizations, accidental contact by legitimate users and access-log handling. The display itself does not report an incident."};
methodOutcomes.ja.honeyword = {deception:"偽パスワードが試された場合、実際の管理画面に見合う隔離セッションへ誘導します。正規の認証やMFAと不自然な差があると気付かれます。", delay:"偽セッションで調査や操作を続ける攻撃者には追加の仕事が生じます。偽候補に一致しない場合は誘導されません。"};
methodOutcomes.en.honeyword = {deception:"A decoy-password match leads to an isolated session resembling the actual management interface. Differences from genuine authentication or MFA may reveal it.", delay:"Exploration and actions in the decoy session add work. No redirection occurs without a registered decoy match."};
methodOutcomes.ja.data_dilution = {deception:"本物と似た構造や業務上の関係を持つ架空レコードを混ぜ、候補の真偽を判断しにくくします。", delay:"攻撃者が本物を選別しようとする場合、照合や確認の仕事が増える可能性があります。全件公開や無差別な自動試行には限界があります。"};
methodOutcomes.en.data_dilution = {deception:"Mix synthetic records with plausible structures and business relationships among genuine records.", delay:"An attacker selecting genuine records may need extra verification. Bulk publication and indiscriminate automated attempts remain possible."};
methodLegal.ja.honeyword = {normal:"自組織が管理する認証で偽パスワードの一致を隔離環境へ分岐する通常利用は、それ自体が不正アクセスとは限りません。", risk:"入力された資格情報や操作ログの取扱い、第三者になりすます画面、監視の範囲を検討します。"};
methodLegal.en.honeyword = {normal:"Routing a decoy-password match in an authentication system you control to an isolated environment is not, by itself, necessarily unauthorized access.", risk:"Review credential and activity-log handling, impersonation and monitoring scope."};
methodLegal.ja.data_dilution = {normal:"管理する環境で合成データを用いて混在の構想を検討すること自体は、通常は第三者システムへの不正アクセスに当たりません。", risk:"本番データの取扱い、偽レコードへの誤送信、個人情報や契約上の義務を検討します。"};
methodLegal.en.data_dilution = {normal:"Evaluating a synthetic-data mixing concept in an environment you control is not, by itself, necessarily unauthorized access to another system.", risk:"Consider production data handling, accidental messages to decoy records, privacy and contractual obligations."};
methodOutcomes.ja.ransomware_tripwire = {deception:"実在の業務で使うファイル名・階層に近い架空ファイルを、通常の書き込み対象から外した場所に置きます。正規アプリが更新すると誤検知になります。", delay:"攻撃者の暗号化を遅らせる仕組みではありません。監視ファイルへの変更がログに残り、担当者が初動できる場合に限り被害拡大を抑えられる可能性があります。"};
methodOutcomes.en.ransomware_tripwire = {deception:"Use fictional files and paths that fit the environment, in a location ordinary applications do not modify. Normal application writes will cause false alarms.", delay:"This does not slow encryption. It may help limit damage only if a change is logged and a responder can act before the attack spreads."};
methodLegal.ja.ransomware_tripwire = {normal:"自組織が管理する環境に架空ファイルとローカル監視ツールを配置する通常利用は、それ自体が同法上の不正アクセスとは限りません。", risk:"他者の端末や共有領域へ無断で配置・監視すること、ログに個人情報や通信データを収集することは別途検討が必要です。"};
methodLegal.en.ransomware_tripwire = {normal:"Placing synthetic files and a local monitor in an environment you control is not, by itself, necessarily unauthorized access under the Act.", risk:"Unauthorized placement or monitoring on another party's device or shared space, and collection of personal or communication data in logs, require separate review."};
usLegal.ja.ransomware_tripwire = ["自組織が管理する端末で架空ファイルを監視する通常利用は、それ自体が第三者システムへの無断アクセスとは限りません。", "他者の端末や共有領域への無断アクセス、個人情報や通信内容の収集は別途検討します。"];
usLegal.en.ransomware_tripwire = ["Monitoring synthetic files on a device you control is not, by itself, necessarily unauthorized access to another system.", "Unauthorized access to another party's device or shared space, and collection of personal or communication data, require separate review."];
Object.assign(translations.ja, {fake_title:"フェイクトラップ", fake_card:"警告や待機表示で再確認を促す", dilution_title:"データ・ディルーション", dilution_card:"本物に偽レコードを混ぜて選別を困難に", honeyword_title:"プリビレッジ・ハニーワード・セッション", honeyword_card:"偽パスワードで隔離デコイへ誘導", technology_only:"技術紹介のみです。生成や本番環境への変更は行いません。", fake_desc:"警告または待機表示の静的HTMLを生成します。", fake_variant:"表示パターン", fake_warning:"異常アクセスの警告", fake_reported:"通報済みの警告", fake_waiting:"認証中のスピナー", fake_note:"ファイル名を空欄にすると認証・セッション処理に使われる名前から自動で選びます。表示だけの静的ページです。検知・通報・認証・情報収集は行わず、外部への通信やプログラム送信もありません。監視・通知は配信側で別途設定してください。通報済みの表示は実際の通報を意味しません。正規利用者の誤接触に配慮してください。", template_replace_confirm:"このテンプレートを適用すると、編集したテーブル名と項目が置き換わります。続けますか？", quick_db_loading:"他のデータベース用プリセットを読み込み中です。顧客管理のサンプルは今すぐ作成できます。", quick_db_failed:"テンプレートを読み込めませんでした。下の「もう一度読み込む」を押してください。", quick_start_help:"最初はサンプルを一つ作成してみてください。生成ファイルは架空データで、ブラウザーから保存します。.envサンプルでは、カスタムファイル名や設定パターンの初期化が必要な場合だけ確認します。他の値は引き継ぎます。カナリア通知には、運用者が発行した監視URLへ実際にアクセスされる必要があります。生成器はURLに接続しません。", quick_env_reset_confirm:"このサンプルのため.envの設定パターンとファイル名を初期値に戻します。カナリアURLは保持します。続けますか？"});
Object.assign(translations.en, {fake_title:"Fake Trap", fake_card:"Prompt reassessment with warnings or waiting screens", dilution_title:"Data Dilution", dilution_card:"Mix real and decoy records to hinder selection", honeyword_title:"Privilege Honeyword Session", honeyword_card:"Route decoy password use to an isolated decoy", technology_only:"Technology overview only. No files are generated and production systems are not changed.", fake_desc:"Generate a static warning or waiting page.", fake_variant:"Display pattern", fake_warning:"Unusual access warning", fake_reported:"Reported warning", fake_waiting:"Authentication spinner", fake_note:"When the filename is blank, the generator selects a common authentication or session-related name automatically. This static page only displays a message. It does not detect, report, authenticate, collect information, communicate externally or send software. Configure monitoring and alerts separately. The reported message does not mean a report was sent. Avoid exposing legitimate users to the page", template_replace_confirm:"Applying this template will replace your edited table name and columns. Continue?", quick_db_loading:"Loading more database presets. The customer sample is ready to create now.", quick_db_failed:"Could not load database templates. Select Retry loading presets below.", quick_start_help:"Start with one sample. Files contain fictional data and are saved by your browser. The .env shortcut asks only if it needs to reset a custom filename or layout; other current values are kept. A canary alert requires your monitoring URL to be accessed. The generator never contacts that URL.", quick_env_reset_confirm:"For this sample, reset the .env layout and filename to their defaults. Your canary URL will be kept. Continue?"});
Object.assign(translations.ja, {tripwire_title:"ランサムウェア・デコイフラッド", tripwire_card:"架空ファイルの改変・削除をローカルで監視", tripwire_desc:"架空の業務ファイルを配置し、そのファイル群の変化を監視するスクリプトを別ファイルで作成します。", tripwire_files_label:"配置する架空ファイル数（4〜8）", tripwire_note:"配置ZIPには架空ファイルだけを入れます。監視スクリプトは運用者専用ファイルとして別に保存し、監視先でPython 3.11以降を使って実行します。起動中のみ、ファイル内容の変更・削除・差し替えを約1秒間隔でローカル記録します。停止中は記録しません。読み取りだけは検知せず、自動停止もしません。見逃しや誤検知があり、本番データの保護や復元にはなりません。対象ディレクトリは正規アプリの書き込み経路から外し、ログは別の保護された場所へ保存してください。", tripwire_monitor_download:"監視スクリプトを保存（運用者専用・公開禁止）", tripwire_deployment_download:"配置用ZIPを保存（架空ファイル）", tripwire_generated_summary:"架空ファイル {count} 件を配置ZIPに作成しました。監視スクリプトは別途ダウンロードし、配置ZIPの外に保管してください。Python 3.11以降の監視先で、展開先ディレクトリを指定して実行します。Windowsは py -3、macOS・Linuxは python3 を使えます。読み取り検知や自動停止は行いません。"});
Object.assign(translations.en, {tripwire_title:"Ransomware Decoy Flood", tripwire_card:"Locally monitor synthetic files for changes or deletion", tripwire_desc:"Generate fictional business files and a separate monitor for changes to those specific files.", tripwire_files_label:"Number of synthetic files (4–8)", tripwire_note:"The deployment ZIP contains synthetic files only. Save the monitor script separately as an operator-only file and run it on the monitored host with Python 3.11 or later. While running, it logs content changes, deletion and replacement locally, polling about once per second. It records nothing while stopped. It does not detect reads or stop a process. It can miss events or produce false alarms; it does not protect or restore production data. Keep the watched directory outside normal application write paths and store logs in a separate protected location.", tripwire_monitor_download:"Save monitor script (operator-only; never publish)", tripwire_deployment_download:"Save deployment ZIP (synthetic files)", tripwire_generated_summary:"Created {count} synthetic files in the deployment ZIP. Download the monitor separately and keep it outside the deployment. On a monitored host with Python 3.11+, run it against the extracted directory, for example: py -3 ransomware_tripwire_monitor.py <extracted-directory> on Windows or python3 ransomware_tripwire_monitor.py <extracted-directory> on macOS/Linux. It does not detect reads or stop processes."});
Object.assign(translations.ja, {quick_start:"サンプルをかんたん作成", quick_env:".env.development用ZIPを作成", quick_html:"静的ポータル（HTML＋配置用ZIP）を作成", quick_db:"選択したDBサンプルを作成", quick_start_confirm:"サンプルを作成します。上のカナリアURLを入力した場合、選択したサンプルの既存URL欄を置き換え、そのまま出力に含めます。続けますか？", quick_database_confirm:"「{name}」テンプレートを適用し、表と項目を置き換えてサンプルを作成します。続けますか？", quick_canary_label:"監視URL（カナリアURL・任意）", quick_canary_url_invalid:"カナリアURLは空白を含まない有効なHTTPS URLにしてください。"});
Object.assign(translations.ja, {tripwire_title:"ランサムウェア・デコイフラッド", tripwire_card:"処理された架空ファイルを補充", tripwire_desc:"架空ファイルと、その変更時に別の架空ファイルを補充するスクリプトを作成します。", tripwire_note:"スクリプトをPython 3.11以降で起動すると、対象ファイルの変更・削除を約1秒間隔で確認し、同じフォルダーに架空ファイルを補充します。補充数と容量は既定で無制限です。任意の上限は起動時に --max-files と --max-bytes で指定できます（0は無制限、各起動中の補充分のみ）。容量不足は業務や復旧を妨げ、満杯でも既存ファイルの上書きを防げるとは限りません。停止中は補充されず、一度取得した一覧しか処理しない攻撃や並列処理には効果が限定されます。", tripwire_generated_summary:"架空ファイル {count} 件と補充スクリプトを作成しました。配置ZIPを展開し、別途保存したスクリプトに展開先を指定して起動してください。補充数と容量の既定値は無制限です。"});
Object.assign(translations.en, {tripwire_title:"Ransomware Decoy Flood", tripwire_card:"Replace synthetic files after they are processed", tripwire_desc:"Create synthetic files and a separate script that replenishes changed decoys.", tripwire_note:"Run the script with Python 3.11 or later. It checks the selected files about once per second and creates a synthetic replacement in the same directory when a file changes or is deleted. Replacement count and bytes are unlimited by default. Optional --max-files and --max-bytes limits apply to replacements created in each run; 0 means unlimited. A full disk can disrupt work and recovery and may not prevent overwriting existing files. No replacements are made while stopped. One-time file listings and parallel processing can bypass the delay.", tripwire_generated_summary:"Created {count} synthetic files and a replenishment script. Extract the deployment ZIP and run the separately saved script against the extracted directory. Replacement count and bytes are unlimited by default."});
methodExplanations.ja.ransomware_tripwire = {title:translations.ja.tripwire_title, how:"架空ファイルの変更・削除を確認し、同じフォルダーに別の架空ファイルを補充して、処理対象を増やします。", target:"ファイルを探索して暗号化や削除を繰り返す攻撃を想定します。", limit:"一度取得した一覧だけを処理する攻撃、並列処理、スクリプト停止では遅延しない場合があります。既定では補充は無制限で、ディスク満杯でも暗号化は止まるとは限りません。"};
methodExplanations.en.ransomware_tripwire = {title:translations.en.tripwire_title, how:"When a synthetic file is changed or deleted, the script creates another synthetic file in the same directory to increase the work an attacker may perform.", target:"Attacks that repeatedly enumerate and encrypt or delete files.", limit:"A cached file list, parallel processing or stopping the script may eliminate any delay. Replacements are unlimited by default; a full disk may not stop encryption."};
methodFlows.ja.ransomware_tripwire = {context:"架空の業務ファイルを配置し、補充スクリプトを同じ端末で動かします。", steps:[["1. 架空ファイルを配置","配置ZIPを展開します。"],["2. 補充を開始","別に保存したスクリプトへ展開先を指定します。"],["3. デコイの変化を確認","変更・削除を約1秒間隔で確認します。"],["4. 架空ファイルを補充","変化ごとに同じフォルダーへ新しい架空ファイルを作ります。"]], ifCase:"攻撃が追加されたファイルも繰り返し探索・処理すれば、仕事を増やせる可能性があります。", elseCase:"一覧を一度しか取得しない攻撃や並列処理では、実ファイルが先に処理される場合があります。", response:"補充数とバイト数は起動オプションで制限できます。既定は無制限です。", note:"ディスク満杯は業務や復旧を妨げ、既存ファイルの上書きを必ず止めるわけではありません。"};
methodFlows.en.ransomware_tripwire = {context:"Place synthetic files and run a replenishment script on the same host.", steps:[["1. Place synthetic files","Extract the deployment ZIP."],["2. Start replenishment","Run the separate script against the extracted directory."],["3. Watch decoy changes","Check for changes and deletion about once per second."],["4. Replenish decoys","Create a new synthetic file in the same directory for each observed change."]], ifCase:"Repeated enumeration and processing of added files may increase attacker work.", elseCase:"A one-time file listing or parallel processing can reach real files first.", response:"Optional startup arguments limit the number and bytes of replacements. The default is unlimited.", note:"A full disk can disrupt work and recovery and does not necessarily prevent overwriting existing files."};
flowScenarios.ja.ransomware_tripwire = "想定：ファイルを探索して暗号化する攻撃に、補充される架空ファイルを処理させます。";
flowScenarios.en.ransomware_tripwire = "Scenario: an encrypting process repeatedly finds and processes replenished synthetic files.";
methodOutcomes.ja.ransomware_tripwire = {deception:"架空の業務ファイルを配置し、変更後は別名で補充します。", delay:"追加ファイルが再探索・処理される場合に仕事を増やす仮説です。"};
methodOutcomes.en.ransomware_tripwire = {deception:"Place synthetic business files and replenish changed files under new names.", delay:"Additional work depends on the attacker discovering and processing replacements."};
Object.assign(translations.ja, {path_maze_title:"パス・メイズ", path_maze_card:"架空ファイルを通常のフォルダーに分散", path_maze_desc:"有限の通常フォルダーに架空ファイルを配置します。", path_depth:"階層の深さ（1〜4）", path_branches:"各フォルダーの分岐数（1〜3）", path_files:"各フォルダーのファイル数（1〜4）", path_note:"通常のフォルダーと架空ファイルを有限個作ります。リンクや常駐プログラムは使いません。攻撃がデコイを処理する場合に追加の仕事が生じます。並列処理や対象の絞り込みでは実ファイルが先に処理されることがあります。バックアップや検索にもファイルが増えます。", sparse_title:"スパース・デコイ", sparse_card:"見かけ上大きな架空ファイルを作成", sparse_desc:"配置先で見かけ上大きな架空ファイルを作るスクリプトを生成します。", sparse_size:"1ファイルの見かけのサイズ（GiB、1〜32）", sparse_files:"ファイル数（1〜4）", sparse_note:"生成ZIPには作成スクリプトと説明書が入り、配置先で手動実行するまで大きなファイルは作りません。Python 3.11以降と対応ファイルシステムが必要です。コピー・バックアップ・同期時には見かけのサイズ分の容量や時間を使う場合があり、ディスクを圧迫することがあります。暗号化結果の書き込みでも容量を消費します。部分暗号化やサイズによる除外では遅延が小さくなります。", path_generated:"{directories}フォルダーに架空ファイル{documents}件を作成しました。運用者用の配置一覧も保存してください。", sparse_generated:"見かけ上{size} GiBの架空ファイルを{count}件作るスクリプトをZIPに入れました。ZIPを展開し、説明書を読んでから配置先で手動実行してください。運用者用の一覧も保存してください。"});
Object.assign(translations.en, {path_maze_title:"Path Maze", path_maze_card:"Distribute synthetic files across ordinary folders", path_maze_desc:"Create synthetic files in a finite tree of ordinary folders.", path_depth:"Directory depth (1–4)", path_branches:"Branches per folder (1–3)", path_files:"Files per folder (1–4)", path_note:"Creates a finite set of ordinary folders and synthetic files without links or a background process. Processing decoys adds work; parallel encryption or selective targeting may reach real files first. The added files also affect searches and backups.", sparse_title:"Sparse Decoy", sparse_card:"Create a synthetic file with a large logical size", sparse_desc:"Generate a script to create synthetic sparse files at the chosen destination.", sparse_size:"Logical size per file (GiB, 1–32)", sparse_files:"Number of files (1–4)", sparse_note:"The ZIP contains a creation script and instructions. Large files are created only when you run the script manually at the destination. Python 3.11+ and a supporting filesystem are required. Copying, backup or sync may consume the full logical size and time, filling storage; encrypted output can also consume space. Partial encryption or size-based exclusions can reduce delay.", path_generated:"Created {documents} synthetic files in {directories} folders. Save the separate operator inventory.", sparse_generated:"The ZIP contains a script to create {count} synthetic files of {size} GiB logical size each. Extract it, read the instructions and run it manually at the destination. Save the separate operator inventory."});
methodExplanations.ja.path_maze = {title:translations.ja.path_maze_title, how:"通常の有限フォルダーに、架空の業務ファイルを分散して配置します。", target:"複数のディレクトリを探索してファイルを暗号化する攻撃。", limit:"探索対象が絞られる場合や並列処理では実ファイルが先に処理されます。検索・バックアップの対象も増えます。"};
methodExplanations.en.path_maze = {title:translations.en.path_maze_title, how:"Distributes synthetic business files across a finite tree of ordinary folders.", target:"An encryptor that traverses directories and processes files.", limit:"Selective targeting or parallel processing can reach real files first. Searches and backups also encounter the additional files."};
methodExplanations.ja.sparse_decoy = {title:translations.ja.sparse_title, how:"配置先で見かけのサイズが大きい架空ファイルを作り、全体を読む暗号化処理の仕事を増やします。", target:"サイズの大きいファイルを全体読み取りして暗号化する攻撃。", limit:"部分暗号化や大きなファイルの除外では効果が弱まります。バックアップや同期で見かけのサイズ分の容量を消費する場合があります。"};
methodExplanations.en.sparse_decoy = {title:translations.en.sparse_title, how:"Creates synthetic files with a large logical size to add work for an encryptor that reads the whole file.", target:"Encryption that reads and processes large files in full.", limit:"Partial encryption or size-based exclusions reduce the effect. Backups and synchronization can consume the entire logical size."};
methodFlows.ja.path_maze = {context:"例：架空の業務フォルダーを配置し、ファイル探索の対象を増やします。", steps:[["1. 階層を作成","有限のフォルダーと架空ファイルをZIPにします。"],["2. 配置","展開先と運用者用の一覧を確認します。"],["3. 攻撃者が探索","階層とデコイを処理します。"],["4. 仕事が増える","デコイの処理分だけ追加の仕事が生じます。"]], ifCase:"攻撃側が対象に含めて処理する場合に仕事が増えます。", elseCase:"並列処理や対象の絞り込みでは、実ファイルが先に処理される場合があります。", response:"運用者専用の一覧を使って配置と撤去を管理します。", note:"通常の検索やバックアップも対象にする場合があります。"};
methodFlows.en.path_maze = {context:"Example: place a tree of fictional business files in an authorized location.", steps:[["1. Create a tree","Generate a finite ZIP of ordinary folders and synthetic files."],["2. Place it","Extract the ZIP and keep the operator inventory."],["3. Attacker traverses","The encryptor discovers and processes decoys."],["4. Work increases","Processing extra files requires additional work."]], ifCase:"Work increases when the attack selects and processes decoys.", elseCase:"Parallel processing or selective targeting can reach real files first.", response:"Use the operator inventory to manage placement and removal.", note:"Ordinary searches and backups may also process these files."};
methodFlows.ja.sparse_decoy = {context:"例：見かけ上1 GiBの架空ファイルを対応ファイルシステムに置きます。", steps:[["1. スクリプトを生成","サイズと個数を指定してZIPを保存します。"],["2. 配置先で作成","説明書を読み、スクリプトを手動で実行します。"],["3. 攻撃側が読み取り","対象に選ばれたデコイが処理されます。"],["4. 仕事が増える","全体を読んで暗号化すれば処理量が増えます。"]], ifCase:"ファイル全体を処理する攻撃に追加の読み取り・暗号化を行わせます。", elseCase:"部分暗号化やサイズによる除外では、追加の仕事が小さくなります。", response:"配置ファイル名の運用者用一覧を保管し、バックアップと同期への影響を確認します。", note:"コピーや暗号化結果は見かけのサイズ分の領域を消費することがあります。"};
methodFlows.en.sparse_decoy = {context:"Example: place a 1 GiB logical-size synthetic file on a filesystem that supports sparse files.", steps:[["1. Generate script","Choose the size and count and save the ZIP."],["2. Create at destination","Read the instructions and run the script manually."],["3. Attacker reads","The encryptor selects and processes a decoy."],["4. Work increases","Reading and encrypting the whole file adds work."]], ifCase:"Full-file encryption must read and process the larger logical file.", elseCase:"Partial encryption or size exclusions can reduce the additional work.", response:"Keep the operator filename inventory and review effects on backup and synchronization.", note:"Copies or encrypted output may consume the full logical size."};

// Keep the three decision fields comparable across every method and language.
// Arrays are rendered as bullets by renderFlowPoints.
const methodGuidance = {
  ja: {
    env: {
      ifCase:["侵入後に設定ファイルや業務文書を探す攻撃者が、内部からカナリアURLへアクセスすれば、外部持ち出し前の兆候を検知する手掛かりになります。","盗み出したファイルのURLを後から試す攻撃者にも、要求が監視先へ届けば接触を記録できます。"],
      elseCase:["URLを試さずファイルだけ読む攻撃、URLへの通信を遮断する環境、監視サービスへ届かない経路では通知されません。","ページが正規利用者にも見つけやすい場所にある、またはファイルを広く共有すると、誤接触や第三者のアクセスが混ざります。"],
      response:["正規利用者が通常アクセスしない場所にページを置き、URLは文書内の自然な文脈に埋め込みます。","内部・外部からの到達性、通知先、Web／OSのファイル取得ログを確認し、URLが露見したら無効化して新しいものに交換します。"]
    },
    database: {
      ifCase:["盗んだDB候補から顧客・注文情報を選別しようとする攻撃者が偽物を本物と誤認すれば、確認や利用に手間がかかり、偽情報を持ち出す可能性があります。"],
      elseCase:["攻撃者が偽DBを無視する、本物を別経路で得る、候補をまとめて持ち出して後で解析する場合、現場での遅延は小さくなります。","実データとの比較材料が明白だと、偽物を早く見分けられます。"],
      response:["侵入後にDBやバックアップを探索される環境で、実在するスキーマや業務名に合わせた合成データを使います。","本番DBと分離し、配置場所・アクセスログを管理します。閲覧だけで通知する仕組みではありません。"]
    },
    web: {
      ifCase:["管理画面やバックアップを探す攻撃者が、偽ポータルのページやリンクを調査すれば、候補の確認に時間を使う可能性があります。","ページ要求やカナリアリンクへのアクセスを監視していれば、探索の兆候を把握できます。"],
      elseCase:["攻撃者がページを無視する、別経路を使う、リンク先へアクセスしない場合、調査の遅延やカナリア通知は期待できません。","ページの内容やURLが不自然で、デコイだとすぐ分かる場合も効果が弱まります。"],
      response:["管理ポータルやアーカイブを探される環境で、実際の業務に沿うページ内容と配置先を選びます。","ページ要求ログとカナリアサービスの通知を別々に監視し、本番認証情報や本番機能を接続しません。"]
    },
    nest: {
      ifCase:["盗んだアーカイブから目的の情報を探す攻撃者が、各階層の候補を安全に選別できないと考えれば、追加の解凍・確認を続けるか、価値不明の候補を捨てるか判断に手間がかかります。","途中で偽物を見つけても未確認の枝に本物がある可能性が残る構成なら、確認作業が続くことがあります。"],
      elseCase:["攻撃者が構造の不自然さや既知の情報との矛盾から罠を見抜く、全体を持ち出して並列・オフライン解析する、本物を別経路で得る場合は現場での遅れが小さくなります。"],
      response:["アーカイブやバックアップを持ち出される可能性がある環境で、自然な階層と一貫した合成文書を設計します。","運用者用のパスワード・構成台帳は公開物から分離し、実データや本物の秘密を混ぜません。"]
    },
    stream: {
      ifCase:["取得完了まで待つ必要があるバックアップを狙う攻撃者が、配信を最後まで待てば、対応者が調査・封じ込めを始める時間を得られる可能性があります。","配信開始イベントをすぐ把握できる構成なら、対応判断を早める手掛かりになります。"],
      elseCase:["攻撃者が部分取得で目的を満たす、切断して別作業を進める、並列接続する場合、待ち時間は小さくなります。無通信タイムアウトでも接続は終了します。","監視や担当者への通知が遅い、帯域制限が厳しい場合は、配信が時間を稼ぐ前に終わることがあります。"],
      response:["隔離したデコイ配信経路を運用でき、帯域・同時接続・費用を監視できる環境向けです。","認証、開始ログ、通知、停止手順と容量上限を準備し、本番データや認証系統から切り離します。"]
    },
    directory_maze: {
      ifCase:["ディレクトリを順に巡って目的のファイルを探す攻撃者が、偽ファイルも個別に取得・確認すれば、要求や選別の手間が増える可能性があります。"],
      elseCase:["攻撃者が対象を絞る、並列クローラーで探索する、全体を一括取得してオフライン解析する場合、現場での遅延は小さくなります。","正規利用者の検索・バックアップもファイルを処理するため、デコイを除外できない運用では影響が出ます。"],
      response:["攻撃者が参照できるファイル共有や静的配信領域で、正規利用者の作業を妨げずに配置できる環境向けです。","自然なフォルダー名と業務に合う合成文書を使い、運用者用の配置一覧とアクセスログを保管します。"]
    },
    encoding_maze: {
      ifCase:["複数の候補ファイルから目的の情報を探す攻撃者が、復元した内容を個別に見比べる場合、候補選別の手間が増える可能性があります。"],
      elseCase:["使われている変換形式が既知なら、攻撃者はスクリプトで一括復元・並列処理できます。明確な形式名や同じ構造の反復も選別を容易にします。"],
      response:["ファイルを自動収集・解析される可能性がある環境で、形式やファイル名に変化を持たせ、すべて合成データにします。","配信・取得ログを別途監視し、オフライン解析では取得自体を検知できない点を踏まえて対応を設計します。"]
    },
    fake_trap: {
      ifCase:["画面の警告や処理中表示を信じて内容を調べ直す攻撃者には、判断や次の操作に時間がかかる可能性があります。"],
      elseCase:["画面を表示せず処理するスクリプト、警告を無視する攻撃者、別の経路を並行探索する攻撃者には表示だけでは作用しません。","通常利用者が誤って画面に到達する配置では、誤警報や業務上の混乱が起きます。"],
      response:["人がブラウザーで探索する可能性があるデコイ経路向けです。攻撃者の自動化にも効くとは限らない前提で使います。","デコイ側でログと通知を設け、正規利用者が接触した場合の案内・復旧手順も決めます。"]
    },
    ransomware_tripwire: {
      ifCase:["ファイルを探索して暗号化・削除する攻撃が監視対象のデコイを変更すれば、その変化を記録し、対応開始の手掛かりにできます。","変更後も攻撃が追加ファイルを繰り返し探索・処理する場合、追加の作業が生じる可能性があります。"],
      elseCase:["読み取りや持ち出しだけの攻撃では反応しません。監視を停止する攻撃、短時間で変更と復元を行う処理、一覧を一度だけ取得する処理では検知や遅延が弱まります。","補充処理が無制限だと、攻撃より先にディスクを圧迫して業務や復旧を妨げる恐れがあります。"],
      response:["ファイル変更を監視できる端末や共有領域向けです。通常業務が触れない場所にデコイを置き、補充数・容量の上限を設定します。","ログは監視対象の外に保管し、既存のEDR・バックアップ・端末隔離手順と連携します。"]
    },
    data_dilution: {
      ifCase:["盗んだデータを販売・利用する攻撃者が本物を確実に選べない場合、データ全体の信頼性や取引価値を下げ、照合・選別の負担を増やす可能性があります。"],
      elseCase:["真偽を選ばず全件を公開・試行する攻撃、外部情報で本物を照合する攻撃、判別台帳や照会権限も奪う攻撃では効果が弱まります。","漏えい元や第三者が真偽を明らかにすると、その範囲の不確実性は減ります。"],
      response:["本番DBへ合成レコードを混在させる構想です。データ形式・業務処理・監査を管理できる組織で、影響を隔離して評価します。","判別台帳と照会権限を本番DBから分離・監査し、誤送信、通知、法令・契約上の扱いを事前に検討します。このツールは本番DBへの混在を実装しません。"]
    },
    honeyword: {
      ifCase:["特権アカウントを狙う攻撃者が、登録済みの偽パスワードを試し、一致後に偽環境を本物と思って探索すれば、試行の検知や偽情報の確認に時間を使わせる可能性があります。"],
      elseCase:["攻撃者が偽候補を試さない、偽パスワードが一致しない、または別経路で本番へ入る場合は誘導されません。","偽環境と本番の差、MFAの挙動、既知の画面情報から仕組みを見抜かれることがあります。正規利用者の誤入力も誤発火要因です。"],
      response:["認証基盤を運用する組織向けの構想で、認証フローに統合できる仕組みと専門的な運用が必要です。このサンプル自体は認証へ接続しません。","本番認証・MFA・試行制限を維持し、偽セッションの権限、データ、ネットワーク、ログを本番から隔離します。"]
    },
    path_maze: {
      ifCase:["広いフォルダー範囲を巡回して暗号化する攻撃が、配置したデコイも対象に含めれば、追加ファイルの発見・処理分だけ作業が増える可能性があります。"],
      elseCase:["攻撃者が対象を絞る、並列処理する、一覧を先に取得して実ファイルから処理する場合、実データが先に処理されることがあります。","通常の検索・バックアップも対象にすると、攻撃前に業務処理が増える場合があります。"],
      response:["広範囲のファイル探索を想定する端末・共有領域向けです。正規業務が使わない場所を選び、有限の規模から導入します。","運用者用一覧で設置・撤去を管理し、バックアップや検索への影響を確認します。"]
    },
    sparse_decoy: {
      ifCase:["ファイル全体を読み取って暗号化する攻撃が大きな論理サイズのデコイを処理すれば、読み取り・暗号化の作業が増える可能性があります。"],
      elseCase:["部分暗号化、サイズによる除外、ファイル先頭だけの処理では追加作業が小さくなります。","バックアップ、同期、コピーや暗号化後の保存先が見かけ上の全サイズを扱うと、運用側の容量・時間も消費します。"],
      response:["疎ファイルに対応するファイルシステムで、容量とバックアップ挙動を管理できる端末向けです。","小規模で検証してからサイズ・個数を制限し、空き容量を監視します。運用者用ファイル名一覧は配置先と分けて保管します。"]
    }
  },
  en: {
    env: {
      ifCase:["If an intruder searching for configuration files or business documents accesses the canary URL from inside the network, the request can provide a lead before data leaves the network.","If an intruder later tests a URL from a stolen file, the contact can be recorded when the request reaches the monitor."],
      elseCase:["Reading a file without requesting its URL, blocked outbound traffic, or a route that cannot reach the monitor produces no alert.","A page that legitimate users can easily find, or a widely shared file, can attract accidental visits, scanners or third parties."],
      response:["Place the page somewhere legitimate users do not normally visit and embed its URL naturally in a document.","Check internal and external reachability, alert routing and file access logs. Disable and replace a URL if it is exposed."]
    },
    database: {
      ifCase:["If an intruder selecting customer or order data from stolen database candidates mistakes a decoy for genuine data, verification or use may take extra work and the intruder may carry away false information."],
      elseCase:["Ignoring the decoy, obtaining the real database elsewhere, or collecting everything for later offline analysis reduces on-site delay.","Clear comparison clues can make a decoy easy to identify."],
      response:["Use synthetic data matching the real schema and business context where intruders may search databases or backups.","Keep it separate from production and monitor placement and access. Reading alone does not generate an alert."]
    },
    web: {
      ifCase:["If an intruder searching for an admin portal or backup examines a decoy page and its links, checking the candidate may take extra time.","Monitoring page requests and canary-link requests can provide evidence of exploration."],
      elseCase:["Ignoring the page, using another route, or never requesting the link means little delay and no canary alert.","Unnatural content or URLs can make the decoy easy to recognize."],
      response:["Use this where intruders may search for portals or archives, with content and placement that fit the business context.","Monitor page requests separately from canary-service alerts. Do not connect production authentication or functions."]
    },
    nest: {
      ifCase:["If an intruder searching a stolen archive cannot confidently distinguish candidates, they may spend effort decrypting and checking more branches or risk discarding files of uncertain value.","A convincing layout that leaves unchecked branches as plausible candidates may extend inspection even after one decoy is found."],
      elseCase:["Unnatural structure or contradictions with known information may expose the trap. Bulk collection followed by parallel offline analysis reduces on-site delay, and a separate route to real data reduces the effect."],
      response:["Use where archives or backups may be stolen; build natural directory structures and internally consistent synthetic documents.","Keep operator-only passwords and structure inventories separate from deployable files. Never mix in real secrets."]
    },
    stream: {
      ifCase:["If an intruder targeting a backup must wait for the complete download, responders may gain time to investigate and contain the activity.","Prompt awareness of stream-start events can help responders make a timely decision."],
      elseCase:["Partial retrieval, disconnecting, or parallel connections can reduce waiting. An inactivity timeout also ends a connection.","If monitoring or response is slow, or bandwidth caps are too restrictive, delivery may end before useful response time is gained."],
      response:["Suitable for an isolated decoy delivery path where bandwidth, concurrency and cost can be monitored.","Prepare authentication, start-event logging, alerts, limits and a stop procedure. Keep it separate from production data and authentication."]
    },
    directory_maze: {
      ifCase:["If an intruder traversing directories to find target files also retrieves and inspects decoys individually, additional requests and selection work may result."],
      elseCase:["Target filtering, parallel crawlers, or bulk collection followed by offline analysis can reduce on-site delay.","Normal searches and backups also process files, so placement may affect routine operations."],
      response:["Suitable for authorized file shares or static delivery areas that intruders could browse without disrupting legitimate work.","Use plausible folder names and synthetic documents; maintain an operator placement inventory and access logs."]
    },
    encoding_maze: {
      ifCase:["If an intruder must compare recovered content from multiple file candidates to find a target, individual review may add selection work."],
      elseCase:["Known encodings can be decoded in bulk with scripts and parallelized. Obvious format labels or repeated structures make selection easier."],
      response:["Use where files may be collected and analyzed automatically; vary formats and names while keeping all data synthetic.","Monitor retrieval at the hosting layer. Offline analysis cannot be detected from the file alone."]
    },
    fake_trap: {
      ifCase:["An intruder who trusts a warning or processing display and investigates or waits may spend extra time deciding what to do."],
      elseCase:["Scripts that do not render the page, intruders who ignore warnings, or parallel exploration through another route bypass the display.","Placement that exposes legitimate users can cause false alerts or operational confusion."],
      response:["Use on decoy routes likely to be explored in a browser, while assuming automated tools may ignore the display.","Set up hosting logs and alerts, and prepare guidance for legitimate users who encounter the page."]
    },
    ransomware_tripwire: {
      ifCase:["If an encrypting or deleting process changes a monitored decoy file, the change can be recorded as a lead for response.","If the attack repeatedly discovers and processes replenished files, the added files may increase its work."],
      elseCase:["Reads or exfiltration alone do not trigger it. Stopping the monitor, briefly changing and restoring files, or processing a cached file list can reduce detection or delay.","Unlimited replenishment can fill storage before the attack does, disrupting work or recovery."],
      response:["Suitable for monitored endpoints or shares. Place decoys where normal applications do not write and set replacement count and byte limits.","Store logs outside the watched area and coordinate with existing EDR, backup and device-isolation procedures."]
    },
    data_dilution: {
      ifCase:["If an intruder selling or using stolen data cannot confidently select genuine records, the dataset may lose reliability or market value and require more validation work."],
      elseCase:["Publishing or testing all records without selection, matching against external information, or compromising the classification inventory weakens the effect.","Disclosure of which records are genuine reduces uncertainty for those records."],
      response:["This concept mixes synthetic records into a production database; it requires an organization able to control data formats, business processes and auditing, with impact assessed in isolation.","Separate and audit the classification inventory and lookup privileges. Review mistaken communications, monitoring, and legal or contractual handling. This tool does not implement production mixing."]
    },
    honeyword: {
      ifCase:["If an intruder targeting a privileged account tries a registered decoy password, matches it, and explores the fake environment as if it were genuine, the attempt may be detected and the false data may consume time."],
      elseCase:["No diversion occurs if the intruder does not try a decoy, the value does not match, or a separate route reaches production.","Differences in the decoy environment, MFA behavior or known screen details may reveal the setup. Legitimate mistakes can also cause false triggers."],
      response:["This concept is for organizations operating an authentication system and requires integration and specialist operations; this sample does not connect to authentication.","Preserve production authentication, MFA and rate limits. Isolate decoy permissions, data, network and logs from production."]
    },
    path_maze: {
      ifCase:["If broad file-enumerating encryption includes decoys in its target set, discovering and processing the extra files may add work."],
      elseCase:["Target filtering, parallel processing or collecting a file list before encryption may let real files be processed first.","Routine searches and backups may also include the files."],
      response:["Suitable for endpoints or shares where broad file traversal is expected. Start small in locations unused by legitimate workflows.","Use the operator inventory for placement and removal, and check effects on search and backup operations."]
    },
    sparse_decoy: {
      ifCase:["If an attack reads and encrypts whole files, processing a decoy with a large logical size may add read and encryption work."],
      elseCase:["Partial encryption, size exclusions or processing only file headers reduce the extra work.","Backups, sync, copies and encrypted output may consume the full apparent size and storage."],
      response:["Suitable for endpoints with sparse-file support and managed storage and backup behavior.","Start with a small deployment, cap file size and count, monitor free space, and keep the operator filename list separately."]
    }
  }
};
for (const lang of Object.keys(methodGuidance)) {
  for (const [method, fields] of Object.entries(methodGuidance[lang])) Object.assign(methodFlows[lang][method], fields);
}
applyMethodKeyPointAdditions();
flowScenarios.ja.path_maze = "想定：フォルダーを探索して暗号化する攻撃に、追加の架空ファイルを処理させます。";
flowScenarios.en.path_maze = "Scenario: a directory-traversing encryptor processes additional synthetic files.";
flowScenarios.ja.sparse_decoy = "想定：大きなファイルを全体暗号化する攻撃に、見かけ上大きな架空ファイルを処理させます。";
flowScenarios.en.sparse_decoy = "Scenario: a full-file encryptor processes a large logical-size synthetic file.";
methodOutcomes.ja.path_maze = {deception:"業務の保存場所に見える名前と架空の文書を組み合わせます。", delay:"攻撃がデコイを処理する場合、追加の探索と暗号化が必要になります。"};
methodOutcomes.en.path_maze = {deception:"Use business-like folder names and synthetic documents.", delay:"An attack that processes the decoys performs additional traversal and encryption."};
methodOutcomes.ja.sparse_decoy = {deception:"業務ファイルらしい名前と架空の内容を持たせます。スパース属性は確認できます。", delay:"攻撃がファイル全体を読む場合、見かけのサイズに応じた処理が発生します。"};
methodOutcomes.en.sparse_decoy = {deception:"Use a business-like filename and fictional content; sparse attributes remain inspectable.", delay:"A full-file reader must process the logical file size."};
for (const lang of ["ja", "en"]) for (const kind of ["path_maze", "sparse_decoy"]) {
  methodLegal[lang][kind] = methodLegal[lang].directory_maze;
  usLegal[lang][kind] = usLegal[lang].directory_maze;
}
Object.assign(translations.en, {quick_start:"Quick create samples", quick_env:"Create .env.development ZIP", quick_html:"Create static portal (HTML + deployment ZIP)", quick_db:"Create selected database sample", quick_start_confirm:"Create this sample? If you entered a canary URL above, it replaces the URL in this sample's settings and is included in the output exactly as entered.", quick_database_confirm:"The {name} template will replace the current table and columns. Continue?", quick_canary_label:"Monitoring URL (canary link, optional)", quick_canary_url_invalid:"Enter a valid HTTPS URL without whitespace."});
Object.assign(translations.ja, {connection_failed:"ローカルの生成サーバーに接続できません。起動用の画面が開いているか確認してください。閉じていた場合はアプリを起動し直し、このページを再読み込みしてください。入力内容はこの画面に残っています。"});
Object.assign(translations.en, {connection_failed:"Could not reach the local generator. Check that its startup window is still open. If it closed, start the app again and reload this page. Your form entries remain on this page."});
translations.ja.quick_start_recommendation = "ここは、代表的なサンプルを少ない操作で作るショートカットです。ボタンを押すとファイルがダウンロードされ、自動配置はしません。手法の説明を読み、詳しい設定を調整したい場合は、次の「手法を選択」から進んでください。初期値では、サービス管理の架空レコード25件を含むHTMLファイルを作成できます。";
translations.en.quick_start_recommendation = "This area provides shortcuts for creating common samples with fewer steps. Buttons generate and download files; nothing is deployed automatically. To read about a method and adjust its detailed settings, use Method selection below. By default, you can create an HTML file with 25 fictional Service management records.";
Object.assign(translations.ja, {
  workspace:"メニュー", main_navigation:"メインメニュー", nav_intro:"初めに", nav_generator:"対策紹介とサンプル生成", nav_license:"ライセンス・著作権",
  workspace_page_intro:"初めに", workspace_page_generator:"対策紹介とサンプル生成", workspace_page_license:"ライセンス・著作権",
  intro_eyebrow:"初めに", intro_title:"Physaliaについて", intro_lead:"Physaliaは、**攻撃者の侵入後に備える対策**を紹介し、架空のファイルやサンプルを生成するローカルツールです。",
  intro_purpose:"予算や人手が限られる環境でも、対策の仕組みや注意点を学び、自分の環境に合う方法を探せます。一部の手法は説明のみを提供します。",
  intro_concept_title:"コンセプト（対策の考え方）", intro_prevention:"AI技術の発展とともに、攻撃の手口は多様化しています。侵入を防ぐ対策だけでは防ぎきれない攻撃もあり、従来の対策に加えて、別の角度から備えることが必要だと考えています。", intro_after_intrusion:"Physaliaは、アンチウイルスソフトなどの対策を置き換えるのではなく、**デコイによる攻撃回避や遅滞対策による攻撃断念に重きを置いたアプローチ**を紹介します。既知の技術もAI時代の攻撃を想定して見直し、仕組みを学べる解説やサンプルを提供します。", intro_concept_scope:"**目指すのは、侵入や情報流出を完全に防ぐことだけに頼るのではなく、侵入や情報流出が起きた後にも効果を発揮する防御策です。**侵入や情報流出に成功すれば攻撃者の勝ち、という状況を変えるため、攻撃が成功した後も攻撃者に負担をかけ、対応する機会を作ることで、攻撃者に偏った状況を少しでも変えることを目指します。", intro_inspiration:"攻撃の手口が多様化するなら、**防御の手段も多様であるべきです。**ひとつひとつの対策が小さくても、重ねることで攻撃者が活動しにくい環境につながると考えています。", intro_boundary:"各手法の仕組みと限界を確認し、自分の環境に役立つものを検討してください。",
  intro_how_title:"使い方", intro_step_1:"「対策紹介とサンプル生成」を開き、**心配なことから対策を探します**。", intro_step_2:"**対策の仕組みや注意点**を読み、必要に応じてサンプルを生成します。", intro_step_3:"生成した内容を確認し、**自分が管理する環境に手動で配置**します。監視が必要な手法では、通知先などを別途用意します。", intro_start:"対策を探す",
  intro_limits_title:"補足情報", intro_limit_synthetic:"**生成データは架空です。**実在の個人情報、実際に使える認証情報、決済カード番号は生成しません。", intro_limit_canary:"カナリアURLは任意です。空欄なら実際の監視通知はありません。生成器はURLへ接続せず、**ファイルを読むだけでも通常はHTTP通知されません。**", intro_limit_effect:"**対策の効果は、配置先や攻撃者の行動によって変わります。**自分の環境に合わせて、仕組みと注意点を確認してください。",
  license_eyebrow:"プロジェクト情報", license_title:"ライセンス・著作権", license_intro:"このリポジトリのソフトウェアと寄稿の利用条件です。", license_software_title:"プロジェクトのライセンス", license_software_body:"PhysaliaはApache License 2.0で公開されています。利用・改変・再配布にはライセンス本文の条件が適用され、特許ライセンス条項を含みます。ソフトウェアは保証なしで提供されます。", license_read_full:"Apache License 2.0の全文を表示", license_copyright_title:"著作権と第三者ライブラリ", license_copyright_body:"Copyright 2026 Physalia contributors. 各寄稿の著作権表示とライセンス条件は、再配布時も保持してください。", license_dependencies_body:"Pythonなどの依存ライブラリは、それぞれ個別のライセンスに従います。このページの説明は依存ライブラリの条件を置き換えません。"
});
Object.assign(translations.en, {
  workspace:"Menu", main_navigation:"Main navigation", nav_intro:"Getting started", nav_generator:"Methods & sample generation", nav_license:"License & copyright",
  workspace_page_intro:"Getting started", workspace_page_generator:"Methods & sample generation", workspace_page_license:"License & copyright",
  intro_eyebrow:"Getting started", intro_title:"About Physalia", intro_lead:"Physalia is a local tool for exploring **defenses against attackers who have gained access** and generating fictional files and samples.",
  intro_purpose:"Learn how each method works and find options suited to your environment, even with limited budget and staff. Some methods are presented as explanations only.",
  intro_concept_title:"Our approach", intro_prevention:"As AI advances, cyberattacks are taking more varied forms. Preventing intrusion alone cannot stop every attack, so we believe organizations need additional ways to prepare.", intro_after_intrusion:"Physalia does not replace antivirus or other protections. It introduces **an approach focused on using decoys to evade attacks and delay tactics to discourage attackers from continuing**. It also revisits established techniques for AI era threats and provides explanations and samples to help people understand how they work.", intro_concept_scope:"**The goal is not to rely solely on preventing every intrusion or data leak. It is to build defenses that remain effective even after one occurs.** We aim to challenge the idea that an intrusion or data leak means the attacker has won by adding work for attackers and creating opportunities to respond, even after an attack succeeds.", intro_inspiration:"As attacks diversify, **defenses should diversify too.** We believe that even small measures, combined, can make it harder for attackers to operate.", intro_boundary:"Review how each method works and where it falls short, then consider whether it could help in your environment.",
  intro_how_title:"How to use it", intro_step_1:"Open Methods & sample generation and **find methods by choosing a concern**.", intro_step_2:"Read **how a method works and its limitations**, then generate a sample if needed.", intro_step_3:"Review the output and **place it manually in an environment you control**. Configure alert delivery separately for methods that need monitoring.", intro_start:"Explore countermeasures",
  intro_limits_title:"Additional information", intro_limit_synthetic:"**Generated data is fictional.** The tool does not create real personal information, usable credentials or payment-card numbers.", intro_limit_canary:"A canary URL is optional. Leaving it blank means no live monitoring alert. The generator never requests the URL, and **merely reading a file normally does not send an HTTP alert.**", intro_limit_effect:"**A method's effect depends on where it is placed and how an attacker behaves.** Review how it works and its limitations in the context of your environment.",
  license_eyebrow:"PROJECT INFORMATION", license_title:"License & copyright", license_intro:"Terms for using this repository's software and contributions.", license_software_title:"Project license", license_software_body:"Physalia is distributed under the Apache License 2.0. Use, modification and redistribution are subject to the license text, which includes a patent license grant. The software is provided without warranty.", license_read_full:"Read the full Apache License 2.0", license_copyright_title:"Copyright and third-party libraries", license_copyright_body:"Copyright 2026 Physalia contributors. Retain copyright notices and license terms for each contribution when redistributing.", license_dependencies_body:"Python and other dependencies have their own licenses. This summary does not replace their terms."
});
Object.assign(translations.ja, {
  fit_question:"心配なことは何ですか？", fit_optional:"近いものを選んでください", fit_all:"すべて見る", fit_files:"ファイルや設定情報を探されそう", fit_website:"Webサイトのページを探られそう", fit_database:"顧客などのデータを狙われそう", fit_credentials:"アカウントやパスワードを盗まれそう", fit_exfiltration:"盗まれたデータの悪用が心配",
  fit_result_count:"候補 {count} 件", select_method:"候補から対策を選ぶ", review_method:"選んだ対策を確認", review_method_help:"仕組み・期待できること・限界", settings:"サンプルを作成する", method_settings:"選択した対策の設定"
});
Object.assign(translations.en, {
  fit_question:"What are you concerned about?", fit_optional:"Choose the closest match", fit_all:"Show all", fit_files:"Someone may search for files or settings", fit_website:"Someone may explore my website", fit_database:"Someone may target customer or business data", fit_credentials:"Someone may steal account details or passwords", fit_exfiltration:"I am concerned about misuse of stolen data",
  fit_result_count:"{count} matching methods", select_method:"Choose a relevant method", review_method:"Review the selected method", review_method_help:"How it works, expected effects and limitations", settings:"Create a sample", method_settings:"Configure the selected method"
});
translations.ja.canary_file = "カナリアファイル";
translations.en.canary_file = "Canary file";
translations.ja.fit_ransomware = "ランサムウェアでファイルを暗号化されそう";
translations.en.fit_ransomware = "Ransomware may encrypt my files";
translations.ja.canary_card = "監視URLへのアクセスを接触の手掛かりに（URLは任意）";
translations.en.canary_card = "Use requests to an optional monitoring URL as a contact signal";
translations.ja.canary_desc = "\u5f62\u5f0f\u3092\u9078\u3093\u3067\u67b6\u7a7a\u30c7\u30fc\u30bf\u5165\u308a\u306e\u6587\u66f8\u3092\u4f5c\u308a\u307e\u3059\u3002\u76e3\u8996URL\u306f\u4efb\u610f\u3067\u8ffd\u52a0\u3067\u304d\u307e\u3059\u3002";
translations.en.canary_desc = "Choose a format to create a document with fictional data. You can add a monitoring URL if you have one.";
translations.ja.reset_defaults = "初期値に戻す";
translations.en.reset_defaults = "Reset to defaults";
translations.ja.downloads_region = "生成ファイル";
translations.en.downloads_region = "Generated files";
translations.ja.reset_defaults_confirm = "画面上の設定と結果・ダウンロードリンクを消して、起動時の初期値に戻します。すでにダウンロードしたファイルは消えません。画面の言語設定は保持します。続けますか？";
translations.en.reset_defaults_confirm = "Reset the settings to their startup defaults and clear the current results and download links? Files already downloaded will remain, and your language choice will be kept.";
translations.ja.reset_defaults_operator_confirm = "管理者専用ファイルの保存確認が済んでいません。初期値に戻すと、そのダウンロードリンクと今回のパスワード・URL対応情報は失われます。すでに保存したファイルは消えません。続けますか？";
translations.en.reset_defaults_operator_confirm = "You have not confirmed saving every operator-only file. Resetting will remove their download links and this generation's password and URL mappings. Files already downloaded will remain. Continue?";
translations.ja.numeric_range = "範囲 {min}〜{max}";
translations.en.numeric_range = "Range {min}–{max}";
translations.ja.candidate_values_preview = "候補: {values}{more}";
translations.en.candidate_values_preview = "Candidates: {values}{more}";
translations.ja.quick_canary_url_invalid = "監視サービスが発行したHTTPS URLを入力してください。localhostなどのローカル宛て、空白、認証情報、フラグメントは使えません。";
translations.en.quick_canary_url_invalid = "Enter an HTTPS URL issued by your monitoring service. Local destinations such as localhost, whitespace, embedded credentials and fragments are not allowed.";
translations.ja.web_html_download = "HTMLページを保存（プレビュー用）";
translations.en.web_html_download = "Save standalone HTML preview";
translations.ja.web_package_download = "配置用サイト一式ZIPを保存";
translations.en.web_package_download = "Save complete website ZIP for deployment";
translations.ja.web_package_note = "ZIPを展開するとindex.htmlとdocumentsフォルダーができます。2つを同じ場所に配置すると、ページの一覧からサンプルファイルを開けます。ZIPはこのツールでは公開されません。";
translations.en.web_package_note = "Extract the ZIP to get index.html and a documents folder. Deploy both in the same location so the listed sample files open. This tool does not publish the ZIP.";
translations.ja.quick_canary_toggle = "監視サービスのURL（任意・空欄ではカナリア通知なし）";
translations.en.quick_canary_toggle = "Monitoring URL (optional; blank means no canary alerts)";
translations.ja.quick_canary_help_scope = "監視サービスで発行したHTTPS URLを入力すると、次に作る対応サンプルへそのまま入ります。URLなしでもサンプルは作れますが、監視通知はありません。";
translations.en.quick_canary_help_scope = "Enter an HTTPS URL issued by your monitoring service. It is copied unchanged into the next supported sample. Samples also work without a URL, but no monitoring alert will be generated.";
translations.ja.quick_canary_help_trigger = "URLへ実際にアクセスされた場合、監視サービスが記録・通知します。ファイルを作成・ダウンロードしただけ、通常に開いただけでは通知されません。";
translations.en.quick_canary_help_trigger = "The monitoring service records or alerts only when the URL is actually requested. Creating, downloading or ordinarily opening the file does not trigger an alert.";
translations.ja.quick_canary_help_hosts = "localhostはリンクを開いた人のPCです。.env内のexample.invalidは予約済みの見本で、監視先として使えません。";
translations.en.quick_canary_help_hosts = "localhost refers to the device opening the link. The example.invalid URL in .env is reserved for examples and cannot serve as a monitoring endpoint.";
translations.ja.quick_canary_help_safety = "生成器はURLへ接続しません。クローラー・リンクプレビュー・自分のクリックでも記録されることがあります。URL入りファイルは公開リポジトリに置かないでください。";
translations.en.quick_canary_help_safety = "The generator never contacts the URL. Crawlers, link previews or your own click may create a record. Do not commit files containing the URL to a public repository.";
translations.ja.quick_canary_help_existing = "詳細設定に別のURLが残っている場合、クイック作成は使用前に確認し、通常の「生成」はそのURLを使います。";
translations.en.quick_canary_help_existing = "If a different URL remains in detailed settings, Quick Create asks before using it; the regular Generate button uses it as entered.";
translations.ja.quick_canary_unsupported = "選択した手法ではカナリアURLを使いません。URL対応の手法を選ぶか、上のURL欄を空にしてください。";
translations.en.quick_canary_unsupported = "The selected method does not use canary URLs. Choose a method that supports one or clear the URL field above.";
translations.ja.quick_start_confirm = "このサンプルを作成します。上のカナリアURLを入力した場合は既存URLを置き換えます。URLは生成物に含まれます。続けますか？";
translations.en.quick_start_confirm = "Create this sample? A canary URL entered above replaces the existing URL and is included in the output.";
translations.ja.generation_settings_changed = "設定が変更されたため、生成結果を破棄しました。現在の設定で再生成してください。";
translations.en.generation_settings_changed = "Settings changed, so the generated result was discarded. Generate again with the current settings.";
translations.ja.quick_existing_url_confirm = "現在の設定にあるカナリアURLを生成物に含めます。続けますか？";
translations.en.quick_existing_url_confirm = "The canary URL in the current settings will be included in the output. Continue?";
translations.ja.default_page_title = "運用ポータル";
translations.ja.overview_only = "解説のみ・生成機能なし";
translations.en.overview_only = "Overview only · no file generated";
translations.en.default_page_title = "Operations Portal";
translations.en.env_advanced_summary = "Optional .env settings (defaults are ready)";
translations.en.nest_password_details = "Password generation options (defaults are ready)";
translations.en.database_schema_summary = "Edit or add columns (optional; the preset works as-is)";
translations.en.database_email_summary = "Use a dedicated email domain (usually leave blank)";
translations.en.maze_advanced_summary = "Folder structure and canary settings (defaults are ready)";
translations.en.encoding_advanced_summary = "Conversion methods and canary settings (defaults are ready)";
translations.en.stream_config_summary = "Stream settings (loopback, 8 KiB/s and 2 connections by default)";
translations.en.stream_ops_summary = "Operations and logging details";
translations.en.canary_help = "Enter the HTTPS URL issued by your monitoring service. If supplied, the URL is included in the generated file; do not publish that file in a public repository. Without a URL, no real canary alert can occur; .env samples use the reserved example.invalid address. The generator never contacts the URL.";
translations.en.canary_note = "Reading a file alone does not trigger an alert; the provider may alert when the URL is accessed. Scanners or link previews may access it automatically. An alert alone cannot identify who viewed the file or caused the request.";
translations.en.canary_advanced_summary = "Format and URL restrictions";
translations.en.canary_advanced_help = "To receive alerts, use a publicly reachable monitoring endpoint. Private IPs and local-only hostnames are rejected, but DNS destinations are not checked. With no URL, only .env samples include the reserved example.invalid placeholder; other formats omit it. Standard .env wraps URLs in single quotes, so choose another format if the URL contains a single quote. URLs containing $, whitespace or a # fragment cannot be used. The development/production note layout has separate input restrictions. PowerPoint includes every requested record, split into slides of up to 10 rows. Correlate alerts with known scanners.";
translations.ja.preview_html = "新しいタブでHTMLをプレビュー";
translations.en.preview_html = "Preview HTML in a new tab";
translations.ja.preview_pdf = "新しいタブでPDFをプレビュー";
translations.en.preview_pdf = "Preview PDF in a new tab";
translations.ja.preview_text_title = "テキストの内容を確認";
translations.en.preview_text_title = "Preview text contents";
translations.ja.preview_text_loading = "プレビューを読み込み中…";
translations.en.preview_text_loading = "Loading preview…";
translations.ja.preview_text_too_large = "ファイルが大きいため、画面内プレビューを省略しました。ダウンロードしたファイルを開いてください。";
translations.en.preview_text_too_large = "This file is too large for an in-page preview. Open the downloaded file to inspect it.";
translations.ja.preview_text_failed = "プレビューを表示できません。ダウンロードしたファイルを開いてください。";
translations.en.preview_text_failed = "The preview could not be displayed. Open the downloaded file to inspect it.";
translations.ja.preview_text_canary_redacted = "入力したURLはプレビュー内で伏せています。";
translations.en.preview_text_canary_redacted = "Operator-supplied URLs are hidden in this preview.";
translations.ja.preview_url_redacted = "[URLは非表示]";
translations.en.preview_url_redacted = "[URL REDACTED]";
translations.ja.quick_db = "選択したデータベースのサンプルを作成";
translations.en.quick_db = "Create selected database sample";
translations.ja.quick_db_template_label = "作成するデータの種類";
translations.en.quick_db_template_label = "Sample data type";
translations.ja.quick_db_template_help = "種類を選ぶと、作成する項目（列）と架空データの例が切り替わります。";
translations.en.quick_db_template_help = "Choose a data type to preview the columns and an example of the fictional data it creates.";
translations.ja.quick_db_filename_note = "ファイル名は用途に合わせて自動設定されます。変更する場合は詳細設定の「ファイル名」欄を使ってください。";
translations.en.quick_db_filename_note = "The filename is chosen for the selected data type. To change it, use the File name field under detailed settings.";
translations.ja.quick_db_purpose_summary = "PCに保存するDBファイルを作成（サーバー・既存DBは不要）";
translations.en.quick_db_purpose_summary = "Create a database file on this PC (no server or existing database needed)";
translations.ja.quick_db_canary_note = "カナリアURLを指定した場合、その値はSQLite内に保存されます。URLが空欄なら通知はなく、DBファイルの作成・ダウンロード・閲覧でも通知されません。URLにアクセスされたとき監視サービスが記録します。生成器自身はURLに接続しません。";
translations.en.quick_db_canary_note = "If you provide a canary URL, it is stored in the SQLite file. A blank URL means no alert; creating, downloading or viewing the database does not trigger one either. The monitoring service records a request only when the URL is accessed. The generator itself never contacts it.";
translations.ja.quick_db_purpose = "DBサーバー不要で、架空データだけを含むSQLiteファイルを1つ作成します。既存DBへの接続や変更はしません。カード番号や認証に使えるパスワードは含みません。電話番号は日本語サンプルでも、実在加入者につながらない北米の架空用予約範囲（+1-202-555-0100〜0199）を使います。ファイルは最大32 MiBです。上限を超えた場合は作成件数を減らしてください。カナリアURLを指定すると生成ファイルに含めます。";
translations.en.quick_db_purpose = "No database server is needed. This creates one SQLite file with fictional data and never connects to or changes an existing database. It contains no payment card numbers or usable passwords. Phone fields use the reserved fictional +1-202-555-0100–0199 range, including in Japanese-language samples. Files are limited to 32 MiB; if generation exceeds the limit, reduce the row count. A supplied canary URL is included in the file.";
translations.ja.database_size_limit = "SQLite生成物が32 MiBの上限を超えました。レコード数、項目数、候補値の長さを減らしてください。";
translations.en.database_size_limit = "The SQLite artifact exceeds the 32 MiB limit. Reduce the row count, column count or candidate value lengths.";
translations.ja.quick_db_custom_schema_help = "詳細設定のテーブル名や項目に変更があります。クイック作成では選択中のプリセットを使い、下の項目例の内容に置き換えて作成します。";
translations.en.quick_db_custom_schema_help = "The table name or fields in detailed settings have been changed. Quick Create will replace them with the selected preset shown below.";
translations.ja.quick_db_retry = "もう一度読み込む";
translations.en.quick_db_retry = "Retry loading presets";
translations.ja.quick_db_language_loading = "選択中の言語に合わせてデータベースの項目を読み込み中です。読み込み後に作成してください。";
translations.en.quick_db_language_loading = "Loading database fields for the selected language. Create the database after loading finishes.";
translations.ja.quick_guide_link = "はじめての作成・配置ガイド";
translations.en.quick_guide_link = "Quick guide to creating and deploying samples";
translations.ja.log_guide_link = "ログの記録と手動確認ガイド";
translations.en.log_guide_link = "Guide to logging and manual review";
translations.ja.scenario_schema_summary = "\u751f\u6210\u30c7\u30fc\u30bf: {name}\uff08{fields}{more}\uff09";
translations.en.scenario_schema_summary = "Generated data: {name} ({fields}{more})";
translations.ja.scenario_schema_more = "\u3001\u4ed6{count}\u9805\u76ee";
translations.en.scenario_schema_more = ", plus {count} more fields";
translations.ja.canary_setup_guide = "カナリアURLの準備・配置ガイド";
translations.en.canary_setup_guide = "Canary URL setup and deployment guide";
translations.ja.quick_db_fields = "作成する項目";
translations.en.quick_db_fields = "Fields included";
translations.ja.quick_db_technical_summary = "列名・データ型の詳細";
translations.en.quick_db_technical_summary = "Column names and data types";
translations.ja.database_identifier_help = "テーブル名・列名は、英字または_で始まる英数字と_のみ、48文字以内です。sqlite_で始まる名前は使えません。例: customers、last_contact。日本語の表示項目名とは別に、ここには英数字の名前を入力します。";
translations.en.database_identifier_help = "Table and column names must start with an ASCII letter or _, use only ASCII letters, digits and _, and be no longer than 48 characters. Names beginning with sqlite_ are reserved. Examples: customers, last_contact. Enter the ASCII identifier here; it is separate from the Japanese display label.";
translations.ja.quick_db_schema_summary = "SQLiteのテーブル: {table}（{count}項目）";
translations.en.quick_db_schema_summary = "SQLite table: {table} ({count} fields)";
translations.ja.quick_db_rows = "架空レコード{rows}件を作成します。";
translations.en.quick_db_rows = "Creates {rows} fictional records.";
translations.ja.template_default_loading = "顧客管理（プリセット読込中・既定）";
translations.en.template_default_loading = "Customer management (default while presets load)";
translations.ja.quick_db_count_label = "作成件数（1〜10,000）";
translations.en.quick_db_count_label = "Number of records (1–10,000)";
translations.ja.quick_db_count_invalid = "作成件数は1〜10,000の範囲で入力してください。";
translations.en.quick_db_count_invalid = "Enter a record count from 1 to 10,000.";
translations.ja.quick_db_example_summary = "生成される架空データの例を見る";
translations.en.quick_db_example_summary = "View an example of the fictional data";
translations.ja.stream_generated_summary = "配信上限は {rate} KiB/秒、同時接続は {streams} 件です。起動方法は同梱のREADMEを参照してください。";
translations.en.stream_generated_summary = "The delivery limit is {rate} KiB/s with {streams} concurrent streams. See the included README for startup instructions.";
translations.ja.directory_generated_summary = "デコイファイル {documents} 個を {directories} 個のディレクトリに作成しました。";
translations.en.directory_generated_summary = "Created {documents} decoy files across {directories} directories.";
translations.ja.encoding_generated_summary = "{scenario}：候補 {candidates} 個に、それぞれ {layers} 段階の変換を作成しました。";
translations.en.encoding_generated_summary = "{scenario}: created {candidates} candidates with {layers} encoding steps each.";
translations.ja.quick_file = "選択形式のサンプルを1つ作成";
translations.en.quick_file = "Create one sample in the selected format";
translations.ja.quick_file_action = "{format}を作成（架空データ{rows}件）";
translations.en.quick_file_action = "Create {format} sample ({rows} records)";
translations.ja.quick_file_env_standard_action = "通常形式の.envをZIPで作成";
translations.en.quick_file_env_standard_action = "Create standard .env ZIP";
translations.ja.quick_file_env_switch_action = ".env.{suffix}切替メモ付き見本ZIPを作成";
translations.en.quick_file_env_switch_action = "Create .env.{suffix} switch-note sample ZIP";
translations.ja.env_suffix_format_help = "英数字で始め、英数字・ハイフン・アンダースコアを1〜32文字で指定します。";
translations.en.env_suffix_format_help = "Use 1–32 ASCII letters, digits, hyphens or underscores; start with a letter or digit.";
translations.ja.env_suffix_format_error = "環境名は英数字で始め、英数字・ハイフン・アンダースコアの1〜32文字で入力してください。";
translations.en.env_suffix_format_error = "Use 1–32 ASCII letters, digits, hyphens or underscores, starting with a letter or digit.";
translations.ja.quick_file_format_env = ".env設定ファイル";
translations.en.quick_file_format_env = ".env settings file";
translations.ja.quick_file_format_label = "ファイル形式";
translations.en.quick_file_format_label = "File format";
translations.ja.quick_file_context_label = "サンプルの用途";
translations.en.quick_file_context_label = "Sample context";
translations.ja.quick_file_context_help = "\u7528\u9014\u3092\u9078\u3076\u3068\u3001\u30d5\u30a1\u30a4\u30eb\u306e\u898b\u51fa\u3057\u3084\u30b5\u30f3\u30d7\u30eb\u306e\u9805\u76ee\u30fb\u30c7\u30fc\u30bf\u304c\u7528\u9014\u306b\u5408\u308f\u305b\u3066\u5909\u308f\u308a\u307e\u3059\u3002";
translations.en.quick_file_context_help = "Choose a purpose to use matching headings, sample fields and data.";
translations.en.context_help = "The selected purpose changes the generated record columns and values, title, and default canary field. When a file contains records, the URL is placed in that field in one record; the result shows the exact field and record. .env files use a matching setting key. The URL is not modified or fetched, and its domain and hyperlink target can still be inspected.";
Object.assign(translations.en, {
  format_env: ".env file",
  format_txt: "Text (.txt)",
  format_json: "JSON",
  format_csv: "CSV",
  format_html: "HTML document (fictional records)",
  format_pdf: "PDF",
  format_xlsx: "Excel (.xlsx)",
  format_pptx: "PowerPoint (.pptx)",
  format_sqlite: "SQLite (.db)",
  format_sql: "SQL",
});
translations.ja.quick_files_group = "ファイルを作成";
translations.en.quick_files_group = "Create a file";
translations.ja.quick_env = ".env.development設定サンプルをZIPで作成";
translations.en.quick_env = "Create a sample settings file (.env.development ZIP)";
translations.ja.quick_env_help = "ZIPはブラウザーが先頭のドットをファイル名から外す場合に備えています。展開すると.env.developmentを取り出せます。これはデコイ専用の見本です。実アプリや本番設定には読み込ませず、隔離した検証環境だけで使ってください。指定したカナリアURLはコメント行に入ります。ファイルを開くだけでは通知されません。通知を試すには、URLをコピーしてブラウザーで開いてください（監視サービスに記録されます）。初期設定のexample.invalidは見本用で、監視通知は届きません。";
translations.en.quick_env_help = "The ZIP preserves the leading dot if your browser removes it from downloaded filenames. Extract it to get .env.development. This is a decoy sample: do not load it into a real application or production configuration; use it only in an isolated test environment. The supplied canary URL is placed in a comment, so opening the file alone does not trigger an alert. To check monitoring, copy the URL and open it in a browser; this may create a monitoring event. The default example.invalid address is a placeholder and cannot send monitoring alerts.";
translations.ja.quick_env_help += " 有効行の開発URLも予約済みexample.invalidの見本値で、実在サービスにはつながりません。クイック作成は詳細設定の有効URLやメモを引き継ぐため、以前に変更した場合は作成前に確認してください。隔離した検証環境で有効行を試す場合だけ、自分が管理するURLへ置き換えてください。";
translations.en.quick_env_help += " The active development URL is also a reserved example.invalid placeholder and does not reach a real service. Quick Create keeps the active URL and notes from detailed settings, so review them first if you changed them. Replace the URL only with one you control when testing the active value in an isolated environment.";
translations.ja.quick_html = "サンプルWebページ（HTML＋配置用ZIP）を作成";
translations.en.quick_html = "Create sample web page (HTML + deployment ZIP)";
translations.ja.quick_html_help = "配置用ZIPを作成します。PC上でZIPのページを確認するには、展開してindex.htmlを開きます。監視URLを指定した場合、一覧の1件は監視先へのリンクです。クリックすると監視サービスに記録・通知されることがあります。監視を意図して確認するときだけクリックしてください。Webサイトとして使う場合は、ZIPを展開してindex.htmlとdocumentsフォルダーを同じ公開フォルダーへ、構成を保って配置してください。ログイン機能はありません。";
translations.en.quick_html_help = "Creates a deployment ZIP. To preview the ZIP on your computer, extract it and open index.html. If you supplied a monitoring URL, one listed item links to it. Clicking it may be logged by the monitoring service and may trigger an alert; open it only when you intend to test monitoring. To use the sample as a website, extract the ZIP and upload index.html and the documents folder together, preserving the folder structure, to a web directory you control. There is no login feature.";
translations.ja.quick_html_details_summary = "ZIPの中身と監視リンクについて";
translations.en.quick_html_details_summary = "ZIP contents and monitoring links";
translations.ja.quick_html_details = "ZIPにはindex.htmlと架空PDF・Excel・CSVが6件入ります。監視URLを指定した場合、一覧の1件が監視先へのリンクになり、その行の文書はページから開けません。ページやプレビューを開くだけでは監視先へ接続せず、リンクをクリックしたときだけ要求が届きます。配置後のページ訪問はWebサーバーのログで確認してください。";
translations.en.quick_html_details = "The ZIP contains index.html and six fictional PDF, Excel and CSV files. If you provide a monitoring URL, one list entry links to it instead of opening its document. Opening the page or preview does not contact the monitoring service; clicking that link does. Check web server logs separately for visits to the deployed page.";
translations.ja.quick_database_group = "データベースを作成";
translations.en.quick_database_group = "Create a database";
translations.ja.quick_db_for = "{name}\u306e\u30c7\u30fc\u30bf\u30d9\u30fc\u30b9\u30d5\u30a1\u30a4\u30eb\uff08.db\uff09\u3092\u4f5c\u6210\uff08\u67b6\u7a7a\u30c7\u30fc\u30bf{rows}\u4ef6\uff09";
translations.en.quick_db_for = "Create {name} database file (.db) with {rows} fictional records";
translations.ja.quick_file_rows_label = "データ件数（1〜500）";
translations.en.quick_file_rows_label = "Number of records (1–500)";
translations.ja.quick_file_rows_invalid = "データ件数は1〜500の整数で入力してください。";
translations.en.quick_file_rows_invalid = "Enter a record count from 1 to 500.";
translations.ja.quick_file_help = "ここでは1ファイルを作成します。件数は詳細設定にも反映されます。ほかの設定は引き継ぎます。上部と詳細設定のURL欄がどちらも空なら通知は発生しません。";
translations.en.quick_file_help = "Creates one file. The record count is also applied in detailed settings. Other settings are kept. No alert is triggered when both the top canary field and the method-specific URL field are empty.";
translations.ja.quick_file_deployment_note = "生成物はダウンロードされるだけで、サーバーへの配置や監視設定は行いません。防御に使う場合は、自分が管理する環境の適切な場所へ配置し、監視サービス側の通知先も設定してください。";
translations.en.quick_file_deployment_note = "Generation only downloads the file; it does not deploy it or configure monitoring. To use it as a decoy, place it in an appropriate location in an environment you control and configure notifications in your monitoring service.";
translations.ja.quick_filename_note = "ファイル名は用途に合わせて自動設定されます。作成後はブラウザーのダウンロード一覧から開けます。名前を変える場合は詳細設定の「ファイル名」欄を使ってください。";
translations.en.quick_filename_note = "The filename is chosen for the selected sample. After creation, find it in your browser's downloads list. To change the name, use the File name field under detailed settings.";
translations.ja.quick_file_env_standard_help = "通常設定形式の.envファイルを作ります。レコード件数は使いません。先頭ドットのファイル名を保つためZIPに入ります。詳細設定のカナリアURLは引き継ぎ、URL項目の値として入れます。作成前に内容を確認してください。ファイルを読むだけではカナリアURLへアクセスしません。";
translations.en.quick_file_env_standard_help = "Creates a standard .env settings file. No record count is used. It is packaged in a ZIP to preserve the leading dot in its filename. The canary URL from detailed settings is kept as the URL value; review the file before using it. Reading it alone does not request the canary URL.";
translations.en.env_dev_url_authorization = "For hosts outside example.invalid, confirm that you own the host and route it only to an isolated test endpoint without production authentication.";
Object.assign(translations.en, {
  candidate_values_error: "Enter one to 100 candidate values, separated by commas.",
  category_description: "Detection helps identify decoy contact or use. Delay adds work for an attacker. Decoy luring directs attention to fictional assets or pages. Post-exfiltration disruption makes copied candidates harder to assess or use. AI attack aware means AI agents are included in evaluation; the method may also affect human and scripted attacks. Detection and alerts may require separate setup, and no effect is guaranteed.",
  category_guide: "What the tags mean",
  column_name_error: "Enter a valid, unique column name.",
  request_too_large: "The generation request is too large. Reduce the amount of input and try again.",
  sensitive_setting_text: "Settings may contain credentials or payment data. Remove sensitive values before saving or loading.",
  tag_ai: "AI attack aware",
});
translations.ja.quick_file_env_switch_help = "開発・本番の切替メモ付き.env.{suffix}を作ります。開発URLを有効にし、カナリアURLは本番用のコメント行に入れます。レコード件数は使いません。詳細設定の有効URLやメモは引き継ぐため、作成前に内容を確認してください。ファイルを読むだけではURLへアクセスしません。これはデコイ見本です。実アプリや本番設定には読み込ませず、隔離した検証環境だけで使ってください。";
translations.en.quick_file_env_switch_help = "Creates .env.{suffix} with development/production switch notes. The development URL is active; the canary URL goes in a commented production line. No record count is used. Active URLs and notes from detailed settings are kept; review them before creating the file. Reading it alone does not request either URL. This is a decoy sample: do not load it into a real application or production configuration; use it only in an isolated test environment.";
translations.ja.quick_preview_available = " 生成後、ダウンロード欄に架空レコードの先頭10件を表示します。";
translations.en.quick_preview_available = " After generation, the download area shows the first 10 fictional records.";
translations.ja.quick_start_help += " 上のカナリアURL欄が空なら、そこから新しいURLは追加しません。ただし詳細設定のURL欄に値がある場合、クイック作成は確認後に使用し、通常の「生成」はその値を使います。既定のexample.invalidは予約済みの無効ドメインで、実際の監視先ではありません。";
translations.en.quick_start_help += " An empty canary field above adds no URL. A URL already entered in detailed settings is still used: Quick Create asks first, while the regular Generate button uses it directly. The default example.invalid URLs are reserved and cannot serve as real monitoring endpoints.";
translations.ja.quick_start_help += " クイック作成欄で形式・用途・件数を変更すると詳細設定にも反映され、設定JSONに保存できます。";
translations.en.quick_start_help += " Changing the format, context or count in quick-create updates detailed settings, where you can save it in the settings JSON.";
translations.ja.quick_filename_note = "ダウンロード名は対策に合わせたPhysalia_*形式です。必要なら保存後に名前を変更してください。配置用ZIP内のファイル名は、形式に必要な名前を保ちます。";
translations.en.quick_filename_note = "Download names use a method-specific Physalia_* pattern. Rename files after saving if needed. Files inside deployment ZIPs retain names required by their formats.";
translations.ja.quick_db_filename_note = translations.ja.quick_filename_note;
translations.en.quick_db_filename_note = translations.en.quick_filename_note;
translations.ja.quick_start_help = "最初はサンプルを一つ作成してみてください。生成ファイルは架空データで、ダウンロード名はPhysalia_*形式です。必要なら保存後に名前を変更してください。カナリア通知には、運用者が発行した監視URLへ実際にアクセスされる必要があります。生成器はURLに接続しません。" + translations.ja.quick_start_help.slice(translations.ja.quick_start_help.indexOf(" 上のカナリアURL欄"));
translations.en.quick_start_help = "Start with one sample. Files contain fictional data and use Physalia_* download names; rename them after saving if needed. A canary alert requires your monitoring URL to be accessed. The generator never contacts that URL." + translations.en.quick_start_help.slice(translations.en.quick_start_help.indexOf(" An empty canary field"));
translations.ja.quick_env_reset_confirm = "このサンプルのため.envの設定パターンを初期値に戻します。カナリアURLは保持します。続けますか？";
translations.en.quick_env_reset_confirm = "Reset the .env configuration pattern for this sample. Your canary URL will be kept. Continue?";
translations.ja.fake_note = "出力ファイル名はPhysalia_*形式です。表示だけの静的ページで、検知・通報・認証・情報収集は行わず、外部への通信やプログラム送信もありません。監視・通知は配信側で別途設定してください。通報済みの表示は実際の通報を意味しません。正規利用者の誤接触に配慮してください。";
translations.en.fake_note = "The downloaded file uses a Physalia_* name. This static page only displays a message. It does not detect, report, authenticate, collect information, communicate externally or send software. Configure monitoring and alerts separately. The reported message does not mean a report was sent. Avoid exposing legitimate users to the page.";
translations.ja.env_switch_help = "空欄のまま作成すると、配置用ZIPには.env.developmentを含めます。開発URLは有効で、カナリアURLはコメント行に入ります。既定URLはexample.invalidです。独自ホストを使う場合は所有を確認し、本番認証のない隔離テスト先だけへ向けてください。このURLはクローラーやエージェントから要求される場合があります。生成器は名前解決・接続を行いません。内部・本番エンドポイントを指定せず、本番設定へ読み込ませないでください。ダウンロードZIP名はPhysalia_*形式です。";
translations.en.env_switch_help = "The deployment ZIP contains .env.development by default. The development URL is active and the canary URL is a commented production alternative. The default uses example.invalid. For a custom host, confirm ownership and route it only to an isolated test endpoint without production authentication. A crawler or agent may request this active URL. The generator does not resolve or contact it. Do not enter internal or production endpoints or load the file in production configuration. The downloaded ZIP uses a Physalia_* name.";
translations.ja.quick_env_help = "配置用ZIPには、アプリ名・ログレベル・ポート・DB/Redis接続先・タイムアウト・再試行回数などを含む.env.developmentが入ります。接続先は予約済みexample.invalidの架空ホストで、認証情報は含みません。カナリアURLはコメント行に入り、ファイルを開くだけでは通知されません。これはデコイ専用の見本です。実アプリや本番設定には読み込ませず、隔離した検証環境だけで使ってください。";
translations.en.quick_env_help = "The deployment ZIP contains .env.development with common settings such as an app name, log level, port, database and Redis endpoints, timeout and retry count. Endpoints use fictional hosts under reserved example.invalid, and the file contains no credentials. The canary URL is in a comment, so opening the file alone does not trigger an alert. This is a decoy sample; do not load it into a real application or production configuration. Use it only in an isolated test environment.";
translations.ja.env_direct_download = "Physalia_*形式で.envサンプルを保存";
translations.en.env_direct_download = "Save .env sample with Physalia_* name";
translations.ja.env_zip_download = "配置用ZIPを保存（ZIP内は.env形式の名前）";
translations.en.env_zip_download = "Save deployment ZIP (contains the required .env filename)";
translations.ja.env_zip_note = "配置用ZIPの中では.env形式の名前を保ちます。ダウンロード後、ZIPを展開して使ってください。";
translations.en.env_zip_note = "The deployment ZIP preserves the required .env filename. Extract the ZIP before use.";
translations.ja.env_switch_help = "切替メモ形式を選ぶと、配置用ZIPには.env.developmentを含めます。開発URLは有効で、カナリアURLはコメント行に入ります。既定URLはexample.invalidです。独自ホストを使う場合は所有を確認し、本番認証のない隔離テスト先だけへ向けてください。このURLはクローラーやエージェントから要求される場合があります。生成器は名前解決・接続を行いません。内部・本番エンドポイントを指定せず、本番設定へ読み込ませないでください。ダウンロード名はPhysalia_*形式です。";
translations.en.env_switch_help = "The switch-note format places .env.development inside the deployment ZIP. The development URL is active and the canary URL is a commented production alternative. The default uses example.invalid. For a custom host, confirm ownership and route it only to an isolated test endpoint without production authentication. A crawler or agent may request this active URL. The generator does not resolve or contact it. Do not enter internal or production endpoints or load the file in production configuration. The download name uses a Physalia_* pattern.";
translations.ja.notice = "\u624b\u6cd5\u3092\u9078\u3073\u3001\u4ed5\u7d44\u307f\u3084\u5bfe\u8c61\u3068\u306a\u308b\u653b\u6483\u3092\u78ba\u8a8d\u3057\u3066\u304b\u3089\u751f\u6210\u3057\u307e\u3059\u3002\u751f\u6210\u7269\u306f\u67b6\u7a7a\u30c7\u30fc\u30bf\u3067\u3001\u81ea\u52d5\u914d\u7f6e\u3055\u308c\u307e\u305b\u3093\u3002\u76e3\u8996URL\u3092\u5165\u308c\u306a\u3044\u5834\u5408\u3001\u30ab\u30ca\u30ea\u30a2\u901a\u77e5\u306f\u767a\u751f\u3057\u307e\u305b\u3093\u3002";
translations.en.notice = "Select a method and review its mechanism and target attacks before generating. Artifacts contain fictional data and are not deployed automatically. No canary alert occurs without a monitoring URL.";
translations.en.intro_step_1 = "Open Methods & sample generation and **find methods by choosing a concern**.";
Object.assign(translations.ja, {
  nav_logs:"ログ分析解説", workspace_page_logs:"ログ分析解説", logs_eyebrow:"手動で行うログ確認",
  logs_title:"ログ分析解説", logs_intro:"デコイへの接触を、自社の既存ログで確認するための考え方と記録例です。",
  logs_badge:"手動確認", logs_scope_title:"このページで扱うこと",
  logs_scope:"このページでは既存ログの確認方法を説明します。外部ログの取り込みや自動分析は行いません。このPCの接触記録は「カナリア接触ログ」で確認できます。",
  logs_fields_title:"必要最小限の記録項目", logs_field_time:"時刻：UTCまたはタイムゾーン付きで統一します。",
  logs_field_event:"event・decoy_id・request_id：接触の種類、デコイ識別子、サーバー内で要求を照合するIDを記録します。完全なカナリアURLや秘密トークンは記録しません。",
  logs_field_request:"method・status・bytes_sent・request_seconds：要求方法、応答状態、サーバー側の送信量と処理時間を記録します。取得完了の証明にはなりません。",
  logs_field_optional:"source_ipやuser_agentは必要性がある場合に限ります。個人を識別し得る情報として扱い、不要なら収集しません。",
  logs_never_collect:"パスワード、Cookie、Authorizationヘッダー、リクエスト本文、顧客データ、URLのクエリ文字列・フラグメントは記録しないでください。カナリアURLと識別子の対応表はログと分け、管理者だけが見られる場所に保管します。",
  logs_example_title:"JSON Linesの記録例", logs_example_note:"以下は架空の例です。送信元IPは必須項目ではなく、必要性がある場合だけ記録します。",
  logs_sample:"{\"time\":\"2026-10-20T01:12:04Z\",\"event\":\"decoy_contact\",\"decoy_id\":\"cfg-backup-01\",\"request_id\":\"req-7a31\",\"method\":\"GET\",\"status\":200,\"bytes_sent\":894,\"request_seconds\":0.018}\n{\"time\":\"2026-10-20T01:13:19Z\",\"event\":\"decoy_contact\",\"decoy_id\":\"cfg-backup-01\",\"request_id\":\"req-7a32\",\"method\":\"HEAD\",\"status\":200,\"bytes_sent\":0,\"request_seconds\":0.006}",
  logs_review_title:"担当者が手動で確認する流れ",
  logs_review_1:"メール保護スキャナー、リンクプレビュー、社内監視など正規の自動アクセスがないか確認します。",
  logs_review_2:"decoy_idごとに時刻順で並べ、GET・HEAD、応答状態、要求間隔、送信量を確認します。",
  logs_review_3:"必要な場合だけ、自組織が管理するWebサーバーや認証基盤の記録をrequest_idや時刻で照合します。",
  logs_review_4:"「URL要求があった」「サーバーが応答した」と「人が読んだ」「保存した」「侵害した」を区別し、断定を避けて判断根拠を記録します。",
  logs_review_5:"原本をアクセス制限された場所に保全し、誤検知を確認してから既存のインシデント対応手順に従います。",
  logs_privacy_title:"プライバシーと安全な調査",
  logs_privacy_body:"IPアドレスやUser-Agent等は個人を識別し得る情報として、利用目的、必要性、閲覧者、保存期間、削除手順を定めて管理します。送信元端末への接続・スキャン、第三者システムへのログイン、無断追跡や反撃は行いません。デコイへの接触は、別システムへアクセスする権限を与えません。",
  logs_full_guide:"詳細な記録例・運用上の注意を読む",
});
Object.assign(translations.en, {
  nav_logs:"Log review guide", workspace_page_logs:"Log review guide", logs_eyebrow:"MANUAL LOG REVIEW",
  logs_title:"Log review guide", logs_intro:"Practical guidance and a sample record for reviewing decoy contacts in logs you control.",
  logs_badge:"Manual review", logs_scope_title:"What this page covers",
  logs_scope:"This page explains how to review existing logs. It does not import or automatically analyze external logs. Open Canary contacts to see this PC's local events.",
  logs_fields_title:"Collect only the minimum needed", logs_field_time:"time: use UTC or an explicit timezone consistently.",
  logs_field_event:"event, decoy_id, request_id: record the event type, an opaque decoy identifier and a server-generated request correlation ID. Do not log a full canary URL or secret token.",
  logs_field_request:"method, status, bytes_sent, request_seconds: record the request method, response status, server-side bytes and processing time. These do not prove complete retrieval.",
  logs_field_optional:"Collect source_ip or user_agent only when necessary. Treat them as potentially identifying information and omit them when not needed.",
  logs_never_collect:"Do not log passwords, cookies, Authorization headers, request bodies, customer data, or URL query strings and fragments. Keep the canary URL-to-ID mapping separate from logs and restrict it to operators.",
  logs_example_title:"JSON Lines example", logs_example_note:"This is fictional. A source IP is optional; include it only when necessary.",
  logs_sample:"{\"time\":\"2026-10-20T01:12:04Z\",\"event\":\"decoy_contact\",\"decoy_id\":\"cfg-backup-01\",\"request_id\":\"req-7a31\",\"method\":\"GET\",\"status\":200,\"bytes_sent\":894,\"request_seconds\":0.018}\n{\"time\":\"2026-10-20T01:13:19Z\",\"event\":\"decoy_contact\",\"decoy_id\":\"cfg-backup-01\",\"request_id\":\"req-7a32\",\"method\":\"HEAD\",\"status\":200,\"bytes_sent\":0,\"request_seconds\":0.006}",
  logs_review_title:"Manual review workflow",
  logs_review_1:"Check for expected automated access from mail security scanners, link previews and internal monitoring.",
  logs_review_2:"Sort by time per decoy_id. Review GET or HEAD sequences, response status, intervals and server-side response volume.",
  logs_review_3:"Only when needed, correlate request_id or time with web-server or identity logs that your organization controls.",
  logs_review_4:"Distinguish a URL request or server response from a person reading or saving a file, or a system being compromised. Record evidence and uncertainty; do not overstate conclusions.",
  logs_review_5:"Preserve originals in an access-controlled location, check for false positives and follow your existing incident-response process.",
  logs_privacy_title:"Privacy and safe investigation",
  logs_privacy_body:"Set a defined purpose, necessity, readers, retention period and deletion process for potentially identifying data such as IP addresses and User-Agent values. Do not connect to or scan a source device, log in to a third-party system, track someone without authorization or retaliate. Contact with a decoy does not authorize access to another system.",
  logs_full_guide:"Open the detailed guide and examples",
});
Object.assign(translations.ja, {nav_canary:"カナリア接触ログ", local_canary_title:"このPCのカナリア接触ログ", local_canary_help:"Physaliaが起動中の同じPCからの接触を記録します。ログは最大500件、アプリ終了時に消えます。", local_canary_privacy:"接続元IP、ブラウザー情報や言語など、アクセス時に送られた情報を記録します。情報は偽装・省略される場合があります。管理権限のある環境で利用し、閲覧を制限してください。", local_canary_limit:"この機能は同じPCからの接触のみを受け付けます。送信元IPは通常127.0.0.1です。", local_canary_ip:"送信元IP", local_canary_empty:"接触ログはありません。", local_canary_scope:"初期URLは、同じPCでPhysaliaが起動中の動作確認用です。別PCからは届きません。", local_canary_record:"接触 #{event_id} · {time} · {method} · ID {canary_id}"});
Object.assign(translations.en, {nav_canary:"Canary contacts", local_canary_title:"Local canary contacts on this PC", local_canary_help:"Records contacts from this PC while Physalia is running. Up to 500 events are kept in memory until the app stops.", local_canary_privacy:"Records information sent with a request, including the source IP, browser information and language. Clients can omit or falsify these values. Use in an environment you are authorized to manage and restrict access to the log.", local_canary_limit:"This feature accepts contacts only from this PC. The source IP is normally 127.0.0.1.", local_canary_ip:"Source IP", local_canary_empty:"No contacts recorded.", local_canary_scope:"The initial URL is for checks on this PC while Physalia is running. Requests from another PC cannot reach it.", local_canary_record:"Contact #{event_id} · {time} · {method} · ID {canary_id}"});
Object.assign(translations.ja, {legal_disclaimer:"以下は日本法に関する一般的な一見解です。個別の適法性を保証するものではありません。実際の導入前に、適用地域に詳しい法律の専門家へ確認してください。", legal_us_disclaimer:"以下は米国法に関する一般的な一見解です。個別の適法性を保証するものではありません。実際の導入前に、適用地域に詳しい法律の専門家へ確認してください."});
Object.assign(translations.en, {legal_us_disclaimer:"This is a general view of US law, not a determination for a particular case. Consult a legal professional familiar with the applicable jurisdiction before deployment."});
Object.assign(translations.ja, {settings_privacy_summary:"設定JSONに保存される内容", settings_privacy_help:"専用URL欄と所有確認チェックは保存しません。ドメイン欄の値や通常の入力値はJSONに残る場合があります。自由入力欄のURLや秘密情報は自動で除かれないため、実データや秘密を入力せず、JSONを安全に保管してください。"});
Object.assign(translations.en, {settings_privacy_summary:"What the settings JSON contains", settings_privacy_help:"Dedicated URL fields and ownership confirmations are not saved. Domain values and ordinary settings may remain in the JSON. URLs or secrets in free-text fields are not automatically removed, so do not enter real data or secrets, and store the JSON securely."});
Object.assign(translations.ja, {context_help:"用途に合う見出し・項目・架空データを設定します。レコード形式では、1件の自然なURL項目にカナリアURLを置き、生成結果に項目名とレコード番号を表示します。.envでは用途に合う設定キーを使います。"});
Object.assign(translations.en, {context_help:"Chooses matching headings, fields and fictional data. Record formats place the canary URL in a natural URL field in one record; the result shows its field and record number. .env files use a matching setting key."});
Object.assign(translations.ja, {
  canary_file_result_summary:"{format}ファイルを作成しました（{rows}件）。",
  database_result_summary:"データベースを作成しました（{rows}件、{columns}項目）。",
  database_result_preset:"使用テンプレート：{preset}",
  database_canary_field:"カナリアURLは「{field}」列のレコード{record}に配置しました。",
  database_canary_api_field:"API接続先「{field}」のレコード{record}に配置しました。",
  database_canary_table:"カナリアURLを接続先テーブルに配置しました。",
  database_preview_title:"データプレビュー",
  database_preview_caption:"全{rows}件のうち、{count}件をプレビューしています。",
  canary_preview_caption:"生成した全{count}件のレコードを確認できます。",
  preview_table_scroll_hint:"表を横にスクロールして右側の項目を確認できます。ページ送りでレコードを切り替えます。",
  preview_page_status:"{start}–{end}件 / {total}件（{page}/{pages}ページ）",
  preview_previous:"前へ", preview_next:"次へ",
  preview_canary_target:"カナリアURLを設定したレコード{record}です。セルを強調表示しています。プレビューではURLを伏せています。"
});
Object.assign(translations.en, {
  canary_file_result_summary:"Created {format} file with {rows} records.",
  database_result_summary:"Created database with {rows} records and {columns} fields.",
  database_result_preset:"Template: {preset}",
  database_canary_field:"Canary URL is placed in record {record}, field {field}.",
  database_canary_api_field:"Canary URL is placed in record {record}, API endpoint {field}.",
  database_canary_table:"Canary URL is stored in a separate connection table.",
  database_preview_title:"Data preview",
  database_preview_caption:"Previewing {count} of {rows} records.",
  canary_preview_caption:"All {count} generated records are available in the preview.",
  preview_table_scroll_hint:"Scroll horizontally to see more fields. Use the page controls to move through records.",
  preview_page_status:"Records {start}–{end} of {total} (page {page} of {pages})",
  preview_previous:"Previous", preview_next:"Next",
  preview_canary_target:"This is record {record} containing the canary URL. Its cell is highlighted; the URL is hidden in the preview."
});
Object.assign(translations.ja, {canary_location_title:"カナリアURLの配置", canary_location_record:"{path} — {field}列、レコード {record}", canary_location_env:"{path} — .env の {field}（本番用設定のコメント行）", canary_location_label:"{path} — {label}", canary_location_hidden:"この結果欄には配置先だけを表示しています。URL自体はダウンロードしたファイルで確認してください。", canary_location_unknown:"生成ファイル内に配置されています。詳細は運用者用インベントリを確認してください。"});
Object.assign(translations.en, {canary_location_title:"Canary URL placement", canary_location_record:"{path} — {field} column, record {record}", canary_location_env:"{path} — .env {field} (commented production setting)", canary_location_label:"{path} — {label}", canary_location_hidden:"This result shows the placement only. Open the downloaded file to inspect the URL.", canary_location_unknown:"The URL is in the generated file. See the operator inventory for its location."});
Object.assign(translations.ja, {canary_help:"動作確認：HTML形式でファイルを生成し、その中のリンクを押すと、左メニューの「カナリア接触ログ」で確認できます。", canary_note:"ファイルを読むだけでは通知されません。URLへのアクセスはスキャナーやリンクプレビューでも発生し、攻撃者や閲覧者の特定には使えません。初期URLは起動中のサンプルで共通のため、接触したファイルを区別できません。再起動後は新しいURLになります。生成器はURLへ接続しません。", canary_advanced_help:"外部の監視サービスを使う場合は、自分のアカウント用に発行されたHTTPS URLを指定します。URLに空白やフラグメント（#以降）は使えません。.env形式では$を含むURLは使えず、通常形式ではシングルクォートも使えません。"});
Object.assign(translations.en, {canary_help:"To try it: generate an HTML file, click its link, then open Canary contacts from the left menu.", canary_note:"Reading the file alone does not send an alert. Scanners and link previews may also access the URL; a request does not identify an attacker or a reader. The initial URL is shared by samples from this session, so the log cannot identify the file; a new URL is created on restart. The generator does not contact the URL.", canary_advanced_help:"For an external monitoring service, use an HTTPS URL issued for your own account. URLs cannot contain spaces or fragments (the part after #). The .env format does not accept URLs containing $, and its standard layout also rejects single quotes."});
Object.assign(translations.ja, {local_canary_browser:"ブラウザー（推定）", local_canary_os:"OS（推定）", local_canary_agent:"ブラウザー情報（User-Agent）", local_canary_language:"言語（Accept-Language）"});
Object.assign(translations.en, {local_canary_browser:"Browser (estimate)", local_canary_os:"OS (estimate)", local_canary_agent:"Browser information (User-Agent)", local_canary_language:"Language (Accept-Language)"});
Object.assign(translations.ja, {local_canary_privacy:"接続時の情報、ブラウザーが提供する画面・端末情報、許可された場合の位置情報を記録します。値は偽装・省略される場合があり、自動操作フラグだけでサンドボックスを判定できません。管理権限のある環境で利用し、閲覧を制限してください。", local_canary_client:"ブラウザーからの追加情報", local_canary_received:"受信済み", local_canary_not_received:"未受信（JavaScriptが動作しない場合など）", local_canary_location:"位置情報", local_canary_location_granted:"取得済み（端末からの申告値）", local_canary_location_denied:"許可されませんでした", local_canary_location_unavailable:"取得できませんでした", local_canary_location_timeout:"取得がタイムアウトしました", local_canary_location_unsupported:"ブラウザーが利用できません", local_canary_location_missing:"未受信（未許可・JavaScript未実行など）"});
Object.assign(translations.en, {local_canary_privacy:"Records request information, screen and device information provided by the browser, and location when permitted. Clients may omit or falsify values, and the automation flag alone cannot establish whether a sandbox is in use. Use in an environment you are authorized to manage and restrict access to the log.", local_canary_client:"Additional browser information", local_canary_received:"Received", local_canary_not_received:"Not received (for example, JavaScript did not run)", local_canary_location:"Location", local_canary_location_granted:"Received (client-reported)", local_canary_location_denied:"Permission not granted", local_canary_location_unavailable:"Location unavailable", local_canary_location_timeout:"Location request timed out", local_canary_location_unsupported:"Unavailable in this browser", local_canary_location_missing:"Not received (for example, not permitted or JavaScript did not run)"});
const canaryBrowserFields = [
  ["language", "ブラウザーの言語", "Browser language"], ["languages", "優先言語", "Preferred languages"],
  ["platform", "プラットフォーム", "Platform"], ["vendor", "ブラウザー提供元", "Browser vendor"],
  ["user_agent", "ブラウザーが報告したUser-Agent", "Browser-reported User-Agent"],
  ["plugins", "ブラウザーが公開するプラグイン", "Browser-exposed plugins"], ["mime_types", "ブラウザーが公開するMIME形式", "Browser-exposed MIME types"],
  ["do_not_track", "追跡拒否設定", "Do Not Track setting"],
  ["timezone", "タイムゾーン", "Time zone"], ["timezone_offset", "UTC−端末時刻（分）", "UTC minus local time (minutes)"],
  ["screen_width", "画面幅（CSS px）", "Screen width (CSS px)"], ["screen_height", "画面高さ（CSS px）", "Screen height (CSS px)"],
  ["screen_available_width", "利用可能な画面幅（CSS px）", "Available screen width (CSS px)"], ["screen_available_height", "利用可能な画面高さ（CSS px）", "Available screen height (CSS px)"],
  ["screen_orientation", "画面の向き", "Screen orientation"], ["viewport_width", "表示領域の幅（CSS px）", "Viewport width (CSS px)"],
  ["viewport_height", "表示領域の高さ（CSS px）", "Viewport height (CSS px)"], ["color_depth", "画面の色深度", "Screen color depth"],
  ["pixel_ratio", "画面のピクセル比", "Device pixel ratio"], ["hardware_concurrency", "利用可能な論理CPU数", "Available logical processors"],
  ["device_memory", "メモリー容量の目安（GB）", "Approximate memory (GB)"], ["max_touch_points", "同時タッチ数", "Maximum touch points"],
  ["touch_capable", "タッチ対応（推定）", "Touch support (estimate)"], ["webdriver", "ブラウザー自動操作フラグ", "Browser automation flag"],
  ["cookies_enabled", "Cookie機能の有効状態", "Cookie support enabled"], ["online", "ブラウザーのオンライン状態", "Browser online state"],
  ["pdf_viewer", "PDF表示機能", "Built-in PDF viewer"], ["global_privacy_control", "プライバシー設定（GPC）", "Global Privacy Control"],
  ["reduced_motion", "動きを減らす設定", "Reduced motion preference"], ["dark_mode", "ダークモード設定", "Dark mode preference"],
  ["connection_type", "ネットワーク種別の目安", "Estimated network type"], ["connection_downlink", "下り速度の目安（Mbps）", "Estimated downlink (Mbps)"],
  ["connection_rtt", "ネットワーク遅延の目安（ms）", "Estimated network RTT (ms)"], ["connection_save_data", "データ節約設定", "Data saving preference"],
  ["ua_brands", "ブラウザーブランド", "Browser brands"], ["ua_mobile", "モバイル端末フラグ", "Mobile device flag"],
  ["ua_platform", "クライアントヒントのOS", "Client hints platform"], ["ua_architecture", "CPUアーキテクチャ", "CPU architecture"],
  ["ua_bitness", "ビット数", "Bitness"], ["ua_model", "端末モデル", "Device model"], ["ua_platform_version", "OSバージョン", "Platform version"],
  ["ua_full_versions", "ブラウザーの詳細バージョン", "Full browser versions"], ["ua_wow64", "Windows互換実行フラグ", "Windows compatibility flag"],
  ["ua_form_factors", "端末の形態", "Device form factors"], ["webgl_vendor", "WebGL提供元", "WebGL vendor"],
  ["webgl_renderer", "WebGLレンダラー", "WebGL renderer"], ["webgl_version", "WebGLバージョン", "WebGL version"],
  ["gpu_vendor", "GPU提供元", "GPU vendor"], ["gpu_renderer", "GPUレンダラー", "GPU renderer"],
];
translations.ja.nav_canary = translations.ja.local_canary_title = "カナリアページ";
translations.en.nav_canary = translations.en.local_canary_title = "Canary page";
translations.ja.canary_help = "動作確認：HTML形式でファイルを生成し、その中のリンクを押すと、左メニューの「カナリアページ」で確認できます。";
translations.en.canary_help = "To try it: generate an HTML file, click its link, then open Canary page from the left menu.";
translations.ja.logs_scope = "このページでは既存ログの確認方法を説明します。外部ログの取り込みや自動分析は行いません。このPCの接触記録は「カナリアページ」で確認できます。";
translations.en.logs_scope = "This page explains how to review existing logs. It does not import or automatically analyze external logs. Open Canary page to see this PC's local events.";
translations.ja.canary_kit_download = "カナリアページ作製キットをダウンロード";
translations.en.canary_kit_download = "Download canary homepage kit";
translations.ja.canary_context = "サンプルの用途";
translations.en.canary_context = "Sample purpose";
translations.ja.tag_detect = "攻撃を検知";
translations.ja.tag_delay = "遅滞効果";
translations.ja.tag_leak = "流出後の攪乱";
translations.ja.tag_lure = "偽の情報へ誘導";

function t(key, values = {}) {
  const message = translations[language]?.[key] ?? translations.en[key] ?? key;
  return Object.entries(values).reduce((text, [name, value]) => text.replaceAll("{" + name + "}", String(value)), message);
}
function estimateCanaryEnvironment(environment) {
  const ua = typeof environment.user_agent === "string" ? environment.user_agent : "";
  const browsers = [[/(?:Edg|EdgiOS|EdgA)\/([\d.]+)/, "Edge"], [/OPR\/([\d.]+)/, "Opera"],
    [/Firefox\/([\d.]+)/, "Firefox"], [/FxiOS\/([\d.]+)/, "Firefox"],
    [/HeadlessChrome\/([\d.]+)/, "Headless Chrome"], [/(?:Chrome|CriOS)\/([\d.]+)/, "Chrome"],
    [/Version\/([\d.]+).*Safari\//, "Safari"]];
  let browser = "";
  for (const [pattern, name] of browsers) {
    const match = ua.match(pattern);
    if (match) { browser = `${name} ${match[1]}`; break; }
  }
  const platforms = [[/Android/i, "Android"], [/iPhone|iPad|iPod/i, "iOS/iPadOS"],
    [/Windows/i, "Windows"], [/CrOS/i, "ChromeOS"], [/Macintosh|Mac OS X/i, "macOS"], [/Linux/i, "Linux"]];
  const os = platforms.find(([pattern]) => pattern.test(ua))?.[1] || "";
  return {browser, os};
}
Object.assign(translations.ja, {local_canary_url:"現在のカナリアURL", footer:"利用許可を得た環境でご利用ください", local_canary_privacy:"接続時の情報、ブラウザーが提供する画面・端末情報、許可された場合の位置情報を記録します。値は偽装・省略される場合があり、自動操作フラグだけでサンドボックスを判定できません。利用許可を得た環境で使い、閲覧を制限してください。"});
Object.assign(translations.en, {local_canary_url:"Current canary URL", footer:"Use only in an environment where you have permission", local_canary_privacy:"Records request information, screen and device information provided by the browser, and location when permitted. Clients may omit or falsify values, and the automation flag alone cannot establish whether a sandbox is in use. Use it only where you have permission and restrict access to the log."});
translations.ja.local_canary_url = "現在のカナリアページURL";
translations.en.local_canary_url = "Current canary page URL";
translations.ja.local_canary_scope = "初期のカナリアページURLは、このPCでPhysaliaを起動している間だけ動作確認に使えます。別PCからは届きません。本番運用では、HTTPSで外部ネットワークからアクセスできる場所にカナリアページを公開し、そのURLをここに指定してください。";
translations.en.local_canary_scope = "The initial canary page URL is only for checks on this PC while Physalia is running; other PCs cannot reach it. For production use, publish a canary page at an HTTPS location reachable from external networks and enter its URL here.";
translations.ja.canary_url = "カナリアページURL";
translations.ja.canary_urls = "カナリアページURL（1行に1つ）";
translations.en.canary_url = "Canary page URL";
translations.en.canary_urls = "Canary page URLs (one per line)";
translations.ja.canary_redirect_method = "カナリアページへの誘導方法";
translations.ja.canary_redirect_text = "文書内のテキストリンク";
translations.ja.canary_redirect_button = "ボタン風リンク";
translations.ja.canary_redirect_image = "アイコン画像リンク";
translations.ja.canary_redirect_email = "メールアドレス表示（クリックでカナリアページへ）";
translations.ja.canary_redirect_next = "「次へ」ボタン";
translations.ja.canary_redirect_pagination = "ページ番号";
translations.ja.canary_redirect_fullpage = "ページ全体（どこを押しても遷移）";
translations.ja.canary_redirect_help = "表示方法を選びます。選択したリンクをクリックしたときだけアクセスします。HTMLを開いただけで自動アクセスする仕掛けはありません。ページ全体を選ぶと、ページ内のどこをクリックしても遷移します。";
translations.en.canary_redirect_method = "How to link to the canary page";
translations.en.canary_redirect_text = "Text link in the document";
translations.en.canary_redirect_button = "Button-style link";
translations.en.canary_redirect_image = "Icon image link";
translations.en.canary_redirect_email = "Email address (opens canary page)";
translations.en.canary_redirect_next = "Next button";
translations.en.canary_redirect_pagination = "Page numbers";
translations.en.canary_redirect_fullpage = "Entire page (click anywhere to open)";
translations.en.canary_redirect_help = "Choose how the link appears. It opens only when clicked; opening the HTML does not trigger an automatic request. With Entire page selected, clicking anywhere in the page opens the canary.";
const canaryEmailOption = document.createElement("option");
canaryEmailOption.value = "email";
canaryEmailOption.dataset.i18n = "canary_redirect_email";
$("#canary-link-style").insertBefore(canaryEmailOption, $("#canary-link-style [value='next']"));
translations.ja.quick_canary_label = "監視先URL（カナリアページURL・任意）";
translations.en.quick_canary_label = "Monitoring URL (canary page URL, optional)";
Object.assign(translations.ja, {
  logs_intro:"このPCの「カナリアページ」接触ログを読み、何が分かり、何は断定できないかを確認します。外部ログの分析例も後半に分けて説明します。",
  logs_scope:"「カナリアページ」には、このPCで受けた接触の詳細が表示されます。外部のWebサーバーや監視サービスのログは取り込まず、自動判定もしません。",
  logs_local_title:"カナリア接触ログで注目する項目", logs_local_intro:"記録を開き、まず概要の時刻・要求方法・IDを見てから詳細を確認します。",
  logs_local_event:"時刻・event_id・canary_id・method：いつ、どのカナリア識別子に、どの要求が届いたかを確認します。同じIDへの繰り返しや短時間の連続要求にも注目します。",
  logs_local_headers:"送信元IP・HTTPヘッダー：User-Agent、Accept-Language、Sec-Fetchなどはアクセス元の手掛かりです。値は省略・偽装されることがあり、IPだけで人物を特定できません。",
  logs_local_browser:"ブラウザー情報：JavaScriptから届いた画面・端末情報などを確認します。情報がない場合も、JavaScript無効・未対応・遮断などが考えられます。受信の有無や自動操作フラグだけで人かAIか、攻撃かどうかを判定できません。",
  logs_local_location:"位置情報：許可状態を確認し、受信時もブラウザーが報告した値として扱います。値は近似・偽装されることがあり、送信元の実所在地を証明しません。",
  logs_local_limits:"URL要求やHTTP応答、ブラウザー情報の受信は、ファイルを人が読んだ・保存した・情報を流出させた証明ではありません。メールスキャナーやリンクプレビューなど正規の自動アクセスも照合します。",
  logs_local_retention:"このPCの記録は最大500件をメモリーに保持し、アプリ終了時に消去されます。別環境の監視ログはここには取り込まれません。",
  logs_fields_title:"別環境のWebサーバーログを分析する場合", logs_example_title:"外部サーバーログのJSON Lines例",
  logs_example_note:"以下は自前のWebサーバーで記録する架空例です。「カナリアページ」の画面表示項目とは異なります。送信元IPは必要な場合だけ記録します。",
  logs_review_title:"カナリア接触ログを確認する流れ",
  logs_review_1:"接触時刻の前後に、メール保護スキャナー、リンクプレビュー、社内監視など正規の自動アクセスがないか確認します。",
  logs_review_2:"canary_idごとに時刻順で並べ、event_id、要求方法、繰り返し回数、詳細情報の有無や位置情報の状態を確認します。",
  logs_review_3:"canary_idとファイル・配置先の対応は、管理者だけが見られる別台帳で確認します。必要な場合は、自組織が管理するWebサーバーのログを時刻などで照合します。",
  logs_review_4:"URL要求・サーバー応答・JavaScript情報の受信と、人による閲覧・保存・侵害を区別します。分かった事実、推測、未確認事項を分けて記録します。",
  logs_review_5:"必要な記録をアクセス制限された場所に保全し、正規アクセスや誤検知を確認してから既存のインシデント対応手順に従います。"
});
Object.assign(translations.en, {
  logs_intro:"Review this PC's Canary page contact log to understand what it shows and what it cannot establish. Guidance for external logs is separated below.",
  logs_scope:"Canary page shows contacts received on this PC, including request details. It does not ingest logs from external web servers or monitoring services, and it does not classify events automatically.",
  logs_local_title:"What to examine in Canary contacts", logs_local_intro:"Open an event and start with its time, request method and IDs, then review the details.",
  logs_local_event:"Time, event_id, canary_id and method: identify when a request arrived and which canary ID it reached. Look for repeats or bursts against the same ID.",
  logs_local_headers:"Source IP and HTTP headers: User-Agent, Accept-Language and Sec-Fetch fields offer clues about the request. Values may be omitted or spoofed; an IP alone does not identify a person.",
  logs_local_browser:"Browser information: review screen and device details reported by JavaScript. Missing data may mean JavaScript was disabled, unsupported or blocked. Receipt or an automation flag alone cannot establish whether a person, AI or attacker was involved.",
  logs_local_location:"Location: check the permission status and treat received coordinates as browser-reported values. They may be approximate or falsified and do not prove the sender's actual location.",
  logs_local_limits:"A URL request, HTTP response or browser report does not prove that a person read or saved a file, or that data was exfiltrated. Check legitimate automated access such as mail scanners and link previews.",
  logs_local_retention:"This PC keeps up to 500 events in memory and clears them when the app stops. Logs from other environments are not imported here.",
  logs_fields_title:"For logs from a separately hosted web server", logs_example_title:"External server log example (JSON Lines)",
  logs_example_note:"Fictional example for a separately operated web server; these fields differ from the Canary page display. Record a source IP only when needed.",
  logs_review_title:"Reviewing Canary page contacts",
  logs_review_1:"Check whether legitimate automated access occurred around the contact time, such as mail security scanners, link previews or internal monitoring.",
  logs_review_2:"Sort by canary_id and time. Review event_id, request method, repeats, whether browser details arrived and the location status.",
  logs_review_3:"Use the operator-only mapping between canary_id and the file or placement. If needed, correlate by time with web-server logs your organization controls.",
  logs_review_4:"Distinguish a URL request, server response or JavaScript report from a person reading or saving a file, or data being exfiltrated. Record facts, inferences and unknowns separately.",
  logs_review_5:"Preserve necessary records in an access-controlled location, check for legitimate requests and false positives, then follow your existing incident-response process."
});
Object.assign(translations.ja, {
  intro_physalia_note_title:"余談：実在するPhysalia（カツオノエボシ）",
  intro_physalia_note_biology:"Physalia physalis（カツオノエボシ）は、クラゲのように見えますが、浮力・捕食・消化・繁殖など異なる役割を担う個虫（ズーイド）が一体として働くクダクラゲの仲間です。青紫色などの気体を含む浮き袋が海面に浮かび、帆のように風を受けます。自力で泳がず、風と潮流に運ばれます。海面下に伸びる触手は平均約10m、長いものは約30mに達することがあり、見えている浮き袋の大きさだけでは危険範囲を判断できません。",
  intro_physalia_note_hazard:"触手には獲物を捕らえる刺胞があり、触れると強い痛みや灼熱感、赤いみみず腫れや水疱が生じることがあります。吐き気、嘔吐、けいれん、呼吸困難、ショックなどの全身症状や死亡はまれですが報告されています。水中で強い痛みや驚きからパニックになれば、溺れる危険もあります。人を狙って襲う生物ではありませんが、知らずに触れると手痛い反応を受けることがあります。漂着した個体や切れた触手も、しばらく刺す力を保つことがあります。",
  intro_physalia_note_avoid:"一番の予防は触らないことです。海中や波打ち際で見つけても近づかず、拾わず、踏まないでください。漂着個体や触手だけの断片にも触れないでください。目撃情報や遊泳禁止の表示がある場所には入らず、監視員・現地当局の案内に従ってください。刺された後に呼吸困難、失神などの強い症状が出た場合は、直ちに救急要請してください。",
  intro_physalia_sources:"出典：", intro_physalia_source_jp:"環境省「自然とのふれあい活動における安全対策」"
});
Object.assign(translations.en, {
  intro_physalia_note_title:"Aside: the real Physalia (Portuguese man o’ war)",
  intro_physalia_note_biology:"Physalia physalis, called katsuono-eboshi in Japan and the Portuguese man o’ war in English, looks like a jellyfish but is a siphonophore: a colony of specialized zooids that work together, with different roles in buoyancy, prey capture, digestion and reproduction. A gas-filled float, often blue, violet or pink, rides at the surface like a sail. The colony cannot swim and drifts with wind and currents. Its tentacles hang below the surface, averaging about 10 m and sometimes reaching about 30 m, so the visible float does not show the full danger area.",
  intro_physalia_note_hazard:"The tentacles carry stinging cells used to capture prey. Contact can cause intense pain or burning, red whip-like welts and blisters. Nausea, vomiting, cramps, breathing problems, shock and death are rare but reported systemic outcomes. In the water, severe pain or panic can also lead to drowning. The animal does not hunt people, but an unaware person can suffer a painful sting on contact. Washed-up animals and detached tentacles may remain capable of stinging, even for weeks.",
  intro_physalia_note_avoid:"The best prevention is to avoid contact. Do not approach, pick up or step on one in the water or at the waterline; do not touch stranded animals or loose tentacles. Stay out of waters where one has been reported or swimming is prohibited, and follow lifeguard and local-authority advice. If a sting is followed by severe symptoms such as trouble breathing or fainting, call emergency services immediately.",
  intro_physalia_sources:"Sources:", intro_physalia_source_jp:"Japan Ministry of the Environment: Safety measures for nature activities"
});
Object.assign(translations.ja, {
  intro_physalia_biology_title:"どんな生き物か",
  intro_physalia_biology_1:"Physalia physalis（カツオノエボシ）は、クラゲのように見えますが、異なる役割を担う個虫が集まって一体として働くクダクラゲの仲間です。",
  intro_physalia_biology_2:"気体を含む青紫色などの浮き袋が海面に浮かび、帆のように風を受けます。自力で泳がず、風や潮流に運ばれます。",
  intro_physalia_biology_3:"海面下に伸びる触手は平均約10m、長いものは約30mに達することがあります。見えている浮き袋だけでは、触手の広がる範囲を判断できません。",
  intro_physalia_name_title:"なぜツール名が「Physalia」なのか",
  intro_physalia_name_reason:"「Physalia」という名には、海面に浮かぶ姿をデコイに、知らずに触れれば痛手を受け、存在を知れば避ける性質を防御の発想に重ねています。攻撃者が自ら探索する中でデコイに遭遇すれば負担を負い、その存在を知れば近寄らなくなることを期待しています。",
  intro_physalia_hazard_title:"刺傷の危険",
  intro_physalia_hazard_1:"触手の刺胞に触れると、強い痛みや灼熱感、赤いみみず腫れ、水疱が生じることがあります。",
  intro_physalia_hazard_2:"吐き気、嘔吐、けいれん、呼吸困難、ショックなどの全身症状や死亡はまれですが報告されています。水中では痛みや驚きからパニックになり、溺れる危険もあります。",
  intro_physalia_hazard_3:"人を狙って襲う生物ではありませんが、知らずに触れると手痛い反応を受けることがあります。漂着した個体や切れた触手も、しばらく刺す力を保つことがあります。",
  intro_physalia_prevention_title:"被害を受けないために",
  intro_physalia_prevention_1:"一番の予防は、触らないこと、見つかった場所に近づかないことです。",
  intro_physalia_prevention_2:"水中や波打ち際で見ても、近づかず、拾わず、踏まないでください。漂着個体や触手だけの断片にも触れないでください。",
  intro_physalia_prevention_3:"目撃情報や遊泳禁止の表示がある場所には入らず、監視員・現地当局の案内に従ってください。刺された後に呼吸困難や失神などの強い症状が出た場合は、直ちに救急要請してください。"
});
Object.assign(translations.en, {
  intro_physalia_biology_title:"What it is",
  intro_physalia_biology_1:"Physalia physalis, called katsuono-eboshi in Japan, looks like a jellyfish but is a siphonophore: specialized zooids with different roles work together as one colony.",
  intro_physalia_biology_2:"A gas-filled, often blue or violet float rests at the surface and acts like a sail. The colony cannot swim and drifts with wind and currents.",
  intro_physalia_biology_3:"Its tentacles hang below the surface, averaging about 10 m and sometimes reaching about 30 m. The visible float does not show how far the tentacles extend.",
  intro_physalia_name_title:"Why is the tool named “Physalia”?",
  intro_physalia_name_reason:"The name connects the animal’s floating form with a decoy, and its painful sting for the unwary with the defensive idea behind the tool. An intruder may encounter a decoy while exploring on their own and incur extra effort; we hope awareness of the decoys will keep them away.",
  intro_physalia_hazard_title:"Sting hazards",
  intro_physalia_hazard_1:"Contact with the stinging cells in its tentacles can cause intense pain or burning, red whip-like welts and blisters.",
  intro_physalia_hazard_2:"Nausea, vomiting, cramps, breathing problems, shock and death are rare but reported systemic outcomes. In the water, pain or panic can also lead to drowning.",
  intro_physalia_hazard_3:"It does not hunt people, but an unaware person can suffer a painful sting on contact. Washed-up animals and detached tentacles may remain capable of stinging for some time.",
  intro_physalia_prevention_title:"How to avoid being stung",
  intro_physalia_prevention_1:"The best prevention is to avoid contact and stay away from places where one has been seen.",
  intro_physalia_prevention_2:"If you see one in the water or at the waterline, do not approach, pick it up or step on it. Do not touch stranded animals or loose tentacles.",
  intro_physalia_prevention_3:"Stay out of waters where one has been reported or swimming is prohibited, and follow lifeguard and local-authority advice. If a sting is followed by severe symptoms such as trouble breathing or fainting, call emergency services immediately."
});
let localCanaryRenderSignature = "";
async function refreshLocalCanaryEvents() {
  if (document.hidden || activeWorkspacePage !== "canary") return;
  try {
    const response = await fetch("/api/local-canary-events", {headers:{"X-ADG-Token": $('meta[name="adg-token"]').content, "X-ADG-Language": language}, cache:"no-store"});
    if (!response.ok) return;
    const events = (await response.json()).events || [];
    const signature = JSON.stringify([language, events]);
    if (signature === localCanaryRenderSignature) return;
    localCanaryRenderSignature = signature;
    const list = $("#local-canary-events");
    const expanded = new Set([...list.querySelectorAll("details[open]")].map(el => el.dataset.eventId));
    list.replaceChildren();
    if (!events.length) {
      const empty = document.createElement("li");
      empty.textContent = t("local_canary_empty");
      list.append(empty);
      return;
    }
    const fields = [["source_ip", t("local_canary_ip")], ["http_version", "HTTP"],
      ["user_agent", t("local_canary_agent")], ["accept_language", t("local_canary_language")],
      ["accept", "Accept"], ["accept_encoding", "Accept-Encoding"],
      ["client_hints_ua", "Sec-CH-UA"], ["client_hints_platform", "Sec-CH-UA-Platform"],
      ["client_hints_mobile", "Sec-CH-UA-Mobile"], ["client_hints_arch", "Sec-CH-UA-Arch"],
      ["client_hints_bitness", "Sec-CH-UA-Bitness"], ["client_hints_model", "Sec-CH-UA-Model"],
      ["client_hints_platform_version", "Sec-CH-UA-Platform-Version"],
      ["client_hints_full_version", "Sec-CH-UA-Full-Version-List"], ["fetch_site", "Sec-Fetch-Site"],
      ["fetch_mode", "Sec-Fetch-Mode"], ["fetch_dest", "Sec-Fetch-Dest"]];
    for (const [index, item] of events.entries()) {
      const row = document.createElement("li");
      const details = document.createElement("details");
      details.dataset.eventId = String(item.event_id);
      details.open = expanded.has(details.dataset.eventId) || (index === 0 && !expanded.size);
      const summary = document.createElement("summary");
      summary.textContent = t("local_canary_record", item);
      details.append(summary);
      const listOfFields = document.createElement("dl");
      const environment = item.environment || {};
      const estimates = estimateCanaryEnvironment(environment);
      for (const [label, value] of [[t("local_canary_browser"), estimates.browser], [t("local_canary_os"), estimates.os]]) {
        if (!value) continue;
        const term = document.createElement("dt"), description = document.createElement("dd");
        term.textContent = label;
        description.textContent = value;
        listOfFields.append(term, description);
      }
      for (const [key, label] of fields) {
        const value = environment[key];
        if (typeof value !== "string" || !value) continue;
        const term = document.createElement("dt"), description = document.createElement("dd");
        term.textContent = label;
        description.textContent = value;
        listOfFields.append(term, description);
      }
      const browserEnvironment = item.browser_environment;
      const hasBrowserEnvironment = browserEnvironment && typeof browserEnvironment === "object";
      const browserTerm = document.createElement("dt"), browserStatus = document.createElement("dd");
      browserTerm.textContent = t("local_canary_client");
      browserStatus.textContent = t(hasBrowserEnvironment ? "local_canary_received" : "local_canary_not_received");
      listOfFields.append(browserTerm, browserStatus);
      if (hasBrowserEnvironment) for (const [key, labelJa, labelEn] of canaryBrowserFields) {
        const value = browserEnvironment[key];
        if (!["string", "number", "boolean"].includes(typeof value) || value === "") continue;
        const term = document.createElement("dt"), description = document.createElement("dd");
        term.textContent = language === "ja" ? labelJa : labelEn;
        description.textContent = typeof value === "boolean"
          ? (language === "ja" ? (value ? "はい" : "いいえ") : (value ? "Yes" : "No")) : String(value);
        listOfFields.append(term, description);
      }
      const location = item.location;
      const locationStates = ["granted", "denied", "unavailable", "timeout", "unsupported"];
      const locationState = location && locationStates.includes(location.status) ? location.status : "missing";
      const locationTerm = document.createElement("dt"), locationStatus = document.createElement("dd");
      locationTerm.textContent = t("local_canary_location");
      locationStatus.textContent = t("local_canary_location_" + locationState);
      listOfFields.append(locationTerm, locationStatus);
      if (locationState === "granted") {
        const locationFields = [["latitude", "緯度", "Latitude"], ["longitude", "経度", "Longitude"],
          ["accuracy", "水平精度（m）", "Horizontal accuracy (m)"], ["altitude", "高度（m）", "Altitude (m)"],
          ["altitude_accuracy", "高度の精度（m）", "Altitude accuracy (m)"], ["heading", "方位（度）", "Heading (degrees)"],
          ["speed", "速度（m/s）", "Speed (m/s)"], ["timestamp", "位置の取得時刻（UTC）", "Location timestamp (UTC)"]];
        for (const [key, labelJa, labelEn] of locationFields) {
          const value = location[key];
          if (typeof value !== "number" || !Number.isFinite(value)) continue;
          const term = document.createElement("dt"), description = document.createElement("dd");
          term.textContent = language === "ja" ? labelJa : labelEn;
          description.textContent = key === "timestamp" ? new Date(value).toISOString() : String(value);
          listOfFields.append(term, description);
        }
      }
      details.append(listOfFields);
      row.append(details);
      list.append(row);
    }
  } catch { /* The generator may be shutting down. */ }
}
window.setInterval(refreshLocalCanaryEvents, 3000);
function localize(root) {
  root.querySelectorAll("[data-i18n]").forEach(element => { element.textContent = t(element.dataset.i18n); });
  root.querySelectorAll("[data-i18n-emphasis]").forEach(element => {
    const message = t(element.dataset.i18nEmphasis);
    const content = document.createDocumentFragment();
    let cursor = 0;
    for (const match of message.matchAll(/\*\*(.+?)\*\*/g)) {
      content.append(document.createTextNode(message.slice(cursor, match.index)));
      const strong = document.createElement("strong");
      strong.textContent = match[1];
      content.append(strong);
      cursor = match.index + match[0].length;
    }
    content.append(document.createTextNode(message.slice(cursor)));
    element.replaceChildren(content);
  });
  root.querySelectorAll("[data-i18n-aria]").forEach(element => { element.setAttribute("aria-label", t(element.dataset.i18nAria)); });
  root.querySelectorAll("[data-i18n-placeholder]").forEach(element => { element.setAttribute("placeholder", t(element.dataset.i18nPlaceholder)); });
}
function estimate() {
  const layers = Number($("#layers").value), branches = Number($("#branches").value), decoys = Number($("#decoys").value);
  const valid = Number.isInteger(layers) && layers >= 1 && layers <= 8 && Number.isInteger(branches) && branches >= 1 && branches <= 3;
  const archives = valid ? Array.from({length: layers}, (_, n) => branches ** n).reduce((a, b) => a + b, 0) : 0;
  $("#nest-estimate").textContent = valid ? t("estimate", {archives, documents: archives * decoys}) + (archives > 40 ? " " + t("over_limit") : "") : t("over_limit");
}
function updateEncodingEstimate() {
  const layers = Number($("#encoding-layers").value), candidates = Number($("#encoding-candidates").value);
  const operations = layers * candidates;
  $("#encoding-estimate").textContent = t("encoding_estimate", {operations, candidates, layers});
}
for (const selector of ["#encoding-layers", "#encoding-candidates"]) {
  $(selector).addEventListener("input", updateEncodingEstimate);
  $(selector).addEventListener("change", updateEncodingEstimate);
}
function updateMazeEstimate() {
  const depth = Number($("#maze-depth").value), branches = Number($("#maze-branches").value);
  const files = Number($("#maze-files").value);
  const valid = Number.isInteger(depth) && depth >= 1 && depth <= 6
    && Number.isInteger(branches) && branches >= 1 && branches <= 5
    && Number.isInteger(files) && files >= 1 && files <= 3;
  let directories = 0;
  if (valid) for (let level = 0; level <= depth; level++) directories += branches ** level;
  const documents = valid ? directories * files : 0;
  const overLimit = !valid || directories > 400;
  const estimate = $("#maze-estimate");
  estimate.textContent = valid ? t("maze_estimate", {directories, documents})
    + (directories > 400 ? " " + t("maze_over_limit") : "") : t("number_input_invalid");
  estimate.dataset.overLimit = String(overLimit);
}
for (const selector of ["#maze-depth", "#maze-branches", "#maze-files"]) {
  $(selector).addEventListener("input", updateMazeEstimate);
  $(selector).addEventListener("change", updateMazeEstimate);
}
function applyLanguage() {
  document.documentElement.lang = language;
  languageSelect.value = language;
  $("#intro-quick-guide").href = "/quickstart/" + language;
  $("#intro-log-guide").href = "/log-guide/" + language;
  $("#log-guide-full").href = "/log-guide/" + language;
  $("#downloads").setAttribute("aria-label", language === "ja" ? "生成ファイル" : "Generated files");
  const currentTranslations = translations[language] || {};
  for (const [key, value] of Object.entries(currentTranslations)) {
    if (typeof value !== "string") continue;
    currentTranslations[key] = language === "ja"
      ? value.replaceAll("カナリアURL", "カナリアページURL")
      : value.replace(/\bCanary URL(s?)\b/g, (_, plural) => `Canary page URL${plural}`)
        .replace(/\bcanary URL(s?)\b/g, (_, plural) => `canary page URL${plural}`);
  }
  localize(document);
  updateMethodFilter(activeFitFilter);
  updateWebTitlePlaceholder();
  updateScenarioSchemaSummaries();
  updateEncodingEstimate();
  updateEnvTemplate();
  if (databaseTemplates.length) renderDatabaseTemplates();
  if (databaseTemplates.length) loadDatabaseTemplates();
  updateExplanation();
  estimate();
  updateMazeEstimate();
  updateCanaryUrlWarning();
  updateCsvSafetyNote();
  result.textContent = "";
  if (generatedAsset) renderDownloads(generatedAsset);
}
function updateWebTitlePlaceholder() {
  const selected = $("#web-scenario").selectedOptions[0];
  $("#title").placeholder = selected?.textContent || t("default_page_title");
}
$("#web-scenario").addEventListener("change", updateWebTitlePlaceholder);
languageSelect.addEventListener("change", () => {
  language = languageSelect.value;
  try { localStorage.setItem("adg-language", language); } catch (_) { /* Continue without persistence. */ }
  applyLanguage();
});
function showWorkspacePage(page, focus = true) {
  if (!["intro", "generator", "canary", "logs", "license"].includes(page)) page = "intro";
  activeWorkspacePage = page;
  document.querySelectorAll(".workspace-page").forEach(section => {
    section.hidden = section.id !== "page-" + page;
  });
  document.querySelectorAll("[data-page-target]").forEach(control => {
    if (control.dataset.pageTarget === page) control.setAttribute("aria-current", "page");
    else control.removeAttribute("aria-current");
  });
  if (page === "canary") refreshLocalCanaryEvents();
  if (focus) {
    $("#main-content").scrollTop = 0;
    const heading = $("#page-" + page + " h1");
    if (heading) { heading.setAttribute("tabindex", "-1"); heading.focus(); }
  }
}

function addColumn(name = "field_" + (document.querySelectorAll(".column-row").length + 1), kind = "text") {
  if (document.querySelectorAll(".column-row").length >= 30) { result.textContent = t("schema_limit"); return; }
  const fragment = $("#column-template").content.cloneNode(true), row = fragment.querySelector(".column-row");
  const nameInput = row.querySelector(".column-name");
  const sourceTemplate = databaseTemplates.find(item => item.id === $("#database-template").value);
  const sourceColumn = sourceTemplate?.columns.find(column => column.name === name);
  row.dataset.templateId = sourceColumn ? sourceTemplate.id : "";
  row.dataset.templateColumn = sourceColumn?.name || "";
  nameInput.addEventListener("input", () => updateColumnFriendlyName(row));
  row.querySelector(".column-name").value = name;
  row.querySelector(".column-kind").value = kind;
  function updateOptions() {
    const current = row.querySelector(".column-kind").value;
    const options = row.querySelector(".column-options");
    const fieldName = row.querySelector(".column-name").value.trim().toLowerCase();
    options.disabled = !["integer", "decimal", "text", "status", "company", "department"].includes(current);
    options.placeholder = ["integer", "decimal"].includes(current)
      ? (fieldName === "quantity" ? "1,100" : fieldName === "unit_price" ? "25,2500" : "0,100000")
      : "active|pending|archived";
  }
  row.querySelector(".column-kind").addEventListener("change", () => {
    clearInvalid(row.querySelector(".column-options"));
    updateOptions();
  });
  row.querySelector(".column-name").addEventListener("input", event => {
    clearInvalid(event.currentTarget);
    updateOptions();
  });
  row.querySelector(".column-options").addEventListener("input", event => clearInvalid(event.currentTarget));
  row.querySelector(".remove-column").addEventListener("click", () => {
    row.remove();
    markDatabaseCustom();
  });
  updateOptions();
  updateColumnFriendlyName(row);
  localize(row);
  $("#columns").append(fragment);
}
function updateColumnFriendlyName(row) {
  const template = databaseTemplates.find(item => item.id === row.dataset.templateId);
  const column = template?.columns.find(item => item.name === row.dataset.templateColumn);
  const matches = row.querySelector(".column-name").value.trim() === row.dataset.templateColumn;
  row.querySelector(".column-friendly-name").textContent = matches && column?.label ? column.label : "";
}
function refreshColumnFriendlyNames() {
  document.querySelectorAll(".column-row").forEach(updateColumnFriendlyName);
}
$("#add-column").addEventListener("click", () => {
  const previousCount = document.querySelectorAll(".column-row").length;
  addColumn();
  if (document.querySelectorAll(".column-row").length !== previousCount) markDatabaseCustom();
});
for (const [name, kind] of [["id", "id"], ["name", "name"], ["email", "email"], ["company", "company"],
  ["phone", "phone"], ["department", "department"], ["status", "status"], ["last_contact", "date"]]) addColumn(name, kind);
function updateCsvSafetyNote() {
  const kind = $('input[name="kind"]:checked')?.value;
  const selector = {env: "#canary-format", nest: "#nest-format", directory_maze: "#maze-format", encoding_maze: "#encoding-format"}[kind];
  const csvSelected = selector && $(selector).value === "csv";
  const csvMayBeMixedIntoNest = kind === "nest" && $("#nest-varied-formats").checked;
  $("#csv-safety-note").hidden = !csvSelected && !csvMayBeMixedIntoNest;
}
function updateFields(forceClear = false) {
  const selected = $('input[name="kind"]:checked').value;
  const changed = selected !== activeKind;
  updateExplanation();
  for (const kind of ["env", "nest", "database", "web", "fake_trap", "ransomware_tripwire", "path_maze", "sparse_decoy", "data_dilution", "honeyword", "stream", "directory_maze", "encoding_maze"]) {
    const fields = $("#" + kind + "-fields");
    fields.hidden = kind !== selected;
    fields.querySelectorAll("input, select, button, textarea").forEach(input => {
      input.disabled = kind !== selected;
      if (kind !== selected) clearInvalid(input);
    });
  }
  const infoOnly = ["data_dilution", "honeyword"].includes(selected);
  $("#canary-method-notes").hidden = selected !== "env";
  button.hidden = infoOnly;
  $("#sample-settings-heading").hidden = infoOnly;
  if (selected === "database") {
    document.querySelectorAll(".column-kind").forEach(input => input.dispatchEvent(new Event("change")));
  }
  updateVaultDomainFields();
  updateEnvTemplate();
  updateCanaryUrlWarning();
  updateCsvSafetyNote();
  result.textContent = "";
  if (changed || forceClear) {
    activeKind = selected;
    clearDownloads();
  }
  return true;
}
function updateVaultDomainFields() {
  const kind = $('input[name="kind"]:checked')?.value;
  const use = (kind === "database" && $("#database-template").value === "passwords")
    || (kind === "nest" && $("#nest-scenario").value === "passwords" && ($("#nest-format").value !== "env" || $("#nest-varied-formats").checked))
    || (kind === "directory_maze" && $("#maze-scenario").value === "passwords" && $("#maze-format").value !== "env")
    || (kind === "encoding_maze" && $("#encoding-scenario").value === "passwords" && $("#encoding-format").value !== "env");
  const panel = $("#vault-domain-fields");
  panel.hidden = !use;
  panel.querySelectorAll("input").forEach(input => { input.disabled = !use; });
}
function vaultDomainSettings() {
  return {vault_domain: $("#vault-domain").value.trim(), vault_domain_authorized: $("#vault-domain-authorized").checked};
}
for (const selector of ["#database-template", "#nest-scenario", "#maze-scenario", "#encoding-scenario", "#nest-format", "#nest-varied-formats", "#maze-format", "#encoding-format"]) {
  $(selector).addEventListener("change", () => { updateVaultDomainFields(); updateCsvSafetyNote(); });
}
const nestDirectoryPresets = {
  crm: ["finance", "operations", "exports", "backups", "archive", "config", "reports"],
  migration: ["migration", "source", "staging", "imports", "batches", "review", "exports"],
  archive: ["archive", "retention", "snapshots", "monthly", "history", "manifests", "exports"],
  cards: ["payments", "cardholders", "billing", "renewals", "reconciliation", "expiry", "reports"],
  companies: ["organizations", "companies", "contacts", "ownership", "industries", "relationships", "exports"],
  passwords: ["vault", "credentials", "services", "recovery", "rotation", "access", "archive"],
  api_credentials: ["api", "integrations", "credentials", "clients", "tokens", "services", "rotation"],
  invoices: ["finance", "billing", "receivables", "payments", "overdue", "reconciliation", "statements"],
  employees: ["hr", "personnel", "departments", "payroll", "onboarding", "roles", "reviews"],
  vendors: ["procurement", "suppliers", "contracts", "reviews", "due_diligence", "services", "finance"],
  orders: ["sales", "orders", "fulfillment", "shipments", "returns", "billing", "reconciliation"],
  tickets: ["support", "cases", "queue", "escalations", "resolution", "customers", "reports"],
  assets: ["assets", "hardware", "endpoints", "licenses", "facilities", "lifecycle", "assignments"],
  cloud: ["platform", "subscriptions", "identity", "storage", "deployments", "regions", "recovery"]
};
const scenarioTemplateAliases = {crm: "customers", migration: "customers", archive: "customers"};
function updateScenarioSchemaSummaries() {
  const ready = databaseTemplatesLanguage === language;
  for (const [selectId, summaryId] of [["nest-scenario", "nest-scenario-schema"],
    ["maze-scenario", "maze-scenario-schema"], ["encoding-scenario", "encoding-scenario-schema"]]) {
    const output = $("#" + summaryId);
    const scenario = $("#" + selectId).value;
    const templateId = scenarioTemplateAliases[scenario] || scenario;
    const template = ready ? databaseTemplates.find(item => item.id === templateId) : null;
    if (!template) { output.hidden = true; continue; }
    const fields = template.columns.slice(0, 6).map(column => column.label || column.name).join(language === "ja" ? "\u3001" : ", ");
    const remaining = Math.max(0, template.columns.length - 6);
    output.textContent = t("scenario_schema_summary", {name: template.label, fields,
      more: remaining ? t("scenario_schema_more", {count: remaining}) : ""});
    output.hidden = false;
  }
}
for (const selector of ["#nest-scenario", "#maze-scenario", "#encoding-scenario"]) {
  $(selector).addEventListener("change", updateScenarioSchemaSummaries);
}
let activeNestDirectoryScenario = $("#nest-scenario").value;
$("#nest-scenario").addEventListener("change", () => {
  const directories = $("#directories");
  const previousPreset = nestDirectoryPresets[activeNestDirectoryScenario];
  const nextPreset = nestDirectoryPresets[$("#nest-scenario").value];
  if (previousPreset && nextPreset
      && directories.value.split(",").map(value => value.trim()).join(",") === previousPreset.join(",")) {
    directories.value = nextPreset.join(",");
  }
  activeNestDirectoryScenario = $("#nest-scenario").value;
});
const previewUrlFields = {
  env: ["#env-url"], nest: ["#nest-url"], database: ["#db-url"], web: ["#web-url"],
  directory_maze: ["#maze-url"], encoding_maze: ["#encoding-url"],
};
const previewUrlRedactions = new WeakMap();
const monitoringUrlFields = {
  env: ["#env-url"], nest: ["#nest-url"], database: ["#db-url"], web: ["#web-url"],
  directory_maze: ["#maze-url"], encoding_maze: ["#encoding-url"],
};
function hasReservedCanaryUrl(value) {
  const reservedSuffixes = ["invalid", "example", "test"];
  const reservedExamples = ["example.com", "example.net", "example.org"];
  return value.split(/\r?\n/).some(line => {
    try {
      const host = new URL(line.trim()).hostname.toLowerCase().replace(/\.$/, "");
      return reservedSuffixes.some(suffix => host.endsWith("." + suffix))
        || reservedExamples.some(name => host === name || host.endsWith("." + name));
    } catch (_) { return false; }
  });
}
function updateCanaryUrlWarning() {
  const warning = $("#canary-url-warning");
  const selected = $('input[name="kind"]:checked')?.value;
  const selectors = monitoringUrlFields[selected] || [];
  const hasReserved = selectors.some(selector => hasReservedCanaryUrl($(selector).value));
  warning.hidden = !hasReserved;
  warning.textContent = hasReserved ? t("monitoring_placeholder") : "";
}
for (const selector of Object.values(monitoringUrlFields).flat()) {
  $(selector).addEventListener("input", updateCanaryUrlWarning);
}
document.querySelectorAll('input[name="kind"]').forEach(input => input.addEventListener("change", () => updateFields()));
let activeFitFilter = "all";
function updateMethodFilter(filter = activeFitFilter) {
  const cards = [...document.querySelectorAll(".cards .card[data-fit]")];
  const matching = cards.filter(card => filter === "all" || card.dataset.fit.split(/\s+/).includes(filter));
  const selected = $('input[name="kind"]:checked');
  if (matching.length && !matching.some(card => card.contains(selected))) {
    matching[0].querySelector('input[name="kind"]').checked = true;
    if (!updateFields()) return false;
  }
  activeFitFilter = filter;
  document.querySelectorAll(".method-filter").forEach(button => {
    button.setAttribute("aria-pressed", String(button.dataset.fitFilter === filter));
  });
  cards.forEach(card => { card.hidden = !matching.includes(card); });
  $("#method-result-count").textContent = t("fit_result_count", {count: matching.length});
  return true;
}
document.querySelectorAll(".method-filter").forEach(button => button.addEventListener("click", () => updateMethodFilter(button.dataset.fitFilter)));
document.querySelectorAll('input[name="kind"]').forEach(input => input.addEventListener("change", () => {
  requestAnimationFrame(() => $("#method-explanation").scrollIntoView({behavior:"smooth", block:"start"}));
}));
document.querySelectorAll('#generator input[type="number"]').forEach(input => input.addEventListener("input", () => {
  if (input.checkValidity()) {
    clearInvalid(input);
    result.textContent = "";
  }
}));
function updateEnvTemplate() {
  const isCanary = $('input[name="kind"]:checked').value === "env";
  const selectedFormat = $("#canary-format").value;
  const linkStyleEnabled = isCanary && selectedFormat === "html";
  $("#canary-link-style-field").hidden = !linkStyleEnabled;
  $("#canary-link-style").disabled = !linkStyleEnabled;
  const contextUnused = isCanary && selectedFormat === "env";
  $("#canary-context-field").hidden = contextUnused;
  $("#canary-context").disabled = !isCanary || contextUnused;
}
$("#canary-format").addEventListener("change", () => {
  updateEnvTemplate();
  updateCsvSafetyNote();
});
async function loadDatabaseTemplates() {
  const requestedLanguage = language;
  try {
    const response = await fetch("/api/database-templates", {headers: {"X-ADG-Language": requestedLanguage}});
    if (!response.ok) throw new Error();
    const data = await response.json();
    if (!Array.isArray(data.templates) || data.templates.length === 0
        || data.templates.some(item => !item || typeof item.id !== "string"
          || typeof item.label !== "string" || typeof item.description !== "string"
          || typeof item.table !== "string" || !Array.isArray(item.columns))) throw new Error();
    if (language !== requestedLanguage) return loadDatabaseTemplates();
    databaseTemplates = data.templates;
    databaseTemplatesLanguage = requestedLanguage;
    updateScenarioSchemaSummaries();
    const select = $("#database-template");
    renderDatabaseTemplates();
    if (select.value !== "custom") applyDatabaseTemplate(select.value);
    refreshColumnFriendlyNames();
    if (select.dataset.handler !== "true") {
      select.addEventListener("change", () => {
        if (select.value === "custom") {
          $("#database-schema-details").open = true;
          markDatabaseCustom();
          return;
        }
        if (select.dataset.selected === "custom" && $("#columns").children.length
            && !window.confirm(t("template_replace_confirm"))) {
          select.value = "custom";
          $("#template-description").textContent = t("template_help");
          return;
        }
        applyDatabaseTemplate(select.value);
      });
      select.dataset.handler = "true";
    }
    select.dataset.ready = "true";
    if (generatedAsset) renderDownloads(generatedAsset);
  } catch (_) {
    if (language !== requestedLanguage) return loadDatabaseTemplates();
    $("#template-description").textContent = t("template_loading");
  }
}
function renderDatabaseTemplates() {
  const select = $("#database-template"), current = select.dataset.selected || select.value || "customers";
  select.replaceChildren(new Option(t("template_custom"), "custom"));
  for (const template of databaseTemplates) select.add(new Option(template.label, template.id));
  select.value = current === "custom" || databaseTemplates.some(item => item.id === current)
    ? current : "customers";
  select.dataset.selected = select.value;
  const template = databaseTemplates.find(item => item.id === select.value);
  if (template && !$("#columns").children.length) applyDatabaseTemplate(template.id);
  else if (select.value === "custom") $("#template-description").textContent = t("template_help");
  else if (template) $("#template-description").textContent = template.description;
}
function applyDatabaseTemplate(id) {
  const template = databaseTemplates.find(item => item.id === id);
  if (!template) return;
  $("#database-template").value = id;
  $("#database-template").dataset.selected = id;
  $("#table-name").value = template.table;
  $("#template-description").textContent = template.description;
  $("#columns").replaceChildren();
  for (const column of template.columns) {
    addColumn(column.name, column.kind);
    const options = $("#columns").lastElementChild.querySelector(".column-options");
    if (column.values) options.value = column.values.join("|");
    else if (["integer", "decimal"].includes(column.kind)) options.value = `${column.min ?? 0},${column.max ?? 100000}`;
  }
}
function markDatabaseCustom() {
  $("#database-template").value = "custom";
  $("#database-template").dataset.selected = "custom";
  $("#template-description").textContent = t("template_help");
}
$("#columns").addEventListener("input", markDatabaseCustom);
$("#columns").addEventListener("change", markDatabaseCustom);
$("#table-name").addEventListener("input", markDatabaseCustom);
// A compact illustration accompanies each method without loading external assets.
const illustrationIcons = {
  file:["M6 2.5h8l4 4V21H6z", "M14 2.5v4h4", "M8.5 11h7M8.5 14h7M8.5 17h4"],
  files:["M7 5h9l3 3v12H7z", "M16 5v3h3", "M4 16V3h9", "M9.5 12h7M9.5 15h7"],
  person:["M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z", "M4.5 21v-1.5c0-3 3.4-5.5 7.5-5.5s7.5 2.5 7.5 5.5V21"],
  search:["M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13z", "m15.5 15.5 5 5"],
  link:["M10 14a4.5 4.5 0 0 0 6.4 0l2.1-2.1a4.5 4.5 0 0 0-6.4-6.4L11 6.6", "M14 10a4.5 4.5 0 0 0-6.4 0l-2.1 2.1a4.5 4.5 0 0 0 6.4 6.4l1.1-1.1"],
  bell:["M6.5 17.5h11l-1.5-2v-4a4 4 0 0 0-8 0v4z", "M10 19.5a2 2 0 0 0 4 0"],
  database:["M4 6c0-2 3.6-3 8-3s8 1 8 3-3.6 3-8 3-8-1-8-3z", "M4 6v12c0 2 3.6 3 8 3s8-1 8-3V6", "M4 12c0 2 3.6 3 8 3s8-1 8-3"],
  browser:["M3 5h18v14H3z", "M3 9h18M6 7h.1M8 7h.1", "M6 12h5M6 15h10"],
  warning:["M12 3 2.5 20h19z", "M12 9v5M12 17h.1"],
  lock:["M6 10h12v10H6z", "M8.5 10V7a3.5 3.5 0 0 1 7 0v3", "M12 14v2.5"],
  folders:["M3 6h7l2 2h9v11H3z", "M6 12h12M6 15h8"],
  clock:["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z", "M12 7v5l3 2"],
  refresh:["M20 8a8 8 0 0 0-14-2L4 8", "M4 4v4h4", "M4 16a8 8 0 0 0 14 2l2-2", "M20 20v-4h-4"],
  key:["M8 14a4.5 4.5 0 1 1 3.9-6.7L21 7v3h-2v2h-3l-2.5 2.5A4.5 4.5 0 0 1 8 14z", "M7 9.5h.1"],
  blocks:["M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z"],
  filter:["M4 5h16l-6.5 7.5V19l-3 1v-7.5z"],
  download:["M12 3v11m-4-4 4 4 4-4", "M4 17v3h16v-3"],
  large:["M5 3h10l4 4v14H5z", "M15 3v4h4", "M8 13h8M8 17h8", "M10 9h4"],
  code:["m8 7-5 5 5 5M16 7l5 5-5 5M14 4l-4 16"],
};
const illustrationStages = {
  env:["file","link","bell"], database:["database","download","search"], web:["person","browser","files"],
  fake_trap:["person","warning","search"], nest:["files","lock","search"], stream:["person","download","clock"],
  directory_maze:["search","folders","files"], encoding_maze:["files","code","search"],
  data_dilution:["database","blocks","filter"], honeyword:["key","filter","browser"],
  ransomware_tripwire:["file","refresh","files"], path_maze:["folders","files","search"], sparse_decoy:["large","lock","clock"],
};
const illustrationLabels = {
  ja:{
    env:["架空ファイル","URLへアクセス","監視先で接触を確認"], database:["架空データベース","持ち出し","真偽を確認"],
    web:["攻撃者が探索","偽のポータル","架空文書へ誘導"], fake_trap:["攻撃者が接触","警告・待機画面","再確認を促す"],
    nest:["複数の候補","暗号化ZIP","解凍・内容確認"], stream:["攻撃者が取得","配信が続く","取得に時間を使う"],
    directory_maze:["攻撃者が探索","分かれた経路","候補の確認"], encoding_maze:["変換された候補","形式を復元","内容を選別"],
    data_dilution:["本物と架空データ","混在して流出","本物を選別"], honeyword:["偽パスワード","登録済みと一致","隔離セッション"],
    ransomware_tripwire:["架空ファイル","変更・削除","架空ファイルを補充"], path_maze:["有限のフォルダー","架空ファイル","探索・処理"],
    sparse_decoy:["大きく見えるファイル","全体を暗号化する場合","処理の仕事が増える"],
  },
  en:{
    env:["Fictional file","URL requested","Review at monitor"], database:["Decoy database","Data taken","Check authenticity"],
    web:["Attacker explores","Decoy portal","Fictional documents"], fake_trap:["Attacker arrives","Warning or wait screen","Prompt reconsideration"],
    nest:["Multiple candidates","Encrypted ZIPs","Unlock and inspect"], stream:["Attacker downloads","Stream continues","Time spent waiting"],
    directory_maze:["Attacker explores","Branching paths","Inspect candidates"], encoding_maze:["Encoded candidates","Decode formats","Inspect contents"],
    data_dilution:["Real and fictional data","Mixed data leaks","Select real records"], honeyword:["Decoy password","Registered match","Isolated session"],
    ransomware_tripwire:["Synthetic file","Change or deletion","New decoy created"], path_maze:["Finite folders","Synthetic files","Explore and process"],
    sparse_decoy:["Large logical file","If fully encrypted","Extra processing"],
  },
};
const methodExplanationImages = {
  env:"01-0001_canary_file", nest:"01-0002_encrypted_deep_nest", database:"01-0003_decoy_database",
  web:"01-0004_static_decoy_portal", fake_trap:"01-0005_fake_trap", ransomware_tripwire:"01-0006_ransomware_decoy_flood",
  path_maze:"01-0007_path_maze", sparse_decoy:"01-0008_sparse_decoy", data_dilution:"01-0009_data_dilution",
  honeyword:"01-0010_privilege_honeyword_session",
  stream:"01-0011_infinite_stream", directory_maze:"01-0012_directory_maze", encoding_maze:"01-0013_encoding_maze",
};
function renderMethodExplanationImage(kind) {
  const image = $("#method-explanation-image");
  const prefix = methodExplanationImages[kind];
  image.hidden = !prefix;
  if (!prefix) { image.removeAttribute("src"); image.alt = ""; return; }
  image.src = `/images/${prefix}_${language}.jpg`;
  const title = methodExplanations[language]?.[kind]?.title || methodExplanations.en?.[kind]?.title || kind;
  image.alt = language === "ja" ? `${title}の説明画像` : `Diagram explaining ${title}`;
}
function renderMethodIllustration(kind) {
  const container = $("#method-illustration");
  const icons = illustrationStages[kind];
  const labels = illustrationLabels[language]?.[kind] || illustrationLabels.en[kind];
  container.replaceChildren();
  if (!icons || !labels) { container.hidden = true; return; }
  container.hidden = false;
  container.setAttribute("aria-label", labels.join(language === "ja" ? " → " : " to "));
  const ns = "http://www.w3.org/2000/svg";
  icons.forEach((name, index) => {
    const stage = document.createElement("div");
    stage.className = "method-illustration-stage";
    const visual = document.createElement("div");
    visual.className = "method-illustration-icon";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    for (const d of illustrationIcons[name]) {
      const path = document.createElementNS(ns, "path");
      path.setAttribute("d", d);
      svg.append(path);
    }
    visual.append(svg);
    const label = document.createElement("span");
    label.className = "method-illustration-label";
    label.textContent = labels[index];
    stage.append(visual, label);
    container.append(stage);
  });
}
function updateExplanation() {
  const selected = document.querySelector('input[name="kind"]:checked')?.value || "env";
  const item = methodExplanations[language]?.[selected] || methodExplanations.en?.[selected] || methodExplanations.ja?.[selected];
  if (!item) {
    renderMethodExplanationImage("");
    const fallback = language === "ja" ? "この手法の説明を読み込めませんでした。ページを再読み込みしてください。" : "The explanation for this method could not be loaded. Reload the page.";
    $("#method-explanation-title").textContent = selected;
    for (const id of ["method-flow-scenario", "method-flow-context", "method-flow-if", "method-flow-else", "method-flow-response", "method-flow-note", "explain-how", "explain-target", "explain-deception", "explain-delay", "explain-limit", "legal-normal", "legal-risk", "legal-other", "legal-us-normal", "legal-us-risk"]) $("#" + id).textContent = fallback;
    $("#method-flow-steps").replaceChildren();
    return;
  }
  const flow = methodFlows[language]?.[selected] || methodFlows.en?.[selected] || methodFlows.ja?.[selected];
  renderMethodExplanationImage(selected);
  const outcomes = methodOutcomes[language]?.[selected] || methodOutcomes.en?.[selected] || methodOutcomes.ja?.[selected];
  const legal = methodLegal[language]?.[selected] || methodLegal.en?.[selected] || methodLegal.ja?.[selected];
  const us = usLegal[language]?.[selected] || usLegal.en?.[selected] || usLegal.ja?.[selected];
  const readableText = value => {
    const text = String(value || "").trim();
    if (language === "ja") return text.replace(/。\s*/g, "。\n");
    return text.replace(/([.!?])\s+(?=[A-Z])/g, "$1\n");
  };
  $("#method-explanation-title").textContent = item.title;
  $("#method-flow-scenario").textContent = readableText(flowScenarios[language]?.[selected] || flowScenarios.en?.[selected] || flowScenarios.ja?.[selected] || item.target);
  $("#method-flow-context").textContent = readableText(flow?.context || item.how);
  const steps = $("#method-flow-steps");
  steps.replaceChildren();
  (flow?.steps || []).forEach(([title, description], index) => {
    const step = document.createElement("li");
    const number = document.createElement("span");
    number.className = "flow-number";
    number.setAttribute("aria-hidden", "true");
    number.textContent = String(index + 1).padStart(2, "0");
    const heading = document.createElement("strong");
    heading.textContent = title.replace(/^\d+\.\s*/, "");
    const text = document.createElement("span");
    text.className = "flow-description";
    text.textContent = readableText(description);
    step.append(number, heading, text);
    steps.append(step);
  });
  const flowNote = $("#method-flow-note");
  flowNote.hidden = !flow?.note;
  flowNote.textContent = flow?.note ? readableText(flow.note) : "";
  const renderFlowPoints = (element, value, fallback) => {
    element.replaceChildren();
    if (Array.isArray(value)) {
      const list = document.createElement("ul");
      for (const point of value) {
        const item = document.createElement("li");
        item.textContent = readableText(point);
        list.append(item);
      }
      element.append(list);
    } else {
      const paragraph = document.createElement("p");
      paragraph.textContent = readableText(value || fallback);
      element.append(paragraph);
    }
  };
  renderFlowPoints($("#method-flow-if"), flow?.ifCase, item.target);
  renderFlowPoints($("#method-flow-else"), flow?.elseCase, item.limit);
  renderFlowPoints($("#method-flow-response"), flow?.response, item.limit);
  $("#explain-how").textContent = readableText(item.how);
  $("#explain-target").textContent = readableText(item.target);
  $("#explain-deception").textContent = readableText(outcomes?.deception || item.how);
  $("#explain-delay").textContent = readableText(outcomes?.delay || item.limit);
  $("#explain-limit").textContent = readableText(item.limit);
  $("#legal-normal").textContent = readableText(legal?.normal);
  $("#legal-risk").textContent = readableText(legal?.risk);
  $("#legal-other").textContent = readableText(legal?.other);
  $("#legal-us-normal").textContent = readableText(us?.[0]);
  $("#legal-us-risk").textContent = readableText(us?.[1]);
  $("#legal-guide-link").href = "/legal/" + language;
  $("#legal-us-guide-link").href = "/legal/" + language;
}
$("#nest-fields").addEventListener("input", estimate);
function columns() {
  const rows = [...document.querySelectorAll(".column-row")];
  if (!rows.length || rows.length > 30) {
    const error = new Error(t("schema_limit"));
    error.focusTarget = $("#add-column");
    throw error;
  }
  const tableInput = $("#table-name");
  const table = tableInput.value.trim();
  if (!/^[A-Za-z_][A-Za-z0-9_]{0,47}$/.test(table) || table.toLowerCase().startsWith("sqlite_")) {
    const error = new Error(t("column_name_error"));
    error.focusTarget = tableInput;
    throw error;
  }
  const names = new Set();
  return rows.map(row => {
    const nameInput = row.querySelector(".column-name");
    const name = nameInput.value.trim();
    if (!/^[A-Za-z_][A-Za-z0-9_]{0,47}$/.test(name) || name.toLowerCase().startsWith("sqlite_") || names.has(name.toLowerCase())) {
      const error = new Error(t("column_name_error"));
      error.focusTarget = nameInput;
      throw error;
    }
    names.add(name.toLowerCase());
    const column = {name, kind: row.querySelector(".column-kind").value};
    const options = row.querySelector(".column-options");
    const value = options.value.trim();
    if (!value && ["integer", "decimal"].includes(column.kind)) {
      const defaults = {
        quantity: [1, 100],
        unit_price: [25, 2500],
        total: [0, 100000],
        subtotal: [0, 100000],
        amount: [0, 100000],
        annual_cost: [0, 100000],
      };
      [column.min, column.max] = defaults[name.toLowerCase()] || [0, 100000];
    }
    if (value && ["integer", "decimal"].includes(column.kind)) {
      const limits = value.split(",");
      const [minimum, maximum] = limits.map(Number);
      if (limits.length !== 2 || limits.some(v => !v.trim() || !Number.isFinite(Number(v)))
          || Math.abs(minimum) > 1e12 || Math.abs(maximum) > 1e12 || minimum > maximum
          || (column.kind === "integer" && (!Number.isInteger(minimum) || !Number.isInteger(maximum)))) {
        const error = new Error(t("invalid_options"));
        error.focusTarget = options;
        throw error;
      }
      column.min = minimum;
      column.max = maximum;
    } else if (value && !options.disabled) {
      const values = value.split("|").map(v => v.trim());
      if (values.length < 1 || values.length > 50 || values.some(v => !v || Array.from(v).length > 120)) {
        const error = new Error(t("candidate_values_error"));
        error.focusTarget = options;
        throw error;
      }
      column.values = values;
    }
    return column;
  });
}
function clearDownloads() {
  downloadUrls.forEach(url => URL.revokeObjectURL(url));
  downloadUrls = [];
  $("#downloads").replaceChildren();
  $("#downloads").hidden = true;
  generatedAsset = null;
}
function downloadLink(data, label, parent = $("#downloads")) {
  let blob = data.blob;
  if (!blob) {
    const encoded = data.content;
    const parts = [];
    // Decode in bounded pieces instead of holding a second full-size binary
    // string while constructing a large ZIP or SQLite download.
    const chunkSize = 64 * 1024; // divisible by four for Base64 boundaries
    for (let offset = 0; offset < encoded.length; offset += chunkSize) {
      const binary = atob(encoded.slice(offset, offset + chunkSize));
      const bytes = new Uint8Array(binary.length);
      for (let index = 0; index < binary.length; index++) bytes[index] = binary.charCodeAt(index);
      parts.push(bytes);
    }
    blob = new Blob(parts, {type: data.mime});
    data.blob = blob;
    delete data.content;
  }
  const url = URL.createObjectURL(blob);
  downloadUrls.push(url);
  const link = document.createElement("a");
  link.href = url;
  link.download = data.name;
  link.textContent = label + " — " + data.name;
  parent.append(link);
  return link;
}
function generatedStatusName(data) {
  const deployment = (data.companions || []).filter(item => item.role === "deployment").pop();
  return deployment?.name || data.downloadName || data.name;
}
function renderDownloads(data) {
  clearDownloads();
  generatedAsset = data;
  $("#downloads").hidden = false;
  const hasDeploymentPackage = (data.companions || []).some(item => item.role === "deployment");
  const isWebPackage = data.summary?.kind === "web" && hasDeploymentPackage;
  const isEnvPackage = typeof data.name === "string" && data.name.endsWith(".env") && hasDeploymentPackage;
  const primary = downloadLink(data, t(data.summary?.kind === "ransomware_tripwire" ? "tripwire_deployment_download"
    : isWebPackage ? "web_html_download" : hasDeploymentPackage ? "env_direct_download" : "download_again"),
    isEnvPackage ? document.createDocumentFragment() : $("#downloads"));
  let automatic = primary;
  const isHtmlPreview = typeof data.mime === "string" && data.mime.startsWith("text/html");
  const isPdfPreview = data.mime === "application/pdf";
  if (isHtmlPreview || isPdfPreview) {
    const preview = document.createElement("a");
    preview.href = primary.href;
    preview.removeAttribute("download");
    preview.target = "_blank";
    preview.rel = "noopener noreferrer";
    preview.textContent = `${t(isHtmlPreview ? "preview_html" : "preview_pdf")} — ${data.name}`;
    preview.className = "preview-link";
    $("#downloads").append(preview);
  }
  const previewMime = typeof data.mime === "string" ? data.mime.split(";", 1)[0].trim() : "";
  if (["text/plain", "text/csv", "application/json"].includes(previewMime)) {
    const previewLimit = 256 * 1024;
    if (data.blob.size <= previewLimit) {
      const details = document.createElement("details");
      details.className = "generated-text-preview";
      const summary = document.createElement("summary");
      summary.textContent = t("preview_text_title");
      const content = document.createElement("pre");
      content.textContent = t("preview_text_loading");
      details.append(summary, content);
      $("#downloads").append(details);
      if (!previewUrlRedactions.has(data)) {
        const urls = (previewUrlFields[$('input[name="kind"]:checked')?.value] || [])
          .flatMap(selector => $(selector).value.split(/\r?\n/))
          .map(value => value.trim()).filter(Boolean);
        previewUrlRedactions.set(data, urls);
      }
      const previewUrls = previewUrlRedactions.get(data);
      if (previewUrls.length) {
        const redacted = document.createElement("p");
        redacted.textContent = t("preview_text_canary_redacted");
        details.append(redacted);
      }
      data.blob.text().then(value => {
        if (generatedAsset !== data) return;
        if (data.summary?.has_monitoring_url && !previewUrls.length) {
          content.textContent = t("preview_text_failed");
          return;
        }
        for (const url of previewUrls) value = value.replaceAll(url, t("preview_url_redacted"));
        content.textContent = value;
      }).catch(() => { content.textContent = t("preview_text_failed"); });
    } else {
      const note = document.createElement("p");
      note.textContent = t("preview_text_too_large");
      $("#downloads").append(note);
    }
  }
  const companions = data.companions || [];
  for (const companion of companions.filter(item => item.role === "deployment")) {
    automatic = downloadLink(companion, t(isWebPackage ? "web_package_download" : "env_zip_download"));
  }
  const operatorFiles = companions.filter(item => item.role !== "deployment" && !item.name.endsWith(".inventory.json"));
  for (const companion of operatorFiles) {
    const label = companion.name === "ransomware_tripwire_monitor.py" ? t("tripwire_monitor_download") : t("operator_download");
    downloadLink(companion, label);
  }
  if (hasDeploymentPackage) {
    const note = document.createElement("p"); note.textContent = t(isWebPackage ? "web_package_note" : "env_zip_note"); $("#downloads").append(note);
  }
  if (data.summary && "has_monitoring_url" in data.summary && !["stream", "ransomware_tripwire", "path_maze", "sparse_decoy"].includes(data.summary.kind)) {
    const noRandomPlacement = data.summary.canary_placements === 0 && data.summary.canary_url_configured;
    if (noRandomPlacement) {
      const note = document.createElement("p");
      note.textContent = t("monitoring_not_placed");
      $("#downloads").append(note);
    }
    if (data.summary.reserved_canary_host) {
      const warning = document.createElement("p");
      warning.className = "inline-note";
      warning.textContent = t("monitoring_placeholder");
      $("#downloads").append(warning);
      $("#canary-url-warning").hidden = true;
    }
  }
  if (data.summary) {
    const examples = Array.isArray(data.summary.canary_location_examples)
      ? data.summary.canary_location_examples
      : Array.isArray(data.summary.canary_locations) ? data.summary.canary_locations
        : [];
    if (examples.length) {
      const section = document.createElement("section");
      section.className = "canary-placement-summary";
      const heading = document.createElement("h3");
      heading.textContent = t("canary_location_title");
      section.append(heading);
      for (const item of examples.slice(0, 3)) {
        const line = document.createElement("p");
        const path = item.path || item.artifact || "";
        if (item.location === "commented production setting") {
          line.textContent = t("canary_location_env", {path, field: item.field || "URL"});
        } else if (item.field && item.record) {
          line.textContent = t("canary_location_record", {path, field: item.field, record: item.record});
        } else if (item.label) {
          line.textContent = t("canary_location_label", {path, label: item.label});
        } else {
          line.textContent = t("canary_location_unknown");
        }
        section.append(line);
      }
      const note = document.createElement("p");
      note.textContent = t("canary_location_hidden");
      section.append(note);
      $("#downloads").append(section);
    }
  }
  if (["database", "canary_file_preview"].includes(data.summary?.kind)) {
    const isDatabasePreview = data.summary.kind === "database";
    const summary = document.createElement("p");
    const summaryData = isDatabasePreview ? data.summary
      : {...data.summary, format: t("format_" + data.summary.format)};
    summary.textContent = t(isDatabasePreview ? "database_result_summary" : "canary_file_result_summary", summaryData);
    $("#downloads").append(summary);
    if (isDatabasePreview) {
      const templateId = typeof data.summary.template === "string" ? data.summary.template : "customers";
      // Keep the last known human-readable preset label while a language
      // switch reloads templates, or if that request fails.
      const template = databaseTemplates.find(item => item.id === templateId);
      const presetName = templateId === "custom" ? t("template_custom")
        : template?.label || templateId;
      const presetNote = document.createElement("p");
      presetNote.textContent = t("database_result_preset", {preset: presetName});
      $("#downloads").append(presetNote);
    }
    if (isDatabasePreview && data.summary.canary_placement) {
      const placement = data.summary.canary_placement;
      const note = document.createElement("p");
      note.textContent = t(placement.kind === "vault_field" ? "database_canary_field"
        : placement.kind === "api_endpoint_field" ? "database_canary_api_field" : "database_canary_table", placement);
      $("#downloads").append(note);
    }
    const previewRows = Array.isArray(data.summary.preview_rows) ? data.summary.preview_rows : [];
    const previewColumns = Array.isArray(data.summary.preview_columns) ? data.summary.preview_columns : [];
    const previewLabels = Array.isArray(data.summary.preview_labels) ? data.summary.preview_labels : [];
    const previewTemplate = isDatabasePreview && databaseTemplatesLanguage === language
      ? databaseTemplates.find(template => template.id === data.summary.template)
      : null;
    if (previewRows.length && previewColumns.length) {
      const section = document.createElement("section");
      section.className = "database-preview";
      const heading = document.createElement("h3");
      heading.textContent = t("database_preview_title");
      section.append(heading);
      const caption = document.createElement("caption");
      caption.textContent = t(isDatabasePreview ? "database_preview_caption" : "canary_preview_caption",
        {count: previewRows.length, rows: data.summary.rows});
      const placement = data.summary.canary_placement || {};
      const targetRecord = Number.isInteger(Number(placement.record)) ? Number(placement.record) : 0;
      const targetFieldIndex = typeof placement.field === "string" ? previewColumns.indexOf(placement.field) : -1;
      if (targetRecord > 0 && targetRecord <= previewRows.length) {
        const targetNote = document.createElement("p");
        targetNote.className = "database-preview-target-note";
        targetNote.textContent = t("preview_canary_target", {record: targetRecord});
        section.append(targetNote);
      }
      const scrollHint = document.createElement("p");
      scrollHint.id = "generated-preview-scroll-hint";
      scrollHint.className = "database-preview-scroll-hint";
      scrollHint.textContent = t("preview_table_scroll_hint");
      const scroll = document.createElement("div");
      scroll.className = "database-preview-scroll";
      scroll.setAttribute("role", "region");
      scroll.setAttribute("aria-label", t("database_preview_title"));
      scroll.setAttribute("aria-describedby", scrollHint.id);
      scroll.tabIndex = 0;
      const table = document.createElement("table");
      table.append(caption);
      const thead = document.createElement("thead");
      const headerRow = document.createElement("tr");
      for (let index = 0; index < previewColumns.length; index += 1) {
        const name = previewColumns[index];
        const th = document.createElement("th");
        th.scope = "col";
        const field = previewTemplate?.columns.find(column => column.name === name);
        const label = field?.label || previewLabels[index];
        if (label && label !== name) {
          const friendlyName = document.createElement("span");
          friendlyName.textContent = label;
          const columnName = document.createElement("small");
          columnName.textContent = String(name);
          th.append(friendlyName, columnName);
        } else th.textContent = String(name);
        headerRow.append(th);
      }
      thead.append(headerRow);
      table.append(thead);
      const tbody = document.createElement("tbody");
      const pageSize = 10;
      const pageCount = Math.max(1, Math.ceil(previewRows.length / pageSize));
      let currentPage = targetRecord > 0 && targetRecord <= previewRows.length
        ? Math.floor((targetRecord - 1) / pageSize) : 0;
      const controls = document.createElement("div");
      controls.className = "database-preview-controls";
      const previous = document.createElement("button");
      previous.type = "button";
      previous.textContent = t("preview_previous");
      const pageStatus = document.createElement("span");
      pageStatus.className = "database-preview-page-status";
      pageStatus.setAttribute("aria-live", "polite");
      const next = document.createElement("button");
      next.type = "button";
      next.textContent = t("preview_next");
      controls.append(previous, pageStatus, next);
      controls.hidden = pageCount <= 1;
      function renderPreviewPage() {
        const start = currentPage * pageSize;
        const end = Math.min(start + pageSize, previewRows.length);
        tbody.replaceChildren();
        for (let offset = start; offset < end; offset += 1) {
          const row = previewRows[offset];
          if (!Array.isArray(row)) continue;
          const recordNumber = offset + 1;
          const isTargetRecord = recordNumber === targetRecord;
          const tr = document.createElement("tr");
          if (isTargetRecord) {
            tr.classList.add("canary-preview-target-row");
            tr.setAttribute("aria-current", "true");
          }
          for (let index = 0; index < previewColumns.length; index += 1) {
            const td = document.createElement("td");
            const value = row[index];
            td.textContent = value == null ? "" : String(value);
            if (isTargetRecord && index === targetFieldIndex) {
              td.classList.add("canary-preview-target-cell");
            }
            tr.append(td);
          }
          tbody.append(tr);
        }
        pageStatus.textContent = t("preview_page_status", {
          start: previewRows.length ? start + 1 : 0, end, total: previewRows.length,
          page: currentPage + 1, pages: pageCount,
        });
        previous.disabled = currentPage <= 0;
        next.disabled = currentPage >= pageCount - 1;
      }
      previous.addEventListener("click", () => {
        if (currentPage > 0) { currentPage -= 1; renderPreviewPage(); }
      });
      next.addEventListener("click", () => {
        if (currentPage < pageCount - 1) { currentPage += 1; renderPreviewPage(); }
      });
      renderPreviewPage();
      table.append(tbody);
      scroll.append(table);
      section.append(scrollHint, scroll, controls);
      $("#downloads").append(section);
    }
  }
  if (data.summary && data.summary.archives) {
    const note = document.createElement("p");
    const formatCounts = data.summary.format_counts;
    const formatNote = formatCounts && Object.keys(formatCounts).length
      ? ` ${t("format_breakdown")}: ${Object.entries(formatCounts).map(([format, count]) => `${t(`format_${format}`)} ${count}`).join(", ")}.`
      : "";
    note.textContent = t("summary", data.summary) + formatNote;
    $("#downloads").append(note);
  }
  if (data.summary && ["stream", "directory_maze", "encoding_maze"].includes(data.summary.kind)) {
    const note = document.createElement("p");
    const details = data.summary;
    const summaryKey = {stream: "stream_generated_summary", directory_maze: "directory_generated_summary", encoding_maze: "encoding_generated_summary"}[details.kind];
    note.textContent = t(summaryKey, {rate: details.rate_kib, streams: details.max_streams,
      directories: details.directories, documents: details.documents,
      scenario: t("scenario_" + details.scenario), candidates: details.candidates, layers: details.layers});
    $("#downloads").append(note);
    if (details.kind === "stream") {
      const dailyGiB = (details.rate_kib * 84.375 / 1024).toFixed(2);
      const budgetNote = document.createElement("p");
      budgetNote.textContent = language === "ja"
        ? `\u9023\u7d9a\u914d\u4fe1\u6642\u306e\u30c7\u30fc\u30bf\u9001\u4fe1\u91cf\u306f\u6700\u5927\u7d04${dailyGiB} GiB/\u65e5\u3067\u3059\u3002\u3053\u308c\u306f\u7d2f\u7a4d\u4e0a\u9650\u3067\u306f\u3042\u308a\u307e\u305b\u3093\u3002\u56de\u7dda\u30fb\u30af\u30e9\u30a6\u30c9\u8cbb\u7528\u3092\u898b\u7a4d\u3082\u308a\u3001\u76e3\u8996\u3068\u505c\u6b62\u624b\u6bb5\u3092\u7528\u610f\u3057\u3066\u304f\u3060\u3055\u3044\u3002`
        : `Continuous delivery can send up to about ${dailyGiB} GiB/day. This is not a cumulative quota. Estimate network/cloud costs and prepare monitoring and a stop procedure.`;
      $("#downloads").append(budgetNote);
    }
  }
  if (data.summary?.kind === "ransomware_tripwire") {
    const note = document.createElement("p");
    note.textContent = t("tripwire_generated_summary", {count: data.summary.files});
    $("#downloads").append(note);
  }
  if (data.summary?.kind === "path_maze" || data.summary?.kind === "sparse_decoy") {
    const note = document.createElement("p");
    note.textContent = data.summary.kind === "path_maze"
      ? t("path_generated", data.summary)
      : t("sparse_generated", {size: data.summary.size_gib, count: data.summary.files});
    $("#downloads").append(note);
  }
  data.downloadName = automatic.download || data.name;
  return automatic;
}
applyLanguage();
updateFields();
showWorkspacePage(activeWorkspacePage, false);
loadDatabaseTemplates();
form.querySelectorAll('input[type="number"]').forEach(input => {
  input.addEventListener("input", () => {
    if (input.checkValidity()) clearInvalid(input);
  });
});
function invalidateGeneratedOnEdit(event) {
  if (!event.isTrusted) return;
  settingsRevision += 1;
  clearDownloads();
  result.textContent = generationInProgress ? t("generation_settings_changed") : "";
}
form.addEventListener("input", invalidateGeneratedOnEdit);
form.addEventListener("change", invalidateGeneratedOnEdit);
form.addEventListener("submit", async event => {
  event.preventDefault();
  form.querySelectorAll('[aria-invalid="true"]').forEach(clearInvalid);
  if (generationInProgress) return;
  const kind = $('input[name="kind"]:checked').value;
  if (["data_dilution", "honeyword"].includes(kind)) return;
  if (kind === "database" && !document.querySelector(".column-row")) {
    result.textContent = t("template_loading");
    result.focus();
    return;
  }
  const invalidNumber = [...$("#" + kind + "-fields").querySelectorAll('input[type="number"]')]
    .find(input => !input.checkValidity());
  if (invalidNumber) {
    result.textContent = t("number_input_invalid");
    markInvalid(invalidNumber);
    invalidNumber.focus();
    return;
  }
  const invalidPattern = [...$("#" + kind + "-fields").querySelectorAll("input[pattern]")]
    .find(input => !input.checkValidity());
  if (invalidPattern) {
    result.textContent = t("env_suffix_format_error");
    markInvalid(invalidPattern);
    invalidPattern.focus();
    return;
  }
  if (kind === "directory_maze" && $("#maze-estimate").dataset.overLimit === "true") {
    result.textContent = $("#maze-estimate").textContent;
    $("#" + ($("#maze-estimate").dataset.recommendedControl || "maze-depth")).focus();
    return;
  }
  if (kind === "nest") {
    const layers = Number($("#layers").value), branches = Number($("#branches").value);
    const archives = Array.from({length: layers}, (_, level) => branches ** level).reduce((sum, count) => sum + count, 0);
    if (archives > 40) {
      result.textContent = $("#nest-estimate").textContent;
      $("#" + ($("#nest-estimate").dataset.recommendedControl || "layers")).focus();
      return;
    }
  }
  let settings, requestBody;
  try {
    settings = {
      env: () => ({format: $("#canary-format").value, canary_url: $("#env-url").value, canary_link_style: $("#canary-link-style").value, canary_context: $("#canary-context").value, canary_field:"", canary_label:"", env_layout: "commented_production", env_suffix: "development", env_variable: "URL", rows: CANARY_DEFAULT_ROWS}),
      nest: () => ({scenario: $("#nest-scenario").value, ...($("#nest-scenario").value === "passwords" && ($("#nest-format").value !== "env" || $("#nest-varied-formats").checked) ? vaultDomainSettings() : {}), layers: Number($("#layers").value), branches: Number($("#branches").value), decoys: Number($("#decoys").value), directory_depth: Number($("#directory-depth").value), rows: Number($("#nest-rows").value),
        format: $("#nest-format").value, varied_formats: $("#nest-varied-formats").checked, directories: $("#directories").value.split(",").map(v => v.trim()),
        canary_urls: $("#nest-url").value.split(/\r?\n/).filter(value => value.trim()), canary_percent: Number($("#canary-percent").value),
        password_policy: {mode: $("#password-mode").value, min_length: Number($("#min-length").value), max_length: Number($("#max-length").value),
          lowercase: $("#lowercase").checked, uppercase: $("#uppercase").checked, digits: $("#digits").checked, symbols: $("#symbols").checked, progressive: $("#progressive").checked, hints: $("#hints").value,
          hint_characters: Number($("#hint-characters").value), ...($("#password-words").value.trim() ? {words: $("#password-words").value.split(",").map(v => v.trim())} : {})}}),
      database: () => ({template: $("#database-template").value || "customers", email_domain: $("#db-email-domain").value.trim(), email_domain_authorized: $("#db-email-domain-authorized").checked, ...( $("#database-template").value === "passwords" ? vaultDomainSettings() : {}), rows: Number($("#rows").value), table: $("#table-name").value, columns: columns(), canary_url: $("#db-url").value}),
      web: () => ({scenario: $("#web-scenario").value, title: $("#title").value, canary_url: $("#web-url").value}),
      fake_trap: () => ({variant: $("#fake-variant").value}),
      ransomware_tripwire: () => ({files: Number($("#tripwire-files").value)}),
      path_maze: () => ({depth: Number($("#path-depth").value), branches: Number($("#path-branches").value), files: Number($("#path-files").value)}),
      sparse_decoy: () => ({size_gib: Number($("#sparse-size").value), files: Number($("#sparse-files").value)}),
      stream: () => ({path: $("#stream-path").value, format: $("#stream-format").value, port: Number($("#stream-port").value), rate_kib: Number($("#stream-rate").value), max_streams: Number($("#stream-concurrency").value)}),
      directory_maze: () => ({scenario: $("#maze-scenario").value, ...($("#maze-scenario").value === "passwords" && $("#maze-format").value !== "env" ? vaultDomainSettings() : {}), title: $("#directory-title").value, depth: Number($("#maze-depth").value), branches: Number($("#maze-branches").value), files_per_directory: Number($("#maze-files").value), cross_links: $("#maze-cross-links").checked, canary_urls: $("#maze-url").value.split(/\r?\n/).filter(value => value.trim()), format: $("#maze-format").value}),
      encoding_maze: () => ({scenario: $("#encoding-scenario").value, ...($("#encoding-scenario").value === "passwords" && $("#encoding-format").value !== "env" ? vaultDomainSettings() : {}), format: $("#encoding-format").value, layers: Number($("#encoding-layers").value), candidates: Number($("#encoding-candidates").value), canary_urls: $("#encoding-url").value.split(/\r?\n/).filter(value => value.trim()), codecs: [...document.querySelectorAll("#encoding-codecs input:checked")].map(input => input.value)}),
    }[kind]();
    requestBody = JSON.stringify({kind, settings});
    if (new Blob([requestBody]).size > MAX_GENERATION_REQUEST_BYTES) {
      result.textContent = t("request_too_large");
      result.focus();
      return;
    }
  } catch (error) {
    result.textContent = error.message;
    if (error.focusTarget) {
      markInvalid(error.focusTarget);
      error.focusTarget.focus();
    } else result.focus();
    return;
  }
  // Tie preview redaction to this request; text fields may remain editable while generation runs.
  const requestPreviewUrls = (previewUrlFields[kind] || [])
    .flatMap(selector => $(selector).value.split(/\r?\n/))
    .map(value => value.trim()).filter(Boolean);
  generationInProgress = true;
  const generationRevision = settingsRevision;
  button.disabled = true;
  languageSelect.disabled = true;
  document.querySelectorAll('input[name="kind"]').forEach(input => { input.disabled = true; });
  clearDownloads();
  result.setAttribute("aria-busy", "true");
  result.textContent = t("generating");
  try {
    let response;
    try {
      response = await fetch("/api/generate", {
        method: "POST", headers: {"Content-Type": "application/json", "X-ADG-Token": $('meta[name="adg-token"]').content, "X-ADG-Language": language},
        body: requestBody,
      });
    } catch (error) {
      if (error instanceof TypeError) throw new Error(t("connection_failed"));
      throw error;
    }
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || t("failed"));
    if (generationRevision !== settingsRevision) {
      clearDownloads();
      result.textContent = t("generation_settings_changed");
      return;
    }
    data.formKind = kind;
    previewUrlRedactions.set(data, requestPreviewUrls);
    const primary = renderDownloads(data);
    primary.focus();
  } catch (error) {
    result.textContent = error.message || t("failed");
    if (error.message === t("database_size_limit")) {
      const rowsInput = kind === "database" ? $("#rows") : $("#canary-format");
      rowsInput.scrollIntoView({block: "center"});
      rowsInput.focus();
    } else result.focus();
  } finally {
    result.removeAttribute("aria-busy");
    generationInProgress = false;
    button.disabled = false;
    languageSelect.disabled = false;
    document.querySelectorAll('input[name="kind"]').forEach(input => { input.disabled = false; });
  }
});

// Explicit local files only; never persist canary URLs or generated passwords.
function configControls() {
  const controls = [...form.querySelectorAll(".fields input, .fields select, .fields textarea")]
    .filter(el => el.type !== "url" && el.type !== "file" && !el.hasAttribute("data-secret-url")
      && !el.hasAttribute("data-operator-attestation") && !el.closest("#columns")
      && el.id !== "canary-link-style");
  controls.push($("#canary-link-style"));
  // Preserve the pre-layout-change settings order for existing saved configs.
  const purposeIndex = controls.findIndex(el => el.id === "canary-context");
  const fieldIndex = controls.findIndex(el => el.id === "canary-field");
  if (purposeIndex >= 0 && fieldIndex >= 0 && purposeIndex < fieldIndex) {
    const [purpose] = controls.splice(purposeIndex, 1);
    controls.splice(controls.findIndex(el => el.id === "canary-field"), 0, purpose);
  }
  return controls;
}
const nonPersistentCanaryUrlControls = new Set(["env-url", "db-url", "web-url"]);
const internalCanaryTemplateControls = new Set(["canary-field", "canary-label"]);
const nonPersistentOperatorAttestations = new Set([
  "db-email-domain-authorized", "vault-domain-authorized",
]);
const unsafeSettingText = /[\p{Cc}\p{Zl}\p{Zp}\p{Cs}\u061c\u200e\u200f\u202a-\u202e\u2066-\u206f]/u;
function hasUnsafeSettingText(value) { return typeof value === "string" && unsafeSettingText.test(value); }
const sensitiveSettingCredential = /-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b|\bgh[pousr]_[A-Za-z0-9]{20,}\b|\bxox[baprs]-[A-Za-z0-9-]{10,}\b|\bAIza[0-9A-Za-z_-]{30,}\b|\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b|\b(?:sk|rk)_live_[A-Za-z0-9]{12,}\b|\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*[^\s,;]+/i;
const sensitiveSettingJwt = /\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b/;
function hasSensitiveSettingText(value) {
  if (typeof value !== "string") return false;
  const normalized = value.normalize("NFKC").replace(/\p{Cf}/gu, "");
  if (sensitiveSettingCredential.test(normalized) || sensitiveSettingJwt.test(normalized)) return true;
  for (const match of normalized.matchAll(/(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)/g)) {
    const digits = match[0].replace(/\D/g, "");
    const parity = digits.length % 2;
    let checksum = 0;
    for (let index = 0; index < digits.length; index++) {
      let digit = Number(digits[index]);
      if (index % 2 === parity) { digit *= 2; if (digit > 9) digit -= 9; }
      checksum += digit;
    }
    if (checksum % 10 === 0) return true;
  }
  return false;
}
if ($("#save-settings")) $("#save-settings").addEventListener("click", () => {
  const controls = configControls();
  const columns = [...document.querySelectorAll(".column-row")].map(row => [row.querySelector(".column-name").value, row.querySelector(".column-kind").value, row.querySelector(".column-options").value]);
  if (controls.some(el => el.type !== "checkbox" && hasUnsafeSettingText(el.value))
      || columns.flat().some(hasUnsafeSettingText)) {
    result.textContent = t("unsafe_setting_text"); return;
  }
  if (controls.some(el => el.type !== "checkbox" && hasSensitiveSettingText(el.value))
      || columns.flat().some(hasSensitiveSettingText)) {
    result.textContent = t("sensitive_setting_text"); return;
  }
  const config = {schema: "adg-ui-v14", kind: $('input[name="kind"]:checked').value,
    // Keep the positional slots for compatibility, but never export canary tokens.
    controls: controls.map(el => el.type === "checkbox"
      ? (nonPersistentOperatorAttestations.has(el.id) ? false : el.checked)
      : nonPersistentCanaryUrlControls.has(el.id) ? ""
        : internalCanaryTemplateControls.has(el.id) ? "" : el.value),
    columns};
  const url = URL.createObjectURL(new Blob([JSON.stringify(config, null, 2)], {type: "application/json"}));
  const link = document.createElement("a"); link.href = url; link.download = "adg-settings.json"; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  result.textContent = t("config_saved");
});
if ($("#load-settings")) {
$("#load-settings").addEventListener("click", () => $("#settings-file").click());
$("#settings-file").addEventListener("change", async event => {
  const file = event.target.files[0];
  event.target.value = "";
  if (!file) return;
  try {
    if (file.size > 1024 * 1024) throw new Error();
    const source = new TextDecoder("utf-8", {fatal: true}).decode(await file.arrayBuffer());
    window.assertNoDuplicateJsonKeys(source);
    const config = JSON.parse(source);
    const addedV4 = ["nest-scenario", "maze-scenario"];
    const addedV3 = ["env-layout", "env-suffix", "env-variable", "env-dev-comment", "env-prod-comment"];
    const excluded = config.schema === "adg-ui-v1" ? [...addedV4, ...addedV3, "canary-context", "canary-field", "canary-label"] : config.schema === "adg-ui-v2" ? [...addedV4, ...addedV3] : config.schema === "adg-ui-v3" ? addedV4 : [];
    if (config.schema !== "adg-ui-v14") excluded.push("canary-link-style");
    const controls = configControls().filter(el => !excluded.includes(el.id));
    const legacyControlIndex = id => {
      const index = controls.findIndex(el => el.id === id);
      const addedControlIndex = controls.findIndex(el => el.id === "nest-varied-formats");
      return index > addedControlIndex ? index - 1 : index;
    };
    const legacy = ["adg-ui-v1", "adg-ui-v2", "adg-ui-v3", "adg-ui-v4"].includes(config.schema);
    let values = legacy && Array.isArray(config.controls) ? config.controls.slice(13) : config.controls;
    // UI v6 stored two trailing values for the retired generator.
    if (config.schema === "adg-ui-v6" && Array.isArray(values)) values = values.slice(0, -2);
    if (Array.isArray(values) && !["adg-ui-v9", "adg-ui-v10", "adg-ui-v11", "adg-ui-v12", "adg-ui-v13", "adg-ui-v14"].includes(config.schema)) {
      // Older schemas predate the database email-domain controls. v1-v8 also
      // predate the trailing vault-domain controls; v9 already contains those.
      if (config.schema !== "adg-ui-v9") values = [...values, "", false];
      const emailDomainIndex = legacyControlIndex("db-email-domain");
      if (emailDomainIndex < 0) throw new Error();
      values.splice(emailDomainIndex, 0, "", false);
    }
    if (Array.isArray(values) && !["adg-ui-v11", "adg-ui-v12", "adg-ui-v13", "adg-ui-v14"].includes(config.schema)) {
      const encodingScenarioIndex = legacyControlIndex("encoding-scenario");
      if (encodingScenarioIndex < 0) throw new Error();
      values.splice(encodingScenarioIndex, 0, "crm");
    }
    if (Array.isArray(values) && !["adg-ui-v12", "adg-ui-v13", "adg-ui-v14"].includes(config.schema)) {
      const variedFormatIndex = controls.findIndex(el => el.id === "nest-varied-formats");
      if (variedFormatIndex < 0) throw new Error();
      values.splice(variedFormatIndex, 0, true);
    }
    if (Array.isArray(values) && !["adg-ui-v13", "adg-ui-v14"].includes(config.schema)) {
      const webScenarioIndex = controls.findIndex(el => el.id === "web-scenario");
      if (webScenarioIndex < 0) throw new Error();
      values.splice(webScenarioIndex, 0, "operations");
    }
    const method = [...document.querySelectorAll('input[name="kind"]')].find(el => el.value === config.kind);
    const kinds = [...$("#column-template").content.querySelectorAll("option")].map(el => el.value);
    if (!["adg-ui-v1", "adg-ui-v2", "adg-ui-v3", "adg-ui-v4", "adg-ui-v5", "adg-ui-v6", "adg-ui-v8", "adg-ui-v9", "adg-ui-v10", "adg-ui-v11", "adg-ui-v12", "adg-ui-v13", "adg-ui-v14"].includes(config.schema) || !method || !Array.isArray(values) || values.length !== controls.length ||
        !Array.isArray(config.columns) || config.columns.length < 1 || config.columns.length > 30) throw new Error();
    values.forEach((value, i) => {
      const el = controls[i];
      if (el.type === "checkbox") { if (typeof value !== "boolean") throw new Error(); }
      else {
        if (typeof value !== "string" || value.length > 6100
            || (el.maxLength >= 0 && value.length > el.maxLength)) throw new Error();
        if (hasUnsafeSettingText(value)) throw new Error("unsafe_setting_text");
        if (hasSensitiveSettingText(value)) throw new Error("sensitive_setting_text");
        // Reject imports that the browser would silently normalize (for
        // example, invalid numeric strings becoming blank) or that violate
        // the current control's min/max/pattern constraints.
        const probe = el.cloneNode();
        probe.value = value;
        if (probe.value !== value || !probe.checkValidity()) throw new Error();
      }
      if (el.tagName === "SELECT" && ![...el.options].some(option => option.value === value)) throw new Error();
    });
    const columnNames = new Set();
    for (const row of config.columns) {
      if (Array.isArray(row) && row.some(v => typeof v === "string" && hasUnsafeSettingText(v))) throw new Error("unsafe_setting_text");
      if (!Array.isArray(row) || row.length !== 3 || row.some(v => typeof v !== "string" || v.length > 6100) || !kinds.includes(row[1])) throw new Error();
      if (row.some(hasSensitiveSettingText)) throw new Error("sensitive_setting_text");
      const [name, kind, options] = row;
      const normalizedName = name.trim().toLowerCase();
      if (!/^[A-Za-z_][A-Za-z0-9_]{0,47}$/.test(normalizedName)
          || normalizedName.startsWith("sqlite_") || columnNames.has(normalizedName)) throw new Error();
      columnNames.add(normalizedName);
      if (["integer", "decimal"].includes(kind) && options.trim()) {
        const range = options.split(",").map(value => value.trim());
        if (range.length !== 2 || range.some(value => !value || !Number.isFinite(Number(value)))) throw new Error();
        const [minimum, maximum] = range.map(Number);
        if (Math.abs(minimum) > 1e12 || Math.abs(maximum) > 1e12 || minimum > maximum
            || (kind === "integer" && (!Number.isInteger(minimum) || !Number.isInteger(maximum)))) throw new Error();
      } else if (["status", "text", "company", "department"].includes(kind) && options.trim()) {
        const candidates = options.split("|").map(value => value.trim());
        if (candidates.length > 50 || candidates.some(value => !value || value.length > 120)) throw new Error();
      }
    }
    if (!["adg-ui-v4", "adg-ui-v5", "adg-ui-v6", "adg-ui-v8", "adg-ui-v9", "adg-ui-v10", "adg-ui-v11", "adg-ui-v12", "adg-ui-v13"].includes(config.schema)) { $("#nest-scenario").value = "crm"; $("#maze-scenario").value = "crm"; }
    if (!["adg-ui-v11", "adg-ui-v12", "adg-ui-v13"].includes(config.schema)) $("#encoding-scenario").value = "crm";
    controls.forEach((el, i) => { if (el.type === "checkbox") el.checked = values[i]; else el.value = values[i]; });
    if (config.schema !== "adg-ui-v14") $("#canary-link-style").value = "text";
    // Retain the legacy settings slots while always using automatic canary defaults.
    $("#canary-name").value = "";
    $("#canary-title").value = "";
    $("#canary-rows").value = String(CANARY_DEFAULT_ROWS);
    $("#canary-field").value = "";
    $("#canary-label").value = "";
    activeNestDirectoryScenario = $("#nest-scenario").value;
    // Ownership attestation must be given by the current operator, not carried in an imported config.
    $("#vault-domain-authorized").checked = false;
    $("#db-email-domain-authorized").checked = false;
    $("#database-template").dataset.selected = $("#database-template").value;
    const selectedTemplate = databaseTemplates.find(item => item.id === $("#database-template").value);
    $("#template-description").textContent = selectedTemplate?.description || t("template_help");
    $("#columns").replaceChildren();
    for (const [name, kind, options] of config.columns) {
      addColumn(name, kind); $("#columns").lastElementChild.querySelector(".column-options").value = options;
    }
    form.querySelectorAll('input[type="url"], [data-secret-url], #env-url, #db-url, #web-url')
      .forEach(el => { el.value = ""; });
    $("#env-url").value = $("#env-url").defaultValue;
    method.checked = true; updateFields(true); updateMethodFilter("all"); estimate(); updateMazeEstimate(); result.textContent = t("config_loaded");
  } catch (error) { result.textContent = error.message === "unsafe_setting_text" ? t("unsafe_setting_text") : error.message === "sensitive_setting_text" ? t("sensitive_setting_text") : t("config_invalid"); }
});
}
