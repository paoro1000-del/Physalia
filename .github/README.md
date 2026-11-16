# Physalia

![Physalia project key visual / Physalia プロジェクトのメインビジュアル](../images/00-0001_Main.jpg)

Physalia is a local toolkit for exploring defensive deception as a way to increase the effort required to reach real targets and create opportunities for detection and response. It helps users examine security measures and prepare synthetic materials for controlled evaluation. Effects depend on the attacker and deployment, and are not guaranteed.

Physaliaは、防御用ディセプションによって本物の目標に到達するまでの攻撃者の作業を増やし、検知・対応の機会を作る方法を検討するためのローカルツールキットです。セキュリティ対策を理解し、管理された評価に使う合成資料を準備できます。効果は攻撃者や配置環境に左右され、保証されません。

Current features include guidance and sample materials for selected measures, plus a local canary page for reviewing contact events. Generating artifacts does not contact canary URLs or deploy files. A contact event is recorded when a client sends a request to a canary URL; simply reading a file does not trigger one. Use it only in environments you own or are authorized to manage.

現在の機能には、一部の対策に関する説明とサンプル資料の生成、および接触イベントを確認するローカルのカナリアページがあります。生成時にカナリアURLへの接続やファイルの配置は行いません。クライアントからカナリアURLにリクエストが届くと接触イベントが記録されますが、ファイルを読むだけでは記録されません。自らが所有する環境、または管理する権限を得た環境でのみ使用してください。

This is currently a personal project, and pull requests from others are not being accepted for the time being.

個人プロジェクトとして開発しているため、当面、他の方からのPull Requestは受け付けていません。

- [English guide](../README_en.md)
- [日本語ガイド](../README.md)

## Security measures and 対策一覧

各対策の仕組み、対象とする脅威、運用上の限界を紹介します。開発中・技術紹介のみの項目は、利用状況を確認してください。

Explore how each measure works, the threats considered and its operational limitations. Check availability for concepts and work in progress.

| 対策 / Measure | 提供状況 / Availability |
| --- | --- |
| [カナリアファイル / Canary File](../docs/measures/canary-file.md) | サンプル生成 / Sample generation |
| [エンクリプテッド・ディープ・ネスト / Encrypted Deep Nest](../docs/measures/encrypted-deep-nest.md) | サンプル生成 / Sample generation |
| [デコイ・データベース / Decoy Database](../docs/measures/decoy-database.md) | サンプル生成 / Sample generation |
| [スタティック・デコイ・ポータル / Static Decoy Portal](../docs/measures/static-decoy-portal.md) | サンプル生成 / Sample generation |
| [フェイクトラップ / Fake Trap](../docs/measures/fake-trap.md) | サンプル生成 / Sample generation |
| [ランサムウェア・デコイフラッド / Ransomware Decoy Flood](../docs/measures/ransomware-decoy-flood.md) | 開発中 / In development |
| [パス・メイズ / Path Maze](../docs/measures/path-maze.md) | サンプル生成 / Sample generation |
| [スパース・デコイ / Sparse Decoy](../docs/measures/sparse-decoy.md) | サンプル生成 / Sample generation |
| [データ・ディルーション / Data Dilution](../docs/measures/data-dilution.md) | 技術紹介のみ / Concept only |
| [特権ハニーワード・セッション / Privilege Honeyword Session](../docs/measures/privilege-honeyword-session.md) | 技術紹介のみ / Concept only |
| [インフィニット・ストリーム / Infinite Stream](../docs/measures/infinite-stream.md) | 開発中 / In development |
| [ディレクトリ・メイズ / Directory Maze](../docs/measures/directory-maze.md) | 開発中 / In development |
| [エンコーディング・メイズ / Encoding Maze](../docs/measures/encoding-maze.md) | 開発中 / In development |
