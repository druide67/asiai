---
description: "LM Studio benchmark on Apple Silicon: fastest MLX engine, port 1234 setup, VRAM usage, and how it compares to Ollama."
---

# LM Studio

LM Studio is the fastest MLX inference engine on Apple Silicon, serving models on port 1234 with an OpenAI-compatible API. On M4 Pro 64GB, it reaches 130 tok/s on Qwen3-Coder-30B (MLX), nearly 2x faster than Ollama's llama.cpp backend for MoE models.

[LM Studio](https://lmstudio.ai) provides an OpenAI-compatible API with a GUI for model management.

## Setup

```bash
brew install --cask lm-studio
```

Start the local server from the LM Studio app, then load a model.

## Details

| Property | Value |
|----------|-------|
| Default port | 1234 |
| API type | OpenAI-compatible |
| VRAM reporting | Yes (via `lms ps --json` CLI) |
| Model format | GGUF, MLX |
| Detection | `/lms/version` endpoint or app bundle plist |

## VRAM reporting

Since v0.7.0, asiai retrieves VRAM usage from the LM Studio CLI (`~/.lmstudio/bin/lms ps --json`). This provides accurate model size data that the OpenAI-compatible API does not expose.

If the `lms` CLI is not installed or unavailable, asiai gracefully falls back to reporting VRAM as 0 (same behavior as before v0.7.0).

## Notes

- LM Studio supports both GGUF and MLX model formats.
- Version detection uses the `/lms/version` API endpoint, with a fallback to the app bundle plist on disk.
- Model names typically use the HuggingFace format (e.g., `gemma-2-9b-it`).

## See also

See how LM Studio compares: [Ollama vs LM Studio benchmark](../ollama-vs-lmstudio.md)
