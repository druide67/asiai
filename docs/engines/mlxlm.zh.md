---
description: "Mac 上的 mlx-lm 服务器基准测试：MoE 模型最优选择，端口 8080 配置和 Apple Silicon 性能数据。"
---

# mlx-lm

mlx-lm 是 Apple 的 MLX 参考推理服务器，通过端口 8080 在 Metal GPU 上原生运行模型。对 Apple Silicon 上的 MoE（混合专家）模型特别高效，利用统一内存实现零拷贝模型加载。

[mlx-lm](https://github.com/ml-explore/mlx-examples) 在 Apple MLX 上原生运行模型，提供高效的统一内存利用。

## 配置

```bash
brew install mlx-lm
mlx_lm.server --model mlx-community/gemma-2-9b-it-4bit
```

## 详情

| 属性 | 值 |
|------|---|
| 默认端口 | 8080 |
| API 类型 | OpenAI 兼容 |
| VRAM 报告 | 否 |
| 模型格式 | MLX（safetensors） |
| 检测方式 | `/version` 端点或 `lsof` 进程检测 |

## 说明

- mlx-lm 与 llama.cpp 共用端口 8080。asiai 使用 API 探测和进程检测来区分两者。
- 模型使用 HuggingFace/MLX 社区格式（如 `mlx-community/gemma-2-9b-it-4bit`）。
- 原生 MLX 执行通常在 Apple Silicon 上提供出色性能。

## 另见

使用 `asiai bench --engines mlxlm` 比较引擎 --- [了解方法](../benchmark-llm-mac.md)
