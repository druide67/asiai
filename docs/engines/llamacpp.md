---
description: "llama.cpp server on Mac: low-level control, port 8080, KV cache metrics, and benchmark results on Apple Silicon."
---

# llama.cpp

llama.cpp is the foundational C++ inference engine for GGUF models, offering maximum low-level control over KV cache, thread count, and context size on port 8080. It powers Ollama's backend but can be run standalone for fine-grained tuning on Apple Silicon.

[llama.cpp](https://github.com/ggml-org/llama.cpp) is a high-performance C++ inference engine supporting GGUF models.

## Setup

```bash
brew install llama.cpp
llama-server -m model.gguf
```

## Details

| Property | Value |
|----------|-------|
| Default port | 8080 |
| API type | OpenAI-compatible |
| VRAM reporting | No |
| Model format | GGUF |
| Detection | `/health` + `/props` endpoints or `lsof` process detection |

## Notes

- llama.cpp shares port 8080 with mlx-lm. asiai detects it via the `/health` and `/props` endpoints.
- The server can be started with custom context sizes and thread counts for tuning.

## See also

Compare engines with `asiai bench --engines llamacpp` --- [learn how](../benchmark-llm-mac.md)
