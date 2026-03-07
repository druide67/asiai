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

VRAM reporting is supported by Ollama and LM Studio. Other engines show "—".
