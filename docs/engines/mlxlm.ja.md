---
description: "Macでのmlx-lmサーバーベンチマーク：MoEモデルに最適、ポート8080設定、Apple Siliconパフォーマンスデータ。"
---

# mlx-lm

mlx-lmはAppleのリファレンスMLX推論サーバーで、Metal GPU上でモデルをネイティブに実行し、ポート8080を使用します。特にApple SiliconでのMoE（Mixture of Experts）モデルに効率的で、ユニファイドメモリを活用したゼロコピーモデルロードを実現します。

[mlx-lm](https://github.com/ml-explore/mlx-examples)は、Apple MLX上でモデルをネイティブに実行し、効率的なユニファイドメモリ活用を提供します。

## セットアップ

```bash
brew install mlx-lm
mlx_lm.server --model mlx-community/gemma-2-9b-it-4bit
```

## 詳細

| プロパティ | 値 |
|-----------|-----|
| デフォルトポート | 8080 |
| APIタイプ | OpenAI互換 |
| VRAMレポート | いいえ |
| モデルフォーマット | MLX (safetensors) |
| 検出方法 | `/version`エンドポイントまたは`lsof`プロセス検出 |

## 備考

- mlx-lmはllama.cppとポート8080を共有します。asiaiはAPIプローブとプロセス検出を使用して区別します。
- モデルはHuggingFace/MLXコミュニティフォーマットを使用します（例：`mlx-community/gemma-2-9b-it-4bit`）。
- ネイティブMLX実行により、Apple Siliconで優れたパフォーマンスを提供します。

## 関連項目

`asiai bench --engines mlxlm` でエンジンを比較 --- [方法を学ぶ](../benchmark-llm-mac.md)
