---
description: "Detailed definitions of all asiai benchmark metrics: tok/s, TTFT, GPU and SoC power, joules per token, efficiency, VRAM, stability, thermal state."
---

# Benchmark Metrics Specification

> **Version**: 0.5.0
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

### M6. `power_watts` — GPU-rail Power (legacy)

**Definition**: Average power of the **GPU rail alone** while **this specific engine** ran
its measured prompts, in watts.

**Scope**: One probe per engine, started after the warmup and stopped after the last run.
Each engine gets its own measurement — no session-wide averaging.

**Source**: IOReport "Energy Model" counters (`libIOReport.dylib`, user space, no sudo),
GPU channel. This is the figure the community leaderboard published as "W" until 2026-09,
and the only one cross-validated against `sudo powermetrics` (<1.5 % on M4 Pro, GPU rail).
It is **kept for continuity** and always labelled `GPU`; it is never averaged with M9.

### M7. `tok_per_sec_per_watt` — GPU-rail Efficiency (legacy)

```
tok_per_sec_per_watt = tok_per_sec / power_watts
```

Uses the corrected tok/s (M1) and the GPU-rail power (M6). Superseded by M10 as the
efficiency headline; still computed, still labelled `(GPU)`.

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

### M9. `soc_watts` — SoC Package Power

**Definition**: Mean package power over the measurement window, in watts, as the sum of the
IOReport rails **GPU + CPU + ANE + DRAM + DCS** (DRAM controller). This rail list is the
base named `soc5`; a submission always carries the list of rails actually read
(`energy.rails`) and the base name (`energy.base`). Two bases are never medianised together.

**Not included**: display, SSD, fans, power-supply losses, and the fabric / memory-cache
rails (`FAB`, `AMCC`) that not every chip exposes. M9 is therefore a **lower bound** on what
a wall meter reads. It has no software counter-measure: `powermetrics` only reports the GPU
rail, so only a wall meter corroborates the SoC figure.

**Window**: standard bench — per **run**, from the request start to the end of the response
(`turn`). Agentic bench — from the first token to the end of the response (`decode`), which
excludes prompt processing. `turn` and `decode` figures are never pooled.

**Refused (no value published, never a 0)**: a required rail (GPU, CPU, DRAM, DCS) missing
from the reading; interval below 1 s; run throttled (`thermal_speed_limit < 100`).

### M10. `energy_per_token_j` — Energy per Generated Token

```
energy_per_token_j = soc_joules / (completion_tokens − 1)
```

`soc_joules` is the M9 energy integrated over the same window; the denominator counts
**intervals between tokens** (n−1), so a one-token answer has no value. Lower is better.

**Published only when** `tokens_source == "usage"` — tokens counted by the engine, never
estimated from characters — and only on runs that passed the thermal gate. The community
leaderboard medianises per-session values of the same `base` and `window`.

### M11. `idle_soc_watts` — Loaded Idle

**Definition**: M9 power with the model **resident** and no request in flight, measured
after the warmup and before the first timed run: 3 s settle, then 5 samples × 2 s, median.

**Invalid (→ absent, the raw M10 stays)** when the sample CV exceeds 10 %, the 1-minute CPU
load exceeds `cores / 2`, the machine is throttled, or a required rail is missing.

`energy_per_token_active_j = (soc_joules − idle_soc_watts × interval_s) / (completion_tokens − 1)`
is published next to M10 when the subtraction stays positive. It answers "what did *this
generation* add on top of keeping the model loaded"; M10 answers "what did the plug pay".

### M12. `energy.rails` / `energy.base` — Provenance

Every energy figure travels with the rails it was built from. Adding or removing a rail is
a **new base** (e.g. `soc7` = `soc5` + `AMCC` + `FAB`), never a silent redefinition. The
leaderboard exposes the distinct bases behind a group (`energy_bases`) and the number of
contributing sessions (`energy_samples`).

### M13. `wall_calibration` — Wall-meter Calibration (optional)

An affine model `wall = a + b · soc_watts` fitted once per machine against a wall meter
(`asiai calibrate wall`), stored locally and declared with the submission (`a`, `b`, `R²`,
`n`, meter, file hash). It **never** enters M9–M11: the leaderboard publishes SoC figures,
the calibration is a declared, contestable factor a reader may apply. Without it, no claim
in € or in battery % is made.

## Implementation Map

| Metric | `base.py` | `ollama.py` | `openai_compat.py` | `runner.py` | `reporter.py` |
|--------|-----------|-------------|--------------------|-----------  |----------------|
| M1 tok/s | field | server API | client (excl. TTFT) | passthrough | avg |
| M2 ttft_ms | field | server API | client streaming | passthrough | avg |
| M3 total_duration_ms | field | server API | client wall-clock | passthrough | avg |
| M4 tokens_generated | field | server API | server or `len//4` | passthrough | avg |
| M5 generation_duration_ms | field | server API | computed | stored in dict | — |
| M6 power_watts (GPU) | — | — | — | per-engine probe | passthrough |
| M7 tok/s/W (GPU) | — | — | — | computed | passthrough |
| M8 std_dev | — | — | — | — | pooled intra-prompt |
| M9 soc_watts | — | — | — | per-run slice (`_annotate_run_energy`) | gated block |
| M10 energy_per_token_j | — | — | — | per run, n−1, usage tokens only | median of gated runs |
| M11 idle_soc_watts | — | — | — | `measure_loaded_idle` before `probe.start()` | passthrough |
| M12 rails / base | `ioreport.py` `rails_present` | — | — | per run | `energy.base`, `energy.rails` |

## Benchmark Protocol

1. **Warmup**: 1 non-timed generation per engine (`"Hello"`, max_tokens=32) to prime caches
   **and** the decode kernels — with `max_tokens=1` the first measured run paid the decode JIT.
   The power probe starts after the warmup, so warmup energy is excluded from M6/M9.
2. **Measured runs**: Default 3 runs per prompt per engine (configurable via `--runs`).
3. **Sampling**: `temperature=0` (greedy) on all engines for deterministic output.
4. **Reporting**: Median tok/s as primary metric (SPEC standard), mean +/- stddev as secondary.
5. **Throttling**: Warning emitted if `thermal_speed_limit < 100%` during any run.
6. **Metadata**: engine_version, model_format, model_quantization, hw_chip, os_version
   stored per result for reproducibility.

See [benchmark-best-practices.md](benchmark-best-practices.md) for full methodology audit.
