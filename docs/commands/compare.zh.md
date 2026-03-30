---
description: 跨模型和跨引擎基准测试矩阵。在单次运行中比较最多 8 个 model@engine 组合。
---

# asiai compare

将你的本地基准测试与社区数据对比。

## 用法

```bash
asiai compare [options]
```

## 选项

| 选项 | 描述 |
|------|------|
| `--chip CHIP` | 对比的 Apple Silicon 芯片（默认：自动检测） |
| `--model MODEL` | 按模型名筛选 |
| `--db PATH` | 本地基准测试数据库路径 |

## 示例

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

## 说明

- 未指定 `--chip` 时，asiai 自动检测你的 Apple Silicon 芯片。
- Delta 显示你的本地中位数与社区中位数之间的百分比差异。
- 正数 delta 表示你的配置比社区平均更快。
- 本地结果来自你的基准测试历史数据库（默认 `~/.local/share/asiai/benchmarks.db`）。
