---
description: "How to benchmark LLM inference on Mac: step-by-step guide to measure tok/s, TTFT, power, and VRAM on Apple Silicon with multiple engines."
---

# How to Benchmark LLMs on Mac

Running a local LLM on your Mac? Here's how to measure real performance — not vibes, not "it feels fast", but actual tok/s, TTFT, power consumption, and memory usage.

## Why Benchmark?

The same model runs at very different speeds depending on the inference engine. On Apple Silicon, MLX-based engines (LM Studio, mlx-lm, oMLX) can be **2x faster** than llama.cpp-based engines (Ollama) for the same model. Without measuring, you're leaving performance on the table.

## Quick Start (2 minutes)

### 1. Install asiai

```bash
pip install asiai
```

Or via Homebrew:

```bash
brew tap druide67/tap
brew install asiai
```

### 2. Detect your engines

```bash
asiai detect
```

asiai automatically finds running engines (Ollama, LM Studio, llama.cpp, mlx-lm, oMLX, vLLM-MLX, Exo) on your Mac.

### 3. Run a benchmark

```bash
asiai bench
```

That's it. asiai auto-detects the best model across your engines and runs a cross-engine comparison.

## What Gets Measured

| Metric | What It Means |
|--------|--------------|
| **tok/s** | Tokens generated per second (generation only, excludes prompt processing) |
| **TTFT** | Time to First Token — latency before generation starts |
| **Power** | GPU + CPU watts during inference (via IOReport, no sudo needed) |
| **tok/s/W** | Energy efficiency — tokens per second per watt |
| **VRAM** | Memory used by the model (native API or estimated via `ri_phys_footprint`) |
| **Stability** | Run-to-run variance: stable (<5% CV), variable (<10%), unstable (>10%) |
| **Thermal** | Whether your Mac throttled during the benchmark |

## Example Output

```
Mac16,11 — Apple M4 Pro  RAM: 64.0 GB  Pressure: normal

Benchmark: qwen3-coder-30b

  Engine        tok/s   Tokens Duration     TTFT       VRAM    Thermal
  lmstudio      102.2      537    7.00s    0.26s    24.2 GB    nominal
  ollama         69.8      512   17.33s    0.23s    32.0 GB    nominal

  Winner: lmstudio (2.6x faster, -24% VRAM)

  Power Efficiency
    lmstudio     102.2 tok/s @ 12.4W = 8.23 tok/s/W
    ollama        69.8 tok/s @ 15.4W = 4.53 tok/s/W
```

## Advanced Options

### Compare specific engines

```bash
asiai bench --engines ollama,lmstudio,omlx
```

### Multiple prompts and runs

```bash
asiai bench --prompts code,reasoning,tool_call --runs 3
```

### Large context benchmark

```bash
asiai bench --context-size 64K
```

### Generate a shareable card

```bash
asiai bench --card --share
```

Creates a benchmark card image and shares results with the [community leaderboard](leaderboard.md).

## Apple Silicon Tips

### Memory matters

On a 16GB Mac, stick to models under 14GB (loaded). MoE models (Qwen3.5-35B-A3B, 3B active) are ideal — they deliver 35B-class quality at 7B-class memory usage.

### Engine choice matters more than you think

MLX engines are significantly faster than llama.cpp on Apple Silicon for most models. [See our Ollama vs LM Studio comparison](ollama-vs-lmstudio.md) for real numbers.

### Thermal throttling

MacBook Air (no fan) throttles after 5-10 minutes of sustained inference. Mac Mini/Studio/Pro handle sustained workloads without throttling. asiai detects and reports thermal throttling automatically.

## Compare with the Community

See how your Mac stacks up against other Apple Silicon machines:

```bash
asiai compare
```

Or visit the [online leaderboard](leaderboard.md).

## Further Reading

- [Benchmark Methodology](methodology.md) — how asiai ensures reliable measurements
- [Benchmark Best Practices](benchmark-best-practices.md) — tips for accurate results
- [Engine Comparison](ollama-vs-lmstudio.md) — Ollama vs LM Studio head-to-head
