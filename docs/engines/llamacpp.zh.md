---
description: "Mac 上的 llama.cpp 服务器：底层控制，端口 8080，KV cache 指标和 Apple Silicon 基准测试结果。"
---

# llama.cpp

llama.cpp 是 GGUF 模型的基础 C++ 推理引擎，提供对 KV cache、线程数和上下文大小的最大底层控制，端口 8080。它是 Ollama 的后端，也可以独立运行用于 Apple Silicon 上的精细调优。

[llama.cpp](https://github.com/ggml-org/llama.cpp) 是支持 GGUF 模型的高性能 C++ 推理引擎。

## 配置

```bash
brew install llama.cpp
llama-server -m model.gguf
```

## 详情

| 属性 | 值 |
|------|---|
| 默认端口 | 8080 |
| API 类型 | OpenAI 兼容 |
| VRAM 报告 | 否 |
| 模型格式 | GGUF |
| 检测方式 | `/health` + `/props` 端点或 `lsof` 进程检测 |

## 说明

- llama.cpp 与 mlx-lm 共用端口 8080。asiai 通过 `/health` 和 `/props` 端点识别它。
- 服务器可以使用自定义上下文大小和线程数启动以进行调优。

## 另见

使用 `asiai bench --engines llamacpp` 比较引擎 --- [了解方法](../benchmark-llm-mac.md)
