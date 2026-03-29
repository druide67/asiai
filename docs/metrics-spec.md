---
description: "Detailed definitions of all asiai benchmark metrics: tok/s, TTFT, power watts, efficiency, VRAM, stability, thermal state."
---

# Benchmark Metrics Specification

> **Version**: 0.4.0
> **Status**: Implemented
> **Scope**: `asiai bench` — all engines

## Motivation

Benchmark results must be **comparable across engines**. Each metric has a single definition
that all engine implementations must respect. The implementation may vary (server-side API vs
client-side measurement), but the semantic must be identical.

## Metrics

### M1. `tok_per_sec` — Generation Speed

**Definition**: Tokens produced per second of **generation time only**, excluding prompt
processing (TTFT).

```
generation_s = total_duration_s - ttft_s
tok_per_sec  = tokens_generated / generation_s    (if generation_s >= 0.01)
             = 0.0                                 (otherwise)
```

| Engine | `generation_s` source |
|--------|----------------------|
| Ollama | `eval_duration / 1e9` (server API — direct) |
| OpenAI-compat | `elapsed_s - (ttft_ms / 1000)` (client-side) |

**Rationale**: At large context sizes (e.g. 64k tokens), TTFT can dominate total duration.
Including it in tok/s makes fast generators appear slow (e.g. 3.2 tok/s instead of 42 tok/s).

### M2. `ttft_ms` — Time to First Token

**Definition**: Time between sending the request and receiving the first output token, in ms.

| Engine | Source |
|--------|--------|
| Ollama | `prompt_eval_duration / 1e6` (server API) |
| OpenAI-compat | `(time.monotonic() at 1st content chunk - t0) * 1000` (client) |

Note: Semantics differ slightly (server vs client measurement), but on localhost the gap is
~1ms — acceptable.

### M3. `total_duration_ms` — Total Duration

**Definition**: Wall-clock total request time (prompt processing + generation), in ms.

**Invariant**: `total_duration_ms >= ttft_ms` — always.

| Engine | Source |
|--------|--------|
| Ollama | `total_duration / 1e6` (server API) |
| OpenAI-compat | `elapsed_s * 1000` (client wall-clock) |

### M4. `tokens_generated` — Token Count

**Definition**: Number of output tokens produced by the model.

**Source (by priority)**:
1. Server counter: Ollama `eval_count`, OpenAI-compat `usage.completion_tokens`
2. Text length estimate: `max(1, len(text) // 4)` (heuristic: ~4 chars/token)
3. **Never** `len(text_parts)` (SSE chunks != tokens)

### M5. `generation_duration_ms` — Generation Duration

**Definition**: Generation time only (excluding TTFT), in ms.
Makes the decomposition `total = ttft + generation` explicit and auditable.

| Engine | Source |
|--------|--------|
| Ollama | `eval_duration / 1e6` (server API — direct) |
| OpenAI-compat | `max(0, elapsed_s - ttft_s) * 1000` (computed) |

### M6. `power_watts` — GPU Power

**Definition**: Average GPU power during execution of **this specific engine**, in watts.

**Scope**: One `PowerMonitor` per engine. Started before the first prompt, stopped after
the last run. Each engine gets its own measurement — no session-wide averaging.

Source: `sudo powermetrics` (macOS).

### M7. `tok_per_sec_per_watt` — Energy Efficiency

```
tok_per_sec_per_watt = tok_per_sec / power_watts
```

Uses the corrected tok/s (M1) and per-engine power (M6).

### M8. `std_dev_tok_s` — Variance (Pooled)

**Definition**: Pooled intra-prompt standard deviation — captures run-to-run noise
**without** mixing in inter-prompt variance.

```
For each prompt_type p with runs [v1, v2, ..., vn]:
    var_p = sum((vi - mean_p)^2) / n    (population variance)

pooled_variance = mean(var_p for all p with n >= 2)
std_dev_tok_s   = sqrt(pooled_variance)
```

**Stability classification** (unchanged):
- CV < 5% → `stable`
- CV < 10% → `variable`
- CV >= 10% → `unstable`

Where CV = `(std_dev_tok_s / avg_tok_s) * 100`.

## Implementation Map

| Metric | `base.py` | `ollama.py` | `openai_compat.py` | `runner.py` | `reporter.py` |
|--------|-----------|-------------|--------------------|-----------  |----------------|
| M1 tok/s | field | server API | client (excl. TTFT) | passthrough | avg |
| M2 ttft_ms | field | server API | client streaming | passthrough | avg |
| M3 total_duration_ms | field | server API | client wall-clock | passthrough | avg |
| M4 tokens_generated | field | server API | server or `len//4` | passthrough | avg |
| M5 generation_duration_ms | field | server API | computed | stored in dict | — |
| M6 power_watts | — | — | — | per-engine monitor | passthrough |
| M7 tok/s/W | — | — | — | computed | passthrough |
| M8 std_dev | — | — | — | — | pooled intra-prompt |

## Benchmark Protocol

1. **Warmup**: 1 non-timed generation per engine (`"Hello"`, max_tokens=1) to prime caches.
2. **Measured runs**: Default 3 runs per prompt per engine (configurable via `--runs`).
3. **Sampling**: `temperature=0` (greedy) on all engines for deterministic output.
4. **Reporting**: Median tok/s as primary metric (SPEC standard), mean +/- stddev as secondary.
5. **Throttling**: Warning emitted if `thermal_speed_limit < 100%` during any run.
6. **Metadata**: engine_version, model_format, model_quantization, hw_chip, os_version
   stored per result for reproducibility.

See [benchmark-best-practices.md](benchmark-best-practices.md) for full methodology audit.
