---
description: "asiai コミュニティリーダーボードを閲覧・クエリ：Apple Siliconチップと推論エンジン間のベンチマーク結果を比較。"
---

# asiai leaderboard

asiai ネットワークからコミュニティベンチマークデータを閲覧します。

## 使用方法

```bash
asiai leaderboard [options]
```

## オプション

| オプション | 説明 |
|-----------|------|
| `--chip CHIP` | Apple Siliconチップでフィルター（例：`M4 Pro`、`M2 Ultra`） |
| `--model MODEL` | モデル名でフィルター |

## 例

```bash
asiai leaderboard --chip "M4 Pro"
```

```
  Community Leaderboard — M4 Pro

  Model                  Engine      tok/s (median)   Runs   Contributors
  ──────────────────── ────────── ──────────────── ────── ──────────────
  qwen3.5:35b-a3b       ollama          30.4          42         12
  qwen3.5:35b-a3b       lmstudio        72.6          38         11
  llama3.3:70b           exo            18.2          15          4
  gemma2:9b              mlx-lm        105.3          27          9

  Source: api.asiai.dev — 122 results
```

## 注意事項

- `api.asiai.dev` のコミュニティAPIが必要です。
- 結果は匿名化されています。個人またはマシン識別データは共有されません。
- `asiai bench --share` で自分の結果を提供できます。
