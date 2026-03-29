---
description: "How fast is Ollama on Apple Silicon? Benchmark setup, default port (11434), performance tips, and comparison with other engines."
---

# Ollama

Ollama is the most popular LLM inference engine for Mac, using a llama.cpp backend with GGUF models on port 11434. In our benchmarks on M4 Pro 64GB, it achieves 70 tok/s on Qwen3-Coder-30B but is 46% slower than LM Studio (MLX) for throughput.

[Ollama](https://ollama.com) is the most popular local LLM runner. asiai uses its native API.

## Setup

```bash
brew install ollama
ollama serve
ollama pull gemma2:9b
```

## Details

| Property | Value |
|----------|-------|
| Default port | 11434 |
| API type | Native (non-OpenAI) |
| VRAM reporting | Yes |
| Model format | GGUF |
| Load time measurement | Yes (via `/api/generate` cold start) |

## Notes

- Ollama reports VRAM usage per model, which asiai displays in benchmark and monitor output.
- Model names use the `name:tag` format (e.g., `gemma2:9b`, `qwen3.5:35b-a3b`).
- asiai sends `temperature: 0` for deterministic benchmark results.

## See also

See how Ollama compares: [Ollama vs LM Studio benchmark](../ollama-vs-lmstudio.md)
