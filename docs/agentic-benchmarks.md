---
description: Agentic-mode benchmark results on Apple Silicon — Qwen3.6 and Qwopus3.6 (27B dense vs 35B-A3B MoE), with and without MTP speculative decoding, across llama.cpp and the MLX engine family. Decode, TTFT, energy, RAM, validity. A living results page.
---

# Agentic Benchmark Results

This page reports real `asiai bench --agentic-mode` results on Apple Silicon. The
agentic protocol runs an 8-phase, prefix-cache-aware conversation (`--runs 5` for
variance), which exercises the way an agent actually uses a model — multi-turn,
long system prefix, 50K-token long-context phase — rather than a single one-shot
generation.

**Why agentic mode — who is this for?** Agent frameworks don't drive a model like a
chatbot: they reuse a large system prefix across many turns, emit tool calls, and
carry long context. A one-shot throughput number misses all of that — and the
ranking can even flip (an engine with great raw decode but a multi-second TTFT or a
broken prefix cache is unusable for an agent). Agentic mode measures the model the
way it is actually driven by **agent orchestrators and coding assistants** — e.g.
[Hermes Agent](https://github.com/nousresearch/hermes-agent),
[OpenClaw](https://github.com/openclaw/openclaw),
[opencode](https://github.com/sst/opencode), Aider, Cline, or Continue — so the
result reflects real agent workloads, not a benchmark artefact.

> **Living document.** These numbers are refreshed as engine versions, model
> revisions and instrumentation improve (e.g. peak-RAM capture). Each row carries
> the exact engine version and model file so a result is always reproducible.

**Campaign 2026-06-03.** Models: Qwen3.6 and the Qwopus3.6 finetune, in two
architectures — **27B dense** and **35B-A3B MoE** (Mixture-of-Experts, ~3B active
parameters per token). Engines: llama.cpp (b9430) and the MLX family (mlx-lm,
mlx_vlm, omlx, rapid-mlx, vllm-mlx). MTP = the model's built-in Multi-Token
Prediction head used for speculative decoding (`--spec-type draft-mtp`).
Hardware: **MacBook Pro M5 Max (128 GB)** and **Mac mini M4 Pro (64 GB)**, both in
High Power Mode.

## How to read the table

Verdict-first. Rows are grouped by a deterministic gate result, not just sorted:

- **★** best validated throughput in the block · **✓** viable · **⚠** reserve
  (passes hard gates but mediocre latency) · **✗** eliminated (failed a gate).
- Gates: `valid ≥ 80%` · `TTFT ≤ 1500 ms` (hard fail > 3000) · `prefix-cache reuse > 0`.
- **dec** = sustained warm decode (tok/s) · **50K** = decode at 50K context ·
  **TTFT** = time-to-first-token (ms) · **t/s/W** = tokens per second per SoC watt
  (efficiency, higher is better) · **RAMpk** = peak engine RSS (GB, the figure that
  governs memory fit) · `—` = not measured (never 0).
- ★ ranks by *throughput only*. Picking a model for real work also weighs output
  quality (see the [dev/code evaluation](dev-quality-benchmarks.md)), which
  throughput does not capture.

> M4 Pro and M5 Max are **not** comparable in absolute terms here — different quant
> (Q5_K_XL vs Q4_K_S). Compare within a machine block.

## MacBook Pro M5 Max 128 GB · Q4

| | model · engine · MTP | dec t/s | peak | 50K | TTFT ms | reuse | t/s/W | RAMpk GB | valid% |
|:--|---|--:|--:|--:|--:|--:|--:|--:|--:|
| **★ Tier 1 — winner + fast** |||||||||| |
| ★ | Qwopus-35B · llamacpp b9430 ▲MTP | 123.3 | 127.5 | 83.8 | 67 | 0.8 | 1.590 | — | 100 |
| ✓ | Qwen-35B · llamacpp b9430 ▲MTP | 118.3 | 123.5 | 82.9 | 62 | 0.8 | 1.513 | — | 100 |
| ✓ | Qwopus-35B · llamacpp b9430 | 105.7 | 108.3 | 76.1 | 63 | 0.8 | 1.507 | — | 100 |
| ✓ | Qwen-35B · llamacpp b9430 | 85.5 | 90.8 | 66.7 | 59 | 0.8 | 1.403 | — | 100 |
| **✓ Tier 2 — viable (slower)** |||||||||| |
| ✓ | Qwen-27B · llamacpp b9430 ▲MTP | 28.0 | 29.5 | 22.9 | 118 | 0.8 | 0.378 | 32.2 | 100 |
| ✓ | Qwopus-27B · llamacpp b9430 ▲MTP | 26.7 | 29.8 | 22.0 | 118 | 0.8 | 0.367 | 31.5 | 100 |
| ✓ | Qwopus-27B · llamacpp b9430 | 25.9 | 27.1 | 20.8 | 110 | 0.8 | 0.342 | 28.4 | 100 |
| ✓ | Qwen-27B · llamacpp b9430 | 23.8 | 24.0 | 19.2 | 111 | 0.8 | 0.340 | 28.9 | 100 |
| **⚠ Tier 3 — reserve (poor latency)** |||||||||| |
| ⚠ | Qwopus-27B · mlx-lm 0.31.3 | 29.2 | 29.3 | 24.3 | 600 | 1.0 | 0.461 | 26.4 | 100 |
| ⚠ | Qwen-27B · rapid-mlx 0.6.71 | 20.6 | 20.7 | 17.9 | 798 | — | 0.357 | — | 85 |
| ⚠ | Qwen-27B · omlx 0.4.0 | 20.0 | 20.2 | 17.5 | 2150 | 0.82 | 0.346 | 26.7 | 100 |
| **✗ Tier 4 — eliminated** |||||||||| |
| ✗ | ~~Qwen-27B · mlx_vlm 0.6.0 ▲MTP~~ | ~~41.0~~ | — | — | ~~10879~~ | 0.0 | — | — | 75 |
| ✗ | ~~Qwen-27B · mlx_vlm 0.6.0~~ | ~~31.9~~ | — | 26.0 | ~~9578~~ | 0.0 | — | — | 100 |
| ✗ | ~~Qwen-27B · vllm-mlx 0.3.0~~ | ~~20.5~~ | — | 18.1 | ~~9578~~ | — | — | 24.3 | 100 |

Eliminations: mlx_vlm+MTP fails validity (75%) and breaks long-context; both
mlx_vlm runs and vllm-mlx have ~9.6 s TTFT (unusable per agent turn).

## Mac mini M4 Pro 64 GB · Q5

| | model · engine · MTP | dec t/s | peak | 50K | TTFT ms | reuse | t/s/W | RAMpk GB | valid% |
|:--|---|--:|--:|--:|--:|--:|--:|--:|--:|
| **★ Tier 1** |||||||||| |
| ★ | Qwen-35B · llamacpp b9430 ▲MTP | 44.6 | 50.7 | 32.6 | 143 | 0.8 | 1.557 | 33.0 | 100 |
| ✓ | Qwen-35B · llamacpp b9430 | 36.3 | 45.6 | 29.6 | 133 | 0.8 | 1.553 | 30.8 | 100 |
| **✓ Tier 2** |||||||||| |
| ✓ | Qwen-27B · llamacpp b9430 | 10.4 | 10.4 | 7.2 | 397 | 0.8 | 0.279 | 31.9 | 100 |
| ✓ | Qwen-27B · llamacpp b9430 ▲MTP | 9.7 | 9.8 | 7.5 | 409 | 0.8 | 0.272 | 35.4 | 100 |

## Key findings

- **The 35B-A3B MoE beats the 27B dense on every throughput axis** on both
  machines — it activates only ~3B parameters per token, so it decodes ~4× faster
  than the dense 27B and is ~3.5× more energy-efficient (1.5 vs ~0.4 tok/s/W).
  Throughput is not quality, however — see the caveat below.
- **MTP gain depends on architecture × hardware.** Measured decode uplift:
  MoE +38% (M5) / +23% (M4); dense +16% (M5) but **−7% (M4)** — on the slower M4
  GPU the dense draft overhead is not amortised. So MTP is a per-model, per-machine
  measurement, not a universal win.
- **The MLX server family is throughput-only here**: mlx-lm has the best MLX decode
  but a 600 ms TTFT floor; mlx_vlm, vllm-mlx and omlx are knocked out by TTFT
  (2–11 s) and/or broken prefix-cache. llama.cpp dominates first-token latency
  (~60–120 ms).
- **Peak vs steady RAM.** mlx-lm's RSS sits at ~14.5 GB steady but **peaks at
  26.4 GB** (lazy KV allocation + compact MLX-4bit weights); llama.cpp pre-allocates
  the full context KV up front (~29 GB flat). At peak they are comparable — use
  **RAMpk** for memory-fit decisions, not the steady value.

## Methodology & caveats

- `asiai bench --agentic-mode --runs 5`, thinking disabled
  (`chat_template_kwargs.enable_thinking=false`), server context ≥ 65536.
- One engine resident at a time (SOLO); page cache purged between GGUF runs that
  share a file.
- **Quant differs by machine** (M5 Q4_K_S/Q4_K_XL, M4 Q5_K_XL) → absolute numbers
  are not comparable across machines, only within a block.
- **High Power Mode** is required on the M5 laptop (otherwise sustained GPU is
  throttled ~40%); the M4 mini desktop is roughly neutral to it.
- **Known instrumentation gaps** (being fixed): peak RAM is missing (`—`) on some
  manually-launched llama.cpp servers; engine version is not yet stamped per run
  (shown here from a version map); prefix-cache `reuse` is a coarse fraction
  pending a true hit-rate.

See also: [Benchmark methodology](methodology.md) · [Metrics spec](metrics-spec.md)
· [Community leaderboard](leaderboard.md).
