---
title: "Which Engine for Qwen3.8-27B on Apple Silicon"
description: "Eight inference engines measured on one M5 Max with the same model. Two engines reading the identical weights file differ by 50%, and the flag that buys 20% is off by default in almost all of them."
type: article
date: 2026-08-16
updated: 2026-08-16
---

# Which Engine for Qwen3.8-27B on Apple Silicon

The model question is settled: Qwen3.8-27B runs on a laptop and holds 262,144 tokens of
context. The engine question is not, and it costs more than people think.

We measured eight engines on one M5 Max. The two most interesting results are not about
speed at all — they are about two engines reading the *same file* and disagreeing by
50%, and about a flag that nobody turns on.

## Conditions, before the numbers

M5 Max 128 GB, mains power, High Power Mode, one engine resident at a time. Reasoning
disabled on every engine so they can be compared to each other. Thermal throttling to
50% within 1-2 minutes on every cell — **these are floors, not maxima**. Output validity
100% on every row. Prompt sizes 7,530 tokens (short phases) and 55,839 (long), output
capped at 400 and 200 tokens.

**We do not claim these are the speeds you will get.** We claim they are the gaps
between engines under one protocol.

## The table

| Engine | Weights | n | Warm | At 56k | First token | Memory | Declared ctx |
|---|---|---|---|---|---|---|---|
| **MTPLX** Bare-Speed | MTPLX 4-bit g64 | 3 | **56.0** | **46.5** | 101 ms | 22.0 GB | engine default |
| **MTPLX** Optimized-Speed | MTPLX 4-bit g32 | **5** | **44.4** | 37.5 | 99 ms | 27.0 GB | engine default |
| **mlx-vlm** + MTP drafter | MLX 4-bit ⁽¹⁾ | 3 | **43.3** | 28.9 | **9,982 ms** | 15.5 GB | engine default |
| **MTPLX** Optimized-Quality | MTPLX 8-bit g64 | 3 | 40.8 | 30.3 | 118 ms | 32.9 GB | engine default |
| Ollama 0.32.13 | GGUF (undeclared) | 3 | 32.8 | 21.7 | 240 ms | 30.3 GB | 65,536 |
| llama.cpp b10434 + MTP | GGUF Q5_K_XL ⁽²⁾ | 3 | 31.8 | 22.7 | **125 ms** | 36.8 GB | 131,072 |
| rapid-mlx 0.12.11 | MLX 4-bit ⁽¹⁾ | 3 | 30.2 | 24.7 | **33,195 ms** | 15.0 GB | engine default |
| oMLX 0.6.0-dev | oQ4e-mtp (third-party) | 3 | 29.8 | 24.6 | 1,968 ms | 16.7 GB | engine default |
| mlx-lm 0.31.3 | MLX 4-bit ⁽¹⁾ | 3 | 28.8 | 24.0 | 432 ms | **14.6 GB** | engine default |
| LM Studio 0.4.21 **+ MTP** | GGUF Q5_K_XL ⁽²⁾ | 3 | 27.8 | 23.4 | 419 ms | 36.3 GB | 65,536 |
| LM Studio 0.4.21 defaults | GGUF Q5_K_XL ⁽²⁾ | 3 | 23.1 | 18.7 | 359 ms | 35.2 GB | 65,536 |

⁽¹⁾ and ⁽²⁾ mark rows sharing a **byte-identical weights file**. Every row is one cell,
one export — no values mixed between runs.

⚠️ **Memory is not comparable across families.** llama.cpp and Ollama mmap their GGUF:
their resident set is file-backed and evictable (llama.cpp: 36.8 GB RSS but 19.8 GB
physical footprint). MLX engines allocate. Read the column within a family, not across.

⚠️ **Declared context differs.** Three engines were given an explicit window; the others
ran on their default. That alone forbids ranking the memory column globally.

## Two engines, one file, 50% apart ⁽¹⁾

mlx-vlm, mlx-lm and rapid-mlx all served `lmstudio-community/Qwen3.8-27B-MLX-4bit`,
snapshot `6067b15c` — the same file on disk.

| Engine | Warm | First token | Memory |
|---|---|---|---|
| mlx-vlm + MTP drafter | **43.3** | 9,982 ms | 15.5 GB |
| rapid-mlx | 30.2 | 33,195 ms | 15.0 GB |
| mlx-lm | 28.8 | **432 ms** | 14.6 GB |

**+50% from mlx-lm to mlx-vlm, with nothing changed but the server.** This is the
cleanest comparison in the campaign: no quantization difference to argue about.

And it inverts immediately: mlx-vlm's 50% advantage costs **23× worse time to first
token**, because it has no prefix cache at all. For a one-shot generation it wins. For an
agent, it is unusable — and the reason is in the next section.

## The flag that buys 20%, and why it is off ⁽²⁾

Qwen3.8 ships a **multi-token prediction head inside the weights**. The model proposes
several tokens ahead, the engine verifies them in one forward pass. Engines that
implement the probability-ratio acceptance rule preserve the output distribution exactly;
we did not verify that property ourselves, and you should not take it on faith from a
benchmark — read your engine's implementation.

Almost every engine ships it **off**.

| Engine | Flag | On by default? |
|---|---|---|
| vmlx | `--native-mtp-depth` | **yes** |
| MTPLX | `--mtp --depth 3` | yes |
| vllm-mlx | `--enable-mtp` | no |
| llama.cpp | `--spec-type draft-mtp` | no |
| LM Studio | `--speculative-draft-mtp` | no |
| mlx-vlm | `--draft-kind mtp` + separate drafter repo | no |
| oMLX | did not engage on Qwen3.8 in our runs | — |
| Ollama · mlx-lm · rapid-mlx | no support | — |

We measured the cost of not knowing on the same weights file, same 65,536 context, same
everything but two flags: **LM Studio goes 23.1 → 27.8 tok/s, +20%.** No GUI surfaces it.

Second-order effect, and it matters more: **comparing two engines at their defaults
compares two different regimes.** vmlx drafts, llama.cpp does not.

## First token spans 350×. Prefill does not explain it.

From 99 ms to 33,195 ms across the table. What decides is **prefix cache granularity** —
how much of a repeated prompt survives between turns. Measured on the same phase (the
warm turn, where first-token latency is taken):

| Engine | Reuses | Re-prefilled every turn | First token |
|---|---|---|---|
| llama.cpp | 7,526 / 7,530 — **token-level** | 4 tokens | 125 ms |
| oMLX | 6,144 / 7,530 — **1024-token blocks** | 1,386 tokens | 1,944 ms |
| mlx-vlm | 0 / 7,530 | 7,530 tokens | 9,982 ms |

6,144 is six times 1,024. oMLX reuses whole blocks and re-prefills anything that does not
fill one — 1,386 tokens, every turn, forever. That is the entire gap between 125 ms and
2 seconds.

⚠️ **Do not compare session-aggregate reuse ratios between engines.** They have different
ceilings depending on how much of the test prompt is cacheable, and comparing them
produces paradoxes that vanish when you compare the same phase. We made that mistake in
an earlier draft of this page.

We are **not** publishing a prefill-throughput column. Ours came from a single
un-repeated cold request, which for lazily-loading engines includes reading 20 GB off
disk — LM Studio measured 216 tok/s on that request and 938 on the very next one. It
would have been a fabricated number.

## Tokens per second is not a speed

Across quantizations of the same model, tok/s partly measures how long the outputs are,
not how fast they arrive:

| Build | tok/s | chars/s |
|---|---|---|
| Bare-Speed | 56.0 | 200.8 |
| Optimized-Speed | 44.4 | **203.1** |
| Optimized-Quality | 40.8 | 165.7 |

Bare-Speed leads by 26% in tokens/second and is **behind** in characters per second.
Same tokenizer on all three — what differs is what the quantizations chose to write.
Publish the definition with the number.

## What we recommend

**For a local autonomous agent: MTPLX with `Qwen3.8-27B-MTPLX-Optimized-Speed`, MTP depth
3.** Fast, 99 ms to first token, token-level prefix reuse, 27 GB.

Not Bare-Speed, though it leads on paper. The three builds differ in
divergence-from-bf16, published by the quantization author: **0.00105** for
Optimized-Quality, **0.0220** for Optimized-Speed, **0.0376** for Bare-Speed. His
measurement, not ours, not reproduced — but it is the only fidelity figure any of us
has, and Bare-Speed sits an order of magnitude away from Quality.

Not Optimized-Quality either: it costs **8.3 GB more** for an edge nobody has
demonstrated on a task.

**Run it with reasoning on.** Qwen recommends the `xhigh` effort level for agentic
work, and states that in multi-turn agentic tasks a lower effort *"can lead to
insufficient analysis, more failures, and repeated retries, which may increase total
latency"*. MTPLX 2.7.1 separately lists disabled reasoning as a known issue for
Qwen3.8. Note that `high` does not exist on this model — Qwen exposes `low`, `medium`
and `xhigh` only, and `xhigh` is the default.

## What we could not measure

**vmlx and vllm-mlx were attempted and are missing.** Both support native MTP — vmlx has
it on by default — so their absence is a real gap in this comparison, not a rounding
error. vllm-mlx died at startup on a command-line quoting error; vmlx was still running
when this went out.

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
separable. The throughput column is far more stable (CV 0.01-0.04).

**Test-retest spread on identical reruns of the same command reached 7.5%** (37.97 /
40.82 / 39.35 tok/s across three runs of Optimized-Quality), and memory moved 5 GB
between reruns. Treat any gap under 8% as nothing.

**Tuning was not symmetric.** llama.cpp received explicit cache flags
(`--cache-reuse 256 --slot-prompt-similarity 0.5`, flash attention, 131k KV) that the MLX
engines did not get. MTPLX ran on `--profile turbo`, not its default. This is a
comparison of configurations we would deploy, not of out-of-the-box defaults.

## Reproducing this

Every number comes from a certified card produced by [asiai](https://asiai.dev), through
a single scripted path with solitude gates, served-model identity proofs and thermal
sampling. Raw exports available.

If you take one thing: **check whether your engine has multi-token prediction, and whether
it is on.**
