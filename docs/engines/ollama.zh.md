---
description: "Ollama 在 Apple Silicon 上的速度如何？Benchmark 设置、默认端口 (11434)、性能优化技巧以及与其他引擎的对比。"
---

# Ollama

Ollama 是 Mac 上最流行的 LLM 推理引擎，基于 llama.cpp 后端，使用 GGUF 格式模型，默认端口为 11434。在我们的 M4 Pro 64GB benchmark 测试中，它在 Qwen3-Coder-30B 上达到 70 tok/s，但吞吐量比 LM Studio (MLX) 慢 46%。

[Ollama](https://ollama.com) 是最受欢迎的本地 LLM 运行工具。asiai 使用其原生 API。

## 安装

```bash
brew install ollama
ollama serve
ollama pull gemma2:9b
```

## 详情

| 属性 | 值 |
|------|-----|
| 默认端口 | 11434 |
| API 类型 | 原生（非 OpenAI） |
| VRAM 报告 | 是 |
| 模型格式 | GGUF |
| 加载时间测量 | 是（通过 `/api/generate` 冷启动） |

## 说明

- Ollama 可报告每个模型的 VRAM 使用量，asiai 在 benchmark 和监控输出中显示该信息。
- 模型名称使用 `name:tag` 格式（例如 `gemma2:9b`、`qwen3.5:35b-a3b`）。
- asiai 发送 `temperature: 0` 以获得确定性的 benchmark 结果。

## 另请参阅

查看 Ollama 的对比：[Ollama vs LM Studio benchmark](../ollama-vs-lmstudio.md)
