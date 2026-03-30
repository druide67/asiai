---
description: "LM Studio Apple Silicon 基准测试：最快的 MLX 引擎，端口 1234 配置，VRAM 占用，以及与 Ollama 的对比。"
---

# LM Studio

LM Studio 是 Apple Silicon 上最快的 MLX 推理引擎，在端口 1234 上提供 OpenAI 兼容 API。在 M4 Pro 64GB 上，Qwen3-Coder-30B（MLX）达到 130 tok/s，对于 MoE 模型比 Ollama 的 llama.cpp 后端快近 2 倍。

[LM Studio](https://lmstudio.ai) 提供 OpenAI 兼容 API 和图形化模型管理界面。

## 配置

```bash
brew install --cask lm-studio
```

从 LM Studio 应用启动本地服务器，然后加载模型。

## 详情

| 属性 | 值 |
|------|---|
| 默认端口 | 1234 |
| API 类型 | OpenAI 兼容 |
| VRAM 报告 | 是（通过 `lms ps --json` CLI） |
| 模型格式 | GGUF、MLX |
| 检测方式 | `/lms/version` 端点或应用 bundle plist |

## VRAM 报告

自 v0.7.0 起，asiai 从 LM Studio CLI（`~/.lmstudio/bin/lms ps --json`）获取 VRAM 占用。这提供了 OpenAI 兼容 API 不暴露的准确模型大小数据。

如果 `lms` CLI 未安装或不可用，asiai 优雅降级为报告 VRAM 为 0（与 v0.7.0 之前行为相同）。

## 说明

- LM Studio 支持 GGUF 和 MLX 模型格式。
- 版本检测使用 `/lms/version` API 端点，降级时使用磁盘上的应用 bundle plist。
- 模型名通常使用 HuggingFace 格式（如 `gemma-2-9b-it`）。

## 另见

查看 LM Studio 的表现：[Ollama vs LM Studio 基准测试](../ollama-vs-lmstudio.md)
