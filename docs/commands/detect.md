# asiai detect

Auto-detect running inference engines across 5 ports.

## Usage

```bash
asiai detect
```

## Output

```
Detected engines:

  ● ollama 0.17.4
    URL: http://localhost:11434

  ● lmstudio 0.4.5
    URL: http://localhost:1234
    Running: 1 model(s)
      - qwen3.5-35b-a3b  MLX
```

## How it works

asiai scans localhost on standard ports:

| Port | Engine |
|------|--------|
| 11434 | Ollama |
| 1234 | LM Studio |
| 8080 | mlx-lm or llama.cpp |
| 8000 | vllm-mlx |

When multiple engines share a port (e.g., mlx-lm and llama.cpp on 8080), asiai uses API endpoint probing and `lsof -i :PORT` process detection to identify the correct engine.
