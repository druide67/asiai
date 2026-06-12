---
description: "vMLX benchmark on Apple Silicon: MLX server with Mamba/SSM hybrid support, OpenAI-compatible API, port 8000."
---

# vMLX

vMLX is a high-performance MLX-based inference server with first-class support for Mamba/SSM hybrid architectures (DeltaNet, Mamba2, RetNet). It exposes an OpenAI-compatible API on port 8000 and identifies itself through a `/version` endpoint, with Prometheus metrics for inference activity.

[vMLX](https://vmlx.net/) targets Apple Silicon and is the only adapter here aimed at state-space / hybrid models alongside standard transformers.

## Setup

```bash
pip install vmlx
vmlx serve --model <repo-id-or-path> --port 8000
```

## Details

| Property | Value |
|----------|-------|
| Default port | 8000 |
| API type | OpenAI-compatible |
| VRAM reporting | No (asiai measures GPU power/VRAM via ioreg) |
| Model format | MLX |
| Detection | `/version` endpoint reporting `vmlx`, or `owned_by: "vmlx"` in `/v1/models` |
| Activity metrics | `/metrics` (Prometheus) |
| Requirements | Apple Silicon (M1+), macOS |

## Notes

- vMLX shares port 8000 with oMLX and vllm-mlx. asiai disambiguates them by probing `/version` and the `owned_by` field of `/v1/models`.
- First-class Mamba/SSM hybrid support (DeltaNet, Mamba2, RetNet) — useful for benchmarking non-transformer architectures that other MLX servers do not load.
- Version resolves from `/version`, falling back to `pip show vmlx`.

## See also

Compare engines with `asiai bench --engines vmlx` --- [learn how](../benchmark-llm-mac.md)
