---
description: "Apple SiliconでのOllamaの速度は？ベンチマーク設定、デフォルトポート（11434）、パフォーマンスのヒント、他のエンジンとの比較。"
---

# Ollama

Ollamaは、Mac上で最も人気のあるLLM推論エンジンで、llama.cppバックエンドを使用し、GGUFモデルをポート11434で提供します。M4 Pro 64GBでのベンチマークでは、Qwen3-Coder-30Bで70 tok/sを達成しましたが、スループットはLM Studio（MLX）より46%遅くなっています。

[Ollama](https://ollama.com)は、最も人気のあるローカルLLMランナーです。asiaiはそのネイティブAPIを使用します。

## セットアップ

```bash
brew install ollama
ollama serve
ollama pull gemma2:9b
```

## 詳細

| プロパティ | 値 |
|-----------|-----|
| デフォルトポート | 11434 |
| APIタイプ | ネイティブ（非OpenAI） |
| VRAMレポート | はい |
| モデルフォーマット | GGUF |
| ロード時間測定 | はい（`/api/generate`コールドスタートによる） |

## 備考

- Ollamaはモデルごとのvram使用量を報告し、asiaiはベンチマークとモニター出力に表示します。
- モデル名は`name:tag`形式を使用します（例：`gemma2:9b`、`qwen3.5:35b-a3b`）。
- asiaiは確定的なベンチマーク結果のために`temperature: 0`を送信します。

## 関連項目

Ollamaの比較を見る：[Ollama vs LM Studio ベンチマーク](../ollama-vs-lmstudio.md)
