---
description: "oMLX 在 Apple Silicon 上的 benchmark：SSD KV 缓存、连续批处理、端口 8000 以及性能对比。"
---

# oMLX

oMLX 是一个原生 macOS 推理服务器，使用分页 SSD KV 缓存来处理超出内存容量的大型上下文窗口，并通过连续批处理在端口 8000 上处理并发请求。它在 Apple Silicon 上同时支持 OpenAI 和 Anthropic 兼容的 API。

[oMLX](https://omlx.ai/) 是一个原生 macOS LLM 推理服务器，具有分页 SSD KV 缓存和连续批处理功能，从菜单栏管理。基于 MLX 构建，专为 Apple Silicon 设计。

## 安装

```bash
brew tap jundot/omlx https://github.com/jundot/omlx
brew install omlx
```

或从 [GitHub releases](https://github.com/jundot/omlx/releases) 下载 `.dmg`。

## 详情

| 属性 | 值 |
|------|-----|
| 默认端口 | 8000 |
| API 类型 | OpenAI 兼容 + Anthropic 兼容 |
| VRAM 报告 | 否 |
| 模型格式 | MLX (safetensors) |
| 检测方式 | `/admin/info` JSON 端点或 `/admin` HTML 页面 |
| 系统要求 | macOS 15+，Apple Silicon (M1+)，最低 16 GB RAM |

## 说明

- oMLX 与 vllm-mlx 共用端口 8000。asiai 使用 `/admin/info` 探测来区分两者。
- SSD KV 缓存可在较低内存压力下支持更大的上下文窗口。
- 连续批处理可提高并发请求下的吞吐量。
- 支持文本 LLM、视觉语言模型、OCR 模型、嵌入和重排器。
- `/admin` 的管理仪表板提供实时服务器指标。
- 通过 `.dmg` 安装时支持应用内自动更新。

## 另请参阅

使用 `asiai bench --engines omlx` 比较引擎 --- [了解方法](../benchmark-llm-mac.md)
