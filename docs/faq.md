---
title: "Frequently Asked Questions"
description: "Common questions about asiai: supported engines, Apple Silicon requirements, benchmarking LLMs on Mac, RAM requirements, and more."
type: faq
faq:
  - q: "What is asiai?"
    a: "asiai is an open-source CLI tool that benchmarks and monitors LLM inference engines on Apple Silicon Macs. It supports 7 engines (Ollama, LM Studio, mlx-lm, llama.cpp, oMLX, vllm-mlx, Exo) and measures tok/s, TTFT, power consumption, and VRAM usage."
  - q: "What is the fastest LLM engine on Apple Silicon?"
    a: "In benchmarks on M4 Pro 64GB with Qwen3-Coder-30B, LM Studio (MLX backend) achieves 102 tok/s vs Ollama's 70 tok/s — 46% faster for token generation. However, Ollama has lower time-to-first-token latency."
  - q: "Does asiai work on Intel Macs?"
    a: "No. asiai requires Apple Silicon (M1, M2, M3, or M4). It uses macOS-specific APIs for GPU metrics, IOReport power monitoring, and hardware detection that are only available on Apple Silicon chips."
  - q: "How much RAM do I need to run LLMs locally?"
    a: "For a Q4-quantized 7B model: 8 GB minimum. For 13B: 16 GB. For 30B: 32-64 GB. MoE models like Qwen3.5-35B-A3B only use about 7 GB of active parameters, making them ideal for 16 GB Macs."
  - q: "Is Ollama or LM Studio better for Mac?"
    a: "It depends on your use case. LM Studio (MLX) is faster for throughput and more power-efficient. Ollama (llama.cpp) has lower first-token latency and handles large context windows (>32K) better. See the detailed comparison at asiai.dev/ollama-vs-lmstudio."
  - q: "Does asiai require sudo or root access?"
    a: "No. All features including GPU observability (ioreg) and power monitoring (IOReport) work without sudo. The optional --power flag for cross-validation with powermetrics is the only feature that uses sudo."
  - q: "How do I install asiai?"
    a: "Install via pip (pip install asiai) or Homebrew (brew tap druide67/tap && brew install asiai). Python 3.11+ required."
  - q: "Can AI agents use asiai?"
    a: "Yes. asiai includes an MCP server with 11 tools and 3 resources. Install with pip install asiai[mcp] and configure as asiai mcp in your MCP client (Claude Code, Cursor, etc.)."
  - q: "How accurate are the power measurements?"
    a: "IOReport power readings have less than 1.5% delta compared to sudo powermetrics, validated across 20 samples on both LM Studio (MLX) and Ollama (llama.cpp)."
  - q: "Can I benchmark multiple models at once?"
    a: "Yes. Use asiai bench --compare to run cross-model benchmarks. Supports model@engine syntax for precise control, with up to 8 comparison slots."
  - q: "How do I share my benchmark results?"
    a: "Run asiai bench --share to anonymously submit results to the community leaderboard. Add --card to generate a shareable 1200x630 benchmark card image."
  - q: "What metrics does asiai measure?"
    a: "Seven core metrics: tok/s (generation speed), TTFT (time to first token), power (GPU+CPU watts), tok/s/W (energy efficiency), VRAM usage, run-to-run stability, and thermal throttling state."
---

# Frequently Asked Questions

## General

**What is asiai?**

asiai is an open-source CLI tool that benchmarks and monitors LLM inference engines on Apple Silicon Macs. It supports 7 engines (Ollama, LM Studio, mlx-lm, llama.cpp, oMLX, vllm-mlx, Exo) and measures tok/s, TTFT, power consumption, and VRAM usage with zero dependencies.

**Does asiai work on Intel Macs or Linux?**

No. asiai requires Apple Silicon (M1, M2, M3, or M4). It uses macOS-specific APIs (`sysctl`, `vm_stat`, `ioreg`, `IOReport`, `launchd`) that are only available on Apple Silicon Macs.

**Does asiai require sudo or root access?**

No. All features including GPU observability (`ioreg`) and power monitoring (`IOReport`) work without sudo. The optional `--power` flag for cross-validation with `powermetrics` is the only feature that uses sudo.

## Engines & Performance

**What is the fastest LLM engine on Apple Silicon?**

In our benchmarks on M4 Pro 64GB with Qwen3-Coder-30B (Q4_K_M), LM Studio (MLX backend) achieves **102 tok/s** vs Ollama's **70 tok/s** — 46% faster for token generation. LM Studio is also 82% more power-efficient (8.23 vs 4.53 tok/s/W). See our [detailed comparison](ollama-vs-lmstudio.md).

**Is Ollama or LM Studio better for Mac?**

It depends on your use case:

- **LM Studio (MLX)**: Best for throughput (code generation, long responses). Faster, more efficient, lower VRAM.
- **Ollama (llama.cpp)**: Best for latency (chatbots, interactive use). Faster TTFT. Better for large context windows (>32K tokens).

**How much RAM do I need to run LLMs locally?**

| Model Size | Quantization | RAM Needed |
|-----------|-------------|-----------|
| 7B | Q4_K_M | 8 GB minimum |
| 13B | Q4_K_M | 16 GB minimum |
| 30B | Q4_K_M | 32-64 GB |
| 35B MoE (3B active) | Q4_K_M | 16 GB (only active params loaded) |

## Benchmarking

**How do I run my first benchmark?**

Three commands:

```bash
pip install asiai     # Install
asiai detect          # Find engines
asiai bench           # Run benchmark
```

**How long does a benchmark take?**

A quick benchmark (`asiai bench --quick`) takes about 2 minutes. A full cross-engine comparison with multiple prompts and 3 runs takes 10-15 minutes.

**How accurate are the power measurements?**

IOReport power readings have less than 1.5% delta compared to `sudo powermetrics`, validated across 20 samples on both LM Studio (MLX) and Ollama (llama.cpp).

**Can I compare my results with other Mac users?**

Yes. Run `asiai bench --share` to anonymously submit results to the [community leaderboard](leaderboard.md). Use `asiai compare` to see how your Mac stacks up.

## AI Agent Integration

**Can AI agents use asiai?**

Yes. asiai includes an MCP server with 11 tools and 3 resources. Install with `pip install "asiai[mcp]"` and configure as `asiai mcp` in your MCP client (Claude Code, Cursor, Windsurf). See the [Agent Integration Guide](agent.md).

**What MCP tools are available?**

11 tools: `check_inference_health`, `get_inference_snapshot`, `list_models`, `detect_engines`, `run_benchmark`, `get_recommendations`, `diagnose`, `get_metrics_history`, `get_benchmark_history`, `refresh_engines`, `compare_engines`.

3 resources: `asiai://status`, `asiai://models`, `asiai://system`.
