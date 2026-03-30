---
description: MacのRAM、GPUコア数、サーマルヘッドルームに基づくハードウェアアウェアなモデル推奨。
---

# asiai recommend

ハードウェアと用途に基づくエンジン推奨を取得します。

## 使用方法

```bash
asiai recommend [options]
```

## オプション

| オプション | 説明 |
|-----------|------|
| `--model MODEL` | 推奨を取得するモデル |
| `--use-case USE_CASE` | 最適化対象：`throughput`、`latency`、`efficiency` |
| `--community` | コミュニティベンチマークデータを推奨に含める |
| `--db PATH` | ローカルベンチマークデータベースのパス |

## データソース

推奨は利用可能な最良データから、優先順位に従って構築されます：

1. **ローカルベンチマーク** — あなた自身のハードウェアでの実行結果
2. **コミュニティデータ** — 同様のチップからの集計結果（`--community` 使用時）
3. **ヒューリスティック** — ベンチマークデータがない場合の組み込みルール

## 信頼度レベル

| レベル | 基準 |
|--------|------|
| High | 5回以上のローカルベンチマーク実行 |
| Medium | 1〜4回のローカル実行、またはコミュニティデータあり |
| Low | ヒューリスティックベース、ベンチマークデータなし |

## 例

```bash
asiai recommend --model qwen3.5 --use-case throughput
```

```
  Recommendation: qwen3.5 — M4 Pro — throughput

  #   Engine       tok/s    Confidence   Source
  ── ────────── ──────── ──────────── ──────────
  1   lmstudio    72.6     high         local (5 runs)
  2   ollama      30.4     high         local (5 runs)
  3   exo         18.2     medium       community

  Tip: lmstudio is 2.4x faster than ollama for this model.
```

## 注意事項

- 最も正確な推奨のために、先に `asiai bench` を実行してください。
- `--community` を使用して、特定のエンジンをローカルでベンチマークしていない場合のギャップを埋められます。
- `efficiency` 用途は消費電力を考慮します（過去のベンチマークの `--power` データが必要）。
