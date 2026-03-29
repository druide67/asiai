---
description: "oMLX benchmark on Apple Silicon: SSD KV caching, continuous batching, port 8000, and performance comparison."
---

# oMLX

oMLX is a native macOS inference server that uses paged SSD KV caching to handle larger context windows than memory alone would allow, with continuous batching for concurrent requests on port 8000. It supports both OpenAI and Anthropic-compatible APIs on Apple Silicon.

[oMLX](https://omlx.ai/) is a native macOS LLM inference server with paged SSD KV caching and continuous batching, managed from the menu bar. Built on MLX for Apple Silicon.

## Setup

```bash
brew tap jundot/omlx https://github.com/jundot/omlx
brew install omlx
```

Or download the `.dmg` from [GitHub releases](https://github.com/jundot/omlx/releases).

## Details

| Property | Value |
|----------|-------|
| Default port | 8000 |
| API type | OpenAI-compatible + Anthropic-compatible |
| VRAM reporting | No |
| Model format | MLX (safetensors) |
| Detection | `/admin/info` JSON endpoint or `/admin` HTML page |
| Requirements | macOS 15+, Apple Silicon (M1+), 16 GB RAM min |

## Notes

- oMLX shares port 8000 with vllm-mlx. asiai uses `/admin/info` probing to distinguish between them.
- SSD KV caching enables larger context windows with lower memory pressure.
- Continuous batching improves throughput under concurrent requests.
- Supports text LLMs, vision-language models, OCR models, embeddings, and rerankers.
- The admin dashboard at `/admin` provides real-time server metrics.
- In-app auto-update when installed via `.dmg`.

## See also

Compare engines with `asiai bench --engines omlx` --- [learn how](../benchmark-llm-mac.md)
