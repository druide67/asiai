---
title: "Which Engine for Qwen3.8-27B on Apple Silicon"
description: "Eleven configurations across eight inference engines on one M5 Max. Swapping the server changes almost nothing; turning on multi-token prediction changes everything — and it is off by default in almost all of them."
type: article
date: 2026-08-16
updated: 2026-08-16
---

# Which Engine for Qwen3.8-27B on Apple Silicon

The model question is settled: Qwen3.8-27B runs on a laptop and holds 262,144 tokens of
context. The engine question is not, and it costs more than people think.

We measured eleven configurations across eight engines on one M5 Max. The result that
surprised us is a negative one: **swapping the server, on a byte-identical weights file,
buys under 5%.** What buys 50% is a decoding flag that most engines ship off.

## Conditions, before the numbers

M5 Max 128 GB, mains power, High Power Mode, one engine resident at a time. Reasoning
disabled on every engine so they can be compared to each other — a measurement decision,
not a deployment one; see *What we recommend*. Thermal throttling to 50% within 70-131
seconds on every cell — **these are floors, not maxima**. Prompt sizes 7,530 tokens
(short phases) and 55,839 (long).

⚠️ **Output was capped at 400 tokens (200 on long phases) and every run hit the cap.**
Nothing here ran a task to completion: this measures streaming throughput on a truncated
continuation. "Output validity 100%" means non-empty, well-formed text came out before
the cap — not that the model finished anything. Because the token count is fixed, tok/s
on this page is the exact inverse of wall-clock time, which makes it the *cleanest*
number here — see *What a token is worth* for the metric that is not.

**We do not claim these are the speeds you will get.** We claim they are the gaps
between engines under one protocol.

## The table

Warm and 56k are tok/s. First token is measured on the warm turn; *first token @56k* on
the first pass over a 55,839-token prompt.

| Engine | Weights | n | Warm | At 56k | First token | @56k | Memory |
|---|---|---|---|---|---|---|---|
| MTPLX Bare-Speed | MTPLX 4-bit g64 | 3 | **56.0** | **46.5** | 101 ms | 322 ms | 22.0 GB |
| MTPLX Optimized-Speed | MTPLX 4-bit g32 | 5 | 44.4 | 37.5 | **99 ms** | **301 ms** | 27.0 GB |
| mlx-vlm + MTP drafter | MLX 4-bit ⁽¹⁾ | 3 | 43.3 | 28.9 | 9,982 ms | 100,733 ms | 15.5 GB |
| MTPLX Optimized-Quality | MTPLX 8-bit g64 | 3 | 40.8 | 30.3 | 118 ms | 100,243 ms | 32.9 GB |
| Ollama 0.32.13 | GGUF (undeclared) | 3 | 32.8 | 21.7 | 240 ms | 574 ms | 30.3 GB |
| llama.cpp b10434 + MTP | GGUF Q5_K_XL ⁽²⁾ | 3 | 31.8 | 22.7 | 125 ms | 365 ms | 36.8 GB |
| rapid-mlx 0.12.11 | MLX 4-bit ⁽¹⁾ | 3 | 30.2 | 24.7 | 33,195 ms | 287,548 ms | 15.0 GB |
| oMLX 0.6.0-dev | oQ4e-mtp (third-party) | 3 | 29.8 | 24.6 | 1,968 ms | 1,991 ms | 16.7 GB |
| mlx-lm 0.31.3 | MLX 4-bit ⁽¹⁾ | 3 | 28.8 | 24.0 | 432 ms | 799 ms | 14.6 GB |
| LM Studio 0.4.21 **+ MTP** | GGUF Q5_K_XL ⁽²⁾ | 3 | 27.8 | 23.4 | 419 ms | 825 ms | 36.3 GB |
| LM Studio 0.4.21 defaults | GGUF Q5_K_XL ⁽²⁾ | 3 | 23.1 | 18.7 | 359 ms | 865 ms | 35.2 GB |

⁽¹⁾ and ⁽²⁾ mark rows sharing a **byte-identical weights file**. Every row is one cell,
one export — no values mixed between runs.

⚠️ **Test-retest spread on identical reruns reached 7.5%, and memory moved 5 GB.** Treat
any throughput gap under 8% as nothing. That dissolves the middle of this table: Ollama,
llama.cpp, rapid-mlx, oMLX, mlx-lm and LM Studio+MTP (32.8 down to 27.8) are not ranked
by these numbers, they are tied.

⚠️ **The two 100-second entries are not engine speed.** Optimized-Quality reaches first
token in 118 ms warm and 100 seconds on a cold 56k prompt — same engine, same version as
the 301 ms row. That column measures cache state, and on the MTPLX rows the cache is
sized by `MTPLX_MEMORY_BUDGET=60GB`, an operator setting, not a property of the engine.
On the repeated 56k turn the same build returns to 498 ms.

⚠️ **Memory is not comparable across families.** llama.cpp and Ollama mmap their GGUF:
their resident set is file-backed and evictable (llama.cpp: 36.8 GB RSS but 19.4 GB
physical footprint). MLX engines allocate. Read the column within a family, not across —
and note that the MLX rows carry a KV cache sized from free RAM at launch. Three engines
were given an explicit context window and the rest ran on their defaults, which forbids
ranking this column globally.

## Three servers, one file: the server is not what matters ⁽¹⁾

mlx-vlm, mlx-lm and rapid-mlx all served `lmstudio-community/Qwen3.8-27B-MLX-4bit`,
snapshot `6067b15c` — the same file on disk, byte for byte.

| Server | Speculative decoding | Warm | First token |
|---|---|---|---|
| mlx-vlm | **MTP drafter** ⁽³⁾ | 43.3 | 9,982 ms |
| rapid-mlx | none | 30.2 | 33,195 ms |
| mlx-lm | none | 28.8 | 432 ms |

⁽³⁾ mlx-vlm ran with a **second model loaded**: `--draft-model
mlx-community/Qwen3.8-27B-MTP-4bit --draft-kind mtp --draft-block-size 4`. The other two
ran the target model alone.

**Compare the two rows that are actually comparable — rapid-mlx and mlx-lm, same file,
no speculation on either side: 30.2 against 28.8, under 5%.** That is below our own
noise floor. Swapping the MLX server, by itself, buys nothing.

mlx-vlm's +50% is the drafter, not the server. It is the same effect measured under
controlled conditions in the next section, and reading it as an engine result — as an
earlier version of this page did — double-counts it.

The first-token column is where these three genuinely differ, and by 77×. That gap is
about prefix caching, measured further down.

## The flag that buys 20%, and why it is off ⁽²⁾

Qwen3.8 ships a **multi-token prediction head inside the weights**. The model proposes
several tokens ahead, the engine verifies them in one forward pass. Engines that
implement the probability-ratio acceptance rule preserve the output distribution exactly;
we did not verify that property ourselves, and you should not take it on faith from a
benchmark — read your engine's implementation.

Almost every engine ships it **off**.

| Engine | Flag | On by default? |
|---|---|---|
| MTPLX ⁽ᵐ⁾ | `--mtp --depth 3` | yes |
| llama.cpp ⁽ᵐ⁾ | `--spec-type draft-mtp` | no |
| LM Studio ⁽ᵐ⁾ | `--speculative-draft-mtp` | no |
| mlx-vlm ⁽ᵐ⁾ | `--draft-kind mtp` + separate drafter repo | no |
| vmlx ⁽ᵈ⁾ | `--native-mtp-depth` | yes |
| vllm-mlx ⁽ᵈ⁾ | `--enable-mtp` | no |
| oMLX | did not engage on Qwen3.8 in our runs | — |
| Ollama · mlx-lm · rapid-mlx ⁽ᵈ⁾ | no support | — |

⁽ᵐ⁾ attested by our own launch commands and engine logs. ⁽ᵈ⁾ from the project's
documentation only — we did not run these paths.

We measured the cost of not knowing under control: same weights file, same 65,536
context, same thermal sequence, everything identical but two flags. **LM Studio goes
23.1 → 27.8 tok/s, +19.9%.** No GUI surfaces it. This is the most tightly controlled
comparison on this page, and it is where the +50% seen on mlx-vlm comes from too.

Second-order effect, and it matters more: **comparing two engines at their defaults
compares two different regimes.** MTPLX drafts out of the box; Ollama cannot draft at all.

## First token spans 335×. Prefill does not explain it.

From 99 ms to 33,195 ms across the table. Part of the answer is **prefix cache
granularity** — how much of a repeated prompt survives between turns. Measured on the
same phase (the warm turn, where first-token latency is taken):

| Engine | Reuses | Re-prefilled every turn | First token |
|---|---|---|---|
| llama.cpp | 7,526 / 7,530 — **token-level** | 4 tokens | 125 ms |
| oMLX | 6,144 / 7,530 — **1024-token blocks** | 1,386 tokens | 1,968 ms |
| mlx-vlm | 0 / 7,530 | 7,530 tokens | 9,982 ms |

6,144 is six times 1,024. oMLX reuses whole blocks and re-prefills anything that does not
fill one — 1,386 tokens, every turn, forever. **That accounts for most of the gap between
125 ms and 2 seconds**, and it is the only causal claim these three rows support.

⚠️ **Granularity does not explain the whole 335× spread.** Four engines report zero reuse
on this phase and still range from 240 ms (Ollama) to 33,195 ms (rapid-mlx) — 138× apart
at identical reuse. Something else dominates there, and we did not isolate it.

⚠️ **Do not compare session-aggregate reuse ratios between engines.** They have different
ceilings depending on how much of the test prompt is cacheable, and comparing them
produces paradoxes that vanish when you compare the same phase. We made that mistake in
an earlier draft of this page.

We are **not** publishing a prefill-throughput column. Ours came from a single
un-repeated cold request, which for lazily-loading engines includes reading 20 GB off
disk — LM Studio measured 216 tok/s on that request and 938 on the very next one. It
would have been a fabricated number.

## What a token is worth

Because every run stopped at the same 400-token cap, tok/s here is exact: Bare-Speed
delivered its 400 tokens in 7.2 s, Optimized-Speed in 9.1 s. The 26% gap is real
wall-clock time, not an artefact.

What is *not* comparable across builds is what those tokens contain:

| Build | tok/s | chars/token | chars/s |
|---|---|---|---|
| Bare-Speed | 56.0 | 3.58 | 200.8 |
| Optimized-Speed | 44.4 | 4.62 | 205.5 |
| Optimized-Quality | 40.8 | 4.06 | 165.7 |

Same tokenizer, same prompt, 29% difference in token density — Bare-Speed answered in
dense LaTeX, Optimized-Speed in prose. It is 26% faster in tokens and delivers slightly
*fewer* characters per second. Neither number is wrong; they answer different questions.
If you publish one, say which.

## What we recommend

**For a local autonomous agent: MTPLX with `Qwen3.8-27B-MTPLX-Optimized-Speed`, MTP depth
3.** 99 ms to first token, 301 ms on a cold 56k prompt, 7,530/7,530 token-level prefix
reuse, 27 GB.

⚠️ **What we recommend is not what we measured**, and the gap is on three axes at once.
Measured: reasoning **off**, MTPLX **2.6.0** serving Qwen3.8 under the Qwen3.6 family
defaults, `--profile turbo`. Recommended: reasoning `xhigh`, **2.7.1**, depth 3. On 2.7.1
the same cell gives **51.2 tok/s and 158 ms**, not 44.4 and 99. And we could not measure
the recommended reasoning regime at all: with a 400-token budget, reasoning consumes the
answer — those cells returned 75% output validity and six empty long phases. The engine
choice rests on the table; the reasoning setting rests on Qwen's own guidance.

Not Bare-Speed, though it leads on paper. The three builds differ in
divergence-from-bf16, published by the quantization author: **0.00105** for
Optimized-Quality, **0.0220** for Optimized-Speed, **0.0376** for Bare-Speed. His
measurement, not ours, not reproduced — but it is the only fidelity figure any of us
has, and Bare-Speed is **36× further from bf16** than Quality.

Not Optimized-Quality either: **5.9 GB more** for an edge nobody has demonstrated on a
task, and a cold 56k first token of 100 seconds against 301 ms.

⚠️ **We are recommending the engine whose quantization format only it can read, measured
with our own tool, published on our own site.** The MTPLX rows are the only ones where
engine and weight format cannot be separated. Weigh the recommendation accordingly; the
per-engine flag table below is the part of this page that costs us nothing to be right
about.

**Run it with reasoning on.** Qwen recommends the `xhigh` effort level for agentic
work, and states that in multi-turn agentic tasks a lower effort *"can lead to
insufficient analysis, more failures, and repeated retries, which may increase total
latency"*. MTPLX 2.7.1 separately lists disabled reasoning as a known issue for
Qwen3.8. Note that `high` does not exist on this model — Qwen exposes `low`, `medium`
and `xhigh` only, and `xhigh` is the default.

## What we could not measure

**vmlx and vllm-mlx are missing, and both support native MTP** — vmlx has it on by
default — so their absence is a real gap, not a rounding error. vllm-mlx died at startup
on a command-line quoting error. vmlx ran 24 complete runs and produced a card, then the
cell was **refused by our own gate**: asiai resolves `-e vmlx` to the ollama family and
saw the vmlx server as an intruder. Its export also shows 2.3 GB resident for a 20 GB
model — it was serving off disk — and a 9.8 GB swap delta. The refusal was right for the
wrong reason, and the numbers are not publishable either way.

**Reasoning was disabled throughout, to make engines comparable.** That is a measurement
decision and not a deployment one — see the recommendation above. We have no figure to
offer on what reasoning does to any of these engines, and we are not going to
extrapolate one.

**Version caveats.** The MTPLX rows ran on **2.6.0**, before the engine shipped a
`qwen3_8` model family — it served Qwen3.8 under Qwen3.6 defaults, including a different
sampling contract. This does not affect throughput; it does affect anything about
behaviour. The oMLX row ran from a temporary development build whose version string the
export did not capture, so that row is not reproducible as published. And our mlx-vlm
export self-identifies as `mlxlm 0.31.3_2` — only the launch log proves `mlx_vlm.server`
was the server.

**The first-token ranking among the three MTPLX builds is inside its own noise** —
coefficients of variation of 0.33 to 0.66 on that metric. 99, 101 and 118 ms are not
separable. Throughput is far more stable (CV 0.006-0.07).

**Test-retest spread reached 7.5%** between two three-run cells of Optimized-Quality
(37.97 and 40.82 tok/s), and memory moved 5 GB between them. Treat any gap under 8% as
nothing.

**Tuning was not symmetric, and neither was throttling.** llama.cpp received explicit
cache flags (`--cache-reuse 256 --slot-prompt-similarity 0.5`, flash attention, 131k KV)
that the MLX engines did not get; MTPLX ran on `--profile turbo`, not its default; Ollama
kept its stock batch sizes against llama.cpp's `--batch-size 4096`. Sampling parameters
were not equalised either — rapid-mlx loads temp 1.0 / top_p 0.95 from the repo's
`generation_config.json`, MTPLX 2.6.0 ran the Qwen3.6 sampling contract. And the engines
did not sit at the same thermal limit: mean speed limit per cell ran from 80.8 (mlx-lm)
down to 54.6 (llama.cpp, Ollama), because the faster engines heat the machine more. Each
published median mixes one unthrottled run with two throttled ones. "Floors, not maxima"
holds per row; it does not preserve the gaps between rows.

**We did not publish energy, and it changes the order.** The exports carry it:
mlx-vlm 0.744 tok/s/W, MTPLX Bare-Speed 0.694, MTPLX Optimized-Speed 0.623, rapid-mlx
0.544, oMLX 0.512, mlx-lm 0.472, Ollama 0.451, LM Studio+MTP 0.422, llama.cpp+MTP 0.395.
For an agent running all day on battery that is the deciding column, and our recommended
engine is third.

## Reproducing this

Every number comes from a certified card produced by [asiai](https://asiai.dev), through
a single scripted path with solitude gates, served-model identity proofs and thermal
sampling. What this page does not yet give you, and should: the raw export files, the
full launch command for each row, the prompt text, and the seeds. Ask and we will publish
them — until then, treat every number here as unverified by you.

If you take one thing: **check whether your engine has multi-token prediction, and whether
it is on.**
