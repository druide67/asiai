---
description: Auto-detect running LLM inference engines on your Mac. 3-layer cascade — config, port scan, process detection.
---

# asiai detect

Auto-detect running inference engines using a 3-layer cascade.

## Usage

```bash
asiai detect                      # Auto-detect (3-layer cascade)
asiai detect --url http://host:port  # Scan specific URL(s) only
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

  ● omlx 0.9.2
    URL: http://localhost:8800
```

## How it works: 3-layer detection

asiai uses a cascade of three detection layers, from fastest to most thorough:

### Layer 1: Config (fastest, ~100ms)

Reads `~/.config/asiai/engines.json` — engines discovered in previous runs. This catches engines on non-standard ports (e.g., oMLX on 8800) without rescanning.

### Layer 2: Port scan (~200ms)

Scans default ports plus an extended range:

| Port | Engine |
|------|--------|
| 11434 | Ollama |
| 1234 | LM Studio |
| 8080 | mlx-lm or llama.cpp |
| 8000-8009 | oMLX or vllm-mlx |
| 52415 | Exo |

### Layer 3: Process detection (fallback)

Uses `ps` and `lsof` to find engine processes listening on any port. Catches engines running on completely unexpected ports.

### Auto-persist

Any engine discovered in Layer 2 or 3 is automatically saved to the config file (Layer 1) for faster detection next time. Auto-discovered entries are pruned after 7 days of inactivity.

When multiple engines share a port (e.g., mlx-lm and llama.cpp on 8080), asiai uses API endpoint probing to identify the correct engine.

## Explicit URLs

When using `--url`, only the specified URLs are scanned. No config is read or written — useful for one-off checks.

```bash
asiai detect --url http://192.168.0.16:11434,http://localhost:8800
```

## See also

- [config](config.md) — Manage persistent engine configuration
