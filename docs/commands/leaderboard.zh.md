---
description: "浏览和查询 asiai 社区排行榜：比较 Apple Silicon 芯片和推理引擎间的基准测试结果。"
---

# asiai leaderboard

浏览 asiai 网络的社区基准测试数据。

## 用法

```bash
asiai leaderboard [options]
```

## 选项

| 选项 | 描述 |
|------|------|
| `--chip CHIP` | 按 Apple Silicon 芯片筛选（如 `M4 Pro`、`M2 Ultra`） |
| `--model MODEL` | 按模型名筛选 |

## 示例

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

## 说明

- 需要 `api.asiai.dev` 的社区 API。
- 结果已匿名化。不分享任何个人或机器识别数据。
- 使用 `asiai bench --share` 贡献你的结果。
