---
description: How asiai measures tok/s, TTFT and power. Warmup, statistical methodology, and why results are reproducible.
---

# Benchmark Methodology

asiai follows established benchmarking standards ([MLPerf](https://mlcommons.org/benchmarks/inference-server/), [SPEC CPU 2017](https://www.spec.org/cpu2017/), [NVIDIA GenAI-Perf](https://docs.nvidia.com/deeplearning/nemo/user-guide/docs/en/stable/benchmarking/genai_perf.html)) to produce reliable, reproducible, and comparable results.

## Protocol

1. **Warmup**: 1 non-timed generation per engine to prime caches
2. **Measured runs**: Default 3 runs per prompt per engine (configurable via `--runs`)
3. **Sampling**: `temperature=0` (greedy) for deterministic output
4. **Reporting**: Median tok/s as primary metric (SPEC standard), mean +/- stddev as secondary
5. **Throttling**: Warning emitted if `thermal_speed_limit < 100%` during any run
6. **Metadata**: Engine version, model format, quantization, hardware chip, macOS version stored per result

## Metrics

### tok/s — Generation Speed

Tokens per second of **generation time only**, excluding prompt processing (TTFT).

```
generation_s = total_duration_s - ttft_s
tok_per_sec  = tokens_generated / generation_s
```

At large context sizes (e.g., 64k tokens), TTFT can dominate total duration. Excluding it from tok/s prevents fast generators from appearing slow.

### TTFT — Time to First Token

Time between sending the request and receiving the first output token, in milliseconds. Measured server-side (Ollama) or client-side at the first SSE content chunk (OpenAI-compatible engines).

### Power — GPU Watts

Average GPU power during execution of each specific engine, measured via `sudo powermetrics`. One `PowerMonitor` per engine — no session-wide averaging.

### tok/s/W — Energy Efficiency

```
tok_per_sec_per_watt = tok_per_sec / power_watts
```

### Variance — Pooled Stddev

Pooled intra-prompt standard deviation captures run-to-run noise **without** mixing in inter-prompt variance.

Stability classification:

- CV < 5% → `stable`
- CV < 10% → `variable`
- CV >= 10% → `unstable`

Where CV = `(std_dev / mean) * 100`.

## Conformance

| Practice | Status |
|----------|--------|
| TTFT separated from tok/s | Implemented |
| Deterministic sampling (temperature=0) | Implemented |
| Token count from server API (not SSE chunks) | Implemented |
| Per-engine power monitoring | Implemented |
| 1 warmup generation per engine | Implemented |
| Default 3 runs (SPEC minimum) | Implemented |
| Median as primary metric (SPEC standard) | Implemented |
| Pooled intra-prompt stddev | Implemented |
| Thermal throttling detection + warning | Implemented |
| Engine version + model metadata stored | Implemented |
| Historical regression detection | Implemented |

## Apple Silicon Considerations

### Unified Memory

Apple Silicon shares memory between CPU and GPU. asiai runs engines **sequentially** to avoid memory contention. Ollama and LM Studio report VRAM per model — other engines show "—".

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
