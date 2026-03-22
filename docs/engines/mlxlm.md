---
description: Benchmark mlx-lm server on Apple Silicon. Pure MLX backend, ideal for models optimized for Metal GPU.
---

# mlx-lm

[mlx-lm](https://github.com/ml-explore/mlx-examples) runs models natively on Apple MLX, providing efficient unified memory utilization.

## Setup

```bash
brew install mlx-lm
mlx_lm.server --model mlx-community/gemma-2-9b-it-4bit
```

## Details

| Property | Value |
|----------|-------|
| Default port | 8080 |
| API type | OpenAI-compatible |
| VRAM reporting | No |
| Model format | MLX (safetensors) |
| Detection | `/version` endpoint or `lsof` process detection |

## Notes

- mlx-lm shares port 8080 with llama.cpp. asiai uses API probing and process detection to distinguish between them.
- Models use the HuggingFace/MLX community format (e.g., `mlx-community/gemma-2-9b-it-4bit`).
- Native MLX execution typically provides excellent performance on Apple Silicon.
