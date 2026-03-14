# oMLX

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
