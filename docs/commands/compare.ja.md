---
description: クロスモデル・クロスエンジンのベンチマークマトリクス。1回の実行で最大8つのmodel@engineの組み合わせを比較。
---

# asiai compare

ローカルベンチマークをコミュニティデータと比較します。

## 使用方法

```bash
asiai compare [options]
```

## オプション

| オプション | 説明 |
|-----------|------|
| `--chip CHIP` | 比較対象のApple Siliconチップ（デフォルト：自動検出） |
| `--model MODEL` | モデル名でフィルター |
| `--db PATH` | ローカルベンチマークデータベースのパス |

## 例

```bash
asiai compare --model qwen3.5
```

```
  Compare: qwen3.5 — M4 Pro

  Engine       Your tok/s   Community median   Delta
  ────────── ──────────── ────────────────── ────────
  lmstudio        72.6           70.1          +3.6%
  ollama          30.4           31.0          -1.9%

  Chip: Apple M4 Pro (auto-detected)
```

## 注意事項

- `--chip` が指定されていない場合、asiai はApple Siliconチップを自動検出します。
- デルタはローカルの中央値とコミュニティの中央値の差をパーセンテージで表示します。
- 正のデルタは、あなたのセットアップがコミュニティ平均より速いことを意味します。
- ローカル結果はベンチマーク履歴データベース（デフォルト：`~/.local/share/asiai/benchmarks.db`）から取得されます。
