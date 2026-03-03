# asiai

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://python.org)
[![macOS](https://img.shields.io/badge/macOS-Apple%20Silicon-black.svg)](https://support.apple.com/en-us/116943)

> Multi-engine LLM benchmark & monitoring CLI for Apple Silicon.

**asiai** compares inference engines side-by-side on your Mac. Load the same model on Ollama, LM Studio, or mlx-lm, run `asiai bench`, get the numbers. No guessing, no vibes — just tok/s, TTFT, VRAM, and CPU usage per engine.

Born from the [OpenClaw](https://github.com/druide67/openclaw-macos-hardened) project, where we needed hard data to pick the fastest engine for multi-agent swarms on Mac Mini M4 Pro.

## Quick start

```bash
brew tap druide67/tap
brew install asiai
```

Or from source:

```bash
git clone https://github.com/druide67/asiai.git
cd asiai
pip install -e .
```

For the TUI dashboard:

```bash
pip install asiai[tui]
```

## Commands

### `asiai detect`

Auto-detect running inference engines (Ollama, LM Studio, mlx-lm).

```
$ asiai detect

Detected engines:

  ● ollama 0.17.2
    URL: http://localhost:11434

  ● lmstudio 0.4.6
    URL: http://localhost:1234
    Running: 1 model(s)
      - gemma-2-9b  N/A
```

### `asiai bench`

Cross-engine benchmark with standardized prompts.

```
$ asiai bench --model gemma2:9b

  MacBookPro18,2 — Apple M1 Max  RAM: 64.0 GB (55% used)  Pressure: normal

Benchmark: gemma2:9b

  Engine          tok/s     TTFT       VRAM   CPU%        RSS    Thermal
  ──────────── ──────── ──────── ────────── ────── ────────── ──────────
  lmstudio         24.4      N/A        N/A    12%    380 MB    nominal
  ollama           45.7    0.12s     8.2 GB    85%    107 MB    nominal

  Winner: ollama (+87% tok/s)
```

Options:

```
--model, -m MODEL      Model to benchmark (default: auto-detect)
--engines, -e LIST     Filter engines (e.g. ollama,lmstudio,mlxlm)
--prompts, -p LIST     Prompt types: code, tool_call, reasoning, long_gen
--history, -H PERIOD   Show past benchmarks (e.g. 7d, 24h)
```

The runner resolves model names across engines automatically — `gemma2:9b` (Ollama) and `gemma-2-9b` (LM Studio) are matched as the same model.

### `asiai models`

List loaded models across all engines.

```
$ asiai models

ollama  http://localhost:11434
  ● gemma2:9b                                    8.2 GB Q4_K_M

lmstudio  http://localhost:1234
  ● gemma-2-9b                                      N/A
```

### `asiai monitor`

System and inference metrics snapshot, stored in SQLite.

```
$ asiai monitor

System
  Uptime:    3d 12h
  CPU Load:  2.45 / 3.12 / 2.89  (1m / 5m / 15m)
  Memory:    45.2 GB / 64.0 GB  71%
  Pressure:  normal
  Thermal:   nominal  (100%)

Inference  ollama 0.17.2
  Models loaded: 1  VRAM total: 8.2 GB

  Model                                        VRAM   Format  Quant
  ──────────────────────────────────────── ────────── ──────── ──────
  gemma2:9b                                  8.2 GB     gguf Q4_K_M
```

Options:

```
--watch, -w SEC        Refresh every SEC seconds
--quiet, -q            Collect and store without output (for daemon use)
--history, -H PERIOD   Show history (e.g. 24h, 1h)
--analyze, -a HOURS    Comprehensive analysis with trends
--compare, -c TS TS    Compare two timestamps
```

### `asiai doctor`

Diagnose installation, engines, system health, and database.

```
$ asiai doctor

Doctor

  System
    ✓ Apple Silicon       MacBookPro18,2 — Apple M1 Max
    ✓ RAM                 64 GB total, 55% used
    ✓ Memory pressure     normal
    ✓ Thermal             nominal (100%)

  Engine
    ✓ Ollama              v0.17.2 — 1 model(s): gemma2:9b
    ✓ LM Studio           v0.4.6 — 2 model(s): gemma-2-9b, qwen2.5-7b
    ✗ mlx-lm              not installed
      Fix: brew install mlx-lm

  Database
    ✓ SQLite              1.2 MB, last entry: 3m ago

  6 ok, 0 warning(s), 1 failed
```

### `asiai daemon`

Background monitoring via macOS launchd. Collects metrics every minute.

```bash
asiai daemon start              # Install and start the daemon
asiai daemon start --interval 30  # Custom interval (seconds)
asiai daemon status             # Check if running
asiai daemon logs               # View recent logs
asiai daemon logs -n 100        # Last 100 lines
asiai daemon stop               # Stop and uninstall
```

### `asiai tui`

Interactive terminal dashboard with auto-refresh. Requires `pip install asiai[tui]`.

```bash
asiai tui
```

Keybindings: `q` quit, `r` refresh, `b` toggle benchmarks.

## Supported engines

| Engine | Port | Install | API |
|--------|------|---------|-----|
| [Ollama](https://ollama.com) | 11434 | `brew install ollama` | Native |
| [LM Studio](https://lmstudio.ai) | 1234 | `brew install --cask lm-studio` | OpenAI-compatible |
| [mlx-lm](https://github.com/ml-explore/mlx-examples) | 8080 | `brew install mlx-lm` | OpenAI-compatible |

## What it measures

| Metric | Source | Ollama | LM Studio | mlx-lm |
|--------|--------|--------|-----------|--------|
| tok/s | API response / wall clock | Native (`eval_duration`) | Client-side timing | Client-side timing |
| TTFT | Time to first token | Native (`prompt_eval_duration`) | N/A | N/A |
| VRAM | Model memory footprint | `/api/ps` | N/A | N/A |
| CPU% | Per-process usage | `ps aux` | `ps aux` | `ps aux` |
| RSS | Resident memory | `ps aux` | `ps aux` | `ps aux` |
| Thermal | CPU throttling state | `sysctl` / `pmset` | `sysctl` / `pmset` | `sysctl` / `pmset` |
| RAM pressure | System memory pressure | `sysctl` | `sysctl` | `sysctl` |

All metrics are stored in SQLite (`~/.local/share/asiai/metrics.db`) with 90-day retention.

## Benchmark prompts

Four standardized prompts test different generation patterns:

| Name | Tokens | Tests |
|------|--------|-------|
| `code` | 512 | Structured code generation (BST in Python) |
| `tool_call` | 256 | JSON function calling / instruction following |
| `reasoning` | 384 | Multi-step math problem |
| `long_gen` | 1024 | Sustained throughput (bash script) |

## Requirements

- macOS on Apple Silicon (M1 / M2 / M3 / M4)
- Python 3.11+
- At least one inference engine: [Ollama](https://ollama.com), [LM Studio](https://lmstudio.ai), or [mlx-lm](https://github.com/ml-explore/mlx-examples)

## Zero dependencies

The core uses only the Python standard library — `urllib`, `sqlite3`, `subprocess`, `argparse`. No `requests`, no `psutil`, no `rich`. Just stdlib.

Optional extras:
- `asiai[tui]` — Textual terminal dashboard
- `asiai[dev]` — pytest, ruff, pytest-asyncio

## Roadmap

| Version | Scope | Status |
|---------|-------|--------|
| **v0.1** | detect + bench + monitor + models (CLI) | **Done** |
| **v0.2** | mlx-lm + doctor + daemon + TUI (Textual) | **Done** |
| v0.3 | vllm-mlx + llama.cpp + tok/s per watt + dashboard web | Next |
| v1.0 | Multi-server, plugins, Homebrew Core | Planned |

## License

Apache 2.0
