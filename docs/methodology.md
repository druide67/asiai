---
description: How asiai measures tok/s, TTFT and power. Warmup, statistical methodology, and why results are reproducible.
---

# Benchmark Methodology

asiai follows established benchmarking standards ([MLPerf](https://mlcommons.org/benchmarks/inference-server/), [SPEC CPU 2017](https://www.spec.org/cpu2017/), [NVIDIA GenAI-Perf](https://docs.nvidia.com/deeplearning/nemo/user-guide/docs/en/stable/benchmarking/genai_perf.html)) to produce reliable, reproducible, and comparable results.

## Protocol

1. **Pre-flight gate check**: Refuse to start if memory pressure is critical or system is heavily throttled (<80%)
2. **Warmup**: 1 non-timed generation per engine to prime JIT compilers and caches
3. **Measured runs**: Default 3 runs per prompt per engine (configurable via `--runs`)
4. **Sampling**: `temperature=0` (greedy) for deterministic output
5. **Model unloading**: After benchmarking each engine, the model is unloaded to free unified memory before the next engine starts. This prevents memory accumulation and swapping when comparing multiple engines on large models
6. **Adaptive cooldown**: After unloading, asiai waits for macOS memory pressure to return to "normal" (max 30s), then adds a minimum 5s thermal cooldown
7. **Sanity checks**: Results with tok/s ≤ 0 are discarded. TTFT > 60s or tok/s > 500 trigger warnings (likely swapping or measurement errors)
8. **Reporting**: Median tok/s as primary metric (SPEC standard), mean ± stddev as secondary
9. **Throttling**: Warning emitted if `thermal_speed_limit < 100%` during any run. Thermal drift (monotone tok/s decrease across runs, ≥5% drop) is detected and reported
10. **Metadata**: Engine version, model format, quantization, hardware chip, macOS version stored per result

## Metrics

### tok/s — Generation Speed

Tokens per second of **generation time only**, excluding prompt processing (TTFT).

**Ollama** (native API, `/api/generate`):
```
tok_per_sec = eval_count / (eval_duration_ns / 1e9)
```
Source: internal GPU timing reported by Ollama. No network overhead. This is the most accurate measurement.

**OpenAI-compatible engines** (LM Studio, llama.cpp, mlx-lm, vllm-mlx):
```
generation_s = wall_clock_s - ttft_s
tok_per_sec  = completion_tokens / generation_s
```
Source: client-side wall clock via streaming SSE. Includes HTTP overhead per chunk (~1% slower than server-side timing, validated by cross-validation).

**Token count**: from `usage.completion_tokens` in the server response. If the server does not report this field, asiai falls back to `len(text) // 4` and logs a warning. This fallback can be ~25% off.

**Cross-validation** (April 2026, Qwen3.5-35B NVFP4, M4 Pro 64GB):

| Method | tok/s | Delta vs reference |
|--------|-------|--------------------|
| Ollama native (internal GPU) | 66.6 | reference |
| OpenAI streaming (client) | 66.1 | -0.8% |

At large context sizes (e.g., 64k tokens), TTFT can dominate total duration. Excluding it from tok/s prevents fast generators from appearing slow.

### TTFT — Time to First Token

Time between sending the request and receiving the first output token, in milliseconds.

**Ollama**: measured server-side via `prompt_eval_duration` (internal timing). This is pure prompt processing time with no network overhead. Reported as `ttft_source: server`.

**OpenAI-compatible engines**: measured client-side at the first SSE content chunk. Includes HTTP setup, request transmission, and server processing. Typically 10-100ms higher than server-side. Reported as `ttft_source: client`.

!!! warning "TTFT comparison"
    Do not compare Ollama server-side TTFT with OpenAI-compat client-side TTFT without accounting for the difference. The `ttft_source` field in benchmark results indicates which method was used.

### Power — GPU Watts

Average GPU power during execution, measured via Apple's IOReport Energy Model framework (no sudo required). One measurement per engine — not session-wide averaging.

### tok/s/W — Energy Efficiency

```
tok_per_sec_per_watt = tok_per_sec / power_watts
```

### Variance — Pooled Stddev

Pooled intra-prompt standard deviation captures run-to-run noise **without** mixing in inter-prompt variance. Uses Bessel's correction (N-1 denominator) for unbiased sample variance.

Stability classification:

- CV < 5% → `stable`
- CV < 10% → `variable`
- CV >= 10% → `unstable`

Where CV = `(std_dev / mean) * 100`.

### VRAM — Memory Usage

**Primary**: engine-native API (Ollama `/api/ps`, LM Studio `/v1/models`).
**Fallback**: `ri_phys_footprint` via ctypes (same as Activity Monitor). Marked "(est.)" in the UI.

## Environment Safety

asiai performs pre-benchmark checks:

1. **Memory pressure**: refuses to start if critical
2. **Thermal throttling**: warns if speed limit < 80%
3. **Duplicate processes**: warns if multiple instances of the same engine are running (e.g., two `ollama serve` processes on the same port)
4. **Engine runner type**: for Ollama, detects whether `--mlx-engine` or `--ollama-engine` runner is active

These checks prevent measurement errors caused by resource contention or incorrect routing.

## Conformance

| Practice | Status |
|----------|--------|
| Pre-flight gate check (memory pressure + thermal) | Implemented |
| Duplicate process detection | Implemented (v1.5.0) |
| Ollama runner type detection (MLX vs llama.cpp) | Implemented (v1.5.0) |
| TTFT separated from tok/s | Implemented |
| TTFT source labeling (server vs client) | Implemented (v1.5.0) |
| Deterministic sampling (temperature=0) | Implemented |
| Token count from server API (not SSE chunks) | Implemented (warning on fallback) |
| Per-engine power monitoring (IOReport, no sudo) | Implemented |
| 1 warmup generation per engine | Implemented |
| Default 3 runs (SPEC minimum) | Implemented |
| Median as primary metric (SPEC standard) | Implemented |
| Pooled intra-prompt stddev (Bessel N-1) | Implemented (corrected v1.5.0) |
| Model unloading between engines | Implemented |
| Adaptive cooldown (memory pressure-aware) | Implemented |
| Sanity checks (tok/s, TTFT bounds) | Implemented |
| Thermal throttling detection + warning | Implemented |
| Thermal drift detection (monotone decrease) | Implemented |
| Engine version + runner type stored per result | Implemented (v1.5.0) |
| Universal VRAM via ri_phys_footprint | Implemented |
| Historical regression detection | Implemented |
| Cross-validation script (3 methods compared) | Available (scripts/cross-validate-bench.py) |

## Apple Silicon Considerations

### Unified Memory

Apple Silicon shares memory between CPU and GPU. asiai runs engines **sequentially** and **unloads models between engines** to avoid memory contention and swapping. VRAM is reported natively by Ollama and LM Studio; for other engines, asiai estimates memory usage via `ri_phys_footprint` (the macOS physical footprint metric, same as Activity Monitor). Estimated values are labeled "(est.)" in the UI.

### Thermal Throttling

- **MacBook Air** (no fan): severe throttling under sustained load
- **MacBook Pro** (fan): mild throttling
- **Mac Mini/Studio/Pro**: active cooling, minimal throttling

asiai records `thermal_speed_limit` per result and warns if throttling is detected.

### KV Cache

Large context sizes (32k+) can cause instability on engines that pre-allocate KV cache. Set engine context length to match the actual test size for fair results.

## Power Measurement

asiai measures GPU, CPU, ANE and DRAM power consumption via Apple's IOReport Energy Model framework — **no sudo required**. Power is measured automatically in every benchmark and every monitoring snapshot.

IOReport reads the same hardware energy counters as `sudo powermetrics`, but through a user-space API (`libIOReport.dylib` via ctypes). This eliminates the need for passwordless sudo configuration.

### Validation

We cross-validated IOReport against `sudo powermetrics` under LLM inference load on M4 Pro 64GB, using 10 paired samples per engine at 2-second intervals:

| Engine | IOReport avg | powermetrics avg | Mean delta | Max delta |
|--------|-------------|-----------------|------------|-----------|
| LM Studio (MLX) | 12.6 W | 12.6 W | 0.9% | 2.1% |
| Ollama (llama.cpp) | 15.6 W | 15.4 W | 1.3% | 4.1% |

Both engines confirmed <1.5% average delta with 10/10 paired samples. ANE power was 0.000W across all 20 samples, confirming no LLM engine currently uses the Neural Engine.

The `--power` flag enables additional cross-validation by running both IOReport and `sudo powermetrics` simultaneously, storing both readings for comparison.

### Power Efficiency

Power efficiency (tok/s per watt) is calculated as `tok_per_sec / gpu_watts` for each benchmark result. This metric enables comparison of inference cost across engines and hardware.

## Metadata

Every benchmark result stores: engine, engine_version, model, model_format, model_quantization, hw_chip, os_version, thermal_level, thermal_speed_limit, power_watts, power_source, metrics_version. This enables fair regression comparison and cross-machine benchmarks.
