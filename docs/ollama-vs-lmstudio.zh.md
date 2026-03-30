---
title: "Ollama vs LM Studio：Apple Silicon 基准测试"
description: "Apple Silicon 上 Ollama vs LM Studio 基准测试：M4 Pro 上使用真实测量数据并排比较 tok/s、TTFT、功耗和 VRAM。"
type: article
date: 2026-03-28
updated: 2026-03-29
dataset:
  name: "Apple Silicon M4 Pro 上 Ollama vs LM Studio 基准测试"
  description: "在 Mac Mini M4 Pro 64GB 上使用 Qwen3-Coder-30B 对 Ollama（llama.cpp）和 LM Studio（MLX）进行正面对比基准测试。指标：tok/s、TTFT、GPU 功耗、能效、VRAM。"
  date: "2026-03"
---

# Ollama vs LM Studio：Apple Silicon 基准测试

哪个推理引擎在你的 Mac 上更快？我们使用 asiai 1.4.0 于 2026 年 3 月在相同模型和硬件上对 Ollama（llama.cpp 后端）和 LM Studio（MLX 后端）进行了正面对比测试。

## 测试配置

| | |
|---|---|
| **硬件** | Mac Mini M4 Pro，64 GB 统一内存 |
| **模型** | Qwen3-Coder-30B（MoE 架构，Q4_K_M / MLX 4-bit） |
| **asiai 版本** | 1.4.0 |
| **方法论** | 每引擎 1 次预热 + 1 次计时运行，temperature=0，引擎间卸载模型（[完整方法论](methodology.md)） |

## 结果

| 指标 | LM Studio (MLX) | Ollama (llama.cpp) | 差异 |
|------|-----------------|-------------------|------|
| **吞吐量** | 102.2 tok/s | 69.8 tok/s | **+46%** |
| **TTFT** | 291 ms | 175 ms | Ollama 更快 |
| **GPU 功耗** | 12.4 W | 15.4 W | **-20%** |
| **能效** | 8.2 tok/s/W | 4.5 tok/s/W | **+82%** |
| **进程内存** | 21.4 GB (RSS) | 41.6 GB (RSS) | -49% |

!!! note "关于内存数据"
    Ollama 会为整个上下文窗口（262K token）预分配 KV cache，导致内存占用偏高。LM Studio 按需分配 KV cache。进程 RSS 反映引擎进程使用的总内存，不仅仅是模型权重。

## 关键发现

### LM Studio 吞吐量胜出（+46%）

MLX 的原生 Metal 优化从 Apple Silicon 统一内存中提取更多带宽。在 MoE 架构上优势显著。在更大的 Qwen3.5-35B-A3B 变体上，差距更大：**71.2 vs 30.3 tok/s（2.3 倍）**。

### Ollama TTFT 胜出

Ollama 的 llama.cpp 后端处理初始 prompt 更快（175ms vs 291ms）。对于短 prompt 的交互式使用，Ollama 感觉更灵敏。对于较长的生成任务，LM Studio 的吞吐量优势主导总时间。

### LM Studio 更节能（+82%）

8.2 tok/s/W vs 4.5，LM Studio 每焦耳生成近两倍的 token。这对使用电池的笔记本和持续运行的服务器都很重要。

### 内存占用：上下文是关键

进程内存的巨大差距（21.4 vs 41.6 GB）部分是因为 Ollama 为最大上下文窗口预分配 KV cache。公平比较时应考虑工作负载中实际使用的上下文，而非峰值 RSS。

## 何时选用哪个

| 使用场景 | 推荐 | 原因 |
|---------|------|------|
| **最大吞吐量** | LM Studio (MLX) | 生成速度快 46% |
| **交互式聊天（低延迟）** | Ollama | TTFT 更低（175 vs 291 ms） |
| **电池续航 / 能效** | LM Studio | tok/s/W 高 82% |
| **Docker / API 兼容性** | Ollama | 更广泛的生态，OpenAI 兼容 API |
| **内存受限（16GB Mac）** | LM Studio | RSS 更低，按需 KV cache |
| **多模型服务** | Ollama | 内置模型管理，keep_alive |

## 其他模型

吞吐量差距因模型架构而异：

| 模型 | LM Studio (MLX) | Ollama (llama.cpp) | 差异 |
|------|-----------------|-------------------|------|
| Qwen3-Coder-30B (MoE) | 102.2 tok/s | 69.8 tok/s | +46% |
| Qwen3.5-35B-A3B (MoE) | 71.2 tok/s | 30.3 tok/s | +135% |

MoE 模型差异最大，因为 MLX 在 Metal 上更高效地处理稀疏专家路由。

## 运行你自己的基准测试

```bash
pip install asiai
asiai bench --engines ollama,lmstudio --prompts code --runs 3 --card
```

asiai 使用相同模型、相同提示词和相同硬件并排比较引擎。引擎间自动卸载模型以防止内存争用。

[查看完整方法论](methodology.md) · [查看社区排行榜](leaderboard.md) · [如何在 Mac 上做 LLM 基准测试](benchmark-llm-mac.md)
