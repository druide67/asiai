---
description: Dev-quality and multilingual-retention benchmark results on Apple Silicon — tool-call reliability (the JSON arg-truncation / empty-object bug), agentic error-recovery, thinking discipline, and language retention. Deterministic, no LLM judge needed for the core signal. A living results page.
---

# Dev-Quality & Language Benchmarks

Throughput is not quality. A model can decode fast and still be unusable for
agentic coding — it truncates tool-call arguments, loops on errors, or its
finetune quietly broke another language. This page reports real
`asiai bench --code` and `asiai bench --language` results: **deterministic**
signals (no LLM judge needed for the core) that measure whether a model actually
works, not how fast it emits tokens.

> **Living document.** Numbers are refreshed as model revisions, engines and
> templates change. Each block names the exact model file and serving config so a
> result is reproducible.

## What is measured

`asiai bench --code` (deterministic, no judge):

- **tool-call** — an 8-turn agentic file-editing session under accumulating
  context. Scores tool-call emission, JSON validity, non-truncation, correct
  tool, schema conformance, and the **empty-object bug**: the `|items` template
  truncation that collapses an `edit_file.edits` array to `{}` / `[]`.
- **tool-call-stress** — the same, harder: deeper context, 8–10-element edit
  arrays, JSON-escaping pressure (newlines, quotes, backslashes, unicode). Used
  to tell apart models that ace the baseline.
- **recovery** — inject a synthetic tool error mid-session; score a corrective
  action vs. a stuck loop (re-emitting the failing call).
- **thinking** — thinking-mode discipline: no `<think>` leak into content,
  non-empty output at a short budget, and `enable_thinking=false` honoured.
- **coding** / **coding-hard** *(optional judge)* — multi-turn coding tasks
  graded 1–5 by an LLM judge at `--judge-url` (any OpenAI-compatible endpoint).

`asiai bench --instruct` (deterministic instruction-following):

- **verifiable** — IFEval-style single-turn prompts with programmatically-checkable
  instructions (word/sentence/section counts, keywords, JSON-only, casing, no
  commas, end phrase, title in `<<>>`, language…). Reported as strict/loose
  accuracy at prompt-level and instruction-level — the public-leaderboard format.
  asiai-native reimplementation of the IFEval paradigm (Zhou et al. 2023); no
  IFEval code or data is vendored.
- **research-brief** — an agentic task: research several topics via tools, then
  write a multi-section briefing, then a secondary tool action (save) **last**.
  Does the model produce the primary briefing, or do the tool work and return only
  the secondary-step confirmation? A model can ace tool-call reliability and still
  skip the main deliverable — scored deterministically by checking the required
  sections appear after the tool turns. **order-control** swaps the order
  (secondary first) as the diagnostic.
- **loop-search** — an ambiguous-search trap: a deep warmup over clear topics,
  then a target fact that `web_search` can never confirm (semantic reformulations
  of the query collapse to one answer). Scores whether the model accepts the
  ambiguity and delivers (sober) or re-issues equivalent queries until a
  no-progress cap halts it (perfectionist), plus an output-token-collapse signal.
  Two modes (`short` sub-1KB result / `unconfirmable` plausible-but-missing-fact).
  This is the failure mode that single-turn IFEval and research-brief don't
  surface.

`asiai bench --language <code>` (deterministic, 8 languages):

- **adherence** — does the model stay in the target language? (target vs. English
  function-word ratio for Latin scripts; target-script character ratio for
  ja/ko/zh).
- **diacritics** — trap prompts whose correct answer must contain specific
  accented tokens (`café`, `préféré`); an ASCII-stripped answer fails.

`asiai bench --thinking-ablation` (cost/benefit of the thinking config):

Runs one representative multi-turn agentic file-editing load (the tool-call-stress
turns, which accumulate context) under three thinking configurations and reports
the trade-off that decides the production setting:

- **enable-off** — no reasoning generated (preserve is moot).
- **enable-on-preserve-on** — reasoning kept in multi-turn history: coherent
  across turns, but context grows.
- **enable-on-preserve-off** — reasoning generated each turn but stripped from
  history: cheaper context, fresher each turn, less loop amplification.

Per config it reports tool-call quality, latency per turn, and prompt (context)
tokens at turn N. The history is rebuilt *with* `reasoning_content` so
`preserve_thinking` has a real effect (without that, preserve on vs off would be
a no-op). Schema `thinking-ablation-v1`; takes a single `--url` target.

All four modes are JSON-only and compare across models by diffing the output.

## Worked example — Qwen3.6-35B-A3B vs Qwopus3.6-35B-A3B vs Qwen3.6-27B dense

A finetune (`Qwopus3.6`, an Opus-distilled finetune of the `Qwen3.6-35B-A3B` MoE)
vs. its base, vs. a dense model half its size. Same llama.cpp, **same chat
template held constant** (only the model file swapped), thinking disabled, 3
repeats. Apple Silicon M5 Max, High Power Mode.

### Tool-call reliability

| model · quant | tool-call clean | empty-object bug | under stress |
|---|--:|--:|--:|
| Qwen3.6-35B-A3B base · Q4 / Q5 | 87.5% | **3** | 87.5% · **3 bugs** |
| **Qwopus3.6-35B-A3B · Q4** | **100%** | **0** | **100% · 0** |
| Qwen3.6-27B dense · Q5 | 100% | 0 | 88.9% · **3 bugs** |

- **The base 35B MoE has a residual tool-call defect the template fix does not
  fully close.** It collapses `edit_file.edits` to the empty-object bug 3/3 on a
  deep-context turn — at **both Q4 and Q5** quants (so it is a generation
  behaviour, not quantisation). The community `froggeric` template, which fixes
  the `|items` bug on simple calls, does not save the base MoE deep in context.
- **The Opus-distilled finetune repairs it completely** — 0 bugs, 100% clean —
  and at a *lower* quant (Q4 vs Q5), which makes the win stronger.
- **Under stress, the finetune is the more robust agent than the dense 27B**:
  the 27B cracks (3 empty-object bugs on the harder suite) while the finetune
  stays at 0. They tie on the baseline; the stress suite separates them.

### Code correctness (LLM-judged hard tasks)

On two trickier multi-turn coding tasks they **split**: on a sliding-window rate
limiter both handle the boundary/eviction edge cases; on an expression evaluator
the **dense 27B gets operator precedence right** (`-2**2 == -4`, unary minus as a
proper operator) while the **finetune does not** (it folds the unary minus into
the number → `4.0`). Tool-call robustness and algorithmic correctness are
*different* axes — measure both.

### Language retention

Running `--language fr` on the finetune and its base, same quant:

| model | adherence | diacritic traps | ASCII-stripped |
|---|--:|--:|--:|
| Qwen3.6-35B-A3B base | 100% | 4/4 | 0 |
| **Qwopus3.6-35B-A3B** | 100% | 4/4 | 0 |

**Zero French regression.** The coding-oriented finetune kept the base model's
French intact (adherence, diacritics, no ASCII-stripping) — a task-specific
finetune did *not* cost another language, which is worth verifying rather than
assuming.

### Perfectionist research loop (loop-search)

`research-brief` saturates at 100% for every model here, so it does not
discriminate the *perfectionist loop* that breaks real agents. The `loop-search`
scenario does. Across a sweep of dense 27B and MoE 35B-A3B configs (M5, llama.cpp
b9430, thinking on/off, both ambiguity modes):

- The **35B-A3B MoE loops** — it re-issues semantically-equivalent searches on an
  unconfirmable fact until a no-progress guardrail halts it, instead of accepting
  the uncertainty and delivering. It does so in **both Q4 and Q8** (architectural,
  not a quant artefact), for the base and the Opus-distilled finetune alike.
- The **dense 27B never loops** (Q4 / Q5 / Q8): it accepts the ambiguous result
  and writes the briefing.

For an agentic harness such as NousResearch's Hermes Agent this is the deciding
signal: the loop-resistant dense model is the safer main even when a faster MoE
exists — throughput buys nothing if the agent spirals on one ambiguous step. It is
also the inverse lesson of the tool-call result above (where the MoE finetune was
the *more* robust agent): **fitness is per-failure-mode, so measure several.**

## How to read this

- **Verdict-first, not speed-first.** These are correctness/reliability signals.
  For throughput, see the [Agentic Benchmarks](agentic-benchmarks.md).
- **Deterministic core, optional judge.** tool-call / recovery / thinking /
  adherence / diacritics need no LLM judge — they are reproducible. The
  `coding`/`fluency` grades are LLM-judged (subjective, optional).
- **Compare within a controlled change.** The example holds the template constant
  and varies only the model, so a difference is the model's, not the harness's.

## Methodology & caveats

- `asiai bench --code` / `--language`, thinking disabled
  (`chat_template_kwargs.enable_thinking=false`), one engine resident at a time.
- **Quant differs across the example** (the finetune Q4 vs the Qwen models Q5):
  the headline empty-object bug is template/generation-driven and was confirmed
  at **both** quants for the base, so quant does not explain the gap — and the
  finetune wins from the lower quant.
- **The code-quality judge is not strictly blind** here (a frontier model read
  the transcripts on the merits); the deterministic tool-call/stress numbers are
  objective.
- **Recovery is weight-sensitive**, not a clean cross-model signal — the headline
  is the tool-call/empty-object reliability, which is stable across repeats.

See also: [Agentic Benchmarks](agentic-benchmarks.md) ·
[Benchmark methodology](methodology.md) · [Metrics spec](metrics-spec.md).
