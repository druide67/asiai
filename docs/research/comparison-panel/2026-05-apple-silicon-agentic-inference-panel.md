# Apple Silicon Agentic Inference Panel

> Comparative benchmark panel across inference engines (llama.cpp, mlx-lm,
> LM Studio, Rapid-MLX, vLLM-MLX, oMLX, vMLX, Ollama) running Qwen 3.6
> family models on Apple Silicon M-series, measured with
> `asiai bench --agentic-mode` and `asiai bench --burst-mode`.
>
> **Workload target**: agent-orchestrator class — ~60-80 tool calls per turn,
> identical system prompt of ~7 KB, user message changing per call. This is
> the worst case for naïve prefix caching: a true cache-reuse cross-USER is
> required, not just cache-on-the-same-prompt.
>
> **Reading the throughput figures**: Section 1 decode rates use the Qwen3
> default chat template (thinking ON), so they include reasoning tokens —
> effective agent-throughput on a thinking model is lower. Thinking is a
> per-task trade-off (caveat 1), not a global on/off.
>
> Published 2026-06 · contributions and corrections welcome via
> [github.com/druide67/asiai](https://github.com/druide67/asiai/issues).

## ⚠️ Known caveats before reading further

1. **Thinking mode is a per-task trade-off.** With the Qwen3 default template
   (thinking ON), Qwen 3.6 / Qwopus emit ~6-7× more tokens, so the Section 1
   decode figures **include reasoning tokens** and effective agent-throughput is
   lower. Thinking ON is **required** for written multi-section deliverables (a
   thinking-OFF model skips the deliverable) but **costs** atomic tool-call
   cleanliness (asiai measures ~100% clean tool calls with thinking OFF vs
   ~77.8% with thinking ON + `preserve_thinking` ON, deterministic across runs;
   `enable_thinking=on` + `preserve_thinking=off` is unusable — a deterministic
   HTTP 500 once reasoning accumulates in the context). Set thinking **per
   task-dimension**, not as one global flag.
2. **Rapid-MLX and vLLM-MLX share an engine.** Rapid-MLX is a community fork of
   `waybarrios/vllm-mlx`; they appear as separate rows below because they have
   diverged in version and features, but the prefix-cache snapshot mechanism is
   the same lineage.
3. **MTP: Qwen 3.6 has a real head; the backend matters.** Qwen 3.6's official
   `config.json` carries `mtp_num_hidden_layers=1` (Qwen naming — **not** the
   DeepSeek `num_nextn_predict_layers` key, so a `nextn`-only check wrongly
   concludes "no head"). Some re-quantized GGUF/MLX artifacts drop the MTP
   tensors while keeping the config flag — verify the tensors in the weight
   index, not just the flag. llama.cpp native MTP (`--spec-type draft-mtp`)
   **requires a `-MTP-GGUF`** that embeds the head; a plain GGUF cannot draft.
   Released mlx-lm does not run the head as native speculative decoding (PR
   [ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990) adds
   it). LM Studio routes GGUF through its llama.cpp-derived backend and MLX
   through `mlx-engine`.
4. **Single-pass measurements, no variance reporting** — Section 1 / 2
   chiffres are single observations. Variance reporting (median + min + max
   across N passes) is supported as of `--burst-runs N` but the rebench
   is pending.

| Section | Topic | Status |
|---------|-------|--------|
| 1 | Single-call performance | 🟡 8 cells, thinking-mode ON (decode includes reasoning tokens) |
| 2 | Concurrent burst (30/60/80 parallel calls) | 🟡 smoke cell + 2 partial concurrent points; no normalized 30/60/80 panel |
| 3 | Caches & optimizations | ✅ 8 engines covered |
| 4 | Memory & resources | ✅ idle + under-load swap (+0) + footprint measured |
| 5 | Model quality (public leaderboards) | 🟡 vendor/self-reported figures (llm-stats) |
| — | **asiai direct measurements** | ✅ dev-quality, thinking ablation, MTP, instruction-following |
| 6 | Operational (license, endpoints, maintenance) | ✅ 8 engines covered |
| 7 | Quality benchmark weighting | 🟡 default weighting, override via `--weights` planned |
| 8 | Custom long-horizon eval (proposal) | 🟡 scoped, not yet built |

---

## Section 1 — Single-call performance

> 🟠 **May 2026 snapshot — indicative, not the reference numbers.** This table was
> captured in May (thinking-mode ON, single-pass) and its source fixtures have not
> been re-verified. For **current, reproducible decode throughput**, use the *asiai
> direct measurements* section below (June, llama.cpp b9430, deterministic). What
> this table is reliable for is the **relative TTFT / prefix-cache** story
> (cross-USER reuse), not absolute t/s. Note in particular that the 123.9 t/s in
> row 5 (LM Studio GGUF+MTP) sits right next to the June **llama.cpp Qwopus+MTP
> 123.3 t/s** — LM Studio's GGUF path is a llama.cpp-derived backend, so the two
> measure essentially the same engine.

> ⚠️ **Read with caveat 1 above**: every figure in this table includes the
> Qwen3 default thinking-mode tokens (reasoning_content). Effective
> agent-throughput requires re-running with
> `chat_template_kwargs={"enable_thinking": false}`. The column is labeled
> "decode (t/s)" not "effective throughput".
>
> The "lower-bound estimate" column is `60 × (TTFT + max_tokens/decode)`,
> assuming sequential dispatch (which Rapid-MLX single-slot enforces). It is
> **not** a production tick prediction — see [Section 7](#section-7) for the
> methodological caveat.
>
> 📌 **Versions tested (May 2026)**: Rapid-MLX 0.6.66, LM Studio 0.4.14,
> llama.cpp b9270. Engine versions churn weekly on Apple Silicon — treat each
> figure as dated, not current. (The asiai-measurements section uses llama.cpp
> b9430.)

| # | Engine | Model | Format | Warm decode (t/s) ¹ | TTFT warm (ms) | TTFT prefix-test median (ms) | TTFT cold (ms) | Lower-bound estimate (60 calls × single-call, optimistic) | Source fixture |
|---|--------|-------|--------|--------------------:|---------------:|----------------------------:|---------------:|----------------------------------------------------------:|----------------|
| 1 | Rapid-MLX 0.6.66 (fork of vllm-mlx) | Qwopus 3.6-35B-A3B-v1 (zaydiscold MLX-4bit) | MLX-4bit | **109.1** ¹ | 139 | **131** | 2074 | ~3.6 min | `cell-rapidmlx-qwopus35b.json` |
| 2 | Rapid-MLX 0.6.66 | Qwen 3.6-35B-A3B-UD (MLX-4bit) | MLX-4bit | 106.9 ¹ | 321 | 319 | 2095 | ~4 min | `cell-rapidmlx-35b-a3b.json` |
| 3 | Rapid-MLX 0.6.66 | Qwopus 3.6-27B-v2 (Jackrong MLX-4bit) | MLX-4bit | 31.8 ¹ | 323 | 323 | 8647 | ~13 min | `cell-rapidmlx-qwopus.json` |
| 4 | Rapid-MLX 0.6.66 | Qwen 3.6-27B-UD (MLX-4bit) | MLX-4bit | 20.5 ¹ | 527 | 527 | 8954 | ~23 min | `cell-rapidmlx-full-27bud.json` |
| 5 | LM Studio 0.4.14 (GGUF backend) ² | Qwen 3.6-35B-A3B-MTP (Unsloth GGUF) | GGUF Q4 + MTP | **123.9** ¹ ² | 309 | 5965 | 6063 | ~3.5 min warm / ~9.2 min prefix-changing | `cell-lmstudio-mtp-qwen35b.json` |
| 6 | LM Studio 0.4.14 (GGUF backend) ² | Qwopus 3.6-35B-A3B-v1 (Jackrong GGUF) | GGUF Q4_K_S | 105.6 ¹ | 292 | 5785 | 5624 | ~3.5 min warm / ~9.6 min prefix-changing | `cell-lmstudio-qwopus35b.json` |
| 7 | llama.cpp b9270 | Qwen 3.6-35B-A3B (UD Q5_K_XL) | GGUF Q5_K_XL | 80.9 ¹ | 3000 | 3000 | n/a | ~8 min | (baseline reference) |
| 8 | llama.cpp b9270 | Qwopus 3.6-27B-v2 (Jackrong GGUF Q4) | GGUF Q4 | 25.3 ¹ | 13000 | 13000 | n/a | ~30 min | (baseline reference) |

¹ **Thinking-mode caveat**: figures captured with default chat template
(thinking ON). Real-world effective throughput on tool-call workloads is
typically 4-12 t/s on Qwopus/Qwen3.6 finetunes when reasoning tokens
inflate output 6-7×. To reproduce these decode figures, pass
`chat_template_kwargs={"enable_thinking": false}` in the request payload.

² **LM Studio backend**: rows 5-6 used a GGUF file, which routes through
LM Studio's llama.cpp-derived backend (NOT the MLX runtime `mlx-engine`).
The MTP claim in row 5 reflects this backend's implementation, not
mlx-engine speculative decoding. Released mlx-lm does not run the MTP head
as native speculative decoding (its `sanitize()` historically dropped MTP
weights during conversion; native support is in PR
[ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990)),
so a hypothetical MLX-format MTP model would not benefit on the released
mlx-engine either.

### Key observations

- On the realistic agent pattern (identical system + changing user prompts),
  **Rapid-MLX + Qwopus 35B-A3B-v1** delivers 131 ms median TTFT prefix-test
  vs 5965 ms for LM Studio GGUF backend (**~44× faster**). The advantage
  comes from the vllm-mlx prefix-cache snapshot mechanism (see Section 3
  for the source-code disambiguation).
- On pure decode throughput (warm path), the **LM Studio GGUF backend with
  Unsloth MTP** records 123.9 t/s vs Rapid-MLX 109.1 t/s (+13.5%). This delta
  reflects the LM Studio llama.cpp-derived backend's speculative decoding on a
  GGUF carrying the MTP head, not an Apple-MLX gain (released mlx-engine does
  not run the head — see footnote 2). On the native llama.cpp path, MTP is
  net-positive on the MoE 35B-A3B — see Section 3.
- All `Qwen 3.6 family` configurations (hybrid DeltaNet + full-attention) fail
  cross-USER prefix cache **except Rapid-MLX**, which keeps an RNN-state
  snapshot. On llama.cpp / LM Studio GGUF `llama_memory_can_shift=false`; on
  mlx-lm / oMLX the recurrent/SSM state can't be split at an arbitrary token
  boundary. The upstream llama.cpp fix for this architecture is not merged
  ([#23121](https://github.com/ggml-org/llama.cpp/pull/23121) closed;
  `preserve_thinking` does not address it,
  [#22615](https://github.com/ggml-org/llama.cpp/issues/22615)).
- **Single-slot serialization confirmed**: smoke burst test (Section 2)
  shows Rapid-MLX 0.6.66 serializes concurrent calls FIFO (p50 ≈ p95 ≈ max
  on burst=5). For 60-80 calls/turn, total wall-time scales linearly with
  burst size on this engine. A multi-slot engine (e.g. llama.cpp
  `--parallel N`) would behave differently, but `--parallel N` on Qwen3.6
  hybrid disables prefix cache per slot (architectural limitation).

---

## Section 2 — Concurrent burst (30/60/80 parallel calls)

> Pattern: 30 to 80 concurrent `POST /v1/chat/completions` calls fired within a
> ~200 ms window. Simulates an agent loop dispatching multiple MCP/tool calls in
> parallel. Measured natively via `asiai bench --burst-mode`.
>
> 🟡 **Status**: 1 smoke cell measured (Rapid-MLX burst-5). Full panel pending.

### Smoke cell (Rapid-MLX 0.6.66 + Qwopus 35B-A3B-v1, burst=5)

| burst N | wall-time (s) | p50 latency (ms) | p95 latency (ms) | max latency (ms) | agg throughput (t/s) |
|--------:|--------------:|-----------------:|-----------------:|-----------------:|---------------------:|
| 5 | 2.8 | 2615 | 2792 | 2812 | 88.8 |

**Smoke finding**: `p50 ≈ p95 ≈ max` indicates the 5 calls were **serialized
server-side** (single-slot engine). Rapid-MLX 0.6.66 does **not** appear to support
concurrent request scheduling — calls queue FIFO internally. To validate at 60/80
calls scale.

### Full concurrent panel — not yet measured

A normalized 30/60/80-concurrent panel has not been run (the measurements here are
sequential agentic-mode, not concurrent burst). The two partial concurrent data
points that exist elsewhere:

- **TurboQuant** (K=`q8_0` V=`turbo2`, Qwen3-4B, M4 Pro): **+9% aggregate at
  4-parallel** (68.5 → 74.7 t/s) even though single-stream is −8% — the KV
  compression buys back the parallel headroom.
- **oMLX** continuous batching (mlx-lm `BatchGenerator`): **×1.8 aggregate at
  burst-8** (12.8 → 22.9 t/s), but it **collapses at burst-30** (17.3 t/s) once a
  27B-dense saturates RAM into swap — 0 crashes.

A dedicated burst-mode panel across all engines is deferred.

---

## Section 3 — Caches & optimizations

| # | Couple | Cache reuse cross-USER | Snapshot persists cross-restart | MTP support | MTP accept rate | TurboQuant compat | KV cache native types | Native parallel slots |
|---|--------|---|---|---|---|---|---|---|
| 1 | Rapid-MLX + Qwopus 35B-A3B-v1 | ✅ YES (RNN-state snapshot, see ³ below) | ✅ persistent in `~/.cache/vllm-mlx/` | ❌ released MLX runtime doesn't run the MTP head as speculative decode (mlx-lm PR #990 pending) | n/a | ❌ MLX only | MLX native (no quant flag exposed) | ⚠️ single slot (smoke burst confirms FIFO serialization) |
| 2 | Rapid-MLX + Qwen 35B-A3B-UD | ✅ YES ³ | ✅ persistent | ❌ | n/a | ❌ | MLX native | ⚠️ single slot |
| 3 | LM Studio + Qwen 35B-A3B-MTP | ❌ NO (architectural hybrid limitation) | n/a | ✅ via mlx-engine v1.8.1 | **82.1 %** (on coding task) | ❌ | mlx-engine v1.8.1 (4bit MLX) | configurable via GUI |
| 4 | LM Studio + Qwopus 35B-A3B-v1 | ❌ NO | n/a | ❌ no heads | n/a | ❌ | mlx-engine v1.8.1 (Q4_K_S GGUF) | configurable via GUI |
| 5 | llama.cpp + Qwen 3.6-35B-A3B | ❌ NO (architectural hybrid limitation) | n/a | ✅ `--spec-type draft-mtp` on a `-MTP-GGUF` (a plain GGUF cannot draft). Net-positive on the MoE 35B-A3B — asiai measures **+38%** decode (base) / **+17%** (Qwopus) on M5 Max (see § asiai measurements) | benefit = intra-session decode delta (no acceptance rate logged) | ✅ turbo2/3/4 V cache | `fp16`, `q8_0`, `q5_0`, `turbo2/3/4` | ⚠️ `--parallel N` works mechanically but **disables prefix cache per slot on hybrid arch** (each slot owns its KV, the `--cache-reuse N` flag is already silently disabled here). Use with caution. |
| 6 | mlx-lm | ❌ NO (PRs #923, #188, #192 pending upstream) | n/a | ❌ broken on hybrid arch | n/a | ❌ | MLX native | ❌ (single slot) |
| 7 | oMLX | ❌ NO (tool calling lost post-cache-hit, issue #825) | partial | ❌ | n/a | ❌ | MLX native + tiered SSD cache | ❌ |
| 8 | vLLM-MLX (`waybarrios`, upstream of Rapid-MLX) | ⚠️ trie prefix-cache, no documented hybrid/DeltaNet support (Rapid-MLX rows 1-2 add the RNN-state snapshot on top) | n/a | ⚠️ MTP added in prerelease 0.4.0rc1 | n/a | ❌ | MLX + paged-attention | ✅ |

³ **Rapid-MLX prefix cache**: the cache stores hybrid-attention KV slabs +
RNN-state snapshots, keyed per `<repo>--<sys_prompt_hash>` and persisted under
`~/.cache/vllm-mlx/`. The observed ~131 ms TTFT prefix-test is an in-RAM KV slab
reattach plus the changed-user forward pass, not a from-disk reload.

**oMLX large-context cache.** oMLX's 2-tier paged SSD KV cache turns a 55K-token
prefill from ~115 s to ~**3.5 s** TTFT on a same-prompt cache-hit (×33; 55,296 /
55,837 tokens cached). On small prompts (~7.5K) there's no advantage (~2-5 s, =
mlx-lm) and decode is ~19 t/s (no raw-speed gain). This is same-prompt reuse, not
cross-USER (which oMLX doesn't do); cross-restart persistence is documented but
not yet A/B-tested.

**TurboQuant KV compression** (llama.cpp). K=`q8_0` V=`turbo2` cuts KV RAM ~**28%**
(22.9 → 16.4 GB on a 4B model, M4 Pro) with tool-call validity unchanged (10/10),
and gains **+9% aggregate at 4-parallel** despite −8% single-stream. The symmetric
K=`turbo3` V=`turbo3` reaches ~−56% RAM but degrades quality (early-stop,
repetition) — the asymmetric `q8_0`/`turbo2` is the usable config.

---

## Section 4 — Memory & resources (Apple Silicon M5 Max 128 GB)

| # | Couple | Working-set RAM (GB) | Disk footprint (GB) | Swap Δ idle | Swap Δ under load | SOLO required? | Cohabitation safe? |
|---|--------|---|---|---|---|---|---|
| 1 | Rapid-MLX + Qwopus 35B-A3B-v1 | ~22 | 19.9 (MLX-4bit) | +0 | **+0 MB** | ⚠️ SOLO (cohabit thrash to 0.4 t/s) | ❌ |
| 2 | Rapid-MLX + Qwen 35B-A3B-UD | ~24 | 20.0 (MLX-4bit) | +0 | **+0 MB** | ⚠️ SOLO | ❌ |
| 3 | LM Studio + Qwen 35B-A3B-MTP | 21.6 | 23.2 (Q4 + MTP heads) | +0 | **+0 MB** | not tested | not tested |
| 4 | LM Studio + Qwopus 35B-A3B-v1 | 18.5 | 19.9 (Q4_K_S) | +0 | **+0 MB** | not tested | not tested |
| 5 | llama.cpp + Qwen 3.6-35B-A3B (reference) | ~16 | ~16 (Q5_K_XL) | +0 | **+0 MB** | ❌ | ✅ with `--parallel 2/3` |

> **"Under load"** = the 8-phase agentic bench including a 50K-token prefill (the
> heaviest *sequential* memory stress measured), M5 Max 128 GB, SOLO: swap delta
> **0 MB / 0 swapouts for every engine** — model + KV fit in free/inactive memory
> with >100 GB headroom. This is sequential-load memory, **not** 60-concurrent
> memory (see Section 2). Working-set RAM is an estimate; measured RSS includes
> mmap'd GGUF / wired MLX pages, so the true incremental footprint is lower (the
> MTP head adds ~+3 GB).

### Observations

- **Rapid-MLX requires SOLO operation on the GPU**: cohabitation with another
  actively-decoding engine triggers a swap delta of 5.4 → 14.2 GB and a decode
  collapse to 0.4 t/s. Do not start a second engine on the same Apple Silicon
  GPU.
- **LM Studio MTP** disk footprint is +13 % vs Q4_K_S without MTP heads, due to
  the MTP weight blocks. Negligible cost relative to the +17 % decode gain.
- On M5 Max 128 GB unified memory: every 35B-A3B configuration tested leaves
  more than 100 GB headroom after load — RAM is not the limiting factor.
- On M4 Pro 64 GB: `Q5_K_XL` does **not** fit alongside auxiliary models (swap
  thrash observed in production). `Q4_K_S` does fit.

---

## Section 5 — Model quality

> Public-benchmark figures here are **vendor / self-reported** and aggregated by
> leaderboards (llm-stats), not independently verified. Cross-validate at
> [llm-stats](https://llm-stats.com) · [LiveBench](https://livebench.ai) ·
> [SWE-bench](https://swebench.com) before relying on them. asiai's own direct
> measurements on Apple Silicon are in the next section.
>
> Author-only claims (Jackrong/Qwopus, Unsloth self-eval) are flagged separately
> and kept out of the public-leaderboard columns.
>
> 🔴 **Critical finding**: the "Hessling agentic" benchmark cited on several
> community model cards is **not independently reproducible** — 16 prompts,
> single curator, no neutral leaderboard integration. All three advisors
> recommend treating it as a smoke test only.

### Open-weight Qwen 3.6 base models

> Public-leaderboard figures (llm-stats), self-reported. The 27B-dense outscores
> the 35B-A3B MoE on SWE-bench — consistent with asiai's own dev-quality finding
> below (the MoE base is the one that hits the tool-call empty-object bug). MTP
> heads are a decode-speed feature and do not change a model's quality scores.

| Model | Architecture | SWE-bench Verified | GPQA Diamond | MMLU-Pro | Terminal-Bench 2.0 | BFCL |
|-------|--------------|-------------------:|-------------:|---------:|-------------------:|------|
| Qwen 3.6-35B-A3B-Instruct | MoE 35B / 3B active | 73.4% | 86.0% | 85.2% | 24.6% | absent from board |
| Qwen 3.6-27B-Dense Instruct | Dense 27B hybrid | 77.2% | 87.8% | 86.2% | 59.3% (vendor) | absent from board |

> Terminal-Bench **2.0** is far harder than the older Terminal-Bench v1 (community
> cards quote ~51.5% for the 35B-A3B on v1); the 24.6% here is the 2.0 generation.

### Qwopus 3.6 family — author-reported only, **not independently verified**

The Qwopus 3.6 finetunes published by Jackrong on HuggingFace claim
substantial gains over the Qwen base. As of May 2026 these claims have
**not been independently reproduced** on neutral leaderboards. Treat as
experimental until BFCL / SWE-bench reruns by a third party are
available.

| Model (author claims) | MMLU-Pro | SWE-bench Verified | Hessling agentic (16 prompts) |
|-----------------------|---------:|-------------------:|------------------------------:|
| Qwopus 3.6-35B-A3B-v1 (Jackrong) | claimed 88+ | claimed 75+ | claimed 88.6 ⚠ non-reproducible |
| Qwopus 3.6-27B-v2 (Jackrong) | claimed 87.43 | claimed 75.25 | n/a |

⚠ The "Hessling agentic" benchmark cited on the Jackrong model cards
appears to be a 16-prompt curator-specific evaluation with no neutral
leaderboard integration. All three advisories queried (Grok-4, GPT-5,
Gemini Advanced) recommend treating it as smoke test only.

### Frontier anchors (mid-2026)

> All figures are **vendor / self-reported**, aggregated by llm-stats — none are
> independently verified there. **Terminal-Bench 2.0** is the exception (the
> tbench team re-runs submissions; rows are peak agent×model scores). GPQA are
> vendor "Diamond" figures and the set is near-saturated — treat as approximate.

| Model | SWE-bench Verified | GPQA Diamond | MMLU-Pro | Terminal-Bench 2.0 | Source |
|-------|-------------------:|-------------:|---------:|-------------------:|--------|
| Claude Opus 4.8 | 88.6% | 93.6% | n/a | — (no TB submission) | llm-stats / Anthropic |
| Claude Opus 4.7 | 87.6% | 94.2% | n/a | **90.2%** | llm-stats / tbench |
| Claude Sonnet 4.6 | 79.6% | 89.9% | n/a | 53.4% | llm-stats / tbench |
| GPT-5.5 | n/a\* (SWE-Pro 58.6%) | 93.6% | n/a | 84.7% | OpenAI / tbench |
| GPT-5 (base) | 74.9% | 85.7% | n/a | 49.6% | llm-stats / tbench |
| Gemini 3.1 Pro | 80.6% | ~94.4% | n/a | 80.2% | llm-stats / tbench |
| DeepSeek-V4-Pro-Max | 80.6% | 90.1% | 87.5% | n/a | vendor (DeepSeek) |
| Llama-3.3-70B-Instruct | n/a | n/a | 68.9% | n/a | Meta (baseline) |

\* GPT-5.5 has no public SWE-bench *Verified* score (OpenAI reports SWE-bench Pro
Public 58.6%); the "88.7% SWE-bench" figure circulating is not on any primary
source. Note: **Qwen 3.6 has no 235B-A22B** — the open family is the 27B-dense
and 35B-A3B (below); the 235B-A22B is the prior Qwen3 generation.

### Same-class open-weights baselines

| Model | MMLU-Pro | SWE-bench Verified | Notes |
|-------|---------:|-------------------:|-------|
| Llama-3.3-70B-Instruct | ~75-80 | ~40-50 | Older but well-characterized baseline |
| Mistral Codestral 25.05 / Devstral | high (coding-specialized) | medium-high | Strong editor-style completion fidelity, weaker on reasoning |
| GLM-4.6-Coder (Zhipu) | vendor claims very high | disputed | Significant skepticism around evaluation methodology (consensus) |

### Quality benchmarks deprecated for this decision

- **HumanEval / HumanEval+** — saturated in 2026, all frontier models above 90 %, no signal left.
- **GSM8K** — saturated, no signal for coding agents.
- **MMLU (original)** — superseded by MMLU-Pro.
- **Author-reported "Hessling agentic" 16-prompt** — non-reproducible, treat as smoke test only.

### Open quality questions (research gaps)

1. **Quality-per-GB-RAM benchmark**: no standard exists. Proposed proxy formula:
   `AgentScorePerGB = (0.5·SWE + 0.3·BFCL + 0.2·TerminalBench) / RAM_resident`.
2. **Long-horizon stability (60+ tool calls)**: closest existing benchmarks are
   τ-bench, PencilPuzzleBench (>1000 turns), MultiAgentBench, TRAIL. None of
   them specifically measure "schema correctness and strategic coherence across
   60-80 sequential tool calls" — that benchmark gap is acknowledged by all
   three advisors.
3. **Conversion-aware evaluation (MLX-4bit vs GGUF Q4_K_M vs Q5_K_XL)**: no
   standardized leaderboard. Community reports diverge — some claim MLX-4bit
   preserves tool-calling stability worse than GGUF Q5_K_M, others say the
   opposite. **Practical advice**: run your own production workload against
   each quant before committing.
4. **Qwopus 3.6 family quality validation**: needs third-party BFCL +
   SWE-bench reruns. Author claims should not drive production decisions.

---

## asiai direct measurements — Apple Silicon, mid-2026

> What the public leaderboards above don't show: measurements asiai ran directly
> on Apple Silicon (M5 Max 128 GB in High Power Mode, M4 Pro 64 GB), llama.cpp
> b9430, deterministic (temp 0), on the public Qwen 3.6 family and the
> Opus-distilled **Qwopus** finetune. Caveat: cross-session absolute throughput on
> the M5 laptop is ±15% (thermal/load); only the **intra-session ±MTP back-to-back
> deltas** are tight, and M5↔M4 absolutes aren't comparable (different quants).

### Dev-quality / tool-call (`asiai bench --code`)

- The **base Qwen 3.6-35B-A3B (MoE)** collapses `edit_file.edits` to an empty
  object on the deep-context turn — **3/3 runs, at both Q4_K_S and Q5_K_XL**, same
  chat template. Tool-call clean **87.5%**, edit-turns clean **66.7%**. It is the
  MoE base's tool-call generation behaviour, not the quant and not the template.
- The **dense 27B** (Q5_K_XL) and **Qwopus-35B-A3B** (Q4_K_S) both score **100%
  clean / 0 bugs** — Qwopus reaches dense-27B tool-call reliability at the MoE's
  ~4× decode rate.
- Under a harder tool-call stress suite, Qwopus stays **100% / 0** while the dense
  27B drops to **88.9% / 3 bugs** (the same empty-object failure). But on an
  expression-evaluator trap (precedence of `**` vs unary minus) the **dense 27B is
  correct and Qwopus is wrong** — they split. (Recovery rate is weight-sensitive
  and noisy — not a headline.)

### Thinking ablation (`asiai bench --thinking-ablation`, Qwopus-35B-A3B, 3 deterministic runs)

| Config | Tool-call clean | Note |
|--------|----------------:|------|
| `enable_thinking=off` | **100%** | the only fully-clean config |
| `enable_thinking=on` + `preserve_thinking=on` | 77.8% | 2/9 turns dirty |
| `enable_thinking=on` + `preserve_thinking=off` | 11.1% | turns 2-8 → HTTP 500 (context corruption); avoid |

### MTP throughput (`--spec-type draft-mtp`, warm decode, intra-session ±MTP)

| Model / hardware | MTP off | MTP on | Δ |
|------------------|--------:|-------:|--:|
| 35B-A3B base · M5 Max | 85.5 t/s | **118.4 t/s** | **+38%** |
| Qwopus 35B-A3B · M5 Max | 105.7 t/s | 123.3 t/s | +17% |
| 27B-dense · M5 Max | 23.8 t/s | 28.0 t/s | +18% |
| Qwopus 27B · M5 Max | 25.9 t/s | 26.7 t/s | +3% |
| 35B-A3B MoE · M4 Pro | 36.3 t/s | 44.6 t/s | +23% |
| 27B-dense · M4 Pro | 10.4 t/s | 9.7 t/s | **−6%** |

MTP gain scales as **(MoE > dense) × (M5 > M4)** — strongly positive on the MoE,
marginal-to-negative on the slow dense path (the draft overhead isn't amortised).
The **Qwopus finetune's MTP head is also weaker than the base** (Qwopus 27B +3% /
35B +17%, vs base 27B-dense +18% / 35B-A3B +38%) — finetuning erodes the draft head.
The MLX-side MTP (mlx_vlm) is disqualified: it breaks long context (empty output,
75% valid). Headline: the 35B-A3B MoE + MTP on llama.cpp sustains **~118 t/s**
decode on M5 Max (~44 t/s on M4 Pro), ~4× the 27B-dense, at ~1.5 tok/s/W, TTFT
~62 ms, 100% output validity.

### Instruction-following (`asiai bench --instruct`, research-brief)

The thinking trade-off has teeth on multi-step deliverables: with
`enable_thinking=false`, Qwopus-35B does the tool work but delivers the requested
multi-section brief **0%** of the time (it stops at the secondary step); with
thinking on, the base model delivers it **100%** (5/5 sections). This pulls the
opposite way from the tool-call result above — thinking-off is cleanest for atomic
tool calls but suppresses written deliverables — which is why asiai sets thinking
**per task-dimension**, not as one global switch.

---

## Section 6 — Operational

> 📌 Capability snapshot (mid-2026). Engine versions churn weekly on Apple
> Silicon — these cells are point-in-time, not a version-pinned guarantee.

| # | Engine | License | Stream OAI-compat | `/v1/models` | `/health` | `/metrics` (Prometheus) | Tool calling | Auto-DL HF | Persisted prefix cache | Maintainer activity |
|---|--------|---------|---|---|---|---|---|---|---|---|
| 1 | Rapid-MLX 0.6.66 | Apache-2.0 | ✅ | ✅ | ✅ (HTML page) | ❌ (logs only) | ✅ | ✅ HF Hub auto-DL on serve | ✅ `~/.cache/vllm-mlx/prefix_cache/` | community (raullenchai) |
| 2 | LM Studio 0.4.14 | proprietary | ✅ | ✅ | partial (websocket) | ❌ | ✅ | ✅ via `lms get` CLI | ❌ | Element Labs |
| 3 | llama.cpp b9270 | MIT | ✅ | ✅ | ✅ | ✅ `--metrics` | ✅ | manual (GGUF on disk) | ❌ (`--cache-reuse N` arch-disabled on hybrid) | ggerganov very active |
| 4 | mlx-lm | MIT | ✅ | ✅ | ✅ | ❌ | partial | ✅ HF auto | ❌ | Apple ml-explore active |
| 5 | oMLX | MIT | ✅ | ✅ | ✅ | ❌ | ✅ (caveat: post-cache-hit bug) | ✅ | partial (tiered SSD) | jundot active |
| 6 | vLLM-MLX | Apache-2.0 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ paged-attention | vllm-project active |
| 7 | vMLX (Mamba/SSM) | Apache-2.0 | ✅ | ✅ | ✅ | partial | untested | partial | untested | community |
| 8 | Ollama | MIT | ✅ | partial | ✅ `/api/version` | ❌ | partial | ✅ `ollama pull` | ❌ | Ollama Inc. very active |

---

## Section 7 — Quality benchmark weighting for agentic-coding workloads

> This is the **asiai default weighting** for an orchestrator-class workload
> (60-80 sequential tool calls per turn, schema-validated output, long-context
> system prompts). It is informed by three frontier-LLM advisories
> (Grok-4, GPT-5, Gemini Advanced) queried May 2026, but is **not a community
> consensus** — treat as a starting point, not authoritative. Override via
> a future `--weights` flag (planned).

| Benchmark | What it measures | Why it matters here | Consensus weight |
|-----------|------------------|---------------------|-----------------:|
| **SWE-bench Verified** | Real GitHub repo navigation + patch + test repair | Best proxy for code-editing fidelity inside an agent loop | **35 %** |
| **BFCL v3** (Berkeley Function Calling Leaderboard) | Multi-turn function-call accuracy, argument fidelity, schema adherence | Direct predictor of orchestrator stability across many tool calls | **25 %** |
| **TerminalBench 2.0 / MCP-Atlas** | CLI and MCP task execution autonomy | "Does the agent survive 40+ actions without derailing" | **20 %** |
| **LiveBench Coding** | Contamination-resistant coding tasks (refreshed monthly) | Catches train-test leakage that inflates HumanEval-class scores | **10 %** |
| **Custom long-horizon stability eval** | 60-80 sequential tool calls with cumulative context growth, malformed JSON recovery | The benchmark that does not exist yet in public form — see Section 8 | **10 %** |

### Benchmarks consciously dropped from the weighting

- MMLU-Pro, GPQA Diamond, HumanEval+ — useful as a general capability signal,
  but **weakly correlated** with agent-loop reliability per 2026 evidence.
  Frontier-lab confirmations indicate single-shot reasoning scores no longer
  predict autonomous agent success at sufficient granularity.
- Author-reported aggregates without third-party reruns (Jackrong Hessling,
  Unsloth self-eval, GLM-4.6-Coder vendor claims).

---

## Section 8 — Custom "endurance" benchmark proposal (research opportunity)

All three advisors converge on the same gap: **the benchmark that would best
characterize an orchestrator workload does not exist publicly yet**. Building
one is the only way to get the missing signal.

### Proposed scope

- **80 sequential tool calls** per trajectory
- **Schema validation at every turn** (strict JSON / structured output)
- **Cumulative context growth** (10K → 50K tokens across the trajectory)
- **Interruption / recovery tests** (mid-trajectory cancel + resume)
- **Malformed XML/JSON recovery** (does the agent self-correct ?)
- **Repo-edit persistence** (do the edits made at turn N still hold at turn 60 ?)

This is on the asiai roadmap (a long-horizon endurance mode, after burst-mode).
If built, it would be the first public benchmark in this specific niche.

---

## Methodology

- **Hardware**: MacBook Pro M5 Max 128 GB unified memory, macOS 26.4.1.
- **Workload**: orchestrator class — system prompt ~7 KB, user prompt ~150-200
  tokens, 60-80 calls per turn.
- **Phases measured** (single-call, agentic-mode v1.6.0):
  - `cold`: first call after fresh start
  - `warm`: same exact prompt as cold (warm cache)
  - `prefix-test-1/2/3`: identical system, user changing — measures cross-USER cache reuse
  - `cold-prefix`: identical system, after restart — measures persistent cache
- **Verdict prefix cache reuse**: `YES` if `median(prefix-test) / cold < 0.2`,
  else `NO`.
- **Anti-bias measures**: SOLO mode (no cohabiting engines), thermal idle
  baseline, mmap warm-up phase.
- **Quality gates** (auto-tracked by asiai bench):
  - `early_stop`: at least 2 runs with `<0.5×` median completion
  - `memory_pressure`: swap delta `>500 MB` OR swapouts delta `>1000`
  - `duplicate_processes`: multiple engine processes detected during the bench

The full protocol is the `asiai bench --agentic-mode` / `--burst-mode`
instrumentation (power/thermal, engine footprint, KV occupancy, prefix-cache
phases) — see the asiai CLI docs.

---

## Open questions

1. **MTP on vLLM-MLX/Rapid-MLX — answered (partly).** vLLM-MLX added MTP in
   prerelease **0.4.0rc1** (2026-05-21); the theoretical combo "MLX + MTP-equipped
   Qwopus 35B-A3B + cross-USER snapshot" could win on both decode and TTFT once
   the Rapid-MLX fork tracks 0.4.x. Track when Rapid-MLX picks up the MTP path.
2. **MTP on the MLX runtime — current state.** Released mlx-lm does not run the
   MTP head as native speculative decoding (`sanitize()` drops the MTP weights
   during conversion; native support is in the unmerged PR
   [ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990)).
   LM Studio's `mlx-engine` wraps mlx-lm, so it inherits this — the +13.5%
   decode gain in Section 1 row 5 comes from LM Studio's **llama.cpp-derived
   backend** (the file is GGUF), not from mlx-engine speculative decoding.
3. **Burst behavior on Rapid-MLX/vllm-mlx at 60-80 calls scale**: smoke
   test confirms single-slot FIFO at burst=5. Full panel pending (Section
   2). The relevant upstream issue is whether vllm-mlx plans
   continuous-batching / multi-slot scheduling for hybrid arch models.
4. **`llama_memory_can_shift=false` on Qwen 3.6 hybrid** — still broken
   upstream. [#18497](https://github.com/ggml-org/llama.cpp/issues/18497) is
   closed (documents full re-processing); [#22384](https://github.com/ggml-org/llama.cpp/issues/22384)
   is an *issue* (closed-as-completed), **not** a merged fix; the actual fix PR
   [#23121](https://github.com/ggml-org/llama.cpp/pull/23121) was **closed
   unmerged** (patches live only on forks). The "just enable `preserve_thinking`"
   workaround is refuted by open issue
   [#22615](https://github.com/ggml-org/llama.cpp/issues/22615) (0.67× speedup =
   cache stays inert). The hybrid DeltaNet layers don't expose a shiftable cache
   state by construction.
5. **Qwopus 3.6 quality independent reproduction**: needs third-party
   BFCL / SWE-bench reruns. Author-published numbers should not drive
   production decisions until cross-verified.
6. **vllm-mlx vs Rapid-MLX lineage — answered.** Rapid-MLX is a community
   **hard fork** of `waybarrios/vllm-mlx`, not a thin wrapper: it vendors the
   engine in-tree (package still named `vllm_mlx`), does not pip-depend on the
   upstream package, and has diverged substantially (Rapid-MLX 0.6.74 vs upstream
   0.3.0). The shared `vllm_mlx` package name and `~/.cache/vllm-mlx/` dir are a
   frequent source of attribution confusion (see Section 3, caveat 2).

---

*This panel is a living document. Contributions, corrections, and additional
bench cells welcome via [github.com/druide67/asiai](https://github.com/druide67/asiai/issues).*
