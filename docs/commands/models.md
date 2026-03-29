---
description: "List all loaded LLM models across engines: see VRAM usage, quantization, context length, and format for each model."
---

# asiai models

List loaded models across all detected engines.

## Usage

```bash
asiai models
```

## Output

```
ollama  v0.17.5  http://localhost:11434
  ● qwen3.5:35b-a3b                             26.0 GB Q4_K_M

lmstudio  v0.4.6  http://localhost:1234
  ● qwen3.5-35b-a3b                              9.2 GB    MLX
```

Shows engine version, model name, VRAM usage (when available), format, and quantization level for each engine.

VRAM is reported natively by Ollama and LM Studio. For other engines, asiai estimates memory usage via `ri_phys_footprint` (the macOS physical footprint, same as Activity Monitor). Estimated values are labeled "(est.)".
