# Ollama

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
