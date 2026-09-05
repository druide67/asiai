---
title: "The Best Engine for a Local Agent on Qwen3.8-27B: MTPLX, and it is not close"
description: "Eleven configurations, eight engines, one M5 Max. For agent work the winner takes every metric that matters: 99 ms to resume a session, token-level prefix reuse, 44 tok/s, 27 GB. And the flag that buys 20-50% is off by default in four of the six engines that support it."
type: article
date: 2026-08-16
updated: 2026-09-02
---

# The Best Engine for a Local Agent on Qwen3.8-27B

**Run MTPLX with `Qwen3.8-27B-MTPLX-Optimized-Speed` and `--mtp --depth 3`.**

We measured eleven configurations across eight engines on one M5 Max. For agent work it
wins on every metric that matters, and the second place is not close:

| | MTPLX Optimized-Speed | llama.cpp b10434 +MTP | Ollama 0.32.13 |
|---|---|---|---|
| First token, resumed session | **99 ms** | 125 ms | 240 ms |
| First token, 56k resumed | **301 ms** | 365 ms | 574 ms |
| Prefix reuse | **7,530 / 7,530** | 7,526 / 7,530 | 0 / 7,530 |
| Throughput | **44.4 tok/s** | 31.8 | 32.8 |
| Memory | **27 GB** | 36.8 GB | 30.3 GB |

That is +40% throughput, 26 ms less latency per turn, and 10 GB less memory than the
best of the rest. We run it in production.

## Why those metrics and not tokens per second

An agent is not a chat. It does not stream one long answer — it takes dozens of short
turns, and **every turn re-reads everything that came before**. So the number you feel is
time to first token, and it depends almost entirely on whether the engine kept the
previous prompt in cache. The latency columns below measure the *resumed* turn — the
engine picking a session back up. A real turn appends new text on top of the cached
prefix and pays its prefill too; what the table ranks is the cache machinery, which is
exactly what separates these engines.

The spread on that metric is **335×** across our table — 99 ms to 33 seconds. The spread
on throughput is 5%. That is the whole argument: for agent work, pick on latency and
prefix reuse; throughput is a tiebreaker.

Two engines reuse at token level (MTPLX, llama.cpp). One reuses in 1,024-token blocks and
re-prefills 1,386 tokens *every single turn, forever* (oMLX, 1,968 ms). Three reuse
nothing at all and pay the full prompt each time — mlx-vlm at 9,982 ms, rapid-mlx at
33,195 ms. On a 60-turn agent session, that last one costs **33 minutes of pure waiting**.

## The full table

Warm and 56k are tok/s. First token and @56k are the resumed turn (median of warm
repeats on a 7,530- and a 55,839-token prompt). For engines with no cache at all —
mlx-vlm, rapid-mlx — resumed equals cold: they pay the full prefill every time.

| Engine | Weights | Warm | At 56k | First token | @56k | Memory | tok/s/W |
|---|---|---|---|---|---|---|---|
| MTPLX Bare-Speed | MTPLX 4-bit g64 | **56.0** | **46.5** | 101 ms | 322 ms | 22.0 GB | 0.694 |
| **MTPLX Optimized-Speed** | MTPLX 4-bit g32 | 44.4 | 37.5 | **99 ms** | **301 ms** | 27.0 GB | 0.623 |
| mlx-vlm + MTP drafter | MLX 4-bit ⁽¹⁾ | 43.3 | 28.9 | 9,982 ms | 100,733 ms | 15.5 GB | **0.744** |
| MTPLX Optimized-Quality | MTPLX 8-bit g64 | 40.8 | 30.3 | 118 ms | 100,243 ms | 32.9 GB | 0.575 |
| Ollama 0.32.13 | GGUF (undeclared) | 32.8 | 21.7 | 240 ms | 574 ms | 30.3 GB | 0.451 |
| llama.cpp b10434 + MTP | GGUF Q5_K_XL ⁽²⁾ | 31.8 | 22.7 | 125 ms | 365 ms | 36.8 GB | 0.395 |
| rapid-mlx 0.12.11 | MLX 4-bit ⁽¹⁾ | 30.2 | 24.7 | 33,195 ms | 287,548 ms | 15.0 GB | 0.544 |
| oMLX 0.6.0-dev | oQ4e-mtp (third-party) | 29.8 | 24.6 | 1,968 ms | 1,991 ms | 16.7 GB | 0.512 |
| mlx-lm 0.31.3 | MLX 4-bit ⁽¹⁾ | 28.8 | 24.0 | 432 ms | 799 ms | **14.6 GB** | 0.472 |
| LM Studio 0.4.21 **+MTP** | GGUF Q5_K_XL ⁽²⁾ | 27.8 | 23.4 | 419 ms | 825 ms | 36.3 GB | 0.422 |
| LM Studio 0.4.21 defaults | GGUF Q5_K_XL ⁽²⁾ | 23.1 | 18.7 | 359 ms | 865 ms | 35.2 GB | 0.351 |

⁽¹⁾ ⁽²⁾ = byte-identical weights file. MTPLX rows ran on 2.6.0. One cell, one export.
All columns are medians of the warm phase. `tok/s/W` divides decode throughput by
**SoC** power — five IOReport rails: GPU, CPU, ANE, DRAM and the DRAM controller, 58 to 83 W depending on the engine — not GPU-only, which ranks
differently.

**How to read it.** Throughput gaps under 8% are noise — Ollama through LM Studio+MTP
(32.8 to 27.8) are tied, not ranked. The two 100-second entries are what a *first pass*
over a 56k prompt actually costs on this hardware — every engine pays it once; the
millisecond entries in that column are resumed turns served from cache (Optimized-Quality
shows both: 100 s on its first pass, 498 ms once cached). Memory is not comparable across
families (llama.cpp mmaps: 36.8 GB resident is 19.4 GB physical).

## The one thing that will surprise you: the server barely matters

mlx-vlm, mlx-lm and rapid-mlx served the *same file*, `lmstudio-community/Qwen3.8-27B-MLX-4bit`,
snapshot `6067b15c`, byte for byte. Two of them ran bare, without speculation:

**30.2 against 28.8 tok/s. A 4.9% difference — below our own rerun noise.**

Swapping the MLX server buys nothing. The third one, mlx-vlm, reached 43.3 — but it ran
with the MTP drafter loaded. **That +50% is the flag, not the server** — see the appendix
on multi-token prediction, which reaches the same conclusion from the other direction.

## Choosing against a different constraint

Our recommendation optimises for agent work. If yours differs, the table already answers:

- **Smallest footprint** → mlx-lm, 14.6 GB. You lose the prefix cache granularity.
- **Best battery life** → mlx-vlm, 0.744 tok/s/W. Unusable for agents (9,982 ms first
  token), excellent for batch.
- **Raw throughput** → MTPLX Bare-Speed, 56.0 tok/s. We advise against it: the quantization
  author publishes a divergence-from-bf16 of 0.0376 against 0.0220 for Optimized-Speed —
  36× further from bf16 than the 8-bit build. His measurement, not ours, not reproduced.
- **You already run llama.cpp** → stay. Add `--spec-type draft-mtp` and you close most of
  the gap; 125 ms first token is fine for an agent.

## Run it with reasoning on

Qwen recommends `xhigh` for agentic work and warns that a lower effort *"can lead to
insufficient analysis, more failures, and repeated retries"*. MTPLX 2.7.1 separately lists
disabled reasoning as a known issue for Qwen3.8. `high` does not exist on this model —
`low`, `medium`, `xhigh` only, and `xhigh` is the default.

⚠️ Note the effort level is a **chat-template variable, not an API field**: sent as a
normal request parameter it is silently ignored. It must be set at launch.

## Five limits that change how you read this

1. **Nothing here ran a task to completion.** Output was capped at 400 tokens and every run
   hit the cap. These are streaming throughput numbers on truncated continuations.
2. **Reasoning was off for all measurements**, to make engines comparable. That is not how
   we deploy — see above. We have no figure on what reasoning costs each engine.
3. **Tuning was not symmetric.** llama.cpp got explicit cache flags the MLX engines did
   not; MTPLX ran `--profile turbo`; sampling parameters and thermal limits differ per
   engine. Gaps *between families* are indicative, not clean.
4. **We are recommending the engine that alone reads its own quantization format, measured
   with our own tool, published on our own site.** The MTPLX rows are the only ones where
   engine and weight format cannot be separated. Weigh it accordingly — the flag table in
   the appendix is the part of this page that costs us nothing to be right about.

5. **MTPLX keeps a persistent on-disk session bank that survives restarts** — and it
   served phases our protocol believed were cold. We discovered this on 2026-09-02
   (three campaigns were contaminated before a fail-closed gate caught it): with the
   bank actually empty, first token on a cold 7.5k prompt is **8.7 s** and a cold 56k
   prefill is **82 s** (measured on MTPLX 2.10.2, thermal-throttled M5 — upper bounds).
   The latency columns above are therefore *session-resume* numbers, which is the metric
   an agent lives on — but they never were cold starts, and engines without a persistent
   bank could not benefit from the same effect between runs. The bench protocol now
   purges the bank per cell and fails closed on replayed phases (agentic-v5).

Two engines with native MTP, vmlx and vllm-mlx, could not be measured in time.

## Appendix: the MTP flag, engine by engine

Qwen3.8 ships a multi-token prediction head **inside the weights**. The model proposes
several tokens ahead, the engine verifies them in one pass. Four of the six engines that
support it ship it **off**.

| Engine | Flag | On by default? |
|---|---|---|
| MTPLX ⁽ᵐ⁾ | `--mtp --depth 3` | **yes** |
| vmlx ⁽ᵈ⁾ | `--native-mtp-depth` | **yes** |
| llama.cpp ⁽ᵐ⁾ | `--spec-type draft-mtp --spec-draft-n-max 4` | no |
| LM Studio ⁽ᵐ⁾ | `--speculative-draft-mtp` | no |
| mlx-vlm ⁽ᵐ⁾ | `--draft-kind mtp --draft-model mlx-community/Qwen3.8-27B-MTP-4bit` | no |
| vllm-mlx ⁽ᵈ⁾ | `--enable-mtp` | no |
| Ollama · mlx-lm · rapid-mlx | no support | — |

⁽ᵐ⁾ attested by our own launch commands and logs. ⁽ᵈ⁾ from project documentation only.

**We measured what it costs to not know**: same weights file, same 65,536 context, same
thermal sequence, everything identical but two flags. **LM Studio goes 23.1 → 27.8 tok/s,
+19.9%.** No GUI surfaces this. On mlx-vlm the same head is worth +50%.

Note the drafter is bundled in the GGUF for llama.cpp and LM Studio, but mlx-vlm needs a
**second repository** downloaded alongside.

**Check it is actually engaged** — a flag accepted is not a flag working:

```
# llama.cpp / LM Studio — the log must mention a draft context at startup
grep -i "draft" server.log        # "creating MTP draft context"
# any OpenAI-compatible engine — acceptance rate should sit at 0.9+
curl -s localhost:8080/v1/chat/completions -d '…' | jq '.timings'
```

## Reproducing this

Every number comes from a certified card produced by [asiai](https://asiai.dev), through a
single scripted path with solitude gates, served-model identity proofs and thermal
sampling. Raw exports, full launch commands and prompt text: ask and we publish them.

If you take one thing: **check whether your engine has multi-token prediction, and whether
it is on.**

## Corrections

**2026-09-02.** The latency columns were relabeled from "first token" / "56k cold" to
*resumed session*: a fail-closed gate added to our bench runner revealed that MTPLX's
persistent on-disk session bank had served prompts across campaigns, so the numbers —
while correctly measured — were never cold starts. True cold figures and the protocol
fix are in limit 5 above. Rankings between cache-capable engines are unchanged; the
mlx-vlm and rapid-mlx entries were always true colds (they have no cache).
