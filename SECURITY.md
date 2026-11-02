# Security Policy

## Supported versions

Physalia is an early-stage project. Until a stable release is published, security fixes are intended for the latest default branch; older commits and generated samples are not maintained separately.

## Reporting a vulnerability

Please report suspected vulnerabilities privately through GitHub's **Report a vulnerability** feature for this repository. Do not publish exploit details in a public issue or discussion before maintainers have had a chance to investigate. Repository maintainers should enable GitHub private vulnerability reporting before inviting public use.

Include the affected commit or release, the component, a concise impact description, and reproduction steps using a local or otherwise authorized test environment. Do not attach real canary URLs, API keys, passwords, route HMAC keys, operator or inventory JSON files, production logs, customer data, or employee data. Redact tokens and personal information from screenshots and command output.

This project has no published response-time commitment. Reports will be reviewed as maintainer capacity allows. If a real credential or canary token was exposed, revoke or rotate it immediately; deleting the public post alone does not revoke it.

## Scope and safe testing

The project scope includes the local GUI and generator, generated sample code, and integration examples in this repository. Third-party dependencies should be reported to their maintainers as appropriate. Test only systems and accounts you own or are explicitly authorized to assess. The generated Infinite Stream sample has no total size or duration cap, but closes a connection after five seconds without socket activity, including a stalled write. Use an isolated environment and controlled clients when evaluating it.

## 日本語

### 対応バージョン

Physaliaは開発初期のプロジェクトです。安定版を公開するまでは、最新のデフォルトブランチを修正対象とします。過去のコミットや生成済みサンプルは個別に保守しません。

### 脆弱性の報告

このリポジトリのGitHubにある **Report a vulnerability** 機能から、非公開で報告してください。調査の機会を確保するため、脆弱性の詳細を公開IssueやDiscussionに投稿しないでください。一般公開を始める前に、メンテナーはGitHub Private Vulnerability Reportingを有効にしてください。

影響するコミットまたはリリース、対象コンポーネント、影響の概要、ローカルまたは明示的に許可された環境での再現手順を記載してください。実際のカナリアURL、APIキー、パスワード、経路HMAC鍵、operator/inventory JSON、本番ログ、顧客・従業員データは添付しないでください。スクリーンショットやコマンド出力に含まれるトークンや個人情報は伏せてください。

報告への対応時間は保証していません。メンテナーの対応可能な範囲で確認します。認証情報やカナリアトークンが漏えいした場合、公開投稿を削除するだけでは無効になりません。直ちに失効またはローテーションしてください。

### 対象範囲と安全な検証

対象範囲は、このリポジトリのローカルGUI・生成器・生成サンプルコード・連携例です。サードパーティ依存パッケージの問題は、必要に応じて各メンテナーへ報告してください。所有または明示的な許可を得たシステムとアカウントだけを検証してください。Infinite Streamの生成サンプルに総容量・総時間の上限はありませんが、ソケットが5秒間無通信になると接続を終了します。受信側が読み取らず書き込みが詰まった場合も対象です。評価時は隔離環境と制御されたクライアントを使用してください。
