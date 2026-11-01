# AiDeceptionGuard

AiDeceptionGuard is a local tool for generating synthetic decoy artifacts and reviewing security events. The generator does not contact canary URLs or deploy files; an HTTP alert generally requires a request to an embedded URL. Use it only in environments you own or are authorized to manage.

- [English guide](../README_en.md)
- [日本語ガイド](../README.md)

The project is an early prototype. Deception and delay effects depend on the attacker and deployment; they are not guaranteed. Keep operator-only inventories, canary URLs and passwords out of public directories and Git.

## Before inviting public contributions

- Enable GitHub Private Vulnerability Reporting so security reports have a private route.
- Enable secret-scanning alerts and push protection for the public repository where available, and keep personal push protection enabled. GitHub scans supported secret patterns only; custom canary URLs and provider tokens may not be recognized, so never rely on scanning to make committing them safe. See [secret-scanning scope](https://docs.github.com/en/code-security/reference/secret-security/secret-scanning-scope) and [supported patterns](https://docs.github.com/en/code-security/reference/secret-security/supported-secret-scanning-patterns).
- Protect the default branch. Require pull requests and the `Quality checks` workflow before merging; verify the required check covers the Python and operating-system matrix.
- Keep Actions permissions read-only unless a documented job needs more. Pin every third-party Action to a reviewed full commit SHA and set `persist-credentials: false` on source checkout.

## 公開前の確認

- GitHub の Private Vulnerability Reporting を有効にし、脆弱性を非公開で報告できる経路を用意します。
- 公開リポジトリの秘密情報スキャン通知とpush protectionを利用可能な範囲で有効にし、個人アカウントのpush protectionも有効のままにします。GitHubが検査するのは対応パターンの秘密情報です。独自カナリアURLや発行元トークンは検出されない場合があるため、検査機能に依存せず、Gitに追加しないでください。[秘密情報スキャンの範囲](https://docs.github.com/en/code-security/reference/secret-security/secret-scanning-scope) / [対応パターン](https://docs.github.com/en/code-security/reference/secret-security/supported-secret-scanning-patterns)を参照します。
- デフォルトブランチを保護し、Pull Request と `Quality checks` ワークフローの成功をマージ条件にします。Python・OSのマトリクス全体が必須チェックに含まれることを確認します。
- Actions の権限は、ジョブに明示的な必要がない限り読み取り専用にします。外部Actionはレビューした完全なコミットSHAで固定し、ソース取得では `persist-credentials: false` を設定します。
