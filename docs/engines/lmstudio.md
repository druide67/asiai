---
description: Benchmark LM Studio MLX on Apple Silicon. Typically 2x faster than llama.cpp engines on MoE models.
---

# LM Studio

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
