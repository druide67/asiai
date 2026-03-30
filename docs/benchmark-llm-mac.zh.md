---
title: "如何在 Mac 上对 LLM 做基准测试"
description: "如何在 Mac 上做 LLM 推理基准测试：逐步指南，测量 tok/s、TTFT、功耗和 VRAM，支持多引擎 Apple Silicon。"
type: howto
date: 2026-03-28
updated: 2026-03-29
duration: PT5M
steps:
  - name: "安装 asiai"
    text: "通过 pip（pip install asiai）或 Homebrew（brew tap druide67/tap && brew install asiai）安装 asiai。"
  - name: "检测引擎"
    text: "运行 'asiai detect' 自动发现 Mac 上运行的推理引擎（Ollama、LM Studio、llama.cpp、mlx-lm、oMLX、vLLM-MLX、Exo）。"
  - name: "运行基准测试"
    text: "运行 'asiai bench' 自动检测引擎上的最佳模型并进行跨引擎比较，测量 tok/s、TTFT、功耗和 VRAM。"
---

# 如何在 Mac 上对 LLM 做基准测试

在 Mac 上运行本地 LLM？下面介绍如何测量真实性能——不是感觉，不是"好像很快"，而是实际的 tok/s、TTFT、功耗和内存占用。

## 为什么要做基准测试？

同一个模型在不同推理引擎上的运行速度差异很大。在 Apple Silicon 上，MLX 引擎（LM Studio、mlx-lm、oMLX）可以比 llama.cpp 引擎（Ollama）**快 2 倍**。不测量的话，你就在白白浪费性能。

## 快速开始（2 分钟）

### 1. 安装 asiai

```bash
pip install asiai
```

或通过 Homebrew：

```bash
brew tap druide67/tap
brew install asiai
```

### 2. 检测引擎

```bash
asiai detect
```

asiai 自动发现 Mac 上运行的引擎（Ollama、LM Studio、llama.cpp、mlx-lm、oMLX、vLLM-MLX、Exo）。

### 3. 运行基准测试

```bash
asiai bench
```

就这样。asiai 自动检测引擎上的最佳模型并进行跨引擎比较。

## 测量内容

| 指标 | 含义 |
|------|------|
| **tok/s** | 每秒生成的 token 数（仅生成阶段，不含 prompt 处理） |
| **TTFT** | 首 token 延迟——生成开始前的等待时间 |
| **Power** | 推理过程中的 GPU + CPU 功耗（通过 IOReport，无需 sudo） |
| **tok/s/W** | 能效——每瓦每秒生成的 token 数 |
| **VRAM** | 模型内存占用（原生 API 或通过 `ri_phys_footprint` 估算） |
| **Stability** | 运行间方差：稳定（CV<5%）、波动（<10%）、不稳定（>10%） |
| **Thermal** | Mac 在基准测试期间是否发生温控降频 |

## 示例输出

```
Mac16,11 — Apple M4 Pro  RAM: 64.0 GB  Pressure: normal

Benchmark: qwen3-coder-30b

  Engine        tok/s   Tokens Duration     TTFT       VRAM    Thermal
  lmstudio      102.2      537    7.00s    0.29s    24.2 GB    nominal
  ollama         69.8      512   17.33s    0.18s    32.0 GB    nominal

  Winner: lmstudio (+46% tok/s)

  Power Efficiency
    lmstudio     102.2 tok/s @ 12.4W = 8.23 tok/s/W
    ollama        69.8 tok/s @ 15.4W = 4.53 tok/s/W
```

*M4 Pro 64GB 真实基准测试的示例输出。你的数据会因硬件和模型而异。[查看更多结果 →](ollama-vs-lmstudio.md)*

## 高级选项

### 指定引擎比较

```bash
asiai bench --engines ollama,lmstudio,omlx
```

### 多提示词和多次运行

```bash
asiai bench --prompts code,reasoning,tool_call --runs 3
```

### 大上下文基准测试

```bash
asiai bench --context-size 64K
```

### 生成可分享卡片

```bash
asiai bench --card --share
```

生成基准测试卡片图片并将结果分享到[社区排行榜](leaderboard.md)。

## Apple Silicon 技巧

### 内存很重要

16GB Mac 上，建议使用加载后不超过 14GB 的模型。MoE 模型（Qwen3.5-35B-A3B，3B 活跃参数）是理想选择——以 7B 级内存占用提供 35B 级质量。

### 引擎选择比你想象的更重要

MLX 引擎在 Apple Silicon 上对大多数模型明显快于 llama.cpp。[查看我们的 Ollama vs LM Studio 对比](ollama-vs-lmstudio.md)获取真实数据。

### 温控降频

MacBook Air（无风扇）在 5-10 分钟持续推理后会降频。Mac Mini/Studio/Pro 可以处理持续工作负载而不降频。asiai 会自动检测和报告温控降频。

## 与社区对比

看看你的 Mac 与其他 Apple Silicon 机器相比如何：

```bash
asiai compare
```

或访问[在线排行榜](leaderboard.md)。

## 常见问题

**问：Apple Silicon 上最快的 LLM 推理引擎是什么？**
答：在 M4 Pro 64GB 的基准测试中，LM Studio（MLX 后端）的 token 生成速度最快——比 Ollama（llama.cpp）快 46%。但 Ollama 有更低的 TTFT（首 token 延迟）。详见我们的[详细对比](ollama-vs-lmstudio.md)。

**问：在 Mac 上运行 30B 模型需要多少 RAM？**
答：Q4_K_M 量化的 30B 模型使用 24-32 GB 统一内存（取决于引擎）。至少需要 32 GB RAM，理想情况下 64 GB 以避免内存压力。MoE 模型如 Qwen3.5-35B-A3B 仅使用约 7 GB 活跃参数。

**问：asiai 在 Intel Mac 上能用吗？**
答：不能。asiai 需要 Apple Silicon（M1/M2/M3/M4）。它使用 macOS 特有的 API 进行 GPU 指标采集、功耗监控和硬件检测，这些仅在 Apple Silicon 上可用。

**问：M4 上 Ollama 和 LM Studio 哪个更快？**
答：LM Studio 吞吐量更高（Qwen3-Coder-30B 上 102 tok/s vs 70 tok/s）。Ollama 首 token 延迟更低（0.18s vs 0.29s），且在大上下文窗口（>32K token）下 llama.cpp 预填充速度快达 3 倍。

**问：基准测试需要多长时间？**
答：快速基准测试约 2 分钟。完整的多引擎多提示词多次运行比较需要 10-15 分钟。使用 `asiai bench --quick` 进行快速单次测试。

**问：能和其他 Mac 用户比较结果吗？**
答：可以。运行 `asiai bench --share` 匿名提交结果到[社区排行榜](leaderboard.md)。使用 `asiai compare` 查看你的 Mac 与其他 Apple Silicon 机器的对比。

## 延伸阅读

- [基准测试方法论](methodology.md) — asiai 如何确保测量可靠
- [基准测试最佳实践](benchmark-best-practices.md) — 获取准确结果的技巧
- [引擎对比](ollama-vs-lmstudio.md) — Ollama vs LM Studio 正面对决
