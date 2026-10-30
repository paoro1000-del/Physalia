# Contributing to AiDeceptionGuard

[日本語](#日本語)

AiDeceptionGuard is an early-stage defensive deception project. Contributions should improve two primary outcomes: make decoys credible to people and AI-assisted attackers, and consume enough attacker time or effort to create a useful response opportunity. Detection quality and impact on authorized users matter too.

## Design and safety

- Evaluate a method from the attacker's information and constraints. Include automated collection, AI-assisted analysis, parallel and offline work, short time budgets, and alternate paths to the real target.
- Explain what makes a decoy plausible in its deployment context, what action creates delay, what signal reaches the defender, and how an attacker or normal user can bypass it. Do not promise that a decoy is indistinguishable or unavoidable.
- Use synthetic data and reserved example domains. Never add real credentials, personal data, secrets, or live third-party endpoints.
- Generated content must remain inert. Do not add executable payloads, credential collection for real services, instructions to disclose or destroy third-party data, unauthorized access, or traffic to third parties. Keep AI-facing lures to bounded, fictional workflow context.
- Keep network access, deployment and alert delivery outside the local generator unless a change explicitly requires them and has a safe, authorized design.
- Preserve resource limits, operator control, and the Infinite Stream's intentional no-total-size/no-total-duration behavior while connected.

## Implementation and documentation

- Keep Japanese and English UI and user documentation aligned. Explain the intended threat, prerequisites, detection behavior, limitations, and operational impact in plain terms. GitHub Actions checks app and cloud-panel translations, backend review-rule descriptions or fallbacks, frontend/backend generation-setting parity, canary URL settings privacy, the integration-kit allowlist, common unsafe browser DOM-sink patterns, audit KQL coverage, study metadata, local Markdown/HTML links, and UTF-8 source integrity. The DOM-sink scan is heuristic and does not prove browser safety. CI also runs unit tests and JavaScript syntax checks on Windows, Ubuntu and macOS with Python 3.11–3.14; the browser integration check runs on Windows.
- Distinguish a reasoned hypothesis from a measured result. Evaluation examples must use mock targets and report authorized-user impact, false alerts, resource costs, and target reach—not just decoy contacts or time spent.
- For Japan-law guidance, state the assumed authorized deployment and the concrete conduct that can change the assessment. Do not present a general legal guarantee.
- Keep dependency versions exact and commit SHA-256 hashes for every allowed distribution. GitHub Actions validates the lock format, installs with `--require-hashes --no-deps --only-binary=:all:`, and runs `pip check`. `--no-deps` alone does not pin isolated source-build dependencies; do not remove the binary-only flag without reviewing and pinning the build toolchain. The PyPI advisory check runs on Ubuntu with Python 3.14 and requires network access. Review the publisher and package contents before deliberately changing versions or hashes; do not replace pins with floating latest-version constraints. Hashes detect changed files but do not establish package safety. The advisory check does not detect every malicious package or vulnerable native library.
- Keep operator inventories, generated artifacts and canary URLs out of source control. Use synthetic fixtures and redact secrets from issues, screenshots and logs.

## Submitting a change

Describe the user problem, attacker model, expected benefit, bypasses, authorized-user risks, resource cost, and how the change can be evaluated safely. Update relevant Japanese and English documentation and examples with the implementation. Do not publish vulnerability details in an issue; follow [SECURITY.md](SECURITY.md) for private reporting.

---

## 日本語

AiDeceptionGuardは開発初期の防御用ディセプション・プロジェクトです。主な目的は、デコイを人やAI支援型の攻撃者に本物らしく見せることと、攻撃者の時間・作業を消費して対応機会を作ることです。検知の質と正規利用者への影響も重視します。

### 設計と安全性

- 攻撃者が持つ情報と制約から手法を評価してください。自動収集、AIによる解析、並列・オフライン処理、短い時間予算、本物への別経路を考慮します。
- 配置先で何が自然に見えるか、どの操作に時間がかかるか、防御側に何が通知されるか、攻撃者や正規利用者がどう迂回・誤操作するかを説明してください。見破れない、回避不能とは表現しません。
- 架空データと予約済みの例示ドメインを使ってください。実認証情報、個人データ、秘密情報、第三者の実在エンドポイントを追加しないでください。
- 生成物は不活性に保ちます。実サービスの認証情報収集、実行可能なペイロード、第三者データの開示・破壊、無断アクセス、第三者への通信を追加しません。AI向けの誘導は、範囲を限定した架空の業務文脈に留めます。
- 明確な要件と安全な権限設計がない限り、ローカル生成器に通信・配置・通知を追加しません。
- リソース上限と運用者の停止手段を維持します。インフィニット・ストリームは、接続中に総サイズ・総時間で終了しない性質を保ちます。

### 実装と説明

- 日本語と英語のUI・利用者向け文書を揃えます。想定脅威、必要条件、検知方法、限界、運用影響を平易に説明してください。GitHub Actionsでは、アプリとクラウド分析パネルの翻訳、バックエンド検知ルールの画面説明またはフォールバック、UIとバックエンドの生成設定キー、カナリアURL設定の秘匿性、統合キットの許可リスト、代表的な危険DOM sinkのパターン、監査KQL、実験メタデータ、Markdown/HTMLのローカルリンク、UTF-8ソースの整合性を検査します。DOM検査はヒューリスティックであり、ブラウザーの安全性を証明するものではありません。CIではWindows・Ubuntu・macOSのPython 3.11〜3.14でユニットテストとJavaScript構文検査も実行し、ブラウザー連携確認はWindowsで実行します。
- 推論と実測を区別します。評価例は模擬ターゲットを使い、デコイ接触や所要時間だけでなく、正規利用者への影響、誤通知、リソース費用、模擬秘密への到達を記録します。
- 日本法の説明は、権限のある配置という前提と、評価を変える具体的行為を示してください。包括的な適法保証はしません。
- 依存バージョンを完全一致で固定し、許可する全配布物のSHA-256もコミットします。GitHub Actionsはロック形式を検査し、`--require-hashes --no-deps --only-binary=:all:`でwheelだけをインストールしてから`pip check`を実行します。`--no-deps`だけではソース配布物の隔離ビルド依存は固定されません。ビルド要件を確認・固定せずにwheel限定を解除しないでください。PyPIの既知脆弱性照合はUbuntu・Python 3.14のジョブで実行し、ネットワーク接続を使います。バージョンやハッシュの変更前に配布元とパッケージ内容を確認してください。ハッシュはファイルの差し替えを検知しますが、パッケージ自体の安全性を保証しません。脆弱性照合も、すべての悪意ある配布物やネイティブライブラリの問題を検出するわけではありません。最新版への浮動指定は使いません。
- operator/inventory、生成物、カナリアURLをソース管理に含めないでください。課題・画面・ログには架空データを用い、秘密情報を伏せてください。

### 変更の提案

利用者の課題、攻撃者モデル、期待する効果、迂回方法、正規利用者へのリスク、リソース費用、安全な評価方法を説明してください。実装に関連する日英の説明と例も更新してください。脆弱性の詳細は公開Issueに書かず、[SECURITY.md](SECURITY.md)の非公開報告手順を使ってください。
