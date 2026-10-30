"use strict";
const $ = selector => document.querySelector(selector);
const MAX_GENERATION_REQUEST_BYTES = Number($('meta[name="adg-generation-request-limit"]').content);
const form = $("#generator"), result = $("#result"), button = $("#submit"), languageSelect = $("#language");
const japanese = {};
for (const root of [document, $("#column-template").content]) {
  root.querySelectorAll("[data-i18n]").forEach(element => { japanese[element.dataset.i18n] = element.textContent; });
}
const translations = {
  ja: {...japanese, intro: "手法を選び、仕組みや対象となる攻撃を確認してから生成します。", notice: "生成したファイルの配置と通知の設定は、ご自身で行ってください。", database_template: "用途別テンプレート", database_help: "顧客・カード台帳・企業・パスワード管理・注文・請求・従業員・取引先・サポート・資産・クラウドのテンプレートがあります。項目は最大30個まで編集できます。会社・部署・状態・テキストの候補値を、業務に合う架空の値へ置き換えると自然さを高められます。氏名やメールも候補値を使う場合は型をテキストに変更してください。実在の個人情報や実接続先は使わないでください。メール・ドメイン型はexample.invalidを使います。既定の保管庫login_urlも予約済みのexample.invalid内で、実在サービスへ接続されません。", template_loading: "読込中…", template_custom: "カスタム（項目を自由に編集）", context_title_auto: "選択した用途に合わせて自動設定", context_title_generic: "空欄時の既定タイトル：Operations archive", template_help: "テンプレート選択後に項目を編集できます。実在の個人情報や実接続先は使わないでください。", kind_phone: "\u5317\u7c73\u306e\u67b6\u7a7a\u4e88\u7d04\u96fb\u8a71\u756a\u53f7\uff08\u975e\u7a3c\u50cd\uff09", kind_domain: "example.invalid ドメイン", kind_card_reference: "無効カード参照値", kind_card_expiry: "カード期限", kind_test_postal: "テスト用郵便番号", kind_credential_preview: "合成パスワード値（実アカウントとの紐付けなし）", kind_currency: "通貨", kind_documentation_ip: "文書用IPアドレス", method_explainer: "この手法を知る", explain_how: "どういう対策か", explain_target: "どの攻撃を想定するか", explain_limit: "できないこと・限界", generating: "生成しています…", generated: "{name} を生成しました。", failed: "生成に失敗しました。",
    estimate: "暗号化ZIP {archives}個 / ダミーファイル {documents}個（上限40 ZIP・生成内容32MiB・暗号化ZIP累積64MiB）", over_limit: "分岐・階層を減らしてください。暗号化ZIPの上限は40個です。", number_input_invalid: "数値欄に、表示された範囲内の整数を入力してください。",
    download_again: "配置用ファイルを保存", operator_download: "管理者用の構成情報を保存（配置禁止）", inventory_download: "運用台帳を保存（管理者専用・配置禁止）", summary: "生成結果：ZIP {archives}個 / 文書 {documents}個 / カナリア入り {canaries}個", format_breakdown: "形式内訳",
    operator_reminder: "パスワードと構成を含む管理者専用ファイルをすべて別途保存してください。運用台帳にもURLや設定が含まれます。", operator_ack_action: "管理者専用ファイルをすべて安全な場所に保存しました", operator_ack_done: "管理者専用ファイルすべての保存を確認しました。別保管を続けてください。", discard_operator_confirmation: "管理者専用ファイルすべての保存確認がまだありません。続行すると現在のダウンロードリンクが失われます。続行しますか？", schema_limit: "項目は1〜30個にしてください。", invalid_options: "数値範囲は最小,最大の2つの数値で指定してください。"},
  en: {
    skip_to_content: "Skip to main content",
    scenario_label: "Decoy scenario", scenario_crm: "Customer account register", scenario_migration: "Customer data migration", scenario_archive: "Customer data archive", scenario_cards: "Payment card inventory", scenario_companies: "Company directory", scenario_passwords: "Credential vault", scenario_invoices: "Invoice and payment register", scenario_employees: "Employee and department register", scenario_vendors: "Vendor and partner register", scenario_orders: "Order and sales ledger", scenario_tickets: "Support ticket queue", scenario_assets: "IT asset inventory", scenario_cloud: "Cloud resource inventory", scenario_help: "Match the synthetic data schema, file names, titles and URL context to the selected business use. No real personal data is used.", directory_title_help: "Leave blank to use the title for the selected scenario.",
    env_zip_download: "Save ZIP with exact .env filename", env_direct_download: "Save file directly (browser may remove leading dot)", env_zip_note: "The ZIP contains the exact filename. Some browsers remove a leading dot from direct downloads; extract the ZIP before deployment.",
    env_layout_title: ".env layout", env_layout_label: "Configuration pattern", env_layout_switch: "Development/production switch note (production URL commented)", env_layout_standard: "Standard URL setting", env_suffix: "Environment suffix", env_variable: "Setting key", env_dev_url: "Active URL for this environment (optional)", env_dev_url_authorized: "I control this host and route it only to an isolated test endpoint without production authentication. It may receive requests from anyone who follows the URL.", env_dev_comment_label: "Development comment (optional)", env_prod_comment_label: "Production switch note (optional)", env_switch_help: "With a blank filename this creates .env.development. The development URL is active and the canary URL is a commented production alternative. The default uses example.invalid. For a custom host, confirm ownership and route it only to an isolated test endpoint without production authentication. A crawler or agent may request this active URL. The generator does not resolve or contact it. Do not enter internal or production endpoints or load the file in production configuration.",
    canary_context: "URL context", context_profile: "Purpose", context_service: "Service administration", context_billing: "Billing", context_support: "Support", context_reports: "Reports", context_auto: "Choose automatically", context_title_auto: "Automatic for selected purpose", context_title_generic: "Blank title defaults to Operations archive", context_field: "URL field name (optional; ASCII letters, digits, _) ", context_label: "Visible link label (optional)", context_help: "Adjust field names and labels to match the intended document. Blank document file names and titles follow the selected purpose. Standard .env files use it for the title and URL key; the development/production note layout uses its environment settings instead. CSV places the URL in the first record; Excel puts a link on the data sheet. The URL is not modified or fetched. Its domain and hyperlink target can still be inspected.",
    legal_title: "Japanese legal assessment (Unauthorized Computer Access Act)", legal_normal: "Normal use:", legal_risk: "Conduct that may violate the Act:", legal_scope: "General assessment for assets you are authorized to manage. The actual authority and actions matter; other laws can also apply.", legal_more: "Basis and method-by-method details", legal_police: "National Police Agency guidance",
    samples_link: "Integration samples ZIP",
    method_explainer: "About this method", explain_how: "How it works", explain_target: "Attacks it addresses", explain_limit: "Limitations",
    database_template: "Use case template", template_loading: "Loading…", template_custom: "Custom (edit columns)", template_help: "Edit the columns after selecting a template. Replacing company, department, status and text candidates with fictional values from your business context can make records more credible. Do not use real personal data or live endpoints. To provide candidate names or emails, change the kind to Text.",
    kind_phone: "Reserved non-working NANP sample number", kind_domain: "example.invalid domain", kind_card_reference: "Nonfunctional card reference", kind_card_expiry: "Card expiry", kind_test_postal: "Test postal label", kind_credential_preview: "Synthetic password value (no linked account)", kind_currency: "Currency", kind_documentation_ip: "Documentation IP address",
    save_settings: "Save settings (exclude URLs and ownership confirmations)", load_settings: "Load settings", guide_link: "Deployment & monitoring guide",
    settings_privacy_help: "Canary URL controls, URL-typed fields (including the environment endpoint), and ownership attestations are omitted. Saving settings does not detect or remove URLs or secrets in free-text fields. Generation rejects unapproved URLs, email addresses, public domains, IP addresses and recognizable common credential/card patterns in free-text inputs, except dedicated canary URL and owned-domain fields which are validated separately. Reserved examples such as example.invalid are allowed. These checks are not comprehensive endpoint or secret detection. The settings JSON retains other inputs and candidates; do not enter real data or secrets, and store it securely.",
    config_saved: "Saved settings. URLs and domain-ownership confirmations are not carried over.", config_loaded: "Loaded settings. Re-enter URLs in their URL fields and reconfirm ownership before using a decoy domain.", config_invalid: "Select valid settings JSON exported by this tool (up to 1 MiB, nesting depth at most 64); duplicate keys are rejected.",
    unsafe_setting_text: "Settings contain control or bidirectional formatting characters. Remove them before saving or loading.",
    monitoring_none: "No canary URL configured. Set up server log monitoring to detect downloads.",
    monitoring_set: "URL embedded. Verify download logging and URL-use notifications separately.",
    monitoring_counts: "Canary placements: {placements}; distinct URLs used: {used}/{supplied}; unused URLs: {unused}.",
    monitoring_placeholder: "At least one configured URL uses a reserved example/test domain. That URL cannot produce a live canary alert; use a URL issued by your monitoring service for deployment.",
    monitoring_not_placed: "A canary URL was provided, but random placement put it in none of the files. Increase placement or adjust the settings before deployment.",
    operator_files_title: "Operator-only files — keep out of deployment",
    operator_files_warning: "These files can contain passwords, canary URLs, archive layouts and verification details. Store them separately with restricted access; never upload them to the public site or include them in the deployed application.",
    workspace: "Workspace", create: "Create a decoy", running: "Running locally", browser_save: "Files are saved by your browser",
    local_mode: "● Local mode", language: "Language", intro: "Choose a file type, configure it, and generate your decoy.",
    getting_started: "Getting started", notice: "This tool generates files. Set up deployment and notification services separately.",
    select_method: "Select a method", file_type: "Choose by intended role", settings: "Settings", method_settings: "Configure the selected method",
    canary_file: "Canary file", canary_card: "Detect suspicious contact when a monitoring URL is used", nest_title: "Encrypted Deep Nest",
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
    maze_depth: "Directory levels below root", maze_files: "Decoy files per directory", maze_cross_links: "Link to other branches and parents to create browsing paths", maze_format: "Single file format for all decoys",
    directory_note: "All decoy files use the single selected format. Up to 400 directories and 16 MiB of content. Cycles are HTML links, without filesystem symlinks or recursive extraction. Crawlers that deduplicate URLs can stop revisiting pages. Canary URLs are assigned up to the number of generated files and mapped to paths in the private operator JSON. Surplus URLs remain unused. Reused URLs cannot identify the exact file.",
    encoding_desc: "Generate independent fictional candidates that match a selected business scenario, then apply layered encodings. File names, titles and schemas follow the scenario. For .env, candidates use common dotenv filenames and APP_ENV matches each filename.", decoded_format: "Decoded file format", encoding_layers: "Encoding layers", encoding_candidates: "Candidate files", encoding_codecs: "Available encodings for each layer",
    encoding_note: "Each layer is JSON with encoding and payload fields. This is not encryption. Operator JSON records the scenario, decode order, URL-to-candidate assignments and final SHA-256. Content limit: 16 MiB. A short script can decode all layers, so evaluate delay in your exploration and verification workflow. URLs beyond the candidate count remain unused. Reused URLs cannot identify the exact candidate.",
    canary_url: "Canary URL", canary_urls: "Canary URLs (one per line)", optional: "Optional", canary_help: "Enter an HTTPS URL issued by your canary service. Use a publicly reachable monitor; private IPs and local-only hostnames such as localhost and .local are rejected. DNS resolution is not checked. A blank URL cannot produce alerts. PowerPoint includes all requested records, split into slides of up to 10 rows. The standard .env layout wraps the URL in single quotes. If it contains a single quote, use the development/production note layout or another format; the note layout has separate input restrictions. URLs containing '$' are rejected by both .env layouts; choose another file format.",
    canary_note: "Use only HTTPS canary URLs issued for your account by your monitoring provider. Reading the file alone does not trigger an alert; the provider may alert when the URL is accessed. Email/document security scanners or link previews may access it automatically. An alert shows a request to the URL, not who caused it or who read the file; correlate with known scanners. The generator does not contact the URL. Whitespace and fragments after # are rejected because fragments are not sent in HTTP requests.", csv_safety_note: "CSV has no cell-type metadata. Text that could be interpreted as a formula is prefixed with an apostrophe to reduce risk. The apostrophe remains in the CSV, and spreadsheet import behavior varies; verify it in the application you use before deployment.",
    format: "File format", filename: "File name (no extension; blank = automatic; start with a letter/digit, then ASCII letters, digits, _ or -; max 64; OS reserved names are unavailable)", document_title: "Document title", document_rows: "Records in document",
    nest_desc: "Generate a policy-based password for each branching archive containing decoy files. Choose a primary format and optionally mix in occasional alternatives. Duplicates are detected and replaced as needed to keep every password unique.", layers: "Encryption layers",
    branches: "Branches to next layer", decoys: "Decoy files per ZIP", directory_depth: "Maximum folder depth within each ZIP", nest_rows: "Records per document / database",
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
    database_desc: "Generate SQLite with your chosen columns and data generators.", rows: "Number of records", table_name: "Table name", schema: "Column definitions", add_column: "+ Add column",
    database_help: "Choose a customer, card inventory, company, password vault, orders, invoices, employees, vendors, support tickets, assets or cloud inventory template. Edit up to 30 columns. Replacing company, department, status and text candidates with fictional values from your business context can make the records more credible. To provide candidate names or emails, change the kind to Text. Do not use real personal data or live endpoints. Email/domain generators use example.invalid. By default, password vault login_url values use the reserved example.invalid domain and cannot reach real services.",
    database_note: "Card data uses a clearly invalid reference only; no PAN or CVV. Password fields contain random synthetic strings that are not linked to real accounts or services; no real credentials or hashes are imported. Reading a database alone does not alert. The Password Vault template places the canary URL in one login_url record when that column exists; otherwise it uses a connection table. Other templates also use a connection table. The monitoring service alerts only if the URL is requested.",
    column_name: "Column name", data_kind: "Data generator", data_options: "Candidate values / numeric range", remove_column: "Remove",
    kind_id: "Sequence (INTEGER)", kind_name: "Full name (TEXT)", kind_email: "Email (TEXT)", kind_company: "Company (TEXT)", kind_department: "Department (TEXT)",
    kind_integer: "Integer (INTEGER)", kind_decimal: "Decimal (REAL)", kind_date: "Date (TEXT)", kind_datetime: "Date and time (TEXT)", kind_status: "Status (TEXT)", kind_text: "Text (TEXT)",
    web_desc: "Generate a static archive page.", page_title: "Page title",
    web_help: "A URL adds a link. Opening the page alone does not access the URL.",
    web_note: "This is static HTML. Login, configuration changes, access monitoring, and infinite streaming require a separate server.",
    generate: "Generate file", footer: "Use only in environments you are authorized to manage",
    generating: "Generating…", generated: "Generated {name}.", failed: "Generation failed.", number_input_invalid: "Enter a whole number within the range shown for the selected method.",
    estimate: "{archives} encrypted ZIPs / {documents} decoy files (limit: 40 ZIPs, 32 MiB of source content, and 64 MiB cumulative encrypted archives)", over_limit: "Reduce depth or branching. The limit is 40 encrypted ZIPs.",
    download_again: "Save deployment file", operator_download: "Save operator details (operator only; never deploy)", inventory_download: "Save lifecycle inventory (operator only; never deploy)", summary: "Generated: {archives} ZIPs / {documents} documents / {canaries} with canary URLs", format_breakdown: "Formats",
    operator_reminder: "Save every operator-only file separately. The lifecycle inventory can also contain URLs and settings.", operator_ack_action: "I saved all operator-only files in a restricted location", operator_ack_done: "All operator-only files are acknowledged as saved. Keep them stored separately.", discard_operator_confirmation: "You have not confirmed saving every operator-only file. Continuing will remove the current download links. Continue?", schema_limit: "Use 1–30 columns.", invalid_options: "Specify a numeric range as two numbers: min,max.",
  },
};
translations.en.workspace_create = "WORKSPACE / CREATE";
translations.ja.hint_characters = "復元メモが「別管理」と装う末尾文字数（実際のパスワード文字は含まない）";
translations.ja.hints = "復元メモのデコイを配置";
translations.ja.hints_none = "配置しない";
translations.ja.password_help = "保守メモは、別の鍵台帳を探させるためのデコイです。実際のパスワード文字は含まず、伏せ字の文字数も利用可能な手掛かりではありません。パスワード本体は管理者専用ファイルにのみ保存されます。既定の9〜13文字では、段階設定により序盤を短くし、深い階層ほど長くします。ZIP取得後はオフラインで並列試行できるため、解読成功や遅延は保証されません。単語形式の候補が重複した場合はランダム値に切り替わります。9〜13文字でも解読困難な場合があり、所要時間はZIP形式や攻撃設備に左右されます。";
translations.en.assets_eyebrow = "DECEPTION ASSETS";
translations.en.workspace_badge = "LOCAL WORKSPACE";
translations.ja.maze_estimate = "ディレクトリ{directories}個・文書{documents}個（上限400ディレクトリ）";
translations.en.maze_estimate = "{directories} directories · {documents} documents (limit: 400 directories)";
translations.ja.maze_over_limit = "上限400ディレクトリを超えています。階層数か分岐数を減らしてください。";
translations.en.maze_over_limit = "This exceeds the 400-directory limit. Reduce depth or branching.";
const methodExplanations = {
  ja: {
    env: {title:"カナリアファイル", how:"もっともらしい文書や設定ファイルに監視サービス発行のURLを入れ、URL利用時に通知する方式です。", target:"`.env`・DB・設定バックアップを探し、見つけた接続先やURLを試す攻撃者を想定します。ファイル形式を問わず取得時点はサーバーやOSログで監視します。", limit:"単体のカナリア生成ではURLを1つ使います。暗号化ネスト、ディレクトリ・メイズ、エンコーディング・メイズはURL一覧からファイルごとに割り当て、台帳に対応を記録します。ファイルの取得・閲覧だけではURL型トークンは発火しません。通信遮断やURLを試さない手順では通知されず、発火してもAIによるアクセスかは判定できません。"},
    database: {title:"デコイ・データベース", how:"実在人物を含まない、もっともらしいテーブルと架空レコードのDBを作ります。指定項目から最大10,000件を生成します。パスワード管理テンプレートでは、カナリアURLをランダムに選んだ1件のlogin_urlへ配置し、password値は保ちます。", target:"`.db`を探して顧客・注文情報を持ち出す攻撃者と、盗んだ後に本物らしさを検証する攻撃者を想定します。", limit:"本ツールは単独テーブルと架空データを作ります。本番DBへの自動接続・読み取り監視はありません。実データや再現し過ぎたスキーマを使わず、本物も同時に漏れ得る前提で運用します。関連技術のデータ・ディルーションは、本番DBに大量の合成レコードを混ぜ、流出後の選別と利用を難しくする構想です。効果は未検証で、本ツールでは技術紹介のみを行い、実装しません。"},
    web: {title:"スタティック・デコイ・ポータル", how:"アーカイブや管理ポータルに見える静的HTMLを作ります。", target:"公開URLや管理画面らしいサブディレクトリを探索し、リンクやファイルをたどる攻撃を想定します。", limit:"静的ページです。認証、ログイン状態、設定変更、アクセス制御、通知処理は実装しません。画面を開くだけではリンク先のカナリアURLにアクセスしません。"},
    nest: {title:"エンクリプテッド・ディープ・ネスト", how:"暗号化ZIPを分岐・多層化し、各層に文書や次のアーカイブを混在させます。選択形式を中心に、Excel・SQLite・.envなども時々混ぜられます。パスワードと復元メモの対応は管理者専用ファイルに分けます。復元メモは別の鍵台帳があるよう示しますが、実際のパスワード文字は含みません。ファイルごとに異なるカナリアURLを割り当てると接触先を識別でき、URLを再利用した場合はグループまでの識別になります。認証情報保管庫シナリオでは、.envにシナリオ別環境変数、その他の形式に架空login_url項目を使い、password値は変えません。", target:"バックアップや設定を急いで一括回収する攻撃者と、候補を順に展開して秘密を探す攻撃者を想定します。", limit:"持ち出した後に並列・オフラインで解析する攻撃者は、現場の時間を使いません。強いパスワードなら解読不能で、反対にヒントが露骨なら罠と見抜かれます。通常データの暗号化やバックアップの代替ではありません。"},
    stream: {title:"インフィニット・ストリーム", how:"認証付きの隔離配信経路で、接続中は総容量・総時間で終わらない応答を返します。帯域と同時接続を抑え、管理者が停止できます。", target:"ファイル取得を完了するまで待つ、全量ダウンロード型の攻撃者を想定します。短時間で撤収したい攻撃者の時間と注意を拘束する狙いです。", limit:"バックエンドは無通信が5秒続くと接続を終了します。受信側が読み取らず書き込みが詰まった場合も対象です。部分取得、並列探索、明示的な切断でも迂回され、接続自体が罠と疑われることがあります。GUIはサーバーを起動せず、認証付き隔離経路・開始検知・負荷管理は配置側で必要です。"},
    directory_maze: {title:"ディレクトリ・メイズ", how:"実際のフォルダーとHTMLリンクで有限の階層・分岐を作り、文書や設定ファイルを配置します。認証情報保管庫シナリオでは、.envにシナリオ別環境変数、その他の形式に架空login_url項目を使い、password値は変えません。", target:"サブディレクトリ名を総当たりし、見つかったファイルを広く収集するクローラやAI生成ツールを想定します。", limit:"階層・ファイル数は有限で、URL重複排除や並列化で探索は速くなります。HTMLを全走査するだけの攻撃者には遅滞効果がなく、重要情報の見落としを保証しません。"},
    encoding_maze: {title:"エンコーディング・メイズ", how:"選択した業務シナリオに合わせ、候補ごとに独立した架空レコード・ファイル名・タイトルを作ってから多段変換します。認証情報保管庫では、.envにシナリオ別環境変数、その他の形式に架空login_url項目を使い、password値は変えません。", target:"取得後に複数候補を復元・正規化し、どれが価値ある情報か見極めようとする攻撃者を想定します。", limit:"暗号化ではありません。一括デコードは容易で、データベース自体が読むだけで通知するわけでもありません。"},
  },
  en: {
    env: {title:"Canary File", how:"Embeds a monitoring-service-issued URL in a plausible document or configuration file; the service alerts when the URL is used.", target:"Intruders searching for .env files, databases and configuration backups, then trying discovered endpoints.", limit:"A standalone canary file uses one URL. Encrypted Deep Nest, Directory Maze and Encoding Maze accept up to 400 URLs and record file assignments in their private operator inventory. If a URL is reused, an alert cannot identify the exact file. Reading or downloading a file alone does not trigger an HTTP token. Network blocking or workflows that never test URLs prevent alerts. An alert does not identify whether a human or AI caused it."},
    database: {title:"Decoy Database", how:"Creates a plausible schema populated only with synthetic records, up to 10,000 rows. The Password Vault template puts its canary URL in one randomly selected login_url record and leaves the password value unchanged.", target:"Intruders collecting .db files for customer or order data, including those who validate stolen data later.", limit:"This creates a standalone database; it does not connect to production or monitor reads. Avoid importing real data. A real database can still leak alongside decoys. The related Data Dilution concept mixes many synthetic records into a production database to make leaked data harder to select and use. Its effectiveness is unverified; this tool only introduces the concept and does not implement it."},
    web: {title:"Static Decoy Portal", how:"Creates a static page that resembles an archive or operations portal.", target:"Attacks that enumerate public URLs and admin-like subdirectories, then follow links or collect files.", limit:"Static HTML has no authentication, session, setting changes, access control or alert delivery. Opening the page does not fetch its canary link."},
    nest: {title:"Encrypted Deep Nest", how:"Builds branching layers of encrypted ZIP files containing decoy files and more archives. The selected primary format stays common; weighted occasional alternatives can include Excel, SQLite and .env. Passwords and the mapping to recovery-note files stay in the operator-only file. The notes imply a separate key register but disclose no password characters. A distinct canary URL per file can identify which assigned file was contacted; reused URLs identify only a group. In the Password Vault scenario, .env files use the scenario's environment variable and other formats use the synthetic login_url field; password values stay unchanged.", target:"Intruders rapidly collecting backups/configuration and those who open candidate archives to find secrets.", limit:"The selected primary format is used for about 75% of decoys when format mixing is enabled. Parallel/offline analysis after exfiltration adds no on-site delay. Strong passwords can be infeasible to crack; obvious clues reveal the trap. This does not replace normal encryption or backups."},
    stream: {title:"Infinite Stream", how:"An authenticated, isolated endpoint returns data without a total size or duration cutoff while connected, with bandwidth/concurrency caps and operator stop.", target:"Bulk-download workflows that wait for the file to finish, occupying a rushed intruder's time and attention.", limit:"The backend closes a connection after five seconds without socket activity, including when a stalled write blocks delivery. Partial downloads, parallel discovery and intentional disconnects also bypass it; an endless response may itself look suspicious. The GUI does not start it; deployment, authentication, start-event monitoring and capacity limits belong in the host environment."},
    directory_maze: {title:"Directory Maze", how:"Creates finite real directories and HTML links with branches, documents and configuration files. In the Password Vault scenario, .env files use the scenario's environment variable and other formats put the canary in a synthetic login_url field without changing password values.", target:"Crawlers and AI-generated tools that enumerate subdirectory names and download discovered files.", limit:"The tree is finite. URL deduplication and parallelism speed exploration; a crawler that only indexes links gains little delay. It cannot guarantee that important files are missed."},
    encoding_maze: {title:"Encoding Maze", how:"Creates independent synthetic records, file names and titles for the selected business scenario, then applies layered encodings. In the Password Vault scenario, .env files use the scenario's environment variable and other formats put the canary in a synthetic login_url field without changing password values.", target:"Intruders who restore and inspect multiple candidates after collection to identify useful information.", limit:"This is not encryption; batch decoding is easy. It does not alert when read."},
  },
};
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
Object.assign(translations.ja, {fake_title:"フェイクトラップ", fake_card:"警告や待機表示で再確認を促す", dilution_title:"データ・ディルーション", dilution_card:"本物に偽レコードを混ぜて選別を困難に", honeyword_title:"プリビレッジ・ハニーワード・セッション", honeyword_card:"偽パスワードで隔離デコイへ誘導", technology_only:"技術紹介のみです。生成や本番環境への変更は行いません。", fake_desc:"警告または待機表示の静的HTMLを生成します。", fake_variant:"表示パターン", fake_warning:"異常アクセスの警告", fake_reported:"通報済みの警告", fake_waiting:"認証中のスピナー", fake_note:"表示だけの静的ページです。検知・通報・認証・情報収集は行わず、外部への通信やプログラム送信もありません。監視・通知は配信側で別途設定してください。通報済みの表示は実際の通報を意味しません。正規利用者の誤接触に配慮してください。"});
Object.assign(translations.en, {fake_title:"Fake Trap", fake_card:"Prompt reassessment with warnings or waiting screens", dilution_title:"Data Dilution", dilution_card:"Mix real and decoy records to hinder selection", honeyword_title:"Privilege Honeyword Session", honeyword_card:"Route decoy password use to an isolated decoy", technology_only:"Technology overview only. No files are generated and production systems are not changed.", fake_desc:"Generate a static warning or waiting page.", fake_variant:"Display pattern", fake_warning:"Unusual access warning", fake_reported:"Reported warning", fake_waiting:"Authentication spinner", fake_note:"This static page only displays a message. It does not detect, report, authenticate, collect information, communicate externally or send software. Configure monitoring and alerts separately. The reported message does not mean a report was sent. Avoid exposing legitimate users to the page."});
methodExplanations.ja.web.how += " ロー・インタラクション・デコイの簡易な静的画面例ですが、状態を保持する応答はありません。";
methodExplanations.en.web.how += " This is a simple static example of a low-interaction decoy; it does not maintain interactive state.";
Object.assign(methodExplanations.ja, {
 fake_trap:{title:"フェイクトラップ",how:"警告またはスピナーを表示する静的な画面を作ります。通報や認証は実行しません。",target:"画面を読んで状況を判断するAIや人間を想定します。",limit:"表示を無視する攻撃には効果が限られます。検知・通知は配信側で別途設定し、効果と誤接触を評価します。"},
 data_dilution:{title:"データ・ディルーション",how:"本物と大量の合成レコードを混在させ、流出後の真偽判定を難しくする構想です。ツールでは紹介のみを行います。",target:"顧客データを大量取得し、販売・利用する攻撃を想定します。",limit:"本物の流出は防げません。判別機構と業務への影響が課題で、効果と費用は未検証です。"},
 honeyword:{title:"プリビレッジ・ハニーワード・セッション",how:"特権アカウントの偽パスワードが使われたとき、独立した偽セッションに誘導する設計です。紹介のみで認証への組み込みは行いません。",target:"偽認証情報を試して偽環境を操作する攻撃者を想定します。",limit:"偽情報を試さない場合は検知できません。正規MFA、権限分離、IdP対応、誤発火と通知の運用が必要です。"}
});
Object.assign(methodExplanations.en, {
 fake_trap:{title:"Fake Trap",how:"Creates a static warning or spinner. It does not report or authenticate.",target:"AI agents and people who read the page and assess the situation.",limit:"It may not affect automated clients that ignore the display. Configure monitoring separately and evaluate delay and legitimate-user impact."},
 data_dilution:{title:"Data Dilution",how:"A concept that mixes genuine and synthetic records to make leaked data harder to distinguish. This is an overview only.",target:"Bulk theft and resale or use of customer data.",limit:"It does not prevent real records from leaking. Classification and business integration require careful design; cost and effectiveness are unverified."},
 honeyword:{title:"Privilege Honeyword Session",how:"A design that routes use of a privileged account's decoy password to an isolated decoy session. This is an overview, not an authentication integration.",target:"Intruders who try decoy credentials and interact with the decoy environment.",limit:"No alert occurs if the decoy is not tried. Real MFA, isolation, IdP compatibility, false positives and notification need separate design."}
});
Object.assign(methodOutcomes.ja, {fake_trap:{deception:"周辺環境に合う警告や待機表示を使います。実際の通報や認証を行うものではありません。",delay:"警告を解釈した攻撃者の再確認を狙います。画面を読まない自動処理は別の罠で評価します。"},data_dilution:{deception:"関連履歴も含めた合成データを整え、真偽の候補を区別しにくくする考え方です。",delay:"取得後の選別・検証を難しくし、データの利用価値を下げる可能性があります。"},honeyword:{deception:"デコイ画面の状態と操作結果を自然に保ちます。",delay:"偽セッションの探索に時間を使わせ、通知と対応の機会を得ることを狙います。"}});
Object.assign(methodOutcomes.en, {fake_trap:{deception:"Use a warning or waiting display suited to the surrounding environment. No report or authentication is performed.",delay:"The message may prompt reassessment; evaluate other decoys for clients that ignore it."},data_dilution:{deception:"Plausible synthetic records and relationships can make candidates harder to distinguish.",delay:"Post-leak selection and verification may become harder and reduce data value."},honeyword:{deception:"Keep decoy screen state and responses consistent.",delay:"Time spent in the decoy may provide an opportunity for detection and response."}});
for (const lang of ["ja", "en"]) {
  methodLegal[lang].fake_trap = methodLegal[lang].web;
  methodLegal[lang].data_dilution = methodLegal[lang].database;
  methodLegal[lang].honeyword = methodLegal[lang].web;
}
Object.assign(translations.en, {category_intro:"Tags describe each method's intended roles. A method can have several roles; results depend on deployment and attacker behavior.", category_guide:"What the tags mean", category_description:"Detection: identify decoy contact or use. Delay: add work for the attacker. Decoy lure: draw exploration to fake assets or screens. Post-leak disruption: make stolen candidates harder to assess or use. AI attacks considered: attacks using AI agents are included in evaluation; the method may also affect human or scripted attacks. Monitoring or alerts may require separate setup, and no effect is guaranteed.", tag_detect:"Detection", tag_delay:"Delay", tag_lure:"Decoy lure", tag_leak:"Post-leak disruption", tag_ai:"AI attacks considered"});
Object.assign(translations.ja, {flow_title:"仕組みの流れ", flow_details:"仕組み・対象・限界を詳しく見る"});
Object.assign(translations.en, {flow_title:"How it works", flow_details:"More about the mechanism, threats and limits"});
Object.assign(translations.ja, {legal_disclaimer:"以下は日本法・米国法に関する一般的な一見解です。個別の適法性を保証するものではありません。実際の導入前に、適用地域に詳しい法律の専門家へ確認してください。", legal_us_title:"米国法上の見解（連邦法・州法）", legal_us_risk:"具体的な注意点", legal_us_scope:"連邦法のほか州法・契約等が関係し、通信の内容や保存方法、関係者の所在地で評価が変わります。自己管理の設備であっても通信内容の監視が常に認められるわけではありません。", legal_us_more:"米国法の根拠と補足"});
Object.assign(translations.en, {legal_disclaimer:"These are general interpretations of Japanese and U.S. law, not a guarantee for your situation. Before deployment, consult a legal professional familiar with the applicable jurisdictions.", legal_us_title:"U.S. legal assessment (federal and state law)", legal_us_risk:"Specific considerations:", legal_us_scope:"Federal and state laws and contracts may apply; the content collected, storage method and locations of those involved matter. Controlling a system does not automatically authorize interception of its communications.", legal_us_more:"U.S. legal sources and context"});
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
Object.assign(translations.ja, {flow_if:"効果が期待できる場合", flow_else:"効果が弱まる条件", flow_response:"検知・対応の準備"});
Object.assign(translations.en, {flow_if:"When it may help", flow_else:"When the effect may be reduced", flow_response:"Detection and response setup"});
Object.assign(methodFlows.ja, {
 env:{context:"例：運用者が発行済みの監視URLを、設定ファイルや業務文書に埋め込みます。",steps:[["1. 偽ファイルを配置","秘密情報に見える文書を、権限のある探索経路に置きます。"],["2. 攻撃者が取得","設定ファイルを回収し、記載されたURLを接続先として調べます。"],["3. URLを試す","攻撃者やスキャナーが監視URLへHTTPリクエストを送ります。"],["4. 通知して対応","監視サービスが要求を受ければ通知し、担当者がログを調査します。"]],ifCase:"URLを試す行動が、侵害や持ち出しを調べる手掛かりになります。",elseCase:"ファイルを読んだだけ、URLを試さない、通信が遮断される場合はURL通知が発生しません。",response:"監視URLの発行・通知先と、ファイル取得を記録するWeb／OS監査を別々に設定します。",note:"通知は設定されたサービスからの要求記録であり、攻撃者本人の特定や対応前の遮断を保証しません。"},
 database:{context:"例：顧客台帳に見える、合成レコードのみのSQLiteを独立したデコイ領域に置きます。",steps:[["1. 偽DBを用意","架空の顧客や注文を含む単一テーブルを生成します。"],["2. 本物らしく配置","業務のバックアップに見える名前や経路で、権限のある場所に置きます。"],["3. 攻撃者が回収","発見したDBを持ち帰り、本物の候補と比較します。"],["4. 真偽を確認","候補ごとに内容や関連性を確認すると、選別に時間がかかる可能性があります。"]],ifCase:"偽物を本物と誤認したり、確認の途中で本物を見落としたりする可能性があります。",elseCase:"偽DBを無視する、本物を別途取得する、全候補を一括で持ち出す行動も可能です。",response:"配信ログやOS・DB監査を別途設定します。カナリアURLを試された場合の通知も別のイベントです。",note:"本番DBと混ぜる方式ではありません。DBの閲覧だけで自動通知されず、本物の流出も防げません。"},
 web:{context:"例：アーカイブや管理ポータルに見える静的ページをデコイ用の経路に配置します。",steps:[["1. ページを用意","タイトルと、必要なら運用者が指定したカナリアURLへのリンクを設定します。"],["2. 攻撃者が探索","管理画面やバックアップを探す途中で、ページにたどり着きます。"],["3. 内容を調べる","表示されたページやリンクを確認し、実際の管理情報か判断します。"],["4. 接触を記録","配信側にアクセスログを設定していればページへの要求を確認できます。"]],ifCase:"ページやリンクを調べる場合は、偽の候補を確認する作業が増える可能性があります。",elseCase:"ページを無視する、直接別経路に進む、リンクを試さない場合もあります。",response:"ページ要求の監視と、リンク先のカナリアサービスの通知を別々に設定します。",note:"生成物は静的HTMLです。ログイン機能や状態保持はなく、開いただけではリンク先へアクセスしません。"},
 nest:{context:"例：バックアップ風のZIP内に、偽文書とさらに別の暗号化ZIPを分岐させて置きます。",steps:[["1. 階層を作る","暗号化ZIPの各層に、偽文書と次のZIPを混在させます。"],["2. 対応を保管","各ZIPのパスワードと構成情報は運用者専用ファイルに分けます。"],["3. 攻撃者が探索","候補ごとにパスワードを探し、開けたものの内容を確認します。"],["4. 判断を繰り返す","複数の分岐を確認する場合、候補の選択と展開に時間を使い得ます。"]],ifCase:"途中の候補が本物と見分けられず、未確認の枝にも有用な情報があり得る場合、調査を続けるほど手間が増え、打ち切れば本物も見落とす可能性があります。偽文書を1つ見つけても、未確認の枝まで全て偽物とは断定できません。",elseCase:"途中で不自然な名前・構造や既知の本番情報との矛盾が見つかれば、罠だと疑われることがあります。ただし、それだけで未確認の内容まで確定するとは限りません。また、見破らなくても全体を持ち出して後で並列解析すれば現場での展開時間は減りますが、持ち出し後の選別作業は残り得ます。本物を別経路で得る場合も、この罠の影響は小さくなります。",response:"アクセス監査や、使用されたカナリアURLの通知を別途設定します。管理者専用の鍵台帳は公開しません。",note:"最後まで見分けられないことは保証できません。ZIPを開くだけでは自動通知されず、実際の効果は比較試験で確認します。"},
 stream:{context:"例：隔離された配信経路を、取得完了まで待つバックアップに見立てます。",steps:[["1. 専用サーバーを用意","生成されたサンプルを隔離先に設置し、認証・帯域・同時接続数を設定します。"],["2. 要求を受ける","認証された要求に対して、サーバーがダミーデータの配信を始めます。"],["3. 配信が続く","接続中は総容量・総時間で終わらず、完了を待つ相手の時間を使わせます。"],["4. 開始を把握","サーバーの開始イベントを収集し、担当者が確認・停止できます。"]],ifCase:"全量のダウンロードが終わるまで待つ相手には、対応する時間を得られる可能性があります。",elseCase:"部分取得、切断、並列探索や無通信タイムアウトで、待たずに別の行動を取れます。",response:"サーバーの起動、ログ収集・通知、接続・帯域制限と停止手順を配信側で設定します。",note:"ツールはサーバーを自動起動しません。無通信が5秒続く接続は終了し、攻撃者の拘束は保証されません。"},
 directory_maze:{context:"例：archive／reports／backupなどの階層に偽ファイルを分散させます。",steps:[["1. 階層を生成","有限のディレクトリと偽文書を作り、必要なら別の枝へHTMLリンクを張ります。"],["2. 隔離先に配置","静的配信先で正規利用者の経路と分け、アクセスログを設定します。"],["3. 攻撃者が探索","ディレクトリやリンクを巡り、見つけたファイルを取得します。"],["4. 候補を確認","複数の文書の中から目的の情報を選ぶ場合、追加の確認が生じ得ます。"]],ifCase:"一つずつ巡り、各ファイルを確認する探索では、追加の要求や選別に時間を使い得ます。",elseCase:"並列探索やURLの重複排除、一括取得後のオフライン解析で、現場での遅れは小さくなります。",response:"配信ログの監視と、埋め込んだカナリアURLの通知を設定し、管理者用の対応表は別保管します。",note:"生成される階層は有限です。重要情報の見落としや通知の到達を保証しません。"},
 encoding_maze:{context:"例：架空の請求情報などを複数候補に分け、それぞれをBase64などで多段変換します。",steps:[["1. 候補を作る","業務シナリオに合わせて、異なる架空レコードやファイル名を用意します。"],["2. 多段変換","各候補を複数のエンコーディング層に包みます。暗号化ではありません。"],["3. 攻撃者が復元","取得後に形式を読み取り、各層をデコードします。"],["4. 内容を選別","復元した候補を比較して、価値がある情報かを判断します。"]],ifCase:"復元後の内容を個別に判断する場合、候補の確認作業が増える可能性があります。",elseCase:"既知の形式ならスクリプトで一括デコードでき、並列化すれば作業が短縮されます。",response:"取得を知るには配信側の監視が必要です。URLを試した場合のカナリア通知と区別します。",note:"オフラインでの復元・閲覧は自動検知できません。デコード順とURL対応は運用者用ファイルに保存します。"},
 fake_trap:{context:"例：通常使わないデコイ経路に『通報済み』の表示や認証中スピナーを置きます。",steps:[["1. 表示を選ぶ","警告、通報済み、認証中のいずれかの静的HTMLを生成します。"],["2. デコイ経路に配置","自組織の管理下に置き、正規利用者や監視ツールの誤接触を避けます。"],["3. 相手が表示を見る","画面を読むAIや人が、検知された可能性について再判断します。"],["4. 防御側が確認","アクセスログを別途監視していれば、経路への接触を確認できます。"]],ifCase:"警告を信じて調べ直す、待機を続けるなどの場合に、探索が遅れる可能性があります。",elseCase:"警告を読まないスクリプトや、別経路を並列に進む攻撃には、この表示だけでは働きません。",response:"配信側でログと内部通知を設定し、接触した正規利用者への対応も準備します。",note:"画面は実際に通報・認証・情報収集を行いません。スピナーも表示のみで接続を維持しません。"},
 data_dilution:{context:"例：本物1万件と架空100万件を混ぜた場合、無作為に1件を選ぶと約99%は偽物です。",steps:[["1. 本物と偽物を混ぜる","関連する架空レコードも整え、同じ流出対象に大量の候補を用意する構想です。"],["2. 正規業務を維持","運用者は保護された判別機構を使い、本物だけを検索・集計します。"],["3. 混在データが流出","攻撃者が大量取得しても、個々の候補の真偽がすぐ分かるとは限りません。"],["4. 攻撃者が選別","外部情報と照合しても複数の説明が成り立つ場合、正解の判断が難しくなり得ます。"]],ifCase:"本物を高い精度で選別できなければ、流出データの利用・取引価値が下がる可能性があります。",elseCase:"選別せず全件を公開する、外部情報で絞る、判別機構も侵害する場合を別途評価します。",response:"判別台帳・アクセス権を分離し、DB読み取りや外部転送の監査と対応手順を設計します。",note:"技術紹介のみで実装はありません。99%は無作為抽出の割合で、被害軽減率ではなく、本物も流出します。"},
 honeyword:{context:"例：管理者アカウントの正規パスワードとは別に、認証側で検知用の偽パスワードを用意します。",steps:[["1. 認証側に偽候補を登録","対象アカウントに正規パスワードと区別できる偽パスワードを登録します。外部ファイルへの配置は必要ありません。"],["2. 攻撃者が試行","総当たりなどでログインを試みる場合や、流出したデータ・ディルーションの偽認証情報を試す場合を想定します。"],["3. 一致で分岐","登録済みの偽パスワードに一致した場合だけ、本番認証を成立させず独立した偽セッションへ誘導します。"],["4. 通知・操作観測","偽セッションへの移行を通知し、偽画面での操作を記録します。"]],ifCase:"試行された値が登録済みの偽パスワードに一致し、攻撃者が偽環境を調べれば、検知・遅滞につながる可能性があります。",elseCase:"偽候補に一致しなければ誘導されません。試行回数や偽候補の選び方によっては総当たりで一致しにくく、正規利用者の誤入力やMFAの差も課題です。",response:"正規認証とMFA、試行制限を維持し、偽セッションの権限・データ・ログを本番から隔離します。試行予算と誤発火を評価します。",note:"技術紹介のみで認証連携は未実装です。一般の誤パスワードすべてを誘導せず、総当たりの検知・阻止を保証しません。"}
});
Object.assign(methodFlows.en, {
 env:{context:"Example: place a monitoring-service URL supplied by the operator in a decoy configuration file or document.",steps:[["1. Place a decoy","Put a plausible-looking file on an authorized discovery path."],["2. Intruder collects it","The intruder finds the file and inspects the apparent endpoint."],["3. URL is requested","An intruder or scanner sends an HTTP request to the monitoring URL."],["4. Alert and investigate","If the monitoring service receives the request, it alerts the responder to inspect logs."]],ifCase:"A URL request can provide a lead for investigating access or exfiltration.",elseCase:"Reading alone, never testing the URL, or blocked outbound traffic produces no URL alert.",response:"Configure the monitoring service and alert destination separately from web or OS auditing of file retrieval.",note:"An alert records a request, not the identity of an attacker; timely response and containment are not guaranteed."},
 database:{context:"Example: place a SQLite file containing only synthetic customer records in a separate decoy area.",steps:[["1. Build the decoy","Generate a single table with fictional customer or order records."],["2. Place it plausibly","Use a backup-like name and authorized location relevant to the environment."],["3. Intruder collects candidates","The intruder takes the decoy and may compare it with other database files."],["4. Verify contents","Checking each candidate's records and context may add selection time."]],ifCase:"An intruder may mistake a decoy for real data or stop checking before finding a real candidate.",elseCase:"The intruder may ignore the decoy, obtain the real database elsewhere, or collect everything in bulk.",response:"Configure hosting logs, OS or DB read auditing separately; a canary URL request is a distinct event.",note:"This is a separate decoy database, not production-record mixing. Reading alone does not alert or prevent a real leak."},
 web:{context:"Example: put a static archive or operations portal lookalike on a dedicated decoy path.",steps:[["1. Prepare the page","Choose a title and optionally a link to an operator-supplied canary URL."],["2. Intruder explores","The page is encountered while looking for an administrative area or backup."],["3. Inspect contents","The intruder reviews the page or link and judges whether it leads to useful data."],["4. Record contact","Hosting access logs can record a request when separately configured."]],ifCase:"Inspecting the page and its link may add candidate-checking work.",elseCase:"The intruder may ignore the page, use another route, or never request the link.",response:"Configure monitoring for page requests and canary-service alerts as separate events.",note:"The generated page is static: no login or persistent state, and opening it does not request the linked URL."},
 nest:{context:"Example: a backup-like archive contains fictional documents and branching encrypted ZIPs.",steps:[["1. Build layers","Place decoy documents and nested ZIPs across multiple branches."],["2. Protect the mapping","Keep passwords and structure in a separate operator-only companion."],["3. Intruder explores","The intruder searches for passwords, opens candidates and inspects their contents."],["4. Repeat selection","Checking several branches may consume time for choosing and opening candidates."]],ifCase:"If candidates remain indistinguishable during exploration and unchecked branches may contain useful information, continuing adds work while stopping risks missing real data. Finding one fake document does not prove every unchecked branch is fake.",elseCase:"Unnatural names or structure, or a contradiction with independently known production information, may raise suspicion; this does not necessarily establish what is in unchecked branches. Without identifying a trap, an intruder can also collect everything and analyze it in parallel later, reducing on-site delay while potentially still facing selection work. Obtaining real data through a separate route can also reduce the effect.",response:"Configure access auditing or canary-use alerts separately. Never deploy the private password inventory.",note:"Indistinguishability through the final branch is not guaranteed. Opening a ZIP alone does not alert; assess actual effectiveness through controlled comparisons."},
 stream:{context:"Example: an isolated download endpoint resembles a backup that a client may wait to complete.",steps:[["1. Prepare a server","Deploy the generated sample in isolation; configure authentication, bandwidth and concurrency limits."],["2. Receive a request","The server begins delivering dummy data to an authenticated requester."],["3. Keep streaming","While connected, the response has no total size or duration cutoff."],["4. Observe the start","A separately collected start event can prompt investigation and operator stop."]],ifCase:"A client waiting for the full download may give responders additional time.",elseCase:"Partial retrieval, disconnecting, parallel exploration or an inactivity timeout ends or bypasses the wait.",response:"Start and monitor the server separately; set up logs, alerts, limits and an operator stop procedure.",note:"The tool does not start the server. A connection with five seconds of inactivity closes; attacker delay is not guaranteed."},
 directory_maze:{context:"Example: distribute decoy files across archive, reports and backup directories.",steps:[["1. Generate a tree","Create finite directories and fictional files, optionally linking branches with HTML."],["2. Host in isolation","Separate it from legitimate paths and configure hosting access logs."],["3. Intruder explores","The intruder follows directories or links and collects files."],["4. Check candidates","Finding useful-looking data may involve inspecting additional documents."]],ifCase:"Sequential traversal and inspection may add requests and selection work.",elseCase:"Parallel crawling, URL deduplication and bulk offline analysis may reduce on-site delay.",response:"Monitor hosting logs and canary URL use separately; retain the operator mapping privately.",note:"The tree is finite. Missing real information or receiving a timely alert is not guaranteed."},
 encoding_maze:{context:"Example: wrap several independent fictional invoice candidates in multiple encoding layers.",steps:[["1. Create candidates","Generate distinct fictional records and filenames for the chosen business scenario."],["2. Encode in layers","Wrap each candidate in multiple encodings; this is not encryption."],["3. Intruder decodes","After collection, the intruder reads the format and restores each layer."],["4. Assess content","The restored candidates are compared to identify useful information."]],ifCase:"Individual content assessment may add selection work after decoding.",elseCase:"Known formats can be decoded in bulk and parallelized to reduce the work.",response:"Use hosting-side monitoring for retrieval; distinguish it from alerts when a canary URL is requested.",note:"Offline decoding and reading are not automatically detected. Decode order and URL mappings are kept in the operator file."},
 fake_trap:{context:"Example: place a 'reported' warning or authentication spinner at an otherwise unused decoy path.",steps:[["1. Choose a display","Generate static HTML for an unusual-access warning, reported message or spinner."],["2. Deploy the page","Host it on an authorized path and avoid accidental access by legitimate users or monitors."],["3. A visitor reads it","An AI agent or person may reassess whether access has been detected."],["4. Defender observes","Separately configured hosting logs can record contact with the path."]],ifCase:"A visitor who investigates the warning or keeps waiting may spend additional time.",elseCase:"A script that ignores the display, or parallel exploration of another route, can bypass this effect.",response:"Configure hosting logs and internal alerts; prepare a response for legitimate users who encounter the page.",note:"The page does not actually report, authenticate or collect information. The spinner does not keep a server connection open."},
 data_dilution:{context:"Example: among 10,000 genuine and 1,000,000 synthetic records, a uniformly random single record is about 99% synthetic.",steps:[["1. Mix candidates","The concept adds many plausible synthetic records and related data to the same leak target."],["2. Maintain legitimate use","Authorized operations rely on a protected mechanism to distinguish real records."],["3. Mixed data leaks","An intruder retrieves the dataset but may not immediately know which records are genuine."],["4. Select candidates","External comparisons can still leave multiple plausible explanations and uncertain answers."]],ifCase:"If real records cannot be selected accurately, leaked data may become less useful or valuable to a buyer.",elseCase:"Evaluate publication without selection, external matching, and compromise of the classification mechanism separately.",response:"Design separated classification data and permissions, database read/transfer auditing and incident response.",note:"Concept overview only: no implementation. The 99% is a random-sample proportion, not a damage-reduction rate; real records still leak."},
 honeyword:{context:"Example: configure a privileged account with decoy passwords separate from its real password.",steps:[["1. Register decoy candidates","Configure decoy passwords for the account in the authentication system. Placing them in an external file is not required."],["2. Attacker attempts login","Consider password guessing or use of decoy credentials leaked through a Data Dilution design."],["3. Branch on a match","Only a registered decoy-password match routes to an isolated session; production authentication remains unsuccessful."],["4. Alert and observe","Alert on the decoy session and record its subsequent actions."]],ifCase:"If an attempt matches a registered decoy password and the attacker explores the fake environment, detection and delay may result.",elseCase:"No decoy session is issued without a match. Match probability depends on the attempt budget and decoy selection; legitimate mistakes and MFA differences also matter.",response:"Preserve real authentication, MFA and rate limits; isolate decoy permissions, data and logs. Evaluate attempt budgets and false positives.",note:"Concept overview only; authentication integration is not implemented. Ordinary incorrect passwords do not all trigger a decoy, and detecting or stopping every guessing attack is not guaranteed."}
});
// State the compromise stage explicitly; no scenario guarantees containment.
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
methodFlows.ja.env.ifCase = "持ち出されたファイルのURLが後から外部接続可能な環境で試されても、監視先に要求が届けば接触を検知できる可能性があります。通知される時刻・接続元IP・User-Agent等は、サービスや設定によって異なります。";
methodFlows.ja.env.elseCase = "踏み台・VPN・サンドボックスからの要求なら、観測されるIP等はその中継・実行環境を示し、攻撃者本人を特定できるとは限りません。ファイルが拡散されると、第三者やスキャナーのアクセスも混ざり、元の攻撃者との区別が難しくなります。通信が遮断される、URLが試されない場合は通知されません。";
methodFlows.ja.env.response = "受信先と通知を別途設定し、記録項目・保持期間を確認します。配置先とURLの対応を管理者専用台帳で保管し、通知をアクセス・認証ログや既知のスキャンと照合して調査します。";
methodFlows.ja.env.note = "このURL型カナリアは、ファイルを読む・開く・実行するだけでは発火せず、URLへの実際の要求が必要です。外部接続できても要求がなければ通知されません。送信元だけで攻撃者本人と断定できず、即時通知も保証されません。";
methodFlows.en.env.ifCase = "Even after a decoy file is exfiltrated, a later request from an environment with external connectivity may trigger detection if it reaches the monitoring endpoint. Available timestamps, source IPs, user agents and other fields depend on the service and its configuration.";
methodFlows.en.env.elseCase = "With a relay, VPN or sandbox, the observed IP and other signals may describe that intermediary or execution environment rather than identify the attacker. If the file spreads, third-party users and scanners may trigger the same URL, making attribution harder. No alert occurs if the URL is not requested or traffic is blocked.";
methodFlows.en.env.response = "Configure the receiving service and alerts, and review recorded fields and retention. Keep the URL-to-placement mapping in an operator-only inventory and correlate alerts with access logs, authentication logs and known scans.";
methodFlows.en.env.note = "For this URL canary, reading, opening or running the file alone does not trigger an alert; an actual request is required. External connectivity alone is insufficient. A source address does not identify the attacker, and prompt delivery is not guaranteed.";
methodFlows.ja.database.steps[3] = ["4. 真偽を確認・利用", "別の情報と照合しても正解が確定せず、時間や費用をかけても判断がつかない場合があります。偽DBを転売する可能性もあります。"];
methodFlows.en.database.steps[3] = ["4. Verify and use", "Comparison with other information may remain inconclusive despite time and expense. The decoy may also be resold as genuine."];
methodFlows.ja.database.ifCase = "DB間でユーザーが一致しない場合も、収録範囲や更新時点の違いなどがあり、それだけでは偽物と断定できません。確実な答え合わせができなければ確認が徒労に終わり、選別の負担が残ります。偽DBの転売後に買い手が偽物と判断して共有すれば、売り手の信用に影響する可能性もあります。";
methodFlows.en.database.ifCase = "A user absent from one database may reflect different coverage or snapshot dates; absence alone does not prove a fake. Without reliable ground truth, verification can consume resources yet remain inconclusive. If a buyer identifies a resold decoy and shares feedback, the seller's reputation may also suffer.";
methodFlows.ja.database.elseCase = "攻撃者が登録したユーザーが見当たらなくても、対象テーブル・収録範囲・更新時点を知らなければ判別できない場合があります。逆に、それらを確実に知る場合は手掛かりになり得ます。生成物は架空データだけであり、本物のユーザーを取り込んで検証を妨げる機能はありません。";
methodFlows.en.database.elseCase = "An attacker's own registered account may be absent because the table, scope or snapshot date is unknown; if those facts are reliably known, absence can be a useful clue. Generated decoys contain only synthetic data and do not import real accounts to defeat this check.";
methodFlows.ja.database.note = "真偽を最後まで判別できない保証はなく、確認が徒労に終わる割合も未測定です。データ・ディルーションは別の紹介用構想であり、組み合わせても判別不能を保証しません。読み取りだけでは通知されません。";
methodFlows.en.database.note = "Indistinguishability is not guaranteed, and the share of inconclusive checks is unmeasured. Data Dilution is a separate concept; combining it does not guarantee indistinguishability. Reading alone does not alert.";
methodOutcomes.ja.database.delay = "偽DBの確認・選別に時間を使わせるほか、本物として転売された偽DBが買い手に見破られれば、売り手の信用や次の取引に影響する可能性があります。効果は未検証です。";
methodOutcomes.en.database.delay = "Besides selection time, a decoy resold as genuine may harm the seller's reputation and future business if the buyer recognizes it as fake. The effect is unverified.";
methodFlows.ja.data_dilution.ifCase = "全件が公開されても、本物を選別できなければ、データの信頼性や利用・取引価値が下がる可能性があります。外部情報との照合にも作業が必要で、一致だけでは正解と断定できない場合があります。";
methodFlows.ja.data_dilution.elseCase = "判別台帳や照会権限も盗まれると、真偽を選別される可能性があります。また、真偽を選ばず大量に自動試行できる攻撃では、低い本物率でも成功が生じ得ます。流出元などが公開された候補の真偽を明らかにした場合も、その範囲では不確実性が減ります。";
methodFlows.ja.data_dilution.response = "判別台帳と照会権限を分離・監査します。偽パスワードを試したときだけ隔離・検知するハニーワードと、試行制限・MFAを組み合わせる構想も評価します。一般の総当たりを一律に検知・阻止する仕組みではありません。";
methodFlows.ja.data_dilution.note = "技術紹介のみで実装・効果は未検証です。全件公開には本物も含まれますが、公開と本物の判別・悪用は別に評価します。漏えい時の法令・契約上の通知義務は別途確認します。";
methodFlows.en.data_dilution.ifCase = "Even if the full dataset is published, its reliability and resale or use value may fall if genuine records cannot be selected. External matching takes work, and a match alone may not establish ground truth.";
methodFlows.en.data_dilution.elseCase = "A stolen classification inventory or lookup privilege may reveal which records are genuine. Large-scale automated attempts without prior selection can still succeed despite a low genuine fraction. If the source or another party discloses which published candidates are genuine, uncertainty is reduced for those records.";
methodFlows.en.data_dilution.response = "Separate and audit the classification inventory and lookup privileges. Evaluate combining rate limits and MFA with honeywords that detect and isolate a specific decoy-password match; honeywords do not detect or stop all bulk attempts.";
methodFlows.en.data_dilution.note = "This is an unimplemented, unverified concept. Full publication includes genuine records, but publication and identifying or exploiting them are assessed separately. Review applicable legal and contractual breach-notification duties.";
let language = "ja";
Object.assign(translations.ja, {
  env_zip_download: "正確な.envファイル名を保持したZIPを保存", env_direct_download: "直接保存（ブラウザーにより先頭の.が消える場合があります）", env_zip_note: "ZIP内には正しいファイル名が保存されています。直接ダウンロードで先頭の.が消えるブラウザーでは、ZIPを展開して配置してください。",
  samples_link: "連携サンプルZIP",
  save_settings: "設定を保存（URL・ドメイン所有確認は除外）", load_settings: "設定を読み込む", guide_link: "導入・監視ガイド",
  settings_privacy_help: "カナリアURL欄、環境接続先などのURL形式入力欄、所有確認は保存しません。設定保存時に自由入力欄のURLや秘密情報を検出・除去する機能はありません。生成時には自由入力に含まれる未承認のURL・メール・公開ドメイン・IPアドレスと、一般的な認証情報・カード番号形式を拒否します（カナリアURLと所有確認付きデコイドメインは専用欄で別途検証します）。example.invalidなどの予約済み例示値は使用できます。検査は限定的で、接続先や秘密情報を網羅的に検出する機能ではありません。設定JSONには他の入力値や候補値が含まれるため、実データや秘密を入力せず安全に保管してください。",
  config_saved: "設定を保存しました。URLとドメイン所有確認は保存対象に含めていません。", config_loaded: "設定を読み込みました。URL欄は再入力し、デコイ用ドメインを使う場合は所有確認をやり直してください。",
  config_invalid: "このツールが保存した形式の設定JSON（1MiB以下、ネスト深度64以下）を選んでください。重複キーを含むJSONは読み込めません。",
  unsafe_setting_text: "設定に制御文字または表示順を変える文字が含まれています。削除してから保存・読み込みしてください。",
  monitoring_none: "カナリアURLは未設定です。取得を検知するには配信側ログの監視を設定してください。",
  monitoring_set: "URLを埋め込みました。取得時のログ監視と、URL使用時の通知を別々に確認してください。",
  monitoring_counts: "カナリア配置: {placements}件 / 使用した異なるURL: {used}/{supplied}件 / 未使用URL: {unused}件",
  monitoring_not_placed: "カナリアURLは入力されましたが、この生成では1件も埋め込まれませんでした。配置率を上げるなど設定を見直してください。",
});
translations.en.vault_domain = "Owned decoy domain (optional)";
translations.en.database_help += " SQLite output is limited to 32 MiB; reduce rows, columns or candidate value lengths if generation reaches the limit.";
translations.en.database_help += " Financial amount columns use a lower-value-skewed synthetic distribution; JPY amounts are whole numbers and other currencies use two decimal places.";
translations.ja.database_help += " 金額項目は低額側に偏った架空分布で生成します。JPYは整数、その他の通貨は小数2桁です。";
translations.en.database_help += " If the filename is blank, the generated database name follows the selected profile.";
translations.ja.database_help += " ファイル名が空欄の場合、生成するデータベース名は選択したテンプレートに合わせます。";
translations.ja.database_help += " SQLite生成物は32 MiB以下です。上限に達した場合はレコード数・項目数・候補値の長さを減らしてください。";
translations.ja.candidate_values_safety = "候補値には実在ドメイン・IPアドレス・URL・メールを指定できません。example.invalidなどの予約済み例示値を使い、監視URLや所有ドメインは専用欄から指定してください。";
translations.en.candidate_values_safety = "Candidate values cannot contain live domains, IP addresses, URLs or email addresses. Use reserved examples such as example.invalid; enter monitored URLs and owned decoy domains in their dedicated fields.";
translations.ja.candidate_values_safety += " 一般的な認証情報・秘密鍵・JWT・カード番号形式も拒否しますが、秘密情報を網羅的に検出するものではありません。実データや秘密は入力しないでください。設定JSONには項目名と候補値が保存されるため、管理者専用として保管してください。";
translations.en.candidate_values_safety += " Common credential, private-key, JWT and payment-card patterns are also rejected, but this is not comprehensive secret detection. Never enter real data or secrets. Settings JSON stores column names and candidate values; keep it operator-only.";
translations.en.settings_privacy_help = translations.en.settings_privacy_help.replace(
  "Saving settings does not detect or remove URLs or secrets in free-text fields.",
  "Saving and loading settings rejects common credential, private-key, JWT and payment-card patterns in free-text fields, but does not detect URLs or all secrets."
);
translations.ja.settings_privacy_help = translations.ja.settings_privacy_help.replace(
  "\u8a2d\u5b9a\u4fdd\u5b58\u6642\u306b\u81ea\u7531\u5165\u529b\u6b04\u306eURL\u3084\u79d8\u5bc6\u60c5\u5831\u3092\u691c\u51fa\u30fb\u9664\u53bb\u3059\u308b\u6a5f\u80fd\u306f\u3042\u308a\u307e\u305b\u3093\u3002",
  "\u8a2d\u5b9a\u306e\u4fdd\u5b58\u30fb\u8aad\u307f\u8fbc\u307f\u6642\u306b\u3001\u81ea\u7531\u5165\u529b\u6b04\u306e\u4e00\u822c\u7684\u306a\u8a8d\u8a3c\u60c5\u5831\u30fb\u79d8\u5bc6\u9375\u30fbJWT\u30fb\u30ab\u30fc\u30c9\u756a\u53f7\u5f62\u5f0f\u306f\u62d2\u5426\u3057\u307e\u3059\u304c\u3001URL\u3084\u3059\u3079\u3066\u306e\u79d8\u5bc6\u60c5\u5831\u3092\u691c\u51fa\u3059\u308b\u308f\u3051\u3067\u306f\u3042\u308a\u307e\u305b\u3093\u3002"
);
translations.ja.sensitive_setting_text = "\u8a2d\u5b9a\u306b\u4e00\u822c\u7684\u306a\u8a8d\u8a3c\u60c5\u5831\u30fb\u79d8\u5bc6\u9375\u30fbJWT\u30fb\u30ab\u30fc\u30c9\u756a\u53f7\u3068\u4e00\u81f4\u3059\u308b\u6587\u5b57\u5217\u304c\u3042\u308a\u307e\u3059\u3002\u5b9f\u30c7\u30fc\u30bf\u3084\u79d8\u5bc6\u306f\u4f7f\u308f\u305a\u3001\u5fc5\u8981\u306a\u3089\u9694\u96e2\u3057\u305f\u4f8b\u793a\u5024\u3078\u7f6e\u304d\u63db\u3048\u3066\u304f\u3060\u3055\u3044\u3002";
translations.en.sensitive_setting_text = "Settings contain text matching common credential, private-key, JWT or payment-card patterns. Do not use real data or secrets; replace them with isolated synthetic examples if needed.";
translations.en.vault_domain_help = "Applies only to synthetic login_url values in the Password Vault scenario. It is used by the standalone database and non-.env outputs from Encrypted Deep Nest, Directory Maze and Encoding Maze; .env output uses its environment variable. These become reachable HTTPS URLs; the generator does not resolve or contact the domain. Use a domain you control, provision a matching TLS certificate, and route wildcard DNS to an isolated decoy without production authentication. This is not a canary token; monitor DNS or web server logs for contact. Leave blank to use safe example.invalid URLs.";
translations.ja.vault_domain_help = "認証情報保管庫シナリオの架空login_urlだけに使います。単独DB、暗号化ネスト、ディレクトリ・メイズ、エンコーディング・メイズの非.env形式に反映されます。.envでは環境変数を使います。入力すると生成物に実際にアクセス可能なHTTPS URLが入ります。ドメインは名前解決・接続しません。所有するドメインを使い、ワイルドカードDNSとTLS証明書を隔離デコイへ向けてください。これは監視トークンではないため、DNS・Webサーバー側のログで接触を監視してください。空欄なら安全なexample.invalidを使います。";
translations.ja.vault_domain_help += " 攻撃者・クローラー・AIツールがそのURLを開くと、隔離先にHTTPS要求が届く場合があります。";
translations.en.vault_domain_help += " An attacker, crawler or AI tool that opens one of these URLs may send HTTPS requests to that isolated host.";
translations.en.vault_domain_authorized = "I control this domain and route it only to an isolated decoy without production authentication";
translations.ja.email_domain = "隔離デコイ専用メールドメイン（任意）";
translations.ja.email_domain_help = "所有するドメインを、本番メールボックスのない隔離デコイ専用にしてください。空欄なら example.invalid を使います。このツールはDNS照会やメール送信をしません。受信先を設定する場合は隔離した監視用シンクに限定してください。";
translations.ja.email_domain_authorized = "このドメインを所有し、本番メールボックスのない隔離デコイ専用にします";
translations.en.email_domain = "Dedicated decoy email domain (optional)";
translations.en.email_domain_help = "Use only a domain you own and dedicate to an isolated decoy with no production mailboxes. Leave blank for example.invalid. The app does not resolve or contact it. Route any mail only to an isolated monitoring sink.";
translations.en.email_domain_authorized = "I own this domain and reserve it for isolated decoys with no production mailboxes";
translations.ja.explain_deception = "本物らしく見せる要素";
translations.ja.explain_delay = "遅滞を生む仕組み";
translations.en.explain_deception = "What makes it look genuine";
translations.en.explain_delay = "How it can delay an attacker";
translations.ja.explain_measurement = "本物らしさ・遅滞は配置環境と攻撃者の自動化度で変わります。ここに示すのは期待条件であり、実測結果や保証ではありません。";
translations.en.explain_measurement = "Plausibility and delay depend on placement and attacker automation. These are conditions to evaluate, not measured or guaranteed outcomes.";
translations.ja.database_help = translations.ja.database_help.replace("メール・ドメイン型はexample.invalidを使います。", "メール・ドメイン型は既定でexample.invalidを使います。隔離デコイ専用ドメインも指定できます。");
translations.en.database_help = translations.en.database_help.replace("Email/domain generators use example.invalid.", "Email/domain generators use example.invalid by default. Use the dedicated decoy email-domain field above for generated addresses on a domain you own.");
translations.ja.request_too_large = "設定データが大きすぎます。カナリアURLの数や項目の候補値を減らしてください（上限4 MiB）。";
translations.en.request_too_large = "Settings are too large. Reduce the canary URL list or candidate values (4 MiB limit).";
translations.ja.operator_files_title = "\u7ba1\u7406\u8005\u5c02\u7528\u30d5\u30a1\u30a4\u30eb\uff08\u914d\u7f6e\u7269\u3068\u5206\u96e2\uff09";
translations.ja.operator_files_warning = "\u30d1\u30b9\u30ef\u30fc\u30c9\u3001\u30ab\u30ca\u30ea\u30a2URL\u3001\u30a2\u30fc\u30ab\u30a4\u30d6\u69cb\u6210\u3001\u691c\u8a3c\u60c5\u5831\u3092\u542b\u3080\u5834\u5408\u304c\u3042\u308a\u307e\u3059\u3002\u6a29\u9650\u3092\u9650\u5b9a\u3057\u3066\u5225\u4fdd\u7ba1\u3057\u3001\u516c\u958b\u30b5\u30a4\u30c8\u3078\u306e\u30a2\u30c3\u30d7\u30ed\u30fc\u30c9\u3084\u672c\u756a\u30a2\u30d7\u30ea\u3078\u306e\u914d\u7f6e\u306f\u3057\u306a\u3044\u3067\u304f\u3060\u3055\u3044\u3002";
translations.en.operator_download_required = "Download each operator-only file above, then confirm after storing it separately from the deployment files.";
translations.ja.operator_download_required = "\u4e0a\u306e\u7ba1\u7406\u8005\u5c02\u7528\u30d5\u30a1\u30a4\u30eb\u3092\u3059\u3079\u3066\u30c0\u30a6\u30f3\u30ed\u30fc\u30c9\u3057\u3001\u914d\u7f6e\u7528\u30d5\u30a1\u30a4\u30eb\u3068\u5206\u3051\u3066\u5b89\u5168\u306b\u4fdd\u5b58\u3057\u305f\u5f8c\u3001\u78ba\u8a8d\u30dc\u30bf\u30f3\u3092\u62bc\u3057\u3066\u304f\u3060\u3055\u3044\u3002";
translations.en.env_switch_help += " When comments are blank, a paired set of operational notes is chosen for each generation; custom comments are kept as entered.";
translations.ja.env_switch_help += "\u30b3\u30e1\u30f3\u30c8\u304c\u7a7a\u6b04\u306e\u5834\u5408\u306f\u3001\u751f\u6210\u3054\u3068\u306b\u904b\u7528\u30e1\u30e2\u306e\u7d44\u307f\u5408\u308f\u305b\u3092\u9078\u3073\u307e\u3059\u3002\u5165\u529b\u3057\u305f\u30b3\u30e1\u30f3\u30c8\u306f\u305d\u306e\u307e\u307e\u4f7f\u3044\u307e\u3059\u3002";
translations.en.env_dev_url = "Active URL for this environment (optional)";
translations.en.env_dev_comment_label = "Current environment note (optional)";
translations.en.env_prod_comment_label = "Alternative URL note (optional)";
translations.en.env_layout_switch = "Environment switch note (alternative URL commented)";
translations.en.env_switch_help = "With a blank filename this creates .env.development. The environment suffix sets APP_ENV and the default endpoint host; a custom URL should match that environment. The active URL is followed by a commented canary URL that resembles a production alternative. The default uses example.invalid. For a custom host, confirm ownership and route it only to an isolated test endpoint without production authentication. A crawler or agent may request the active URL. The generator does not resolve or contact it. Do not enter internal or production endpoints or load the file in production configuration. Blank comments use varied operational notes; custom comments are preserved. Reading the comment does not alert; a request to the canary URL is required.";
translations.ja.env_dev_url = "\u3053\u306e\u74b0\u5883\u3067\u4f7f\u3046\u6709\u52b9\u306aURL\uff08\u4efb\u610f\uff09";
translations.ja.env_dev_url_authorized = "\u3053\u306e\u30db\u30b9\u30c8\u3092\u7ba1\u7406\u3057\u3001\u672c\u756a\u8a8d\u8a3c\u306e\u306a\u3044\u9694\u96e2\u691c\u8a3c\u5148\u3060\u3051\u306b\u5411\u3051\u3066\u3044\u307e\u3059\u3002URL\u3092\u305f\u3069\u308b\u5229\u7528\u8005\u304b\u3089\u30ea\u30af\u30a8\u30b9\u30c8\u3092\u53d7\u3051\u308b\u53ef\u80fd\u6027\u304c\u3042\u308a\u307e\u3059\u3002";
translations.ja.env_dev_comment_label = "\u73fe\u5728\u306e\u74b0\u5883\u306e\u30e1\u30e2\uff08\u4efb\u610f\uff09";
translations.ja.env_prod_comment_label = "\u4ee3\u66ffURL\u306e\u30e1\u30e2\uff08\u4efb\u610f\uff09";
translations.ja.env_layout_switch = "\u74b0\u5883\u5207\u66ff\u30e1\u30e2\uff08\u4ee3\u66ffURL\u306f\u30b3\u30e1\u30f3\u30c8\uff09";
translations.ja.env_switch_help = "\u30d5\u30a1\u30a4\u30eb\u540d\u304c\u7a7a\u6b04\u306a\u3089 .env.development \u306b\u306a\u308a\u307e\u3059\u3002\u74b0\u5883\u30b5\u30d5\u30a3\u30c3\u30af\u30b9\u306fAPP_ENV\u3068\u65e2\u5b9aURL\u306e\u30db\u30b9\u30c8\u306b\u53cd\u6620\u3055\u308c\u307e\u3059\u3002\u624b\u5165\u529b\u3059\u308bURL\u3082\u305d\u306e\u74b0\u5883\u306b\u5408\u308f\u305b\u3066\u304f\u3060\u3055\u3044\u3002\u6709\u52b9\u306aURL\u306e\u4e0b\u306b\u672c\u756a\u7528\u306b\u898b\u3048\u308b\u30ab\u30ca\u30ea\u30a2URL\u3092\u30b3\u30e1\u30f3\u30c8\u3067\u914d\u7f6e\u3057\u307e\u3059\u3002\u65e2\u5b9aURL\u306fexample.invalid\u3067\u3059\u3002\u5225\u306e\u30db\u30b9\u30c8\u3092\u5165\u529b\u3059\u308b\u5834\u5408\u306f\u6240\u6709\u3092\u78ba\u8a8d\u3057\u3001\u672c\u756a\u8a8d\u8a3c\u306e\u306a\u3044\u9694\u96e2\u691c\u8a3c\u5148\u306e\u307f\u306b\u5411\u3051\u3066\u304f\u3060\u3055\u3044\u3002\u30af\u30ed\u30fc\u30e9\u3084\u30a8\u30fc\u30b8\u30a7\u30f3\u30c8\u304c\u6709\u52b9URL\u3078\u30a2\u30af\u30bb\u30b9\u3059\u308b\u53ef\u80fd\u6027\u304c\u3042\u308a\u307e\u3059\u3002\u751f\u6210\u5668\u306f\u540d\u524d\u89e3\u6c7a\u30fb\u63a5\u7d9a\u3092\u884c\u3044\u307e\u305b\u3093\u3002\u5185\u90e8\u30fb\u672c\u756a\u63a5\u7d9a\u5148\u306f\u5165\u529b\u305b\u305a\u3001\u672c\u756a\u30a2\u30d7\u30ea\u306b\u8aad\u307f\u8fbc\u307e\u305b\u3093\u3002\u7a7a\u6b04\u306e\u30b3\u30e1\u30f3\u30c8\u306f\u751f\u6210\u3054\u3068\u306b\u5909\u308f\u308a\u3001\u5165\u529b\u3057\u305f\u6587\u9762\u306f\u4fdd\u6301\u3057\u307e\u3059\u3002\u30ab\u30ca\u30ea\u30a2URL\u306f\u305d\u306eURL\u3078\u5b9f\u969b\u306b\u30a2\u30af\u30bb\u30b9\u3055\u308c\u305f\u6642\u306b\u901a\u77e5\u3055\u308c\u307e\u3059\u3002";
translations.ja.monitoring_placeholder = "\u5165\u529b\u3057\u305fURL\u306e\u5c11\u306a\u304f\u3068\u30821\u4ef6\u306f\u4e88\u7d04\u6e08\u307f\u306e\u4f8b\u793a\u30fb\u30c6\u30b9\u30c8\u7528\u30c9\u30e1\u30a4\u30f3\u3067\u3059\u3002\u8a72\u5f53\u3059\u308bURL\u3067\u306f\u5b9f\u969b\u306e\u30ab\u30ca\u30ea\u30a2\u901a\u77e5\u306f\u767a\u751f\u3057\u307e\u305b\u3093\u3002\u672c\u756a\u914d\u7f6e\u306b\u306f\u76e3\u8996\u30b5\u30fc\u30d3\u30b9\u304c\u767a\u884c\u3057\u305fURL\u3092\u4f7f\u3063\u3066\u304f\u3060\u3055\u3044\u3002";
translations.ja.deployment_download_warning = "\u3053\u308c\u3089\u306f\u30ed\u30fc\u30ab\u30eb\u306b\u4f5c\u6210\u3055\u308c\u308b\u30c0\u30a6\u30f3\u30ed\u30fc\u30c9\u3067\u3001\u81ea\u52d5\u914d\u7f6e\u306f\u3057\u307e\u305b\u3093\u3002\u914d\u7f6e\u7528\u30d5\u30a1\u30a4\u30eb\u306b\u306f\u5165\u529b\u3057\u305f\u30ab\u30ca\u30ea\u30a2URL\u304c\u542b\u307e\u308c\u308b\u5834\u5408\u304c\u3042\u308a\u307e\u3059\u3002\u516c\u958b\u30ea\u30dd\u30b8\u30c8\u30ea\u306b\u5b9f\u30c8\u30fc\u30af\u30f3\u3001\u7ba1\u7406\u8005\u5c02\u7528\u30d5\u30a1\u30a4\u30eb\u3001\u672c\u756a\u30c7\u30fc\u30bf\u3092\u8ffd\u52a0\u3057\u306a\u3044\u3067\u304f\u3060\u3055\u3044\u3002\u914d\u7f6e\u524d\u306b\u5185\u5bb9\u3068\u76e3\u8996\u65b9\u6cd5\u3092\u78ba\u8a8d\u3057\u3066\u304f\u3060\u3055\u3044\u3002";
translations.en.deployment_download_warning = "These are local downloads; the tool does not deploy them. A deployment file may contain the canary URLs you supplied. Do not commit real tokens, operator-only files or production data to a public repository. Review the contents and monitoring path before deployment.";
let downloadUrls = [];
let generatedAsset = null;
let operatorFilesAcknowledged = false;
let operatorFileDownloads = new Set();
let activeKind = $('input[name="kind"]:checked')?.value || "env";
function hasUnacknowledgedOperatorFile() {
  return Boolean(generatedAsset && (generatedAsset.companions || []).some(item => item.role !== "deployment")
    && !operatorFilesAcknowledged);
}
try { if (localStorage.getItem("adg-language") === "en") language = "en"; } catch (_) { /* Storage may be disabled. */ }
function t(key, values = {}) {
  const message = translations[language]?.[key] ?? translations.en[key] ?? key;
  return Object.entries(values).reduce((text, [name, value]) => text.replaceAll("{" + name + "}", String(value)), message);
}
function localize(root) {
  root.querySelectorAll("[data-i18n]").forEach(element => { element.textContent = t(element.dataset.i18n); });
  root.querySelectorAll("[data-i18n-aria]").forEach(element => { element.setAttribute("aria-label", t(element.dataset.i18nAria)); });
  root.querySelectorAll("[data-i18n-placeholder]").forEach(element => { element.setAttribute("placeholder", t(element.dataset.i18nPlaceholder)); });
}
function estimate() {
  const layers = Number($("#layers").value), branches = Number($("#branches").value), decoys = Number($("#decoys").value);
  const valid = Number.isInteger(layers) && layers >= 1 && layers <= 8 && Number.isInteger(branches) && branches >= 1 && branches <= 3;
  const archives = valid ? Array.from({length: layers}, (_, n) => branches ** n).reduce((a, b) => a + b, 0) : 0;
  $("#nest-estimate").textContent = valid ? t("estimate", {archives, documents: archives * decoys}) + (archives > 40 ? " " + t("over_limit") : "") : t("over_limit");
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
  $("#downloads").setAttribute("aria-label", language === "ja" ? "生成ファイル" : "Generated files");
  $("#guide-link").href = "/guide/" + language;
  localize(document);
  updateEnvTemplate();
  if (databaseTemplates.length) renderDatabaseTemplates();
  if (databaseTemplates.length) loadDatabaseTemplates();
  updateExplanation();
  estimate();
  updateMazeEstimate();
  updateCanaryUrlWarning();
  updateCsvSafetyNote();
  result.textContent = generatedAsset ? t("generated", {name: generatedAsset.name}) : "";
  if (generatedAsset) renderDownloads(generatedAsset);
}
languageSelect.addEventListener("change", () => {
  language = languageSelect.value;
  try { localStorage.setItem("adg-language", language); } catch (_) { /* Continue without persistence. */ }
  applyLanguage();
});
function addColumn(name = "field_" + (document.querySelectorAll(".column-row").length + 1), kind = "text") {
  if (document.querySelectorAll(".column-row").length >= 30) { result.textContent = t("schema_limit"); return; }
  const fragment = $("#column-template").content.cloneNode(true), row = fragment.querySelector(".column-row");
  row.querySelector(".column-name").value = name;
  row.querySelector(".column-kind").value = kind;
  function updateOptions() {
    const current = row.querySelector(".column-kind").value;
    const options = row.querySelector(".column-options");
    options.disabled = !["integer", "decimal", "text", "status", "company", "department"].includes(current);
    options.placeholder = ["integer", "decimal"].includes(current) ? "0,100000" : "active|pending|archived";
  }
  row.querySelector(".column-kind").addEventListener("change", updateOptions);
  row.querySelector(".remove-column").addEventListener("click", () => row.remove());
  updateOptions();
  localize(row);
  $("#columns").append(fragment);
}
$("#add-column").addEventListener("click", () => addColumn());
for (const [name, kind] of [["id", "id"], ["name", "name"], ["email", "email"], ["status", "status"]]) addColumn(name, kind);
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
  if (changed && !forceClear && hasUnacknowledgedOperatorFile()
      && !window.confirm(t("discard_operator_confirmation"))) {
    const previous = [...document.querySelectorAll('input[name="kind"]')].find(input => input.value === activeKind);
    if (previous) { previous.checked = true; previous.focus(); }
    return false;
  }
  updateExplanation();
  for (const kind of ["env", "nest", "database", "web", "fake_trap", "data_dilution", "honeyword", "stream", "directory_maze", "encoding_maze"]) {
    const fields = $("#" + kind + "-fields");
    fields.hidden = kind !== selected;
    fields.querySelectorAll("input, select, button, textarea").forEach(input => {
      input.disabled = kind !== selected;
      if (kind !== selected) input.removeAttribute("aria-invalid");
    });
  }
  const infoOnly = ["data_dilution", "honeyword"].includes(selected);
  button.hidden = infoOnly;
  $(".settings-actions").hidden = infoOnly;
  $('[data-i18n="settings_privacy_help"]').hidden = infoOnly;
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
  invoices: ["finance", "billing", "receivables", "payments", "overdue", "reconciliation", "statements"],
  employees: ["hr", "personnel", "departments", "payroll", "onboarding", "roles", "reviews"],
  vendors: ["procurement", "suppliers", "contracts", "reviews", "due_diligence", "services", "finance"],
  orders: ["sales", "orders", "fulfillment", "shipments", "returns", "billing", "reconciliation"],
  tickets: ["support", "cases", "queue", "escalations", "resolution", "customers", "reports"],
  assets: ["assets", "hardware", "endpoints", "licenses", "facilities", "lifecycle", "assignments"],
  cloud: ["platform", "subscriptions", "identity", "storage", "deployments", "regions", "recovery"]
};
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
const canaryUrlFields = {
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
  const selectors = canaryUrlFields[selected] || [];
  const hasReserved = selectors.some(selector => hasReservedCanaryUrl($(selector).value));
  warning.hidden = !hasReserved;
  warning.textContent = hasReserved ? t("monitoring_placeholder") : "";
}
for (const selector of Object.values(canaryUrlFields).flat()) {
  $(selector).addEventListener("input", updateCanaryUrlWarning);
}
document.querySelectorAll('input[name="kind"]').forEach(input => input.addEventListener("change", () => updateFields()));
document.querySelectorAll('#generator input[type="number"]').forEach(input => input.addEventListener("input", () => {
  if (input.checkValidity()) {
    input.removeAttribute("aria-invalid");
    result.textContent = "";
  }
}));
function updateEnvTemplate() {
  const isCanary = $('input[name="kind"]:checked').value === "env";
  const enabled = isCanary && $("#canary-format").value === "env";
  const options = $("#env-template-options"), switchOptions = $("#env-switch-options");
  options.hidden = !enabled;
  $("#env-layout").disabled = !enabled;
  const switchEnabled = enabled && $("#env-layout").value === "commented_production";
  switchOptions.hidden = !switchEnabled;
  switchOptions.querySelectorAll("input").forEach(input => { input.disabled = !switchEnabled; });
  const context = $("#canary-context-options");
  context.hidden = switchEnabled;
  context.querySelectorAll("input, select").forEach(input => { input.disabled = !isCanary || switchEnabled; });
  $("#canary-title").placeholder = t(switchEnabled ? "context_title_generic" : "context_title_auto");
}
$("#canary-format").addEventListener("change", () => { updateEnvTemplate(); updateCsvSafetyNote(); });
$("#env-layout").addEventListener("change", updateEnvTemplate);
$("#env-dev-url").addEventListener("input", () => { $("#env-dev-url-authorized").checked = false; });
let databaseTemplates = [];
async function loadDatabaseTemplates() {
  const requestedLanguage = language;
  try {
    const response = await fetch("/api/database-templates", {headers: {"X-ADG-Language": requestedLanguage}});
    if (!response.ok) throw new Error();
    const data = await response.json();
    if (language !== requestedLanguage) return loadDatabaseTemplates();
    databaseTemplates = data.templates;
    const select = $("#database-template"), firstLoad = select.dataset.ready !== "true";
    renderDatabaseTemplates();
    if (firstLoad) applyDatabaseTemplate(select.value);
    if (select.dataset.handler !== "true") {
      select.addEventListener("change", () => {
        if (select.value !== "custom") applyDatabaseTemplate(select.value);
        else $("#template-description").textContent = t("template_help");
      });
      select.dataset.handler = "true";
    }
    $("#database-template").dataset.ready = "true";
  } catch (_) {
    $("#template-description").textContent = language === "ja" ? "テンプレート一覧を読み込めません。手動で項目を設定できます。" : "Could not load templates. You can define columns manually.";
  }
}
function renderDatabaseTemplates() {
  const select = $("#database-template"), current = select.dataset.selected || select.value || "customers";
  select.replaceChildren(new Option(t("template_custom"), "custom"));
  for (const template of databaseTemplates) select.add(new Option(template.label, template.id));
  select.value = databaseTemplates.some(item => item.id === current) ? current : "customers";
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
function markDatabaseCustom() { $("#database-template").value = "custom"; $("#database-template").dataset.selected = "custom"; $("#template-description").textContent = t("template_help"); }
$("#columns").addEventListener("input", markDatabaseCustom);
$("#columns").addEventListener("change", markDatabaseCustom);
$("#table-name").addEventListener("input", markDatabaseCustom);
function updateExplanation() {
  const selected = document.querySelector('input[name="kind"]:checked')?.value || "env";
  const item = methodExplanations[language][selected] || methodExplanations.ja[selected];
  if (!item) return;
  $("#method-explanation-title").textContent = item.title;
  const flow = methodFlows[language][selected];
  $("#method-flow-scenario").textContent = flowScenarios[language][selected];
  $("#method-flow-context").textContent = flow.context;
  const steps = $("#method-flow-steps");
  steps.replaceChildren();
  flow.steps.forEach(([title, description], index) => {
    const step = document.createElement("li");
    const number = document.createElement("span");
    number.className = "flow-number";
    number.setAttribute("aria-hidden", "true");
    number.textContent = String(index + 1).padStart(2, "0");
    const heading = document.createElement("strong");
    heading.textContent = title.replace(/^\d+\.\s*/, "");
    const text = document.createElement("span");
    text.className = "flow-description";
    text.textContent = description;
    step.append(number, heading, text);
    steps.append(step);
  });
  $("#method-flow-note").textContent = flow.note;
  $("#method-flow-if").textContent = flow.ifCase;
  $("#method-flow-else").textContent = flow.elseCase;
  $("#method-flow-response").textContent = flow.response;
  $("#explain-how").textContent = item.how;
  $("#explain-target").textContent = item.target;
  const outcomes = methodOutcomes[language][selected] || methodOutcomes.en[selected];
  $("#explain-deception").textContent = outcomes.deception;
  $("#explain-delay").textContent = outcomes.delay;
  $("#explain-limit").textContent = item.limit;
  const legal = methodLegal[language][selected];
  $("#legal-normal").textContent = legal.normal;
  $("#legal-risk").textContent = legal.risk;
  $("#legal-other").textContent = legal.other || "";
  const us = usLegal[language][selected];
  $("#legal-us-normal").textContent = us[0];
  $("#legal-us-risk").textContent = us[1];
  $("#legal-guide-link").href = "/legal/" + language;
  $("#legal-us-guide-link").href = "/legal/" + language;
  $("#cloud-legal-guide").href = "/legal/" + language;
}
$("#nest-fields").addEventListener("input", estimate);
function columns() {
  const rows = [...document.querySelectorAll(".column-row")];
  if (!rows.length) throw new Error(t("schema_limit"));
  return rows.map(row => {
    const column = {name: row.querySelector(".column-name").value.trim(), kind: row.querySelector(".column-kind").value};
    const value = row.querySelector(".column-options").value.trim();
    if (value && ["integer", "decimal"].includes(column.kind)) {
      const limits = value.split(",");
      if (limits.length !== 2 || limits.some(v => !v.trim() || !Number.isFinite(Number(v)))) throw new Error(t("invalid_options"));
      [column.min, column.max] = limits.map(Number);
    } else if (value && !row.querySelector(".column-options").disabled) column.values = value.split("|").map(v => v.trim());
    return column;
  });
}
function clearDownloads() {
  downloadUrls.forEach(url => URL.revokeObjectURL(url));
  downloadUrls = [];
  $("#downloads").replaceChildren();
  $("#downloads").hidden = true;
  generatedAsset = null;
  operatorFilesAcknowledged = false;
  operatorFileDownloads = new Set();
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
function renderDownloads(data) {
  const sameAsset = generatedAsset === data;
  const acknowledged = generatedAsset === data && operatorFilesAcknowledged;
  const downloaded = sameAsset ? new Set(operatorFileDownloads) : new Set();
  clearDownloads();
  generatedAsset = data;
  operatorFilesAcknowledged = acknowledged;
  operatorFileDownloads = downloaded;
  $("#downloads").hidden = false;
  const handlingWarning = document.createElement("p");
  handlingWarning.className = "inline-note";
  handlingWarning.textContent = t("deployment_download_warning");
  $("#downloads").append(handlingWarning);
  const hasDeploymentPackage = (data.companions || []).some(item => item.role === "deployment");
  const primary = downloadLink(data, t(hasDeploymentPackage ? "env_direct_download" : "download_again"));
  let automatic = primary;
  const companions = data.companions || [];
  for (const companion of companions.filter(item => item.role === "deployment")) {
    automatic = downloadLink(companion, t("env_zip_download"));
  }
  const operatorFiles = companions.filter(item => item.role !== "deployment");
  if (operatorFiles.length) {
    const section = document.createElement("section");
    section.className = "operator-downloads";
    const heading = document.createElement("h3");
    heading.textContent = t("operator_files_title");
    const warning = document.createElement("p");
    warning.textContent = t("operator_files_warning");
    const instructions = document.createElement("p");
    instructions.textContent = t("operator_download_required");
    section.append(heading, warning, instructions);
    const acknowledge = document.createElement("button");
    acknowledge.type = "button";
    acknowledge.className = "secondary operator-acknowledge";
    acknowledge.textContent = t(operatorFilesAcknowledged ? "operator_ack_done" : "operator_ack_action");
    acknowledge.disabled = operatorFilesAcknowledged || operatorFiles.some(item => !operatorFileDownloads.has(item.name));
    acknowledge.addEventListener("click", () => {
      operatorFilesAcknowledged = true;
      acknowledge.textContent = t("operator_ack_done");
      acknowledge.disabled = true;
    });
    for (const companion of operatorFiles) {
      const label = companion.name.endsWith(".inventory.json") ? t("inventory_download") : t("operator_download");
      const link = downloadLink(companion, label, section);
      link.addEventListener("click", () => {
        operatorFileDownloads.add(companion.name);
        acknowledge.disabled = operatorFilesAcknowledged || operatorFiles.some(item => !operatorFileDownloads.has(item.name));
      });
    }
    section.append(acknowledge);
    $("#downloads").append(section);
  }
  if (hasDeploymentPackage) {
    const note = document.createElement("p"); note.textContent = t("env_zip_note"); $("#downloads").append(note);
  }
  if (data.summary && "has_monitoring_url" in data.summary && data.summary.kind !== "stream") {
    const status = document.createElement("p");
    const noRandomPlacement = data.summary.canary_placements === 0 && data.summary.canary_url_configured;
    status.textContent = t(noRandomPlacement ? "monitoring_not_placed" : data.summary.has_monitoring_url ? "monitoring_set" : "monitoring_none");
    $("#downloads").append(status);
    if (data.summary.canary_url_configured) {
      const counts = document.createElement("p");
      counts.textContent = t("monitoring_counts", {placements: data.summary.canary_placements,
        used: data.summary.canary_urls_used, supplied: data.summary.canary_urls_supplied,
        unused: data.summary.canary_urls_unused});
      $("#downloads").append(counts);
    }
    if (data.summary.reserved_canary_host) {
      const warning = document.createElement("p");
      warning.className = "inline-note";
      warning.textContent = t("monitoring_placeholder");
      $("#downloads").append(warning);
      $("#canary-url-warning").hidden = true;
    }
  }
  if (data.summary && data.summary.archives) {
    const note = document.createElement("p");
    const formatCounts = data.summary.format_counts;
    const formatNote = formatCounts && Object.keys(formatCounts).length
      ? ` ${t("format_breakdown")}: ${Object.entries(formatCounts).map(([format, count]) => `${format} ${count}`).join(", ")}.`
      : "";
    note.textContent = t("summary", data.summary) + formatNote + " " + t("operator_reminder");
    $("#downloads").append(note);
  }
  if (data.summary && ["stream", "directory_maze", "encoding_maze"].includes(data.summary.kind)) {
    const note = document.createElement("p");
    const details = data.summary;
    note.textContent = language === "ja" ? ({stream: `配信上限：合計${details.rate_kib} KiB/秒・${details.max_streams}接続。起動方法は同梱READMEを参照してください。`, directory_maze: `${details.directories}ディレクトリ・${details.documents}文書を生成しました。`, encoding_maze: `${t("scenario_" + details.scenario)}：${details.candidates}候補・各${details.layers}階層を生成しました。`}[details.kind]) :
      ({stream: `Aggregate limit: ${details.rate_kib} KiB/s, ${details.max_streams} streams. See the included README to start.`, directory_maze: `Generated ${details.directories} directories and ${details.documents} documents.`, encoding_maze: `${t("scenario_" + details.scenario)}: generated ${details.candidates} candidates with ${details.layers} layers each.`}[details.kind]);
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
  return automatic;
}
window.addEventListener("beforeunload", event => {
  if (generatedAsset && (generatedAsset.companions || []).some(item => item.role !== "deployment") && !operatorFilesAcknowledged) {
    event.preventDefault();
    event.returnValue = "";
  }
});
applyLanguage();
updateFields();
loadDatabaseTemplates();
form.querySelectorAll('input[type="number"]').forEach(input => {
  input.addEventListener("input", () => {
    if (input.checkValidity()) input.removeAttribute("aria-invalid");
  });
});
form.addEventListener("submit", async event => {
  event.preventDefault();
  const kind = $('input[name="kind"]:checked').value;
  if (["data_dilution", "honeyword"].includes(kind)) return;
  const invalidNumber = [...$("#" + kind + "-fields").querySelectorAll('input[type="number"]')]
    .find(input => !input.checkValidity());
  if (invalidNumber) {
    invalidNumber.setAttribute("aria-invalid", "true");
    result.textContent = t("number_input_invalid");
    invalidNumber.focus();
    return;
  }
  if (kind === "directory_maze" && $("#maze-estimate").dataset.overLimit === "true") {
    result.textContent = t("maze_over_limit");
    $("#maze-depth").focus();
    return;
  }
  if (kind === "nest") {
    const layers = Number($("#layers").value), branches = Number($("#branches").value);
    const archives = Array.from({length: layers}, (_, level) => branches ** level).reduce((sum, count) => sum + count, 0);
    if (archives > 40) {
      result.textContent = t("over_limit");
      $("#layers").focus();
      return;
    }
  }
  let settings, requestBody;
  try {
    settings = {
      env: () => ({format: $("#canary-format").value, canary_url: $("#env-url").value, canary_context: $("#canary-context").value, canary_field: $("#canary-field").value, canary_label: $("#canary-label").value, env_layout: $("#env-layout").value, env_suffix: $("#env-suffix").value, env_variable: $("#env-variable").value, env_dev_url: $("#env-dev-url").value, env_dev_url_authorized: $("#env-dev-url-authorized").checked, env_dev_comment: $("#env-dev-comment").value, env_prod_comment: $("#env-prod-comment").value, title: $("#canary-title").value, rows: Number($("#canary-rows").value), ...($("#canary-name").value ? {filename: $("#canary-name").value} : {})}),
      nest: () => ({scenario: $("#nest-scenario").value, ...($("#nest-scenario").value === "passwords" && ($("#nest-format").value !== "env" || $("#nest-varied-formats").checked) ? vaultDomainSettings() : {}), layers: Number($("#layers").value), branches: Number($("#branches").value), decoys: Number($("#decoys").value), directory_depth: Number($("#directory-depth").value), rows: Number($("#nest-rows").value),
        format: $("#nest-format").value, varied_formats: $("#nest-varied-formats").checked, directories: $("#directories").value.split(",").map(v => v.trim()),
        canary_urls: $("#nest-url").value.split(/\r?\n/).filter(value => value.trim()), canary_percent: Number($("#canary-percent").value), ...($("#nest-name").value ? {filename: $("#nest-name").value} : {}),
        password_policy: {mode: $("#password-mode").value, min_length: Number($("#min-length").value), max_length: Number($("#max-length").value),
          lowercase: $("#lowercase").checked, uppercase: $("#uppercase").checked, digits: $("#digits").checked, symbols: $("#symbols").checked, progressive: $("#progressive").checked, hints: $("#hints").value,
          hint_characters: Number($("#hint-characters").value), ...($("#password-words").value.trim() ? {words: $("#password-words").value.split(",").map(v => v.trim())} : {})}}),
      database: () => ({template: $("#database-template").value || "customers", email_domain: $("#db-email-domain").value.trim(), email_domain_authorized: $("#db-email-domain-authorized").checked, ...( $("#database-template").value === "passwords" ? vaultDomainSettings() : {}), rows: Number($("#rows").value), table: $("#table-name").value, columns: columns(), canary_url: $("#db-url").value, ...($("#db-name").value ? {filename: $("#db-name").value} : {})}),
      web: () => ({title: $("#title").value, canary_url: $("#web-url").value, ...($("#web-name").value ? {filename: $("#web-name").value} : {})}),
      fake_trap: () => ({variant: $("#fake-variant").value, ...($("#fake-name").value ? {filename: $("#fake-name").value} : {})}),
      stream: () => ({path: $("#stream-path").value, format: $("#stream-format").value, port: Number($("#stream-port").value), rate_kib: Number($("#stream-rate").value), max_streams: Number($("#stream-concurrency").value), ...($("#stream-name").value ? {filename: $("#stream-name").value} : {})}),
      directory_maze: () => ({scenario: $("#maze-scenario").value, ...($("#maze-scenario").value === "passwords" && $("#maze-format").value !== "env" ? vaultDomainSettings() : {}), title: $("#directory-title").value, depth: Number($("#maze-depth").value), branches: Number($("#maze-branches").value), files_per_directory: Number($("#maze-files").value), cross_links: $("#maze-cross-links").checked, canary_urls: $("#maze-url").value.split(/\r?\n/).filter(value => value.trim()), format: $("#maze-format").value, ...($("#directory-name").value ? {filename: $("#directory-name").value} : {})}),
      encoding_maze: () => ({scenario: $("#encoding-scenario").value, ...($("#encoding-scenario").value === "passwords" && $("#encoding-format").value !== "env" ? vaultDomainSettings() : {}), format: $("#encoding-format").value, layers: Number($("#encoding-layers").value), candidates: Number($("#encoding-candidates").value), canary_urls: $("#encoding-url").value.split(/\r?\n/).filter(value => value.trim()), codecs: [...document.querySelectorAll("#encoding-codecs input:checked")].map(input => input.value), ...($("#encoding-name").value ? {filename: $("#encoding-name").value} : {})}),
    }[kind]();
    requestBody = JSON.stringify({kind, settings});
    if (new Blob([requestBody]).size > MAX_GENERATION_REQUEST_BYTES) {
      result.textContent = t("request_too_large");
      return;
    }
  } catch (error) { result.textContent = error.message; return; }
  if (hasUnacknowledgedOperatorFile() && !window.confirm(t("discard_operator_confirmation"))) return;
  button.disabled = true;
  $("#save-settings").disabled = true;
  $("#load-settings").disabled = true;
  languageSelect.disabled = true;
  document.querySelectorAll('input[name="kind"]').forEach(input => { input.disabled = true; });
  clearDownloads();
  result.textContent = t("generating");
  try {
    const response = await fetch("/api/generate", {
      method: "POST", headers: {"Content-Type": "application/json", "X-ADG-Token": $('meta[name="adg-token"]').content, "X-ADG-Language": language},
      body: requestBody,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || t("failed"));
    const primary = renderDownloads(data);
    primary.click();
    result.textContent = t("generated", {name: data.name});
    // Move keyboard and screen-reader focus to the newly created download
    // link after the automatic download has been requested.
    primary.focus();
  } catch (error) {
    result.textContent = error instanceof TypeError ? t("failed") : (error.message || t("failed"));
  } finally {
    button.disabled = false;
    $("#save-settings").disabled = false;
    $("#load-settings").disabled = false;
    languageSelect.disabled = false;
    document.querySelectorAll('input[name="kind"]').forEach(input => { input.disabled = false; });
  }
});

// Explicit local files only; never persist canary URLs or generated passwords.
function configControls() {
  return [...form.querySelectorAll(".fields input, .fields select, .fields textarea")]
    .filter(el => el.type !== "url" && el.type !== "file" && !el.hasAttribute("data-secret-url")
      && !el.hasAttribute("data-operator-attestation") && !el.closest("#columns"));
}
const nonPersistentCanaryUrlControls = new Set(["env-url", "db-url", "web-url"]);
const nonPersistentOperatorAttestations = new Set([
  "env-dev-url-authorized", "db-email-domain-authorized", "vault-domain-authorized",
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
$("#save-settings").addEventListener("click", () => {
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
  const config = {schema: "adg-ui-v12", kind: $('input[name="kind"]:checked').value,
    // Keep the positional slots for compatibility, but never export canary tokens.
    controls: controls.map(el => el.type === "checkbox"
      ? (nonPersistentOperatorAttestations.has(el.id) ? false : el.checked)
      : nonPersistentCanaryUrlControls.has(el.id) ? "" : el.value),
    columns};
  const url = URL.createObjectURL(new Blob([JSON.stringify(config, null, 2)], {type: "application/json"}));
  const link = document.createElement("a"); link.href = url; link.download = "adg-settings.json"; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  result.textContent = t("config_saved");
});
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
    if (Array.isArray(values) && !["adg-ui-v9", "adg-ui-v10", "adg-ui-v11", "adg-ui-v12"].includes(config.schema)) {
      // Older schemas predate the database email-domain controls. v1-v8 also
      // predate the trailing vault-domain controls; v9 already contains those.
      if (config.schema !== "adg-ui-v9") values = [...values, "", false];
      const emailDomainIndex = legacyControlIndex("db-email-domain");
      if (emailDomainIndex < 0) throw new Error();
      values.splice(emailDomainIndex, 0, "", false);
    }
    if (Array.isArray(values) && !["adg-ui-v11", "adg-ui-v12"].includes(config.schema)) {
      const encodingScenarioIndex = legacyControlIndex("encoding-scenario");
      if (encodingScenarioIndex < 0) throw new Error();
      values.splice(encodingScenarioIndex, 0, "crm");
    }
    if (Array.isArray(values) && config.schema !== "adg-ui-v12") {
      const variedFormatIndex = controls.findIndex(el => el.id === "nest-varied-formats");
      if (variedFormatIndex < 0) throw new Error();
      values.splice(variedFormatIndex, 0, true);
    }
    const method = [...document.querySelectorAll('input[name="kind"]')].find(el => el.value === config.kind);
    const kinds = [...$("#column-template").content.querySelectorAll("option")].map(el => el.value);
    if (!["adg-ui-v1", "adg-ui-v2", "adg-ui-v3", "adg-ui-v4", "adg-ui-v5", "adg-ui-v6", "adg-ui-v8", "adg-ui-v9", "adg-ui-v10", "adg-ui-v11", "adg-ui-v12"].includes(config.schema) || !method || !Array.isArray(values) || values.length !== controls.length ||
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
    if (hasUnacknowledgedOperatorFile() && !window.confirm(t("discard_operator_confirmation"))) return;
    if (["adg-ui-v1", "adg-ui-v2"].includes(config.schema)) $("#env-layout").value = "standard";
    if (!["adg-ui-v4", "adg-ui-v5", "adg-ui-v6", "adg-ui-v8", "adg-ui-v9", "adg-ui-v10", "adg-ui-v11", "adg-ui-v12"].includes(config.schema)) { $("#nest-scenario").value = "crm"; $("#maze-scenario").value = "crm"; }
    if (!["adg-ui-v11", "adg-ui-v12"].includes(config.schema)) $("#encoding-scenario").value = "crm";
    controls.forEach((el, i) => { if (el.type === "checkbox") el.checked = values[i]; else el.value = values[i]; });
    activeNestDirectoryScenario = $("#nest-scenario").value;
    // Ownership attestation must be given by the current operator, not carried in an imported config.
    $("#vault-domain-authorized").checked = false;
    $("#db-email-domain-authorized").checked = false;
    $("#env-dev-url-authorized").checked = false;
    $("#database-template").dataset.selected = $("#database-template").value;
    const selectedTemplate = databaseTemplates.find(item => item.id === $("#database-template").value);
    $("#template-description").textContent = selectedTemplate?.description || t("template_help");
    $("#columns").replaceChildren();
    for (const [name, kind, options] of config.columns) {
      addColumn(name, kind); $("#columns").lastElementChild.querySelector(".column-options").value = options;
    }
    form.querySelectorAll('input[type="url"], [data-secret-url], #env-url, #db-url, #web-url')
      .forEach(el => { el.value = ""; });
    method.checked = true; updateFields(true); estimate(); updateMazeEstimate(); result.textContent = t("config_loaded");
  } catch (error) { result.textContent = error.message === "unsafe_setting_text" ? t("unsafe_setting_text") : error.message === "sensitive_setting_text" ? t("sensitive_setting_text") : t("config_invalid"); }
});
