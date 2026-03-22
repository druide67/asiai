---
description: Hardware-aware model recommendations based on your Mac's RAM, GPU cores and thermal headroom.
---

# asiai recommend

Get engine recommendations for your hardware and use case.

## Usage

```bash
asiai recommend [options]
```

## Options

| Option | Description |
|--------|-------------|
| `--model MODEL` | Model to get recommendations for |
| `--use-case USE_CASE` | Optimize for: `throughput`, `latency`, or `efficiency` |
| `--community` | Include community benchmark data in recommendations |
| `--db PATH` | Path to local benchmark database |

## Data sources

Recommendations are built from the best available data, in priority order:

1. **Local benchmarks** — your own runs on your hardware
2. **Community data** — aggregated results from similar chips (with `--community`)
3. **Heuristics** — built-in rules when no benchmark data is available

## Confidence levels

| Level | Criteria |
|-------|----------|
| High | 5 or more local benchmark runs |
| Medium | 1 to 4 local runs, or community data available |
| Low | Heuristic-based, no benchmark data |

## Example

```bash
asiai recommend --model qwen3.5 --use-case throughput
```

```
  Recommendation: qwen3.5 — M4 Pro — throughput

  #   Engine       tok/s    Confidence   Source
  ── ────────── ──────── ──────────── ──────────
  1   lmstudio    72.6     high         local (5 runs)
  2   ollama      30.4     high         local (5 runs)
  3   exo         18.2     medium       community

  Tip: lmstudio is 2.4x faster than ollama for this model.
```

## Notes

- Run `asiai bench` first for the most accurate recommendations.
- Use `--community` to fill gaps when you haven't benchmarked a specific engine locally.
- The `efficiency` use case factors in power consumption (requires `--power` data from previous benchmarks).
