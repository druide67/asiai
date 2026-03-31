---
title: "TurboQuant Benchmark on Apple Silicon: Run 70B Models on Mac"
description: "Real benchmarks of TurboQuant KV cache compression on Mac Mini M4 Pro 64GB: Llama 70B at 6.3 tok/s with 5x memory savings. Setup guide and results."
type: article
date: 2026-03-31
updated: 2026-03-31
faq:
  - q: "Can I run a 70B model on a Mac with 64GB RAM?"
    a: "Yes, with TurboQuant. The KV cache is compressed 5x, so Llama 70B Q4_K_M (40GB weights) fits comfortably in 64GB with 32K context. We measured 6.3 tok/s on a Mac Mini M4 Pro."
  - q: "Does TurboQuant reduce quality?"
    a: "No measurable quality loss. The perplexity increase is under 1% vs q8_0, and Needle-in-a-Haystack retrieval scores 100% through 32K context."
  - q: "Which TurboQuant format should I use?"
    a: "We recommend asymmetric: q8_0 for keys (sensitive to compression) and turbo3 for values (5x compression, no quality impact). This is based on findings from the turboquant_plus project."
  - q: "Does TurboQuant work with MLX engines?"
    a: "Community MLX implementations exist but are less mature than the llama.cpp fork. For production use on Apple Silicon, we recommend TheTom/llama-cpp-turboquant with Metal kernels."
  - q: "How much faster is TurboQuant?"
    a: "Decode speed is about 0.9x of q8_0 (slightly slower per token), but prefill can be faster at long context due to reduced memory bandwidth. The real gain is fitting larger models and longer contexts in the same RAM."
---

# TurboQuant Benchmark on Apple Silicon

TurboQuant (Google Research, ICLR 2026) compresses the KV cache of LLMs by 5x with no quality loss, enabling 70B models to run on a Mac Mini with 64GB RAM. These are real benchmarks measured with [asiai](/) on actual hardware.

## Results

**Llama-3.1-70B-Instruct Q4_K_M on Mac Mini M4 Pro 64GB**

| Metric | Value |
|--------|-------|
| **Throughput** | 6.3 tok/s (stable, CI 95%: 6.3-6.3) |
| **TTFT** | 196 ms (median) |
| **GPU Power** | 23.8 W |
| **Model VRAM** | 44.1 GB (40 GB weights + 4 GB KV turbo3) |
| **Context** | 32,768 tokens |
| **GPU Offload** | 81/81 layers on Metal |
| **Thermal** | Nominal (no throttling) |
| **Stability** | Stable (std dev 0.04 tok/s across 3 runs) |

KV cache configuration: keys at q8_0 (high precision), values at turbo3 (3-bit, 5x compression).

## Before vs After TurboQuant

| | Without TurboQuant | With TurboQuant (turbo3) |
|--|-------------------|--------------------------|
| **KV cache (32K ctx)** | ~20 GB (q8_0) | ~4 GB (turbo3) |
| **Total RAM needed** | 60+ GB (OOM on 64GB) | 44 GB (fits in 64GB) |
| **Can run 70B on 64GB?** | No | **Yes** |
| **Quality** | Baseline | -1% PPL (negligible) |
| **NIAH retrieval** | 100% | 100% |

## What Is TurboQuant?

TurboQuant is a KV cache compression algorithm from Google Research, presented at ICLR 2026. During LLM inference, the KV cache stores intermediate attention states and grows linearly with context length. For a 70B model at 128K context in FP16, this cache alone can consume 20-40 GB of RAM.

TurboQuant compresses this cache to 3 bits per value using:

- **Random rotation** (Walsh-Hadamard transform) to Gaussianize the data
- **Optimal scalar quantization** (PolarQuant) near the Shannon limit
- **QJL** (Quantized Johnson-Lindenstrauss) to preserve dot products

The result: 5x memory reduction, no fine-tuning needed, and near-zero quality loss.

## Setup Guide

### Hardware

- Mac Mini M4 Pro, 64 GB unified memory ($2,700)
- Any Apple Silicon Mac with 32+ GB should work (adjust model size accordingly)

### Install TurboQuant llama.cpp

```bash
# Install build tools
brew install cmake

# Clone the TurboQuant fork
git clone https://github.com/TheTom/llama-cpp-turboquant.git
cd llama-cpp-turboquant
git checkout feature/turboquant-kv-cache

# Build with Metal (Apple Silicon GPU)
cmake -B build -DGGML_METAL=ON -DGGML_METAL_EMBED_LIBRARY=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(sysctl -n hw.ncpu)
```

### Download a Model

```bash
# Llama 3.1 70B Q4_K_M (~40 GB)
curl -L -o llama-3.1-70b-q4_k_m.gguf \
  "https://huggingface.co/bartowski/Meta-Llama-3.1-70B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-70B-Instruct-Q4_K_M.gguf"
```

### Raise macOS GPU Memory Limit

```bash
sudo sysctl iogpu.wired_limit_mb=61440
```

### Launch the Server

```bash
./build/bin/llama-server \
  -m llama-3.1-70b-q4_k_m.gguf \
  --cache-type-k q8_0 --cache-type-v turbo3 \
  -c 32768 \
  --port 8081 \
  --host 0.0.0.0 \
  -fa 1 \
  -ngl 99 \
  -t 10 \
  --no-mmap \
  --chat-template chatml
```

### Configuration Explained

| Parameter | Value | Why |
|-----------|-------|-----|
| `--cache-type-k q8_0` | Keys at 8-bit | Keys are sensitive to compression |
| `--cache-type-v turbo3` | Values at 3-bit | Values tolerate extreme compression (5x) |
| `-fa 1` | Flash Attention | Required for TurboQuant |
| `-ngl 99` | Full GPU offload | All 81 layers on Metal |
| `-t 10` | 10 threads | M4 Pro has 10 performance cores |
| `--no-mmap` | No memory mapping | Loads everything at boot, avoids page faults |
| `--chat-template chatml` | ChatML format | Best compatibility with this fork |

## Benchmark with asiai

```bash
pip install asiai
asiai detect --url http://localhost:8081
asiai bench --engines llamacpp --prompts code --runs 3 --kv-cache turbo3 --card
```

## Models That Fit on 64GB with TurboQuant

| Model | Weights (Q4_K_M) | KV Cache (32K, turbo3) | Total | Status |
|-------|-------------------|----------------------|-------|--------|
| Llama 3.1 70B | 40 GB | ~4 GB | 44 GB | **Tested: 6.3 tok/s** |
| Qwen2.5 72B | 40 GB | ~4 GB | 44 GB | Should work |
| Llama 70B 128K ctx | 40 GB | ~16 GB (turbo3) | 56 GB | Tight but possible |
| Command-R+ 104B | 58 GB | ~4 GB | 62 GB | Very tight |

## FAQ

**Can I run a 70B model on a Mac with 64GB RAM?**

Yes, with TurboQuant. The KV cache is compressed 5x, so Llama 70B Q4_K_M (40GB weights) fits comfortably in 64GB with 32K context. We measured 6.3 tok/s on a Mac Mini M4 Pro.

**Does TurboQuant reduce quality?**

No measurable quality loss. The perplexity increase is under 1% vs q8_0, and Needle-in-a-Haystack retrieval scores 100% through 32K context.

**Which TurboQuant format should I use?**

Asymmetric: q8_0 for keys + turbo3 for values. Keys are sensitive to compression (all quality degradation comes from K compression). Values can be compressed to 2-3 bits with zero effect on attention quality.

**Does TurboQuant work with MLX?**

Community implementations exist ([turboquant-mlx](https://github.com/helgklaizar/turboquant_mlx)) but are less mature than the llama.cpp fork. For production use, we recommend [TheTom/llama-cpp-turboquant](https://github.com/TheTom/llama-cpp-turboquant).

**How does this compare to standard llama.cpp?**

Decode speed is ~0.9x of q8_0 (slightly slower per token), but the real gain is fitting models and contexts that simply didn't fit before. Prefill can actually be faster at long context due to reduced memory bandwidth pressure.

## References

- [Google Research Blog — TurboQuant](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/)
- [TurboQuant Paper (ICLR 2026)](https://arxiv.org/abs/2504.19874)
- [TheTom/turboquant_plus](https://github.com/TheTom/turboquant_plus) — Extended implementation with Sparse V
- [TheTom/llama-cpp-turboquant](https://github.com/TheTom/llama-cpp-turboquant) — llama.cpp fork with Metal kernels
- [llama.cpp Discussion #20969](https://github.com/ggml-org/llama.cpp/discussions/20969) — Community thread
