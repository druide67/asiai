---
title: "Qwen3.8-27B on Apple Silicon: +45% for One Flag"
description: "Qwen3.8-27B ships its speculative decoding head inside the GGUF, disabled by default. Measured on M5 Max: 21.9 to 31.8 tok/s with one flag, and why the draft cap inherited from Qwen3.6 gains you nothing."
type: article
date: 2026-08-15
updated: 2026-08-15
---

# Qwen3.8-27B on Apple Silicon: +45% for One Flag

Qwen3.8-27B ships its own **multi-token prediction head inside the GGUF file**. No
separate draft model to download, no extra memory. llama.cpp only loads it when
you pass `--spec-type draft-mtp` — without the flag it drops the tensors as
"unused" and says nothing.

Measured on an M5 Max, same model, same quantization, everything else identical:

```bash
--spec-type draft-mtp --spec-draft-n-max 4
```

**21.9 → 31.8 tok/s.** That is a 45% gain for one line of configuration.

## The Draft Cap Is Where People Will Lose It

The flag alone is not enough, and this is the part that will cost most people
their gain. `--spec-draft-n-max` sets how many tokens the draft head proposes per
step, and it has an **optimum**:

| Draft cap | Throughput (warm) | |
|---|---|---|
| speculation off | 21.9 tok/s | baseline |
| `--spec-draft-n-max 2` | 22.2 tok/s | **the Qwen3.6 value — gains nothing** |
| **`--spec-draft-n-max 4`** | **31.8 tok/s** | **+45%** |
| `--spec-draft-n-max 6` | 21.6 tok/s | back to square one |

**2 is the value carried over from Qwen3.6 presets.** Anyone migrating will turn
speculation on, measure a 1% gain, and conclude that MTP is not worth it on this
model. It is worth 45% — at cap 4.

Why 6 loses: the cost of producing the draft grows linearly with the cap, while
acceptance saturates. Measured at cap 4 the model accepts 54.8% of drafted tokens;
at cap 6, 48.5% — for 23% more tokens drafted. The extra work is not paid back.

A note for anyone tempted to tune further: **the acceptance rate does not tell you
whether the cap is right**. At cap 2 acceptance was an excellent 75% while the
engine was leaving 45% of its throughput on the table. Measure throughput, not
acceptance.

## Context and KV Cache: 23% at Depth

Two settings interact, and the winning combination beats each of its parts.

Quantizing the KV cache saves memory and costs throughput at depth:

| KV cache | Throughput at 56k ctx | Resident memory |
|---|---|---|
| `q8_0` | 18.5 tok/s | 36.0 GB |
| **`f16`** | **20.6 tok/s** | 44.8 GB |

Halving the context window from 262144 to 131072 costs **no throughput at all**
and saves 4.8 GB. Combine the two:

| Configuration | Warm | At 56k ctx | Memory |
|---|---|---|---|
| ctx 262144 · KV `q8_0` | 29.6 | 18.5 | 36.0 GB |
| **ctx 131072 · KV `f16`** | **31.8** | **22.7** | **36.8 GB** |

**+23% throughput at depth for 800 MB.** An `f16` cache over half the context
weighs what a quantized cache weighs over the full one. If your workload never
exceeds 128k tokens, this is free performance.

## What This Costs You

Dropping to 131072 halves the model's **native** context (262144, extensible to
1M). If you actually work beyond 128k tokens, keep the full window — the
measurement says the KV cache precision matters, the window size does not.

## Reproducing This

```bash
# with speculation
llama-server --model Qwen3.8-27B-UD-Q5_K_XL.gguf \
  --ctx-size 131072 --flash-attn on --n-gpu-layers 999 --jinja \
  --cache-type-k f16 --cache-type-v f16 \
  --spec-type draft-mtp --spec-draft-n-max 4 --metrics

# then verify it actually loaded — the witness is in the server log
grep "creating MTP draft context" <server.log>

# and confirm it is working, from the artifact rather than the log
curl -s localhost:8080/metrics | grep spec_decode
```

That last check matters: `llamacpp:spec_decode_num_draft_tokens_total` divided by
`llamacpp:spec_decode_num_drafts_total` gives the tokens drafted per step. It
should equal your cap. If it does not, the flag did not take.

## Conditions

M5 Max 128 GB, macOS 26.5.2, mains power, High Power Mode, llama.cpp b10434,
`Qwen3.8-27B-UD-Q5_K_XL`, agentic protocol n=3, reasoning disabled and verified,
single resident engine, production stopped. Thermal throttling to 50% was present
on every measurement (expected M5 behaviour after 80-110 s of dense generation)
and is therefore neutral for comparisons within this table — but it makes these
numbers non-comparable to figures published elsewhere without the same conditions.

Depth matters: the same engine drops from 31.8 tok/s at 7.5k prompt tokens to
22.7 at 56k. A tok/s figure without its context depth means nothing.

## See Also

- [Choosing an Engine for Qwen3.8-27B](qwen38-27b-engine-choice.md) — four engines
  measured, and why the fastest one is unusable for agents
- [Agentic Benchmarks](agentic-benchmarks.md) — the protocol behind these numbers
- [Benchmark Best Practices](benchmark-best-practices.md)
