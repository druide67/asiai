---
title: "How to Benchmark LLMs on Mac"
description: "How to benchmark LLM inference on Mac: step-by-step guide to measure tok/s, TTFT, power, and VRAM on Apple Silicon with multiple engines."
type: howto
date: 2026-03-28
updated: 2026-03-29
duration: PT5M
steps:
  - name: "Install asiai"
    text: "Install asiai via pip (pip install asiai) or Homebrew (brew tap druide67/tap && brew install asiai)."
  - name: "Detect your engines"
    text: "Run 'asiai detect' to automatically find running inference engines (Ollama, LM Studio, llama.cpp, mlx-lm, oMLX, vLLM-MLX, Exo) on your Mac."
  - name: "Run a benchmark"
    text: "Run 'asiai bench' to auto-detect the best model across engines and run a cross-engine comparison measuring tok/s, TTFT, power, and VRAM."
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
  lmstudio      102.2      537    7.00s    0.29s    24.2 GB    nominal
  ollama         69.8      512   17.33s    0.18s    32.0 GB    nominal

  Winner: lmstudio (+46% tok/s)

  Power Efficiency
    lmstudio     102.2 tok/s @ 12.4W = 8.23 tok/s/W
    ollama        69.8 tok/s @ 15.4W = 4.53 tok/s/W
```

*Example output from a real benchmark on M4 Pro 64GB. Your numbers will vary by hardware and model. [See more results →](ollama-vs-lmstudio.md)*

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

## FAQ

**Q: What is the fastest LLM inference engine on Apple Silicon?**
A: In our benchmarks on M4 Pro 64GB, LM Studio (MLX backend) is the fastest for token generation — 46% faster than Ollama (llama.cpp). However, Ollama has lower TTFT (time to first token). See our [detailed comparison](ollama-vs-lmstudio.md).

**Q: How much RAM do I need to run a 30B model on Mac?**
A: A Q4_K_M quantized 30B model uses 24-32 GB of unified memory depending on the engine. You need at least 32 GB RAM, ideally 64 GB to avoid memory pressure. MoE models like Qwen3.5-35B-A3B only use ~7 GB active parameters.

**Q: Does asiai work on Intel Macs?**
A: No. asiai requires Apple Silicon (M1/M2/M3/M4). It uses macOS-specific APIs for GPU metrics, power monitoring, and hardware detection that are only available on Apple Silicon.

**Q: Is Ollama or LM Studio faster on M4?**
A: LM Studio is faster for throughput (102 tok/s vs 70 tok/s on Qwen3-Coder-30B). Ollama is faster for first-token latency (0.18s vs 0.29s) and for large context windows (>32K tokens) where llama.cpp prefill is up to 3x faster.

**Q: How long does a benchmark take?**
A: A quick benchmark takes about 2 minutes. A full cross-engine comparison with multiple prompts and runs takes 10-15 minutes. Use `asiai bench --quick` for a fast single-run test.

**Q: Can I compare my results with other Mac users?**
A: Yes. Run `asiai bench --share` to anonymously submit results to the [community leaderboard](leaderboard.md). Use `asiai compare` to see how your Mac compares to other Apple Silicon machines.

## Further Reading

- [Benchmark Methodology](methodology.md) — how asiai ensures reliable measurements
- [Benchmark Best Practices](benchmark-best-practices.md) — tips for accurate results
- [Engine Comparison](ollama-vs-lmstudio.md) — Ollama vs LM Studio head-to-head
