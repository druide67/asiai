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
| Multi-run variance | ✅ `--runs` | ✅ `--runs` repeats the protocol (`phase_stats`: median + CV) | ✅ `--burst-runs` |
| **SoC power (watts)** | ✅ per-engine window | ✅ **decode-scoped per-run window** | ✅ **aggregate** over the concurrent window |
| powermetrics cross-validation (sudo) | ✅ leaderboard provenance | ❌ noise (sudo + smears over 2–8 s) | ❌ noise |
| Efficiency tok/s per SoC-watt | ✅ decode | ✅ decode per run | ✅ aggregate throughput |
| **Output validity** (deterministic) | ✅ degenerate gate | ✅ degenerate gate | ✅ arithmetic exact-match |
| thermal_speed_limit | ✅ per run | ✅ summary over 8 phases | ✅ one sample/window |
| thermal **drift** (tok/s slope) | ✅ repeats N identical runs ⇒ slope is meaningful | ❌ phases differ | ❌ no repeated runs |
| early-stop / token-ratio | ✅ | ✅ **catches spec-decode/MTP EOS bugs** | ❌ noise (short answer = correct) |
| duplicate processes | ✅ | ✅ | ✅ |
| memory pressure (swap/swapouts) | ⚠️ pre-check only *(gap, see below)* | ✅ continuous watcher | ✅ continuous watcher (KV blowup under N slots) |

## Three design positions

1. **`soc_watts` means three different things by mode.** Per-engine (standard
   compares engines), decode-scoped per-run window (agentic compares cold vs warm
   — a session average would erase the very signal), aggregate (burst measures
   the energy cost of serving N parallel requests). Hence `read()` vs
   `read_aggregate()` on the probe. `gpu_watts` is kept beside it as a
   diagnostic, but the headline is the full package rail.
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
  - `read()` → `{gpu_watts, soc_watts, energy_joules, thermal_speed_limit, …}`
    (per-window; agentic, burst). `read_power()` is the lighter power-only read
    used to split a window into prefill vs decode at first-token.
  - `read_aggregate()` → provenance dict with `power_source` + `soc_watts` +
    `energy_joules`; powermetrics arm only when `cross_validate=True` (standard
    runner, opt-in).
- `MemoryWatcher` — background swap/swapout watcher (context manager).
- `check_duplicate_processes(engine)` — canonical engine→process pattern map.
- `detect_early_stop(runs)` / `summarize_thermal(runs)`.
- `output_gates.py` — deterministic output validity (degenerate / arithmetic).

`_check_thermal_drift` stays runner-local on purpose: a tok/s slope is only
interpretable across repeated identical runs, which only standard mode produces.

## Metrics generation (1.11.0)

The 1.11.0 audit overhaul changed several formulas; the metrics generation is
tracked by `metrics_version = 3` (standard/leaderboard DB) and
`SCHEMA_VERSION = agentic-v3` (agentic JSON). v3 points must never be aggregated
with older v2/v1 points — the definitions differ:

- **Power headline is SoC, not GPU.** `soc_watts = gpu + cpu + ane + dram + dcs`
  (the DRAM-controller rail). On unified memory a decode is memory-bound, so
  GPU-only badly undercounts (measured idle on M5: GPU 0.07 W vs SoC 21.8 W).
  `gpu_watts` is kept as a diagnostic; the efficiency headline is
  `tok_s_per_soc_watt` (≈ tokens/Joule) with `energy_per_token_j`.
- **Power is decode-scoped** in agentic/burst: the window is rebaselined at
  first-token so watts/energy pair with `decode_tok_s`; prefill is captured
  separately as `prefill_watts`.
- **Token counts are server-exact** (`stream_options.include_usage`,
  `tokens_source='usage'`); the old chars//4 estimate is gone. One unified
  client-side decode formula `(n-1)/(t_last - t_first)` for every engine.
- **Thermal** comes from the notifyd `com.apple.system.thermalpressurelevel`
  channel (the Intel sysctl OID is dead on Apple Silicon).
- **Variance**: `--runs N` repeats the agentic protocol; `phase_stats` reports
  per-phase median + CV. Confidence intervals use the Student-t quantile, not z=2.
- **Output validity**: deterministic gates (`output_gates.py`) flag degenerate
  output; an engine below 80% valid is refused a ranking.
- **Prefix-cache reuse** publishes a raw cross-family signal (`reuse_fraction`,
  `cache_source`, `reuse_corroborated_by_ttft`); the categorical yes/no verdict
  is engine-family-specific and must not be compared across families.

The standard runner now also wraps the continuous `MemoryWatcher` around its
loop (parity with agentic/burst), so swap/swapout growth mid-run is caught, not
just a one-shot pre-check.

## Cross-family campaign protocol

When comparing engines from different families on the *same* model, the engine
must be the only variable that moves. These steps are mandatory, not optional:

1. **Shared GGUF page cache.** llama.cpp, Ollama and LM Studio mmap the *same*
   weights file. The first engine pays the cold disk read; the next finds it
   already warm in the page cache, so its "cold" run is fake. Between GGUF
   engines either `sudo purge` (drop the page cache) or fix the engine order and
   report it — never let an unpurged later engine claim a fast cold load. (MLX
   engines load their own format, so this is GGUF-only.)
2. **Cooldown + clean table between engines.** Unload the previous model, wait
   for memory pressure to return to nominal, and confirm no other inference
   engine is resident (a second engine holding a model competes for GPU and
   memory bandwidth and corrupts both). Run strictly one engine at a time.
3. **Tokenizer trap.** tok/s is only comparable at *comparable token counts*.
   Use `usage.completion_tokens` (server-exact) as ground truth, and never
   compare tok/s across engines whose tokenizers differ materially without
   saying so. With an identical model (same GGUF / same MLX repo) the tokenizer
   is identical and tok/s is directly comparable.
4. **Chat-template concordance.** GGUF and MLX builds can ship different chat
   templates. Assert `prompt_tokens` agrees across engines for the same prompt —
   a divergence means a template mismatch is changing the actual input, which
   invalidates the comparison before it starts.
5. **enable_thinking off, uniformly.** Pass
   `--extra-body '{"chat_template_kwargs":{"enable_thinking":false}}'` to every
   engine so Qwen3 reasoning tokens don't pollute tok/s/TTFT on some engines and
   not others (Ollama uses `{"think": false}`).
