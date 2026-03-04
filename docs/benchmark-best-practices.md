# Benchmark Best Practices

> **Version**: 0.3.2
> **Status**: Living document — updated as methodology evolves
> **References**: MLPerf Inference, SPEC CPU 2017, NVIDIA GenAI-Perf

## Overview

`asiai bench` follows established benchmarking standards to produce **reliable, reproducible,
and comparable** results across inference engines on Apple Silicon. This document tracks
which best practices are implemented, planned, or intentionally excluded.

## Conformance Summary

| Category | Practice | Status | Since |
|----------|----------|--------|-------|
| **Metrics** | TTFT separated from tok/s | Implemented | v0.3.1 |
| | Deterministic sampling (temperature=0) | Implemented | v0.3.2 |
| | Token count from server API (not SSE chunks) | Implemented | v0.3.1 |
| | Per-engine power monitoring | Implemented | v0.3.1 |
| | generation_duration_ms explicit field | Implemented | v0.3.1 |
| **Warmup** | 1 warmup generation per engine (non-timed) | Implemented | v0.3.2 |
| **Runs** | Default 3 runs (SPEC minimum) | Implemented | v0.3.2 |
| | Median as primary metric (SPEC standard) | Implemented | v0.3.2 |
| | Mean + stddev as secondary | Implemented | v0.3.0 |
| **Variance** | Pooled intra-prompt stddev | Implemented | v0.3.1 |
| | CV-based stability classification | Implemented | v0.3.0 |
| **Environment** | Sequential engine execution (memory isolation) | Implemented | v0.1 |
| | Thermal throttling detection + warning | Implemented | v0.3.2 |
| | Thermal level + speed_limit recorded | Implemented | v0.1 |
| **Reproducibility** | Engine version stored per benchmark | Implemented | v0.3.2 |
| | Model format + quantization stored | Implemented | v0.3.2 |
| | Hardware chip + macOS version stored | Implemented | v0.3.2 |
| | Open-source benchmark code | Implemented | v0.1 |
| **Regression** | Historical baseline comparison (SQLite) | Implemented | v0.3.0 |
| | Comparison by (engine, model, prompt_type) | Implemented | v0.3.1 |
| | metrics_version filtering | Implemented | v0.3.1 |
| **Prompts** | 4 diverse prompt types + context fill | Implemented | v0.1 |
| | Fixed max_tokens per prompt | Implemented | v0.1 |

## Planned Improvements

### P1 — Statistical Rigor

| Practice | Description | Standard |
|----------|-------------|----------|
| **95% confidence intervals** | CI = mean +/- 2*SE. More informative than +/- stddev. | Academic |
| **Percentiles (P50/P90/P99)** | For TTFT especially — tail latency matters. | NVIDIA GenAI-Perf |
| **Outlier detection (IQR)** | Flag runs outside [Q1 - 1.5*IQR, Q3 + 1.5*IQR]. | Statistical standard |
| **Trend detection** | Detect monotone performance degradation across runs (thermal drift). | Academic |

### P2 — Reproducibility

| Practice | Description | Standard |
|----------|-------------|----------|
| **Cooldown between engines** | Pause 3-5s between engines to let thermals stabilize. | GPU benchmark |
| **Token ratio verification** | Warn if tokens_generated < 90% of max_tokens. | MLPerf |
| **Export format** | `asiai bench --export` JSON for community submissions. | MLPerf submissions |

### P3 — Advanced

| Practice | Description | Standard |
|----------|-------------|----------|
| **`ignore_eos` option** | Force generation to max_tokens for throughput benchmarks. | NVIDIA |
| **Concurrent request testing** | Test batching throughput (relevant for vllm-mlx). | NVIDIA |
| **Background process audit** | Warn if heavy processes are running during benchmark. | SPEC |

## Intentional Deviations

| Practice | Reason for deviation |
|----------|---------------------|
| **MLPerf minimum 600s duration** | Designed for datacenter GPUs. Local inference on Apple Silicon with 3 runs + 4 prompts already takes ~2-5 minutes. Sufficient for stable results. |
| **SPEC 2 non-timed warmup workloads** | We use 1 warmup generation (not 2 full workloads). Single warmup is sufficient for local inference engines where JIT warmup is minimal. |
| **Population vs sample stddev** | We use population stddev (N divisor) instead of sample stddev (N-1 divisor). With small N (3-5 runs), the difference is minimal and population is more conservative. |
| **Frequency scaling control** | Apple Silicon does not expose CPU governor controls. We record thermal_speed_limit instead to detect throttling. |

## Apple Silicon Specific Considerations

### Unified Memory Architecture

Apple Silicon shares memory between CPU and GPU. Two key implications:

1. **Never benchmark two engines simultaneously** — they compete for the same memory pool.
   `asiai bench` runs engines sequentially by design.
2. **VRAM reporting** — Only Ollama reports `size_vram` (GPU-mapped portion). OpenAI-compatible
   engines don't expose this. We show "—" rather than misleading values.

### Thermal Throttling

- **MacBook Air** (no fan): severe throttling under sustained load. Results degrade after 5-10 min.
- **MacBook Pro** (fan): throttling is mild and usually handled by the fan ramping up.
- **Mac Mini/Studio/Pro**: active cooling, minimal throttling.

`asiai bench` records `thermal_speed_limit` per result and warns if throttling is detected
(speed_limit < 100%) during any run.

### KV Cache and Context Length

Large context sizes (32k+) can cause performance instability on engines that pre-allocate
KV cache at model load time. Example: LM Studio defaults to `loaded_context_length: 262144`
(256k), which allocates ~15-25 GB of KV cache for a 35B model, potentially saturating
64 GB of unified memory.

**Recommendations**:
- When benchmarking large contexts, set engine context length to match the actual test size
  (e.g. `lms load model --context-length 65536` for 64k tests).
- Compare engines with equivalent context length settings for fair results.

## Metadata Stored Per Benchmark

Every benchmark result in SQLite includes:

| Field | Example | Purpose |
|-------|---------|---------|
| `engine` | "ollama" | Engine identification |
| `engine_version` | "0.17.4" | Detect performance changes across updates |
| `model` | "qwen3.5:35b-a3b" | Model identification |
| `model_format` | "gguf" | Differentiate format variants |
| `model_quantization` | "Q4_K_M" | Differentiate quantization levels |
| `hw_chip` | "Apple M4 Pro" | Hardware identification |
| `os_version` | "15.3" | macOS version tracking |
| `thermal_level` | "nominal" | Environment condition |
| `thermal_speed_limit` | 100 | Throttling detection |
| `metrics_version` | 2 | Formula version (prevents cross-version regression) |

This metadata enables:
- **Fair regression comparison**: only compare results with matching metadata
- **Cross-machine benchmarks**: identify hardware differences
- **Community data sharing**: self-describing results (planned for v1.x)
