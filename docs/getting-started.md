# Getting Started

**Apple Silicon AI** — Multi-engine LLM benchmark & monitoring CLI.

asiai compares inference engines side-by-side on your Mac. Load the same model on Ollama and LM Studio, run `asiai bench`, get the numbers. No guessing, no vibes — just tok/s, TTFT, power efficiency, and stability per engine.

## Quick start

```bash
brew tap druide67/tap
brew install asiai
```

Or with pip:

```bash
pip install asiai
```

Then detect your engines:

```bash
asiai detect
```

And benchmark:

```bash
asiai bench -m qwen3.5 --runs 3 --power
```

## What it measures

| Metric | Description |
|--------|-------------|
| **tok/s** | Generation speed (tokens/sec), excluding prompt processing |
| **TTFT** | Time to first token — prompt processing latency |
| **Power** | GPU power draw in watts (`sudo powermetrics`) |
| **tok/s/W** | Energy efficiency — tokens per second per watt |
| **Stability** | Run-to-run variance: stable (<5%), variable (<10%), unstable (>10%) |
| **VRAM** | GPU memory footprint (Ollama, LM Studio) |
| **Thermal** | CPU throttling state and speed limit percentage |

## Supported engines

| Engine | Port | API |
|--------|------|-----|
| [Ollama](https://ollama.com) | 11434 | Native |
| [LM Studio](https://lmstudio.ai) | 1234 | OpenAI-compatible |
| [mlx-lm](https://github.com/ml-explore/mlx-examples) | 8080 | OpenAI-compatible |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | 8080 | OpenAI-compatible |
| [vllm-mlx](https://github.com/vllm-project/vllm) | 8000 | OpenAI-compatible |

## Requirements

- macOS on Apple Silicon (M1 / M2 / M3 / M4)
- Python 3.11+
- At least one inference engine running locally

## Zero dependencies

The core uses only the Python standard library — `urllib`, `sqlite3`, `subprocess`, `argparse`. No `requests`, no `psutil`, no `rich`.

Optional extras:

- `asiai[tui]` — Textual terminal dashboard
- `asiai[dev]` — pytest, ruff, pytest-cov
