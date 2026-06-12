---
description: "Rapid-MLX benchmark on Apple Silicon: Homebrew packaging of vllm-mlx, OpenAI-compatible API, port 8000."
---

# Rapid-MLX

Rapid-MLX is a Homebrew packaging of the vllm-mlx engine (raullenchai upstream). The `rapid-mlx` wrapper delegates to the embedded vllm-mlx Python module in the formula's libexec virtualenv, so you get vllm-mlx's serving behaviour with a one-line `brew install` and no manual venv management.

## Setup

```bash
brew install raullenchai/rapid-mlx/rapid-mlx
# or, without Homebrew:
pip install rapid-mlx
```

## Details

| Property | Value |
|----------|-------|
| Default port | 8000 |
| API type | OpenAI-compatible |
| VRAM reporting | No (asiai measures GPU power/VRAM via ioreg) |
| Model format | MLX |
| Detection | `owned_by: "rapid-mlx"` in `/v1/models`, version via `rapid-mlx --version` |
| Requirements | Apple Silicon (M1+), macOS, Homebrew (for the brew install path) |

## Notes

- Rapid-MLX shares port 8000 with oMLX, vllm-mlx and vMLX. asiai disambiguates them by the `owned_by` field of `/v1/models` (`rapid-mlx`) and falls back to common brew install paths to resolve the binary.
- Because it wraps vllm-mlx, serving semantics (continuous batching, OpenAI-compatible endpoints) match vllm-mlx; the difference is purely packaging and update path (Homebrew vs pip/manual venv).
- `aisctl upgrade rapidmlx` is whitelisted (brew formula `raullenchai/rapid-mlx/rapid-mlx`) when asiai-inference-server is installed alongside.

## See also

Compare engines with `asiai bench --engines rapidmlx` --- [learn how](../benchmark-llm-mac.md)
