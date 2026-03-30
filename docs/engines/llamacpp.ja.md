---
description: "Macでのllama.cppサーバー：低レベル制御、ポート8080、KVキャッシュメトリクス、Apple Siliconでのベンチマーク結果。"
---

# llama.cpp

llama.cppはGGUFモデル用の基盤的なC++推論エンジンで、ポート8080でKVキャッシュ、スレッド数、コンテキストサイズの最大限の低レベル制御を提供します。Ollamaのバックエンドとして動作しますが、Apple Siliconでの細かいチューニングのためにスタンドアロンで実行することもできます。

[llama.cpp](https://github.com/ggml-org/llama.cpp)はGGUFモデルをサポートする高性能C++推論エンジンです。

## セットアップ

```bash
brew install llama.cpp
llama-server -m model.gguf
```

## 詳細

| プロパティ | 値 |
|-----------|-----|
| デフォルトポート | 8080 |
| APIタイプ | OpenAI互換 |
| VRAMレポーティング | なし |
| モデルフォーマット | GGUF |
| 検出 | `/health` + `/props` エンドポイントまたは `lsof` プロセス検出 |

## 注意事項

- llama.cppはmlx-lmとポート8080を共有しています。asiai は `/health` と `/props` エンドポイントで検出します。
- サーバーはチューニングのためにカスタムコンテキストサイズとスレッド数で起動できます。

## 関連項目

`asiai bench --engines llamacpp` でエンジンを比較 --- [詳しくはこちら](../benchmark-llm-mac.md)
