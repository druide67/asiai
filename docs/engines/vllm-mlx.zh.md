---
description: "Apple Silicon 上的 vLLM-MLX：基于 MLX 的 vLLM 兼容 API、端口 8000、Prometheus 指标和 benchmark 数据。"
---

# vllm-mlx

vLLM-MLX 将 vLLM 服务框架通过 MLX 引入 Apple Silicon，提供连续批处理和 OpenAI 兼容 API（端口 8000）。在优化模型上可达 400+ tok/s，是 Mac 上并发推理最快的选择之一。

[vllm-mlx](https://github.com/vllm-project/vllm) 通过 MLX 将连续批处理带到 Apple Silicon。

## 安装

```bash
pip install vllm-mlx
vllm serve mlx-community/gemma-2-9b-it-4bit
```

## 详情

| 属性 | 值 |
|------|-----|
| 默认端口 | 8000 |
| API 类型 | OpenAI 兼容 |
| VRAM 报告 | 否 |
| 模型格式 | MLX (safetensors) |
| 检测方式 | `/version` 端点或 `lsof` 进程检测 |

## 说明

- vllm-mlx 支持连续批处理，适合处理并发请求。
- 在 Apple Silicon 上使用优化模型可达 400+ tok/s。
- 使用标准 vLLM OpenAI 兼容 API。

## 另请参阅

使用 `asiai bench --engines vllm-mlx` 比较引擎 --- [了解方法](../benchmark-llm-mac.md)
