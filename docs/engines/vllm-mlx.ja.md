---
description: "Apple SiliconでのvLLM-MLX：MLXベースのvLLM互換API、ポート8000、Prometheusメトリクス、ベンチマークデータ。"
---

# vllm-mlx

vLLM-MLXは、MLXを通じてvLLMサービングフレームワークをApple Siliconに導入し、連続バッチ処理とOpenAI互換API（ポート8000）を提供します。最適化されたモデルでは400+ tok/sを達成でき、Mac上での同時推論で最速の選択肢の一つです。

[vllm-mlx](https://github.com/vllm-project/vllm)は、MLXを通じてApple Siliconに連続バッチ処理を提供します。

## セットアップ

```bash
pip install vllm-mlx
vllm serve mlx-community/gemma-2-9b-it-4bit
```

## 詳細

| プロパティ | 値 |
|-----------|-----|
| デフォルトポート | 8000 |
| APIタイプ | OpenAI互換 |
| VRAMレポート | いいえ |
| モデルフォーマット | MLX (safetensors) |
| 検出方法 | `/version`エンドポイントまたは`lsof`プロセス検出 |

## 備考

- vllm-mlxは連続バッチ処理をサポートしており、同時リクエスト処理に適しています。
- Apple Siliconの最適化モデルで400+ tok/sを達成できます。
- 標準のvLLM OpenAI互換APIを使用します。

## 関連項目

`asiai bench --engines vllm-mlx` でエンジンを比較 --- [方法を学ぶ](../benchmark-llm-mac.md)
