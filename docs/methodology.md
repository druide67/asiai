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

Since v1.6.0, asiai measures **two TTFT values** for Ollama, and one for all other engines:

**Ollama** (dual measurement):

- **Server-side TTFT** (`ttft_ms`): extracted from `prompt_eval_duration` in the Ollama response. This is pure GPU prompt processing time with zero network overhead — the most accurate measurement possible. Reported as `ttft_source: server`.
- **Client-side TTFT** (`ttft_client_ms`): measured at the arrival of the first SSE content chunk. Includes HTTP setup, request transmission, and server processing. This is the same method used for all other engines.

**OpenAI-compatible engines** (LM Studio, llama.cpp, mlx-lm, vllm-mlx):

- **Client-side TTFT** (`ttft_client_ms`): measured at the first SSE content chunk. This is the only measurement available since these engines do not expose internal prompt processing timing. Both `ttft_ms` and `ttft_client_ms` contain the same value.

**Comparable metric**: `ttft_client_ms` is the **cross-engine comparable** metric — it uses the same measurement method regardless of the engine. Use this when comparing TTFT across different engines. The server-side `ttft_ms` from Ollama is more accurate for absolute prompt processing time, but not directly comparable with other engines.

**Cross-validation** (April 2026, Qwen3.5-35B NVFP4, M4 Pro 64GB):

| Method | TTFT | Delta |
|--------|------|-------|
| Ollama server-side (`ttft_ms`) | 27 ms | reference |
| Ollama client-side (`ttft_client_ms`) | 51 ms | +24 ms |

The 24ms delta represents HTTP overhead on localhost. This overhead is consistent and predictable but significant enough to matter when comparing engines.

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

## Agentic Mode — Prefix Cache Reuse Benchmark

Standard single-shot benchmarks measure how fast an engine generates tokens
in isolation. They miss the dominant cost pattern of multi-turn agent
workloads: a long shared **system** prompt (tools, rules, persona — often
6K+ tokens) plus a short **user** message that changes every turn. An
engine that does not reuse the cached prefix re-processes those 6K tokens
on every call, and TTFT explodes.

`asiai bench --agentic-mode` runs an 8-phase protocol designed to expose
this behavior explicitly.

### Protocol

| Phase | System | User | max_tokens | Purpose |
|---|---|---|---|---|
| `cold` | SYS_A | USER_X | 400 | First run, no cache |
| `warm` | SYS_A | USER_X | 400 | Same request — full cache hit |
| `prefix-test-1` | SYS_A | USER_Y | 400 | **Sys identical, user different** — the real test |
| `prefix-test-2` | SYS_A | USER_X | 400 | Back to USER_X — should be cache hit |
| `prefix-test-3` | SYS_A | USER_Y | 400 | Repeat the cross-user pattern |
| `cold-prefix` | SYS_B | USER_X | 400 | Sys changes — should miss cache |
| `long-context` | SYS_A | USER_L (~50K tok) | 200 | Saturate decode at long context |
| `long-prefix` | SYS_A | USER_L | 200 | Same long context — cache hit |

Prompts are generated deterministically with a sentinel pattern that
breaks naive substring caches; sizes are calibrated for Qwen-family
tokenizers (~5.3 chars/token on English prose).

### Verdict

`prefix_cache_reuse` is computed from the prefix-test phases:

1. **Primary signal** — if the engine reports `usage.prompt_tokens_details.cached_tokens`
   in its streaming response (llama.cpp, mlx-lm), the ratio `cached / prompt`
   is averaged across the prefix-test phases:
   - `≥ 0.5` → `yes`
   - `≥ 0.1` → `partial`
   - otherwise → `no`
2. **Fallback signal** — if the engine does not report `cached_tokens`
   (LM Studio, vllm-mlx, oMLX), TTFT ratio is used: prefix-test TTFT
   versus cold TTFT.
   - `< cold/5` → `yes`
   - `< cold/2` → `partial`
   - otherwise → `no`

### Quality gates

Three gates run alongside the bench and surface in `result["quality_gates"]`:

- **`early_stop`** — flags phases where `completion_tokens` drops below
  50% of the requested `max_tokens` on two or more runs. Catches engine
  bugs where a speculatively-drafted EOS token is accepted incorrectly
  under prefix cache reuse — the result still parses as valid
  OpenAI-compat but the engine silently returns truncated answers.
- **`memory_pressure`** — a background thread polls `vm_stat` and
  `vm.swapusage` every 15s with the baseline taken at bench start. Alerts
  when swap usage grows >500 MB or swapouts grow >1000 from baseline.
  Both indicate the OS is paging the model or KV cache to disk, so the
  measured `tok/s` no longer represents the engine itself.
- **`duplicate_processes`** — a single `ps` snapshot before the bench
  rejects runs where two instances of the same engine are bound, since
  one will compete with the bench for GPU and confuse process attribution.

When a gate trips, the CLI prints a red warning under the verdict line
and the JSON output keeps full per-sample detail so a leaderboard or
regression tracker can refuse to publish the result.

### Reproducible cold starts (opt-in `aisctl` integration)

`asiai bench --agentic-mode --agentic-auto-restart` calls
`aisctl restart <engine>` before the first phase and polls `/health`
until ready. Useful for engines without a model-unload API (llama.cpp,
oMLX, TurboQuant) where a daemon restart is the only reliable way to
wipe the KV cache. Add `--agentic-auto-restart-required` to abort
instead of proceeding when `aisctl` is unavailable.

This integration requires
[`asiai-inference-server`](https://github.com/druide67/asiai-inference-server)
installed; otherwise the bench logs a warning and proceeds against
whatever the engine state already is.

### Why it matters

A single-shot `tok/s` number is meaningless for agent workflows when the
engine does not reuse the system prefix. Two engines with identical
single-shot throughput can differ by **5-10× on agent tick latency**
depending on whether the prefix cache holds.

`agentic-mode` exposes that gap explicitly so the leaderboard and
engine-selection decisions reflect the dominant workload, not a
microbenchmark.

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
| Dual TTFT measurement (server + client) | Implemented (v1.6.0) |
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
