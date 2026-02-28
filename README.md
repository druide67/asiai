# asiai

> Multi-engine LLM benchmark & monitoring CLI for Apple Silicon.

**asiai** compares inference engines side-by-side on your Mac. Load the same model on Ollama and LM Studio, run `asiai bench`, get the numbers. No guessing, no vibes — just tok/s, TTFT, VRAM, and CPU usage per engine.

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

## Commands

### `asiai detect`

Auto-detect running inference engines.

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
--engines, -e LIST     Filter engines (e.g. ollama,lmstudio)
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
--history, -H PERIOD   Show history (e.g. 24h, 1h)
--analyze, -a HOURS    Comprehensive analysis with trends
--compare, -c TS TS    Compare two timestamps
```

## What it measures

| Metric | Source | Ollama | LM Studio |
|--------|--------|--------|-----------|
| tok/s | API response / wall clock | Native (`eval_duration`) | Client-side (`time.monotonic`) |
| TTFT | Time to first token | Native (`prompt_eval_duration`) | N/A (non-streaming) |
| VRAM | Model memory footprint | `/api/ps` | N/A |
| CPU% | Per-process usage | `ps aux` | `ps aux` |
| RSS | Resident memory | `ps aux` | `ps aux` |
| Thermal | CPU throttling state | `sysctl` / `pmset` | `sysctl` / `pmset` |
| RAM pressure | System memory pressure | `sysctl` | `sysctl` |

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
- At least one inference engine: [Ollama](https://ollama.com) or [LM Studio](https://lmstudio.ai)

## Zero dependencies

The core uses only the Python standard library — `urllib`, `sqlite3`, `subprocess`, `argparse`. No `requests`, no `psutil`, no `rich`. Just stdlib.

## Roadmap

| Version | Scope | Status |
|---------|-------|--------|
| **v0.1** | detect + bench + monitor + models (CLI) | Current |
| v0.2 | doctor + recommend + analyze + TUI (Textual) | Planned |
| v0.3 | Dashboard web (FastAPI + htmx + ApexCharts) | Planned |
| v1.0 | Multi-server, plugins, Homebrew Core | Planned |

## License

Apache 2.0
