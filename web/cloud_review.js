"use strict";
(() => {
  const byId = id => document.getElementById(id);
  const graphHosts = new Set([
    "graph.microsoft.com", "graph.microsoft.us", "dod-graph.microsoft.us",
    "microsoftgraph.chinacloudapi.cn"
  ]);
  const copy = {
    ja: {
      utf8: "UTF-8で保存したログを選択してください。不正なUTF-8は文字化けしたまま解析せず、読み込みを拒否します。",
      encoding_error: "ログをUTF-8として読み込めませんでした。文字コードを確認し、UTF-8で保存し直してください。",
      legal: "日本法では、権限のあるログの分析自体は通常、不正アクセスに当たりません。米国のCFAAでも、権限のあるログ分析自体は第三者への無断アクセスとは限りません。他人の認証情報による無断ログインや、通信内容・個人情報の取扱いには日米の法令や州法が関係し得ます。これは一般的な一見解であり、導入前に適用地域に詳しい法律の専門家へ確認してください。",
      legal_guide: "法的ガイド",
      jump: "認証・クラウド操作ログを分析する ↓", title: "認証・クラウド操作ログの分析",
      intro: "Microsoft Entra / Graphの監査ログとデコイ接触イベントをローカルで確認します。",
      help: "Azure Monitor形式のCSV・JSON配列・JSON Linesを最大4ファイル、合計4MiB・10,000件まで選択します。CSVは1行256列までです。JSONのキー名は大文字小文字を区別せず、重複は曖昧な入力として拒否します。分析規則が使う項目だけをローカルAPIへ渡し、その他の列は送信前に除外します。ユーザー集計はUserIdを優先し、無い場合はUserPrincipalNameを使います。両方がない記録は項目不足として集計から除外します。同じユーザーを異なる識別子で表す記録が混在すると、別々に数えられることがあります。UserIdとUserPrincipalNameはローカル集計だけに使い、結果には返しません。調査用にテナントID、アプリID、サービスプリンシパルID、GraphのOperationId/RequestId、送信元IPは結果に表示される場合があります。結果には元ログの行番号も含まれ、元ログと照合すると個人を特定できる場合があります。結果画面と元ログを適切に保護してください。デコイ接触パスはハッシュ化して表示します。ログはこのPC内で処理し保存しません。examples/access_events.py はパスを既定でハッシュ化します。元のWebサーバーログには生パスが残るため、秘密トークンを含む場合は保護してください。リアルタイム監視・通知・遮断は行いません。",
      agent_help: "対話型または非対話型ユーザー、サービスプリンシパル、マネージドIDの成功サインインにAgent情報がある場合、AIエージェント活動候補を表示します。結果には種類別に「Agent列あり／対象記録数」と「値あり件数」も出ます。列の内容は送信・表示せず、有無だけを使います。正規利用も含むため要確認です。Agent情報がないことはAIエージェント不使用の証明ではありません。",
      choose: "ログファイル", analyze: "選択したログを分析", sample: "架空サンプルを分析", result: "分析結果", guide: "必要なログと対応手順",
      limits: "要確認の兆候です。通常操作でも発生します。該当なしは安全の証明ではなく、欠落ログ・対象外の操作は検知できません。",
      reading: "ローカルで分析中…", done: "分析が完了しました。", sample_done: "架空サンプルの分析が完了しました。", selection_changed: "ファイル選択が変わりました。新しい選択内容を分析してください。", invalid: "CSV・JSON配列・JSON Linesで、合計4MiB・10,000件以内のログを選んでください。", empty_file: "選択したファイルにログがありません。", too_many_files: "選択できるログは最大4ファイルです。", too_many_records: "ログが10,000件を超えているか、CSVのデータ行が多すぎます。対象期間を分けてください。", input_too_large: "選択したファイルの合計が4MiBを超えています。ファイルを分けるか、期間を短くしてください。", error: "分析できませんでした。ファイル形式とサーバーの状態を確認してください。", nofile: "ログファイルを選んでください。", empty: "要確認の兆候はありません。ログの種類・欠落件数も確認してください。", truncated: "優先度順に最大500件を表示し、同じ優先度では新しい時刻を先に並べます。全件を確認するには対象期間を分けて再分析してください。",
      coverage: "入力 {total}件 / 対象外 {skipped}件 / 重複サインイン {duplicates}件 / 要確認 {findings}件。ログ種別（認識件数 / 必須項目不足）: {coverage}",
      agent_coverage: "{identity}のAgent列あり {provided}/{records}件、値あり {populated}件",
      rules: {stream_auth_failure_summary: ["ストリーム認証の失敗", "無効なBearer認証の要約イベントです。誤設定もあり得ます。run_idとゲートウェイログを照合し、自動遮断には使わないでください。"], decoy_contact: ["デコイへの接触", "2xxはHTTP応答を示すだけで、本文全体の受信完了は保証しません。テストや正規スキャナーも含め、配信側ログと照合してください。"], credential_change: ["アプリ資格情報の追加・変更・削除", "変更者、対象アプリ、承認済み変更かを監査記録で確認してください。"], application_control_change: ["アプリ登録・所有者・ポリシーの変更", "アプリやサービスプリンシパルの作成・削除、所有者またはポリシーの変更を確認してください。正規の更新も該当します。"], role_assignment: ["ディレクトリロールの割り当て・変更・削除", "対象・変更者・承認を監査記録で確認してください。"], app_permission: ["アプリ権限または同意の変更", "付与先、権限の範囲、承認を確認してください。"], identity_security_change: ["ユーザーの認証情報・アカウント状態の変更", "パスワード、アプリパスワード、アカウント状態、パスキー等の変更を確認してください。正規の本人操作や管理作業も該当します。"], security_policy_change: ["認証・アクセス制御ポリシーの変更", "条件付きアクセス、セキュリティ既定値、リスクポリシー、バイパス対象ユーザーの変更を確認してください。承認済み変更も候補に含まれます。"], signin_burst: ["複数ユーザーへの認証失敗の集中", "同一テナント・IPで15分間に10失敗以上、5ユーザー以上です。正規アクセスと照合してください。"], agentic_signin: ["Agent情報を伴う成功サインイン", "EntraのAgent列に情報があるユーザー、サービスプリンシパルまたはマネージドIDの成功記録です。AIエージェント活動の調査候補ですが、正規利用もあり、侵害の証拠ではありません。Agent列の内容は画面に出しません。"], app_signin_then_graph: ["アプリ認証後のGraph操作", "同じテナント・アプリ・サービスプリンシパルで1時間以内に記録されたHTTP 2xx応答です。通常の業務通信も含みます。関連付けの強さを確認してください。侵害の証明ではありません。バッチ要求は外側の応答だけでは個別操作の成否が分からないため、OperationIdと個別リクエストのログを確認してください。"]},
      categories: {mail: "メール", files: "ファイル／サイト", roles: "ロール", application_permissions: "アプリ権限", authentication: "認証方法・ポリシー", privileged_access: "特権アクセス", device_management: "デバイス管理", security: "セキュリティ", agent_mcp: "Graph MCP エージェント", applications: "アプリ", directory: "ディレクトリ情報", batch: "一括要求"},
      correlations: {token_id: "トークンID一致（強い関連）", time_window: "時間幅のみ（弱い関連）"},
      correlation_notes: {token_id: "SignInActivityIdとUniqueTokenIdentifierの一致で関連付けました。侵害の証明ではありません。", time_window: "相関IDがないため、同一アプリと1時間以内の時刻だけで関連付けた候補です。"},
      record: "行", related: "関連行", tenant: "テナント", app: "アプリID", principal: "サービスプリンシパルID", identity_type: "ID種別", operation_id: "Operation ID", request_id: "Request ID", run_id: "実行ID", scope: "認証範囲", correlation: "関連付け", ip: "送信元IP", category: "操作分類", activity: "操作", outcome: "結果", method: "HTTPメソッド", http_status: "HTTP状態", body_bytes_sent: "送信バイト数（サーバー記録）", request_seconds: "処理時間（秒）", rate_limit_status: "Nginxのレート制限状態", connection_limit_status: "Nginx同時接続制限状態", path: "パス（制御文字はU+表記）", failures: "失敗", users: "対象ユーザー", when: "時刻", request_completed_at: "終了時刻",
    },
    en: {
      utf8: "Select logs saved as UTF-8. Invalid UTF-8 is rejected instead of being analyzed with replacement characters.",
      encoding_error: "The log could not be decoded as UTF-8. Check its encoding and save it as UTF-8.",
      legal: "Under Japanese law, reviewing logs you are authorized to access ordinarily is not unauthorized access. Under the U.S. CFAA, authorized log analysis is not necessarily unauthorized access to another system. Unauthorized login with another person's credentials and handling communications or personal data can implicate Japanese, federal or state law. This is a general interpretation; consult counsel familiar with the applicable jurisdictions before deployment.",
      legal_guide: "Legal guidance (Japan and U.S.)",
      jump: "Analyze identity and cloud activity logs ↓", title: "Identity and cloud log review",
      intro: "Review Microsoft Entra / Graph logs and decoy contact events locally.",
      help: "Select up to four Azure Monitor CSV, JSON array or JSON Lines files, totaling 4 MiB and 10,000 records. CSV files are limited to 256 columns per row. JSON keys are case-insensitive for review and duplicate names after case normalization are rejected as ambiguous. Only fields used by the review rules are sent to the local API; other columns are removed first. UserId is preferred for user aggregation, with UserPrincipalName as a fallback. Records with neither identifier are incomplete and excluded. If records identify the same user in different ways, they may be counted separately. UserId and UserPrincipalName are used only for local aggregation and are omitted from results. Findings may display tenant, app and service-principal IDs, Graph OperationId/RequestId and source IPs for investigation. Findings also include source row numbers, which may identify people when linked to the original logs; protect both accordingly. Decoy-contact paths are hashed before display. Logs stay on this computer and are not saved. examples/access_events.py hashes paths by default; protect the original web-server logs because they retain raw paths. No real-time monitoring, notification or blocking is performed.",
      agent_help: "Successful interactive or non-interactive user, service-principal and managed-identity sign-ins with Agent details can produce a possible AI-agent activity signal. Results show Agent-field coverage and nonempty values separately for each identity type. Raw field contents are not sent or displayed. Legitimate use also matches, so review it. Missing Agent details do not establish that no AI agent was used.",
      choose: "Log files", analyze: "Analyze selected logs", sample: "Analyze sample data", result: "Review findings", guide: "Required logs and response guide",
      limits: "These are review signals, including normal activity. No findings does not prove safety; missing logs and unsupported operations are not detected.",
      reading: "Analyzing locally…", done: "Analysis complete.", sample_done: "Sample data analysis complete.", selection_changed: "File selection changed. Analyze the new selection to refresh results.", cleared: "Selected files and displayed results were cleared from this page.", clear: "Clear files and results", invalid: "Choose valid CSV, JSON arrays or JSON Lines, up to 4 MiB and 10,000 records.", empty_file: "The selected file contains no log records.", too_many_files: "Select no more than four log files.", too_many_records: "The logs exceed 10,000 records or CSV data rows. Split them into shorter time ranges.", input_too_large: "The selected files exceed the 4 MiB combined limit. Split them or use a shorter time range.", error: "Analysis failed. Check the file format and local server.", nofile: "Select a log file.", empty: "No matching signals. Check log coverage and incomplete record counts too.", truncated: "Up to 500 findings are shown by rule priority, with the newest timestamps first within each priority. Analyze smaller time ranges to review all findings.",
      coverage: "Input {total} / unsupported {skipped} / duplicate sign-ins {duplicates} / signals {findings}. Log types (recognized / missing required fields): {coverage}",
      agent_coverage: "{identity} Agent field present: {provided}/{records}; nonempty: {populated}",
      rules: {stream_auth_failure_summary: ["Infinite Stream authentication failures", "This summarizes invalid backend Bearer attempts. Misconfiguration can also trigger it. Correlate the run_id with gateway logs; do not block automatically."], decoy_contact: ["Decoy contact", "A 2xx status shows an HTTP response, not that the full body was received. Correlate against hosting logs and expected scanner/test activity."], credential_change: ["Application credential added, changed or removed", "Check the actor, target application and approved change in the audit record."], application_control_change: ["Application, owner or policy change", "Review application or service-principal creation/deletion and owner or policy changes. Approved maintenance can also match."], role_assignment: ["Directory role assigned, changed or removed", "Review target, actor and approval in the audit record."], app_permission: ["App permission or consent change", "Review the app, scope and approval."], identity_security_change: ["User credential or account-state change", "Review password, app-password, account-state and passkey changes. Legitimate user actions and administration can also match."], security_policy_change: ["Authentication or access-policy change", "Review Conditional Access, security defaults, risk policies and bypass-user changes. Approved changes can also match."], signin_burst: ["Concentrated failures across accounts", "At least 10 failures across 5 users in the same tenant and IP within a sliding 15-minute window. Compare with expected activity."], distributed_signin_spray: ["Failures spread across multiple IPs", "At least 10 failures across 5 users and 2 source IPs in the same tenant within a sliding 15-minute window. VPNs and identity providers may generate legitimate matches; correlate users, source locations and known automation."], agentic_signin: ["Successful sign-in with Agent details", "A user, service-principal or managed-identity success record contains nonempty Entra Agent details. Review as possible AI-agent activity; legitimate use is also expected, so this is not proof of compromise. Raw Agent details are not displayed."], app_signin_then_graph: ["Graph activity following app sign-in", "HTTP 2xx response events share tenant, app and service principal within one hour. Normal workflows also match. Check the displayed correlation strength; no finding proves compromise. For a batch request, the outer response does not show whether each operation succeeded; review OperationId and individual request logs."]},
      categories: {mail: "Mail", files: "Files / sites", roles: "Roles", application_permissions: "App permissions", authentication: "Authentication methods / policy", privileged_access: "Privileged access", device_management: "Device management", security: "Security", agent_mcp: "Graph MCP agent", applications: "Applications", directory: "Directory data", batch: "Batch request"},
      correlations: {token_id: "Token ID match (stronger link)", time_window: "Time window only (weak link)"},
      correlation_notes: {token_id: "Matched SignInActivityId to UniqueTokenIdentifier. This does not prove compromise.", time_window: "The token ID was unavailable; this candidate uses only the same app and a one-hour time window."},
      record: "Record", related: "Related record", tenant: "Tenant", app: "App ID", principal: "Service principal ID", identity_type: "Identity type", operation_id: "Operation ID", request_id: "Request ID", run_id: "Run ID", scope: "Auth scope", correlation: "Correlation", ip: "Source IP", category: "Category", activity: "Activity", outcome: "Outcome", method: "HTTP method", http_status: "HTTP status", body_bytes_sent: "Bytes sent (server-side)", request_seconds: "Request time (seconds)", rate_limit_status: "Nginx rate-limit status", connection_limit_status: "Nginx connection-limit status", path: "Path (controls shown as U+ codes)", failures: "Failures", users: "Users", source_ips: "Source IPs", window_start: "Window start", when: "Time", request_completed_at: "Request completed",
    },
  };
  copy.ja.clear = "\u30ed\u30b0\u3068\u7d50\u679c\u3092\u6d88\u53bb";
  copy.ja.intro += " Infinite Streamのstream_auth_failure_summaryイベントも読み込み、無効なBearer認証の集計を確認できます。";
  copy.ja.cleared = "\u9078\u629e\u30d5\u30a1\u30a4\u30eb\u3068\u8868\u793a\u7d50\u679c\u3092\u753b\u9762\u304b\u3089\u6d88\u53bb\u3057\u307e\u3057\u305f\u3002";
  copy.en.intro += " It also reviews Infinite Stream stream_auth_failure_summary events for aggregated invalid Bearer attempts.";
  copy.ja.help += " \u7d4c\u8defID\u306f\u65e2\u5b9a\u3067\u9375\u306a\u3057SHA-256\u3067\u3059\u3002\u533f\u540d\u5316\u3067\u306f\u306a\u304f\u3001/admin\u7b49\u306e\u63a8\u6e2c\u3057\u3084\u3059\u3044\u30d1\u30b9\u306f\u7167\u5408\u3055\u308c\u308b\u53ef\u80fd\u6027\u304c\u3042\u308a\u307e\u3059\u3002\u30ab\u30ca\u30ea\u30a2\u30c8\u30fc\u30af\u30f3\u3092\u542b\u3080\u7d4c\u8def\u3067\u306f、examples/access_events.py \u306b\u7ba1\u7406\u8005\u3060\u3051\u304c\u8aad\u3081\u308b\u30e9\u30f3\u30c0\u30e0\u9375\u3092\u6307\u5b9a\u3057\u3066HMAC-SHA-256\u3092\u4f7f\u3044\u3001\u540c\u3058\u9375\u3067\u7d4c\u8def\u3092\u7167\u5408\u3057\u3066\u304f\u3060\u3055\u3044\u3002";
  copy.en.help += " Route IDs use unkeyed SHA-256 by default. This is pseudonymization, not anonymization; guessable paths such as /admin may be recovered by matching candidates. If routes contain canary tokens, use examples/access_events.py with a random HMAC key readable only by operators, and use the same key when correlating routes.";
  copy.ja.help = copy.ja.help.replace("\u5143\u30ed\u30b0\u306e\u884c\u756a\u53f7", "\u5165\u529b\u30ec\u30b3\u30fc\u30c9\u756a\u53f7");
  copy.ja.help += " \u30d5\u30a1\u30a4\u30eb\u3054\u3068\u306e\u8a18\u9332\u756a\u53f7\u3068\u5143\u30d5\u30a1\u30a4\u30eb\u540d\u306f\u30d6\u30e9\u30a6\u30b6\u5185\u3067\u5bfe\u5fdc\u4ed8\u3051\u3001\u30ed\u30fc\u30ab\u30ebAPI\u3078\u306f\u9001\u308a\u307e\u305b\u3093\u3002CSV\u306f\u30d8\u30c3\u30c0\u30fc\u3068\u7a7a\u884c\u3092\u9664\u3044\u305f\u30c7\u30fc\u30bf\u884c\u756a\u53f7\u3001JSON Lines\u306f\u7a7a\u884c\u3092\u9664\u3044\u305f\u8a18\u9332\u756a\u53f7\u3067\u3059\u3002";
  copy.en.help = copy.en.help.replace(
    "Findings also include source row numbers, which may identify people when linked to the original logs; protect both accordingly.",
    "Findings include combined input record numbers. For selected files, the browser adds each source file name and per-file record number locally; file names are not sent to the API. CSV numbering excludes the header and blank rows, and JSON Lines numbering excludes blank lines. Protect results and original logs because they may identify people."
  );
  copy.ja.source_file = "\u5143\u30d5\u30a1\u30a4\u30eb";
  copy.ja.source_record = "\u30d5\u30a1\u30a4\u30eb\u5185\u30ec\u30b3\u30fc\u30c9";
  copy.en.source_file = "Source file";
  copy.en.source_record = "Record in file";
  copy.ja.too_large = "\u89e3\u6790\u30c7\u30fc\u30bf\u3092API\u306b\u9001\u308bJSON\u304c8 MiB\u306e\u4e0a\u9650\u3092\u8d85\u3048\u3066\u3044\u307e\u3059\u3002\u30d5\u30a1\u30a4\u30eb\u3092\u5206\u5272\u3057\u3001\u671f\u9593\u3054\u3068\u306b\u5206\u3051\u3066\u5206\u6790\u3057\u3066\u304f\u3060\u3055\u3044\u3002";
  copy.en.too_large = "The projected analysis request exceeds the 8 MiB API limit. Split the files and analyze shorter time ranges.";
  copy.ja.rules.signin_after_failures = ["複数回の認証失敗後に成功", "同一ユーザーで15分以内に5回以上失敗した後の成功サインインです。本人の入力ミスや正規アクセスもあり得るため、対象アカウントと送信元、MFA・条件付きアクセスの結果を元ログで確認してください。"];
  copy.en.rules.signin_after_failures = ["Successful sign-in after repeated failures", "A successful sign-in followed at least five failures for the same user within 15 minutes. User mistakes and legitimate access can also match; review the account, source and MFA/Conditional Access results in the original logs."];
  const language = () => byId("language").value === "en" ? "en" : "ja";
  const tr = key => copy[language()][key];
  let lastResult = null, lastSources = null, statusKey = "";
  function setStatus(key) {
    statusKey = key;
    byId("cloud-status").textContent = key ? tr(key) : "";
  }
  function translate() {
    document.querySelectorAll("[data-cloud-i18n]").forEach(element => { element.textContent = tr(element.dataset.cloudI18n); });
    byId("cloud-guide").href = "/guide/" + language();
    if (lastResult) render(lastResult, lastSources);
    if (statusKey) setStatus(statusKey);
  }
  function visibleValue(value) {
    return Array.from(String(value), character => {
      if (!/[\p{Cc}\p{Cf}\p{Cs}\p{Zl}\p{Zp}]/u.test(character)) return character;
      return `<U+${character.codePointAt(0).toString(16).toUpperCase().padStart(4, "0")}>`;
    }).join("");
  }
  function render(data, recordSources = null) {
    const coverageLabels = language() === "ja"
      ? {decoy_contact: "デコイ接触", stream_auth_failure_summary: "Infinite Stream認証失敗"}
      : {decoy_contact: "Decoy contact", stream_auth_failure_summary: "Infinite Stream auth failures"};
    const coverage = Object.keys(data.coverage).map(name => `${coverageLabels[name] || name}: ${data.coverage[name]} / ${data.incomplete[name]}`).join(", ");
    const agent = data.agent_field || {};
    const coverageText = tr("coverage").replace("{total}", data.input_records).replace("{skipped}", data.skipped).replace("{duplicates}", data.duplicates).replace("{findings}", data.finding_count).replace("{coverage}", coverage);
    const agentText = [[language() === "ja" ? "ユーザー" : "User", agent.user_signin], ["SP", agent.service_principal], ["MI", agent.managed_identity]].map(([identity, metrics]) => {
      metrics = metrics || {records: 0, provided: 0, populated: 0};
      return tr("agent_coverage").replace("{identity}", identity).replace("{provided}", metrics.provided).replace("{populated}", metrics.populated).replace("{records}", metrics.records);
    }).join(" / ");
    byId("cloud-coverage").textContent = `${coverageText} ${agentText}`;
    const list = byId("cloud-findings"); list.replaceChildren();
    if (!data.findings.length) { const item = document.createElement("li"); item.textContent = tr("empty"); list.append(item); }
    for (const finding of data.findings) {
      const item = document.createElement("li"), title = document.createElement("strong"), evidence = document.createElement("span"), action = document.createElement("span");
      const description = tr("rules")[finding.rule] || (finding.rule === "distributed_signin_spray" && language() === "ja"
        ? ["IP\u5206\u6563\u578b\u306e\u8a8d\u8a3c\u5931\u6557", "15\u5206\u9593\u306b10\u4ef6\u4ee5\u4e0a\u306e\u5931\u6557\u30015\u30e6\u30fc\u30b6\u30fc\u4ee5\u4e0a\u30012\u9001\u4fe1\u5143IP\u4ee5\u4e0a\u3002VPN\u3084ID\u30d7\u30ed\u30d0\u30a4\u30c0\u30fc\u306e\u6b63\u898f\u52d5\u4f5c\u3082\u7167\u5408\u3057\u3066\u304f\u3060\u3055\u3044\u3002"]
        : finding.rule === "targeted_signin_failures" ? (language() === "ja"
          ? ["\u5358\u4e00\u30a2\u30ab\u30a6\u30f3\u30c8\u3078\u306e\u8a8d\u8a3c\u5931\u6557\u96c6\u4e2d", "\u540c\u4e00\u30c6\u30ca\u30f3\u30c8\u3067\u9023\u7d9a\u3059\u308b15\u5206\u9593\u306b20\u4ef6\u4ee5\u4e0a\u3067\u3059\u3002\u5143\u30ed\u30b0\u306e\u884c\u756a\u53f7\u304b\u3089\u5bfe\u8c61\u30a2\u30ab\u30a6\u30f3\u30c8\u3092\u78ba\u8a8d\u3057\u3001\u627f\u8a8d\u6e08\u307f\u81ea\u52d5\u51e6\u7406\u3084\u6b63\u898f\u5229\u7528\u3068\u7167\u5408\u3057\u3066\u304f\u3060\u3055\u3044\u3002\u30a2\u30ab\u30a6\u30f3\u30c8\u540d\u306f\u753b\u9762\u306b\u51fa\u3057\u307e\u305b\u3093\u3002"]
          : ["Repeated failures for one account", "At least 20 failures against one account in the same tenant within a sliding 15-minute window. Use the source record number to identify the account; correlate with approved automation and normal user activity. The account name is not displayed."])
        : [finding.rule, ""]);
      title.textContent = description[0];
      const fields = [["record", "record"], ["related_record", "related"], ["time", "when"], ["request_completed_at", "request_completed_at"], ["window_start", "window_start"], ["tenant", "tenant"], ["app_id", "app"], ["service_principal_id", "principal"], ["identity_type", "identity_type"], ["correlation", "correlation"], ["operation_id", "operation_id"], ["request_id", "request_id"], ["run_id", "run_id"], ["scope", "scope"], ["source_ip", "ip"], ["path", "path"], ["failures", "failures"], ["distinct_users", "users"], ["distinct_source_ips", "source_ips"], ["category", "category"], ["activity", "activity"], ["outcome", "outcome"], ["method", "method"], ["http_status", "http_status"], ["body_bytes_sent", "body_bytes_sent"], ["request_seconds", "request_seconds"], ["rate_limit_status", "rate_limit_status"], ["connection_limit_status", "connection_limit_status"]];
      const details = fields.filter(([field]) => finding[field] !== undefined && finding[field] !== "").map(([field, label]) => {
        let value = finding[field];
        if (field === "outcome" && value === "response_2xx") value = language() === "ja" ? "2xx応答" : "HTTP 2xx response";
        else if (field === "outcome" && value === "response_non_2xx") value = language() === "ja" ? "2xx以外の応答" : "HTTP non-2xx response";
        else if (field === "category") value = tr("categories")[value] || value;
        else if (field === "identity_type") value = language() === "ja" ? ({user_signin: "ユーザー", managed_identity: "マネージドID", service_principal: "サービスプリンシパル"}[value] || value) : ({user_signin: "User", managed_identity: "Managed identity", service_principal: "Service principal"}[value] || value);
        else if (field === "correlation") value = tr("correlations")[value] || value;
        const localizedLabel = field === "time" && finding.rule === "decoy_contact"
          ? (finding.request_completed_at
            ? (language() === "ja" ? "推定接触開始" : "Estimated contact start")
            : (language() === "ja" ? "ログ時刻" : "Log time"))
          : label === "source_ips" ? (language() === "ja" ? "\u9001\u4fe1\u5143IP\u6570" : tr(label))
          : label === "window_start" ? (language() === "ja" ? "\u96c6\u8a08\u7a93\u958b\u59cb" : tr(label)) : tr(label);
        return `${localizedLabel}: ${visibleValue(value)}`;
      });
      const sourceDetail = recordNumber => {
        if (!Number.isInteger(recordNumber) || recordNumber < 1) return "";
        const source = recordSources?.[recordNumber - 1];
        if (!source) return "";
        return `${tr("source_file")} ${source.fileIndex}: ${visibleValue(source.fileName)} (${tr("source_record")} ${source.fileRecord})`;
      };
      const source = sourceDetail(finding.record), relatedSource = sourceDetail(finding.related_record);
      if (source) details.push(source);
      if (relatedSource) details.push(`${tr("related")}: ${relatedSource}`);
      evidence.textContent = details.join(" / ");
      action.textContent = description[1] + (finding.correlation ? " " + (tr("correlation_notes")[finding.correlation] || "") : ""); item.append(title, evidence, action); list.append(item);
    }
    if (data.truncated) { const item = document.createElement("li"); item.textContent = tr("truncated"); list.append(item); }
    byId("cloud-result").hidden = false;
  }
  function clearResults() {
    lastResult = null;
    lastSources = null;
    byId("cloud-result").hidden = true;
    byId("cloud-coverage").textContent = "";
    byId("cloud-findings").replaceChildren();
  }
  function parseFile(text) {
    const trimmed = text.replace(/^\uFEFF/, "").trim();
    if (!trimmed) throw new Error("empty");
    try {
      window.assertNoDuplicateJsonKeys(trimmed);
      const parsed = JSON.parse(trimmed);
      return Array.isArray(parsed) ? parsed : [parsed];
    } catch (_) {
      return trimmed.split(/\r?\n/).filter(line => line.trim()).map(line => {
        window.assertNoDuplicateJsonKeys(line);
        return JSON.parse(line);
      });
    }
  }
  function parseCsv(text) {
    const maxColumns = 256;
    text = text.replace(/^\uFEFF/, "");
    const rows = []; let row = [], value = "", quoted = false, closed = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (quoted) {
        if (c === '"' && text[i + 1] === '"') { value += '"'; i++; }
        else if (c === '"') { quoted = false; closed = true; }
        else value += c;
      } else if (c === '"' && !value && !closed) quoted = true;
      else if (c === "," || c === "\n" || c === "\r") {
        if (row.length >= maxColumns) throw new Error("invalid");
        row.push(value); value = ""; closed = false;
        if (c !== ",") {
          if (c === "\r" && text[i + 1] === "\n") i++;
          if (rows.length >= 10001) throw new Error("too_many_records");
          rows.push(row); row = [];
        }
      } else {
        if (closed || c === '"') throw new Error("invalid");
        value += c;
      }
    }
    if (quoted) throw new Error("invalid");
    if (value || row.length || closed) {
      if (row.length >= maxColumns) throw new Error("invalid");
      if (rows.length >= 10001) throw new Error("too_many_records");
      row.push(value); rows.push(row);
    }
    if (!rows.length || rows.length > 10001) throw new Error("invalid");
    const headers = rows.shift().map(name => name.trim());
    if (headers.some(name => !name) || new Set(headers.map(name => name.toLowerCase())).size !== headers.length) throw new Error("invalid");
    return rows.filter(values => values.some(value => value !== "")).map(values => {
      if (values.length !== headers.length) throw new Error("invalid");
      const record = Object.create(null);
      headers.forEach((name, i) => { record[name] = values[i]; });
      return record;
    });
  }
  const retainedFields = new Map([
    ["type", ["Type", 80]], ["event", ["event", 80]], ["createddatetime", ["CreatedDateTime", 64]],
    ["activitydatetime", ["ActivityDateTime", 64]], ["timegenerated", ["TimeGenerated", 64]], ["time", ["time", 64]], ["timestamp", ["timestamp", 64]], ["request_completed_at", ["request_completed_at", 64]],
    ["id", ["Id", 128]],
    ["aadtenantid", ["AADTenantId", 128]], ["appid", ["AppId", 128]], ["serviceprincipalid", ["ServicePrincipalId", 128]],
    ["operationid", ["OperationId", 128]], ["requestid", ["RequestId", 128]],
    ["request_id", ["request_id", 32]], ["run_id", ["run_id", 16]], ["scope", ["scope", 16]], ["failures_total", ["failures_total", 32]],
    ["uniquetokenidentifier", ["UniqueTokenIdentifier", 256]], ["signinactivityid", ["SignInActivityId", 256]],
    ["resulttype", ["ResultType", 64]], ["status", ["Status", 64]], ["agent", ["Agent", 512]], ["ipaddress", ["IPAddress", 128]],
    ["userprincipalname", ["UserPrincipalName", 200]], ["userid", ["UserId", 200]],
    ["activitydisplayname", ["ActivityDisplayName", 160]], ["result", ["Result", 40]],
    ["responsestatuscode", ["ResponseStatusCode", 16]], ["requesturi", ["RequestUri", 2048]], ["requestmethod", ["RequestMethod", 16]], ["outcome", ["outcome", 30]],
    ["method", ["method", 8]], ["http_status", ["http_status", 3]], ["body_bytes_sent", ["body_bytes_sent", 32]], ["request_seconds", ["request_seconds", 32]], ["rate_limit_status", ["rate_limit_status", 32]], ["connection_limit_status", ["connection_limit_status", 32]], ["path", ["path", 512]], ["route_id", ["route_id", 80]],
  ]);
  const decoyOnlyFields = new Set(["request_completed_at", "outcome", "method", "http_status",
    "body_bytes_sent", "request_seconds", "rate_limit_status", "connection_limit_status", "path", "route_id"]);
  const streamOnlyFields = new Set(["timestamp", "run_id", "scope", "failures_total"]);
  function projectRecord(record) {
    // The analyzer skips non-object rows. Drop them here instead of sending
    // their arbitrary contents to the local API unnecessarily.
    if (!record || typeof record !== "object" || Array.isArray(record)) return null;
    const projected = Object.create(null);
    const eventValue = Object.entries(record).find(([key]) => key.toLowerCase() === "event")?.[1];
    const typeValue = Object.entries(record).find(([key]) => key.toLowerCase() === "type")?.[1];
    const isDecoyContact = (typeof eventValue === "string" && eventValue.toLowerCase() === "decoy_contact")
      || (typeof typeValue === "string" && typeValue.toLowerCase() === "decoy_contact");
    const isStreamAuthFailure = typeof eventValue === "string" && eventValue.toLowerCase() === "stream_auth_failure_summary";
    const routeIdValue = Object.entries(record).find(([key]) => key.toLowerCase() === "route_id")?.[1];
    const validRouteId = isDecoyContact && typeof routeIdValue === "string"
      && /^\/(?:sha256|hmac-sha256)\/[0-9a-f]{64}$/.test(routeIdValue);
    for (const [key, value] of Object.entries(record)) {
      const normalizedKey = key.toLowerCase();
      if (!isDecoyContact && decoyOnlyFields.has(normalizedKey)) continue;
      if (!isStreamAuthFailure && streamOnlyFields.has(normalizedKey)) continue;
      const selected = retainedFields.get(normalizedKey);
      if (!selected) continue;
      const [name, limit] = selected;
      if (normalizedKey === "agent") {
        // Preserve whether the export supplied this field, but never its raw metadata.
        if (typeof value === "string") {
          const text = value.trim();
          if (!text) projected[name] = false;
          else if (text.length > 8192) {
            const emptyContainer = ((text.startsWith("{") && text.endsWith("}"))
              || (text.startsWith("[") && text.endsWith("]"))) && !text.slice(1, -1).trim();
            projected[name] = !emptyContainer;
          }
          else {
            try {
              const parsed = JSON.parse(text);
              projected[name] = parsed === null || parsed === false || parsed === "" ? false
                : parsed && typeof parsed === "object" ? Object.keys(parsed).length > 0 : true;
            } catch (_) { projected[name] = true; }
          }
        } else {
          projected[name] = value === true || (typeof value === "number" && Number.isFinite(value))
            || Boolean(value && typeof value === "object" && Object.keys(value).length);
        }
        continue;
      }
      if (value === null || value === undefined || value === "") continue;
      if (normalizedKey === "body_bytes_sent" || normalizedKey === "request_seconds") {
        const numeric = typeof value === "number" ? value
          : typeof value === "string" && /^(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)$/.test(value.trim()) ? Number(value.trim()) : NaN;
        const maximum = normalizedKey === "body_bytes_sent" ? Number.MAX_SAFE_INTEGER : 1e9;
        if (Number.isFinite(numeric) && numeric >= 0 && numeric <= maximum) projected[name] = numeric;
      } else if (normalizedKey === "rate_limit_status") {
        if (isDecoyContact && ["PASSED", "DELAYED", "REJECTED", "DELAYED_DRY_RUN", "REJECTED_DRY_RUN"].includes(value)) projected[name] = value;
      } else if (normalizedKey === "connection_limit_status") {
        if (isDecoyContact && ["PASSED", "REJECTED", "REJECTED_DRY_RUN"].includes(value)) projected[name] = value;
      } else if (normalizedKey === "status") {
        const statusCode = typeof value === "number" ? value : typeof value === "string" && /^[0-9]{3}$/.test(value.trim()) ? Number(value.trim()) : NaN;
        if (isDecoyContact && Number.isInteger(statusCode) && statusCode >= 100 && statusCode <= 599) {
          projected.http_status = statusCode;
          continue;
        }
        // CSV exports stringify dynamic Status objects. Parse locally, then
        // forward only errorCode; failure descriptions and other details may
        // contain sensitive data and are not needed by the analyzer.
        let statusObject = value;
        if (typeof statusObject === "string") {
          try {
            window.assertNoDuplicateJsonKeys(statusObject);
            statusObject = JSON.parse(statusObject);
          } catch (_) { continue; }
        }
        if (!statusObject || typeof statusObject !== "object" || Array.isArray(statusObject)) continue;
        const code = Object.entries(statusObject).find(([child]) => child.toLowerCase() === "errorcode")?.[1];
        if (typeof code === "string") projected[name] = {errorCode: code.slice(0, limit)};
        else if (typeof code === "number" || typeof code === "boolean") projected[name] = {errorCode: code};
      } else if (normalizedKey === "requesturi" && typeof value === "string") {
        // Keep only paths from official HTTPS Graph endpoints. Do not let an
        // unrelated absolute URL classify as a Graph API operation.
        const uri = value.trim();
        if (uri.startsWith("//") || uri.includes("\\")) continue;
        try {
          const absoluteUri = /^[a-z][a-z0-9+.-]*:/i.test(uri);
          const parsed = absoluteUri ? new URL(uri) : new URL(uri, "https://graph.microsoft.com");
          if (parsed.protocol !== "https:") continue;
          if (absoluteUri && (!graphHosts.has(parsed.hostname.replace(/\.$/, "").toLowerCase())
              || parsed.username || parsed.password || (parsed.port && parsed.port !== "443"))) continue;
          projected[name] = parsed.pathname.slice(0, limit);
        } catch (_) { continue; }
      } else if (normalizedKey === "route_id") {
        // Only accept the converter's pseudonymous ID field for decoy events.
        // Raw paths that merely resemble a digest are still passed as `path`
        // and hashed by the local analyzer.
        if (validRouteId && value === routeIdValue) projected[name] = value;
      } else if (normalizedKey === "request_id") {
        // Decoy-contact correlation IDs are useful only in the server's
        // fixed 32-hex format. Do not forward arbitrary free-text values.
        if (isDecoyContact && typeof value === "string" && /^[0-9a-fA-F]{32}$/.test(value)) {
          projected[name] = value.toLowerCase();
        }
      } else if (normalizedKey === "path") {
        // Paths are relevant only for decoy contacts. Remove request metadata
        // before sending the remaining route to the local analyzer. A validated
        // route_id makes the raw path unnecessary.
        if (isDecoyContact && !validRouteId && typeof value === "string") {
          projected[name] = value.split(/[?#]/, 1)[0].slice(0, limit);
        }
      } else if (typeof value === "string") projected[name] = value.slice(0, limit);
      else if ((typeof value === "number" && Number.isFinite(value)) || typeof value === "boolean") projected[name] = value;
    }
    return projected;
  }
  async function analyze(records, completionStatus = "done", recordSources = null) {
    if (!Array.isArray(records) || records.length > 10000) throw new Error("invalid");
    const body = JSON.stringify({records: records.map(projectRecord)});
    if (new Blob([body]).size > 8 * 1024 * 1024) throw new Error("too_large");
    const response = await fetch("/api/analyze", {method: "POST", headers: {"Content-Type": "application/json", "X-ADG-Token": document.querySelector('meta[name="adg-token"]').content, "X-ADG-Language": language()}, body});
    if (!response.ok) throw new Error("server");
    lastResult = await response.json(); lastSources = recordSources; render(lastResult, lastSources); setStatus(completionStatus);
    byId("cloud-results-title").focus();
  }
  async function run(loader, completionStatus = "done") {
    byId("cloud-analyze").disabled = true; byId("cloud-sample").disabled = true;
    byId("cloud-files").disabled = true; byId("cloud-clear").disabled = true;
    clearResults(); setStatus("reading");
    try {
      const loaded = await loader();
      const records = Array.isArray(loaded) ? loaded : loaded.records;
      const sources = Array.isArray(loaded) ? null : loaded.sources;
      await analyze(records, completionStatus, sources);
    }
    catch (error) { setStatus(error.message === "nofile" ? "nofile" : error.message === "server" ? "error" : error.message === "encoding" ? "encoding_error" : error.message === "too_large" ? "too_large" : error.message === "empty" ? "empty_file" : error.message === "too_many_records" ? "too_many_records" : error.message === "input_too_large" ? "input_too_large" : error.message === "too_many_files" ? "too_many_files" : "invalid"); }
    finally { byId("cloud-analyze").disabled = false; byId("cloud-sample").disabled = false; byId("cloud-files").disabled = false; byId("cloud-clear").disabled = false; }
  }
  byId("cloud-analyze").addEventListener("click", () => run(async () => {
    const files = [...byId("cloud-files").files];
    if (!files.length) throw new Error("nofile");
    if (files.length > 4) throw new Error("too_many_files");
    if (files.reduce((total, file) => total + file.size, 0) > 4 * 1024 * 1024) throw new Error("input_too_large");
    const records = [], sources = [];
    for (let fileIndex = 0; fileIndex < files.length; fileIndex++) {
      const file = files[fileIndex];
      let content;
      try { content = new TextDecoder("utf-8", {fatal: true}).decode(await file.arrayBuffer()); }
      catch (_) { throw new Error("encoding"); }
      const parsed = file.name.toLowerCase().endsWith(".csv") ? parseCsv(content) : parseFile(content);
      if (records.length + parsed.length > 10000) throw new Error("too_many_records");
      for (let recordIndex = 0; recordIndex < parsed.length; recordIndex++) {
        records.push(parsed[recordIndex]);
        sources.push({fileIndex: fileIndex + 1, fileName: file.name.slice(0, 255), fileRecord: recordIndex + 1});
      }
    }
    return {records, sources};
  }));
  byId("cloud-sample").addEventListener("click", () => run(async () => {
    const response = await fetch("/cloud-review-sample.json");
    if (!response.ok) throw new Error("server");
    return response.json();
  }, "sample_done"));
  byId("cloud-files").addEventListener("change", () => {
    clearResults();
    setStatus(byId("cloud-files").files.length ? "selection_changed" : "");
  });
  byId("cloud-clear").addEventListener("click", () => {
    byId("cloud-files").value = "";
    clearResults();
    setStatus("cleared");
    byId("cloud-files").focus();
  });
  byId("language").addEventListener("change", translate);
  translate();
})();
