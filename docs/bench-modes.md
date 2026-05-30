# Benchmark modes

`asiai bench` has three modes, each answering a different question, all built on
one shared instrumentation brick (`asiai.benchmark.quality_gates`).

| Mode | Flag | Question it answers |
|------|------|---------------------|
| Standard | *(default)* | How fast / efficient is each engine on a fixed prompt set? (leaderboard) |
| Agentic | `--agentic-mode` | Does the engine reuse a cached system prefix across turns? (multi-turn agents) |
| Burst | `--burst-mode` | How does the engine behave under N concurrent calls? (tool-call fan-out) |

## What each mode *should* capture

Not "what is technically supported" — what is genuinely useful for that mode
versus noise. ✅ capture · ⚠️ capture in a mode-specific shape · ❌ noise / not
applicable.

| Data / metric | Standard | Agentic | Burst |
|---|---|---|---|
| decode tok/s | ✅ per prompt | ✅ per phase | ⚠️ aggregate only (not per-call) |
| TTFT | ✅ | ✅ cold / warm / prefix-hit | ✅ p50/p95/p99 |
| Latency p50/p95/p99/max | ❌ sequential | ❌ sequential | ✅ **the concurrency signal** |
| Aggregate throughput (calls/s, tok/s) | ❌ | ❌ | ✅ **the point of the mode** |
| cached_tokens + prefix-cache verdict | ❌ | ✅ **the point of the mode** | ❌ |
| Multi-run variance | ✅ `--runs` | ❌ 1 run/phase (fixed protocol) | ✅ `--burst-runs` |
| **GPU power (watts)** | ✅ per-engine window | ✅ **per-run window** | ✅ **aggregate** over the concurrent window |
| powermetrics cross-validation (sudo) | ✅ leaderboard provenance | ❌ noise (sudo + smears over 2–8 s) | ❌ noise |
| Efficiency tok/s/W | ✅ decode/W | ✅ decode/W per run | ✅ aggregate throughput/W |
| thermal_speed_limit | ✅ per run | ✅ summary over 8 phases | ✅ one sample/window |
| thermal **drift** (tok/s slope) | ✅ repeats N identical runs ⇒ slope is meaningful | ❌ phases differ | ❌ no repeated runs |
| early-stop / token-ratio | ✅ | ✅ **catches spec-decode/MTP EOS bugs** | ❌ noise (short answer = correct) |
| duplicate processes | ✅ | ✅ | ✅ |
| memory pressure (swap/swapouts) | ⚠️ pre-check only *(gap, see below)* | ✅ continuous watcher | ✅ continuous watcher (KV blowup under N slots) |

## Three design positions

1. **`gpu_watts` means three different things by mode.** Per-engine (standard
   compares engines), per-run windowed (agentic compares cold vs warm — a
   session average would erase the very signal), aggregate (burst measures the
   energy cost of serving N parallel requests). Hence `read()` vs
   `read_aggregate()` on the probe.
2. **powermetrics is only useful for standard.** It is the leaderboard producer,
   where the IOReport↔powermetrics provenance is worth publishing. Elsewhere it
   is sudo friction plus a 500 ms sampler that smears across short windows.
   Hence `cross_validate` is opt-in.
3. **drift and early-stop are noise outside their mode.** Drift only makes sense
   where identical runs repeat (standard); early-stop must not fire on the
   short-but-correct answers of burst.

## Shared instrumentation brick

`asiai.benchmark.quality_gates` is the single source of truth, consumed by all
three modes:

- `PowerThermalProbe` — IOReport (no sudo) window sampler.
  - `read()` → `{gpu_watts, thermal_speed_limit}` (per-window; agentic, burst).
  - `read_aggregate()` → 5-field provenance dict with `power_source`; only when
    constructed `cross_validate=True` (standard runner, opt-in powermetrics).
- `MemoryWatcher` — background swap/swapout watcher (context manager).
- `check_duplicate_processes(engine)` — canonical engine→process pattern map.
- `detect_early_stop(runs)` / `summarize_thermal(runs)`.

`_check_thermal_drift` stays runner-local on purpose: a tok/s slope is only
interpretable across repeated identical runs, which only standard mode produces.

## Known gap

Standard mode still uses a one-shot memory pre-check (refuse to start under
critical pressure) rather than the continuous `MemoryWatcher` that agentic and
burst wrap around their loops. Wiring `MemoryWatcher` into the standard runner
loop is the remaining step toward full parity; the brick already exists.
