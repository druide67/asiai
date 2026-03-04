# vllm-mlx

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
