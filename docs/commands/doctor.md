# asiai doctor

Diagnose installation, engines, system health, and database.

## Usage

```bash
asiai doctor
```

## Output

```
Doctor

  System
    ✓ Apple Silicon       Mac Mini M4 Pro — Apple M4 Pro
    ✓ RAM                 64 GB total, 42% used
    ✓ Memory pressure     normal
    ✓ Thermal             nominal (100%)

  Engine
    ✓ Ollama              v0.17.4 — 1 model(s): qwen3.5:35b-a3b
    ✓ LM Studio           v0.4.5 — 1 model(s): qwen3.5-35b-a3b
    ✗ mlx-lm              not installed
    ✗ llama.cpp            not installed
    ✗ vllm-mlx            not installed

  Database
    ✓ SQLite              2.4 MB, last entry: 1m ago

  5 ok, 0 warning(s), 3 failed
```

## Checks

- **System**: Apple Silicon detection, RAM, memory pressure, thermal state
- **Engine**: Reachability and version for all 5 supported engines
- **Database**: SQLite schema version, size, last entry timestamp
