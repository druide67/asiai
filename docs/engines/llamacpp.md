# llama.cpp

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
