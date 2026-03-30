---
description: "Apple SiliconでのoMLXベンチマーク：SSD KVキャッシュ、連続バッチ処理、ポート8000、パフォーマンス比較。"
---

# oMLX

oMLXはネイティブmacOS推論サーバーで、ページドSSD KVキャッシュを使用してメモリだけでは対応できない大きなコンテキストウィンドウを処理し、ポート8000で連続バッチ処理による同時リクエスト処理を実現します。Apple Silicon上でOpenAIおよびAnthropic互換APIの両方をサポートしています。

[oMLX](https://omlx.ai/)は、ページドSSD KVキャッシュと連続バッチ処理を備えたネイティブmacOS LLM推論サーバーです。メニューバーから管理でき、Apple Silicon向けにMLXで構築されています。

## セットアップ

```bash
brew tap jundot/omlx https://github.com/jundot/omlx
brew install omlx
```

または[GitHubリリース](https://github.com/jundot/omlx/releases)から`.dmg`をダウンロードしてください。

## 詳細

| プロパティ | 値 |
|-----------|-----|
| デフォルトポート | 8000 |
| APIタイプ | OpenAI互換 + Anthropic互換 |
| VRAMレポート | いいえ |
| モデルフォーマット | MLX (safetensors) |
| 検出方法 | `/admin/info` JSONエンドポイントまたは`/admin` HTMLページ |
| 要件 | macOS 15+、Apple Silicon (M1+)、最低16 GB RAM |

## 備考

- oMLXはvllm-mlxとポート8000を共有します。asiaiは`/admin/info`プローブを使用して区別します。
- SSD KVキャッシュにより、メモリ圧力を抑えつつ大きなコンテキストウィンドウに対応できます。
- 連続バッチ処理により、同時リクエスト時のスループットが向上します。
- テキストLLM、視覚言語モデル、OCRモデル、埋め込み、リランカーをサポートしています。
- `/admin`の管理ダッシュボードでリアルタイムのサーバーメトリクスを確認できます。
- `.dmg`インストール時はアプリ内自動更新に対応しています。

## 関連項目

`asiai bench --engines omlx` でエンジンを比較 --- [方法を学ぶ](../benchmark-llm-mac.md)
