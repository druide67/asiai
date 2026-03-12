# asiai setup

Interactive setup wizard for first-time users. Detects your hardware, checks for inference engines, and suggests next steps.

## Usage

```bash
asiai setup
```

## What it does

1. **Hardware detection** — identifies your Apple Silicon chip and RAM
2. **Engine scan** — checks for installed inference engines (Ollama, LM Studio, mlx-lm, llama.cpp, vllm-mlx, Exo)
3. **Model check** — lists loaded models across all detected engines
4. **Daemon status** — shows whether the monitoring daemon is running
5. **Next steps** — suggests commands based on your setup state

## Example output

```
  Setup Wizard

  Hardware:  Apple M4 Pro, 64 GB RAM

  Engines:
    ✓ ollama (v0.17.7) — 3 models loaded
    ✓ lmstudio (v0.4.5) — 1 model loaded

  Daemon: running (monitor + web)

  Suggested next steps:
    • asiai bench              Run your first benchmark
    • asiai monitor --watch    Watch metrics live
    • asiai web                Open the dashboard
```

## When no engines are found

If no engines are detected, setup provides installation guidance:

```
  Engines:
    No inference engines detected.

  To get started, install an engine:
    brew install ollama && ollama serve
    # or download LM Studio from https://lmstudio.ai
```
