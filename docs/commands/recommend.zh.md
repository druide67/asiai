---
description: 基于硬件的模型推荐，考虑 Mac 的 RAM、GPU 核心数和温控余量。
---

# asiai recommend

获取基于硬件和使用场景的引擎推荐。

## 用法

```bash
asiai recommend [options]
```

## 选项

| 选项 | 描述 |
|------|------|
| `--model MODEL` | 要获取推荐的模型 |
| `--use-case USE_CASE` | 优化目标：`throughput`、`latency` 或 `efficiency` |
| `--community` | 在推荐中包含社区基准测试数据 |
| `--db PATH` | 本地基准测试数据库路径 |

## 数据来源

推荐基于最佳可用数据构建，按优先级排列：

1. **本地基准测试** — 你自己在你的硬件上的运行结果
2. **社区数据** — 相似芯片的聚合结果（需 `--community`）
3. **启发式规则** — 无基准测试数据时的内置规则

## 置信度级别

| 级别 | 标准 |
|------|------|
| 高 | 5 次以上本地基准测试运行 |
| 中 | 1-4 次本地运行，或有社区数据 |
| 低 | 基于启发式，无基准测试数据 |

## 示例

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

## 说明

- 先运行 `asiai bench` 以获得最准确的推荐。
- 使用 `--community` 填补未在本地测试过的引擎的空白。
- `efficiency` 使用场景会考虑功耗（需要之前基准测试的 `--power` 数据）。
