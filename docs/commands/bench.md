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
| `--power` | Measure GPU power via powermetrics (sudo required) |
| `--context-size SIZE` | Context fill prompt: `4k`, `16k`, `32k`, `64k` |
| `--export FILE` | Export results to JSON file |
| `-H, --history PERIOD` | Show past benchmarks (e.g., `7d`, `24h`) |

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

## Thermal drift detection

When running 3+ runs, asiai detects monotone tok/s degradation across consecutive runs. If tok/s drops consistently (>5%), a warning is emitted indicating possible thermal throttling buildup.
