---
title: "常见问题"
description: "关于 asiai 的常见问题：支持的引擎、Apple Silicon 要求、Mac 上 LLM 基准测试、RAM 需求等。"
type: faq
faq:
  - q: "什么是 asiai？"
    a: "asiai 是一个开源 CLI 工具，用于在 Apple Silicon Mac 上对 LLM 推理引擎做基准测试和监控。支持 7 个引擎（Ollama、LM Studio、mlx-lm、llama.cpp、oMLX、vllm-mlx、Exo），测量 tok/s、TTFT、功耗和 VRAM 占用。"
  - q: "Apple Silicon 上最快的 LLM 引擎是什么？"
    a: "在 M4 Pro 64GB 上用 Qwen3-Coder-30B 的基准测试中，LM Studio（MLX 后端）达到 102 tok/s，Ollama 为 70 tok/s——token 生成快 46%。但 Ollama 的首 token 延迟更低。"
  - q: "asiai 能在 Intel Mac 上运行吗？"
    a: "不能。asiai 需要 Apple Silicon（M1、M2、M3 或 M4）。它使用 macOS 特有 API 进行 GPU 指标采集、IOReport 功耗监控和硬件检测，这些仅在 Apple Silicon 芯片上可用。"
  - q: "本地运行 LLM 需要多少 RAM？"
    a: "Q4 量化的 7B 模型：最低 8 GB。13B：16 GB。30B：32-64 GB。Qwen3.5-35B-A3B 等 MoE 模型仅使用约 7 GB 活跃参数，非常适合 16 GB Mac。"
  - q: "Mac 上用 Ollama 还是 LM Studio 更好？"
    a: "取决于用途。LM Studio（MLX）吞吐量更高且更节能。Ollama（llama.cpp）首 token 延迟更低，处理大上下文窗口（>32K）更好。详见 asiai.dev/ollama-vs-lmstudio。"
  - q: "asiai 需要 sudo 或 root 权限吗？"
    a: "不需要。包括 GPU 监测（ioreg）和功耗监控（IOReport）在内的所有功能都无需 sudo。可选的 --power 参数用于与 powermetrics 交叉验证，是唯一使用 sudo 的功能。"
  - q: "如何安装 asiai？"
    a: "通过 pip（pip install asiai）或 Homebrew（brew tap druide67/tap && brew install asiai）安装。需要 Python 3.11+。"
  - q: "AI Agent 能使用 asiai 吗？"
    a: "可以。asiai 包含 11 个工具和 3 个资源的 MCP 服务器。用 pip install asiai[mcp] 安装，在 MCP 客户端（Claude Code、Cursor 等）中配置 asiai mcp。"
  - q: "功耗测量有多准确？"
    a: "IOReport 功耗读数与 sudo powermetrics 相比差异不到 1.5%，在 LM Studio（MLX）和 Ollama（llama.cpp）上均通过 20 个样本验证。"
  - q: "能同时对多个模型做基准测试吗？"
    a: "可以。使用 asiai bench --compare 运行跨模型基准测试。支持 model@engine 语法精确控制，最多 8 个比较槽位。"
  - q: "如何分享基准测试结果？"
    a: "运行 asiai bench --share 匿名提交结果到社区排行榜。添加 --card 生成 1200x630 的可分享基准测试卡片图片。"
  - q: "asiai 测量哪些指标？"
    a: "七个核心指标：tok/s（生成速度）、TTFT（首 token 延迟）、功耗（GPU+CPU 瓦特）、tok/s/W（能效）、VRAM 占用、运行间稳定性和温控降频状态。"
---

# 常见问题

## 通用

**什么是 asiai？**

asiai 是一个开源 CLI 工具，用于在 Apple Silicon Mac 上对 LLM 推理引擎做基准测试和监控。支持 7 个引擎（Ollama、LM Studio、mlx-lm、llama.cpp、oMLX、vllm-mlx、Exo），测量 tok/s、TTFT、功耗和 VRAM 占用，零依赖。

**asiai 能在 Intel Mac 或 Linux 上运行吗？**

不能。asiai 需要 Apple Silicon（M1、M2、M3 或 M4）。它使用 macOS 特有 API（`sysctl`、`vm_stat`、`ioreg`、`IOReport`、`launchd`），这些仅在 Apple Silicon Mac 上可用。

**asiai 需要 sudo 或 root 权限吗？**

不需要。包括 GPU 监测（`ioreg`）和功耗监控（`IOReport`）在内的所有功能都无需 sudo。可选的 `--power` 参数用于与 `powermetrics` 交叉验证，是唯一使用 sudo 的功能。

## 引擎与性能

**Apple Silicon 上最快的 LLM 推理引擎是什么？**

在 M4 Pro 64GB 上用 Qwen3-Coder-30B（Q4_K_M）的基准测试中，LM Studio（MLX 后端）达到 **102 tok/s**，Ollama 为 **70 tok/s**——token 生成快 46%。LM Studio 能效也高 82%（8.23 vs 4.53 tok/s/W）。详见我们的[详细对比](ollama-vs-lmstudio.md)。

**Mac 上用 Ollama 还是 LM Studio 更好？**

取决于你的使用场景：

- **LM Studio（MLX）**：适合高吞吐量场景（代码生成、长文本回复）。更快、更高效、VRAM 占用更低。
- **Ollama（llama.cpp）**：适合低延迟场景（聊天机器人、交互式使用）。TTFT 更快。更适合大上下文窗口（>32K token）。

**本地运行 LLM 需要多少 RAM？**

| 模型大小 | 量化 | 需要 RAM |
|---------|------|---------|
| 7B | Q4_K_M | 最低 8 GB |
| 13B | Q4_K_M | 最低 16 GB |
| 30B | Q4_K_M | 32-64 GB |
| 35B MoE（3B 活跃） | Q4_K_M | 16 GB（仅加载活跃参数） |

## 基准测试

**如何运行第一个基准测试？**

三条命令：

```bash
pip install asiai     # 安装
asiai detect          # 发现引擎
asiai bench           # 运行基准测试
```

**基准测试需要多长时间？**

快速基准测试（`asiai bench --quick`）约 2 分钟。完整的多引擎多提示词 3 次运行比较需要 10-15 分钟。

**功耗测量有多准确？**

IOReport 功耗读数与 `sudo powermetrics` 相比差异不到 1.5%，在 LM Studio（MLX）和 Ollama（llama.cpp）上均通过 20 个样本验证。

**能和其他 Mac 用户比较结果吗？**

可以。运行 `asiai bench --share` 匿名提交结果到[社区排行榜](leaderboard.md)。使用 `asiai compare` 查看你的 Mac 如何。

## AI Agent 集成

**AI Agent 能使用 asiai 吗？**

可以。asiai 包含 11 个工具和 3 个资源的 MCP 服务器。用 `pip install "asiai[mcp]"` 安装，在 MCP 客户端（Claude Code、Cursor、Windsurf）中配置 `asiai mcp`。详见 [Agent 集成指南](agent.md)。

**有哪些 MCP 工具？**

11 个工具：`check_inference_health`、`get_inference_snapshot`、`list_models`、`detect_engines`、`run_benchmark`、`get_recommendations`、`diagnose`、`get_metrics_history`、`get_benchmark_history`、`refresh_engines`、`compare_engines`。

3 个资源：`asiai://status`、`asiai://models`、`asiai://system`。
