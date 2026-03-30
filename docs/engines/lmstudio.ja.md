---
description: "Apple SiliconでのLM Studioベンチマーク：最速MLXエンジン、ポート1234セットアップ、VRAM使用量、Ollamaとの比較。"
---

# LM Studio

LM StudioはApple Silicon上で最速のMLX推論エンジンで、ポート1234でOpenAI互換APIによりモデルを提供します。M4 Pro 64GBでは、Qwen3-Coder-30B（MLX）で130 tok/sに達し、MoEモデルではOllamaのllama.cppバックエンドの約2倍の速度です。

[LM Studio](https://lmstudio.ai)はモデル管理用GUIを備えたOpenAI互換APIを提供します。

## セットアップ

```bash
brew install --cask lm-studio
```

LM Studioアプリからローカルサーバーを起動し、モデルをロードしてください。

## 詳細

| プロパティ | 値 |
|-----------|-----|
| デフォルトポート | 1234 |
| APIタイプ | OpenAI互換 |
| VRAMレポーティング | あり（`lms ps --json` CLI経由） |
| モデルフォーマット | GGUF、MLX |
| 検出 | `/lms/version` エンドポイントまたはアプリバンドルplist |

## VRAMレポーティング

v0.7.0以降、asiai はLM Studio CLI（`~/.lmstudio/bin/lms ps --json`）からVRAM使用量を取得します。これにより、OpenAI互換APIが公開しない正確なモデルサイズデータが提供されます。

`lms` CLIがインストールされていないか利用できない場合、asiai はVRAMを0として報告するフォールバック動作（v0.7.0以前と同じ）に移行します。

## 注意事項

- LM StudioはGGUFとMLXの両方のモデルフォーマットをサポートしています。
- バージョン検出は `/lms/version` APIエンドポイントを使用し、フォールバックとしてディスク上のアプリバンドルplistを使用します。
- モデル名は通常HuggingFaceフォーマット（例：`gemma-2-9b-it`）を使用します。

## 関連項目

LM Studioの比較を見る：[Ollama対LM Studioベンチマーク](../ollama-vs-lmstudio.md)
