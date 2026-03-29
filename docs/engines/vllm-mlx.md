---
description: "vLLM-MLX on Apple Silicon: vLLM-compatible API on MLX, port 8000, Prometheus metrics, and benchmark data."
---

# vllm-mlx

vLLM-MLX brings the vLLM serving framework to Apple Silicon via MLX, offering continuous batching and an OpenAI-compatible API on port 8000. It can achieve 400+ tok/s on optimized models, making it one of the fastest options for concurrent inference on Mac.

[vllm-mlx](https://github.com/vllm-project/vllm) brings continuous batching to Apple Silicon via MLX.

## Setup

```bash
pip install vllm-mlx
vllm serve mlx-community/gemma-2-9b-it-4bit
```

## Details

| Property | Value |
|----------|-------|
| Default port | 8000 |
| API type | OpenAI-compatible |
| VRAM reporting | No |
| Model format | MLX (safetensors) |
| Detection | `/version` endpoint or `lsof` process detection |

## Notes

- vllm-mlx supports continuous batching, making it suitable for concurrent request handling.
- Can achieve 400+ tok/s on Apple Silicon with optimized models.
- Uses the standard vLLM OpenAI-compatible API.

## See also

Compare engines with `asiai bench --engines vllm-mlx` --- [learn how](../benchmark-llm-mac.md)
