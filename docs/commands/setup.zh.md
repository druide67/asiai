---
description: "asiai 快速配置：设置引擎、测试连接，验证你的 Apple Silicon Mac 已准备好进行 LLM 基准测试。"
---

# asiai setup

面向新用户的交互式配置向导。检测硬件、查找推理引擎并建议下一步操作。

## 用法

```bash
asiai setup
```

## 功能

1. **硬件检测** — 识别 Apple Silicon 芯片和 RAM
2. **引擎扫描** — 检查已安装的推理引擎（Ollama、LM Studio、mlx-lm、llama.cpp、oMLX、vllm-mlx、Exo）
3. **模型检查** — 列出所有已检测引擎上的已加载模型
4. **守护进程状态** — 显示监控守护进程是否在运行
5. **下一步建议** — 基于配置状态建议命令

## 示例输出

```
  Setup Wizard

  Hardware:  Apple M4 Pro, 64 GB RAM

  Engines:
    ✓ ollama (v0.17.7) — 3 models loaded
    ✓ lmstudio (v0.4.5) — 1 model loaded

  Daemon: running (monitor + web)

  Suggested next steps:
    • asiai bench              Run your first benchmark
    • asiai monitor --watch    Watch metrics live
    • asiai web                Open the dashboard
```

## 未找到引擎时

如果未检测到引擎，setup 提供安装指导：

```
  Engines:
    No inference engines detected.

  To get started, install an engine:
    brew install ollama && ollama serve
    # or download LM Studio from https://lmstudio.ai
```
