---
description: 安装 asiai 并在 2 分钟内完成首次 LLM 基准测试。一条命令，零依赖，适用于所有 Apple Silicon Mac。
---

# 快速入门

**Apple Silicon AI** — 多引擎 LLM 基准测试与监控 CLI 工具。

asiai 可以在你的 Mac 上对推理引擎进行并排比较。将同一个模型加载到 Ollama 和 LM Studio，运行 `asiai bench`，即可获得数据。不靠猜测，不靠感觉——只有 tok/s、TTFT、能效和稳定性等硬指标。

## 快速开始

```bash
pipx install asiai        # 推荐：隔离安装
```

或通过 Homebrew：

```bash
brew tap druide67/tap
brew install asiai
```

其他方式：

```bash
uvx asiai detect           # 免安装运行（需要 uv）
pip install asiai           # 标准 pip 安装
```

### 首次启动

```bash
asiai setup                # 交互式向导——检测硬件、引擎、模型
asiai detect               # 或直接跳到引擎检测
```

然后运行基准测试：

```bash
asiai bench -m qwen3.5 --runs 3 --power
```

示例输出：

```
  Mac Mini M4 Pro — Apple M4 Pro  RAM: 64.0 GB (42% used)  Pressure: normal

Benchmark: qwen3.5

  Engine       tok/s (±stddev)    Tokens   Duration     TTFT       VRAM    Thermal
  ────────── ───────────────── ───────── ────────── ──────── ────────── ──────────
  lmstudio    72.6 ± 0.0 (stable)   435    6.20s    0.28s        —    nominal
  ollama      30.4 ± 0.1 (stable)   448   15.28s    0.25s   26.0 GB   nominal

  Winner: lmstudio (2.4x faster)
  Power: lmstudio 13.2W (5.52 tok/s/W) — ollama 16.0W (1.89 tok/s/W)
```

## 测量指标

| 指标 | 说明 |
|------|------|
| **tok/s** | 生成速度（token/秒），不含 prompt 处理时间 |
| **TTFT** | 首 token 延迟——prompt 处理耗时 |
| **Power** | GPU 功耗（瓦特）（`sudo powermetrics`） |
| **tok/s/W** | 能效——每瓦每秒生成的 token 数 |
| **Stability** | 运行间方差：稳定（<5%）、波动（<10%）、不稳定（>10%） |
| **VRAM** | 内存占用——原生报告（Ollama、LM Studio）或通过 `ri_phys_footprint` 估算（所有引擎） |
| **Thermal** | CPU 温控状态和速度限制百分比 |

## 支持的引擎

| 引擎 | 端口 | API |
|------|------|-----|
| [Ollama](https://ollama.com) | 11434 | 原生 |
| [LM Studio](https://lmstudio.ai) | 1234 | OpenAI 兼容 |
| [mlx-lm](https://github.com/ml-explore/mlx-examples) | 8080 | OpenAI 兼容 |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | 8080 | OpenAI 兼容 |
| [oMLX](https://github.com/jundot/omlx) | 8000 | OpenAI 兼容 |
| [vllm-mlx](https://github.com/vllm-project/vllm) | 8000 | OpenAI 兼容 |
| [Exo](https://github.com/exo-explore/exo) | 52415 | OpenAI 兼容 |

## 自定义端口

如果你的引擎运行在非标准端口上，asiai 通常会通过进程检测自动找到它。你也可以手动注册：

```bash
asiai config add omlx http://localhost:8800 --label mac-mini
```

手动添加的引擎会被持久化保存，不会被自动清理。详见 [config](commands/config.md)。

## 系统要求

- macOS + Apple Silicon（M1 / M2 / M3 / M4）
- Python 3.11+
- 至少一个本地运行的推理引擎

## 零依赖

核心仅使用 Python 标准库——`urllib`、`sqlite3`、`subprocess`、`argparse`。无 `requests`，无 `psutil`，无 `rich`。

可选扩展：

- `asiai[web]` — FastAPI Web 仪表板（含图表）
- `asiai[tui]` — Textual 终端仪表板
- `asiai[mcp]` — AI Agent MCP 服务器
- `asiai[all]` — Web + TUI + MCP
- `asiai[dev]` — pytest、ruff、pytest-cov
