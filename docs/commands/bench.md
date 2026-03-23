---
description: Run side-by-side LLM benchmarks on Apple Silicon. Compare engines, measure tok/s, TTFT, power efficiency. Share results.
---

# asiai bench

Cross-engine benchmark with standardized prompts.

## Usage

```bash
asiai bench [options]
```

## Options

| Option | Description |
|--------|-------------|
| `-m, --model MODEL` | Model to benchmark (default: auto-detect) |
| `-e, --engines LIST` | Filter engines (e.g., `ollama,lmstudio,mlxlm`) |
| `-p, --prompts LIST` | Prompt types: `code`, `tool_call`, `reasoning`, `long_gen` |
| `-r, --runs N` | Runs per prompt (default: 3, for median + stddev) |
| `--power` | Cross-validate power with sudo powermetrics (IOReport always-on) |
| `--context-size SIZE` | Context fill prompt: `4k`, `16k`, `32k`, `64k` |
| `--export FILE` | Export results to JSON file |
| `-H, --history PERIOD` | Show past benchmarks (e.g., `7d`, `24h`) |
| `-Q, --quick` | Quick benchmark: 1 prompt (code), 1 run (~15 seconds) |
| `--compare MODEL [MODEL...]` | Cross-model comparison (2–8 models, mutually exclusive with `-m`) |
| `--card` | Generate a shareable benchmark card (SVG locally, PNG with `--share`) |
| `--share` | Share results to community benchmark database |

## Example

```bash
asiai bench -m qwen3.5 --runs 3 --power
```

```
  Mac Mini M4 Pro — Apple M4 Pro  RAM: 64.0 GB (42% used)  Pressure: normal

Benchmark: qwen3.5

  Engine       tok/s (±stddev)    Tokens   Duration     TTFT       VRAM    Thermal
  ────────── ───────────────── ───────── ────────── ──────── ────────── ──────────
  lmstudio    72.6 ± 0.0 (stable)   435    6.20s    0.28s        —    nominal
  ollama      30.4 ± 0.1 (stable)   448   15.28s    0.25s   26.0 GB   nominal

  Winner: lmstudio (2.4x faster)
  Power: lmstudio 13.2W (5.52 tok/s/W) — ollama 16.0W (1.89 tok/s/W)
```

## Prompts

Four standardized prompts test different generation patterns:

| Name | Tokens | Tests |
|------|--------|-------|
| `code` | 512 | Structured code generation (BST in Python) |
| `tool_call` | 256 | JSON function calling / instruction following |
| `reasoning` | 384 | Multi-step math problem |
| `long_gen` | 1024 | Sustained throughput (bash script) |

Use `--context-size` to test with large context fill prompts instead.

## Cross-engine model matching

The runner resolves model names across engines automatically — `gemma2:9b` (Ollama) and `gemma-2-9b` (LM Studio) are matched as the same model.

## JSON export

Export results for sharing or analysis:

```bash
asiai bench -m qwen3.5 --export bench.json
```

The JSON includes machine metadata, per-engine statistics (median, CI 95%, P50/P90/P99), raw per-run data, and a schema version for forward compatibility.

## Regression detection

After each benchmark, asiai compares results against the last 7 days of history and warns about performance regressions (e.g., after an engine update or macOS upgrade).

## Quick benchmark

Run a fast benchmark with a single prompt and one run (~15 seconds):

```bash
asiai bench --quick
asiai bench -Q -m qwen3.5
```

This is ideal for demos, GIFs, and quick checks. The `code` prompt is used by default. You can override with `--prompts` if needed.

## Cross-model comparison

Compare multiple models in a single session with `--compare`:

```bash
# Auto-expand across all available engines
asiai bench --compare qwen3.5:4b deepseek-r1:7b

# Filter to a specific engine
asiai bench --compare qwen3.5:4b deepseek-r1:7b -e ollama

# Pin each model to an engine with @
asiai bench --compare qwen3.5:4b@lmstudio deepseek-r1:7b@ollama
```

The `@` notation splits on the **last** `@` in the string, so model names containing `@` are handled correctly.

### Rules

- `--compare` and `--model` are **mutually exclusive** — use one or the other.
- Accepts 2 to 8 model slots.
- Without `@`, each model is expanded to every engine where it is available.

### Session types

The session type is detected automatically based on the slot list:

| Type | Condition | Example |
|------|-----------|---------|
| **engine** | Same model, different engines | `--compare qwen3.5:4b@lmstudio qwen3.5:4b@ollama` |
| **model** | Different models, same engine | `--compare qwen3.5:4b deepseek-r1:7b -e ollama` |
| **matrix** | Mixed models and engines | `--compare qwen3.5:4b@lmstudio deepseek-r1:7b@ollama` |

### Combined with other flags

`--compare` works with all output and run flags:

```bash
asiai bench --compare qwen3.5:4b deepseek-r1:7b --quick
asiai bench --compare qwen3.5:4b deepseek-r1:7b --card --share
asiai bench --compare qwen3.5:4b deepseek-r1:7b --runs 5 --power
```

## Benchmark card

Generate a shareable benchmark card:

```bash
asiai bench --card                    # SVG saved locally
asiai bench --card --share            # SVG + PNG (via community API)
asiai bench --quick --card --share    # Quick bench + card + share
```

The card is a 1200x630 dark-themed image with:
- Model name and hardware chip badge
- Specs banner: quantization, RAM, GPU cores, context size
- Terminal-style bar chart of tok/s per engine
- Winner highlight with delta (e.g., "2.4x")
- Metric chips: tok/s, TTFT, stability, VRAM, power (W + tok/s/W), engine version
- asiai branding

The SVG is saved to `~/.local/share/asiai/cards/`. With `--share`, a PNG is also downloaded from the API.

## Community sharing

Share your results anonymously:

```bash
asiai bench --share
```

View the community leaderboard with `asiai leaderboard`.

## Thermal drift detection

When running 3+ runs, asiai detects monotone tok/s degradation across consecutive runs. If tok/s drops consistently (>5%), a warning is emitted indicating possible thermal throttling buildup.
