# asiai models

List loaded models across all detected engines.

## Usage

```bash
asiai models
```

## Output

```
ollama  http://localhost:11434
  ● qwen3.5:35b-a3b                             26.0 GB Q4_K_M

lmstudio  http://localhost:1234
  ● qwen3.5-35b-a3b                                 MLX
```

Shows model name, VRAM usage (when available), format, and quantization level for each engine.
