# ADR 0002 — Matching rule for the "This machine vs community" panel

- Status: accepted
- Date: 2026-07-18
- Scope: `GET /api/v1/leaderboard/compare`, Leaderboard page panel

## Context

The Leaderboard page can filter community groups down to the local chip
("This machine"), but it never answers the question users actually come
with: *is my machine in line with everyone else's?* The compare panel
puts local medians (from the local benchmarks DB) next to community
medians (from `api.asiai.dev`), per engine, with a signed delta.

The risky part is not the visual — it is deciding when a local number
and a community group talk about *the same thing*. A wrong match
produces a confidently wrong delta, which is worse than no panel.

## Decision

A local slice and a community group match on the triple
**(chip, model, engine), compared strictly**:

- **Chip** — `collect_hw_chip()` locally vs the group's `hw_chip`,
  case-insensitive string equality after trimming. Both sides come from
  the same asiai collector, so formats agree by construction. No fuzzy
  or substring matching: "Apple M4" must never match "Apple M4 Pro".
  (The community API filters by substring server-side; the strict
  equality re-check happens client-side after the fetch.)
- **Model** — the local model name is passed through
  `normalize_model_name()` — the *same* normalizer used at submission
  time, so what this machine submits is exactly what it later matches
  against — then compared case-insensitively to the group's `model`.
  Quantization is part of the name and therefore part of the identity:
  a Q5_K_XL local run and a Q4_K_M community group do **not** match.
- **Engine** — case-insensitive equality on the display engine name
  (`llamacpp`, `mlx`, `ollama`, …).

Further consequences:

- **Conditions are pooled, not matched.** The v2 aggregates carry one
  median per group; they are not partitioned by ctx/kv-cache/power.
  The panel footer states this honestly ("all submitted conditions
  pooled") instead of implying condition-level matching.
- **Zero match is a first-class state.** When no community group
  survives the strict match, the panel renders the local medians alone
  with an explanatory empty state — it never widens the match to fill
  the void. A "compare against the base model instead" affordance needs
  a base-model notion we do not have; it stays out of v1.
- **Model selection** — the panel compares one model. The route takes
  `?model=`; when the client sends none, the server picks the local
  model with the most runs in the window (deterministic, documented in
  the route). The page seeds it from its model filter, which is a
  **substring** filter (same semantics as the table beside it): the
  server picks the most-benched local model whose normalized name
  contains it. Strict equality governs the *community* match, never
  this local pre-selection — a substring here selects which local
  model to compare, it cannot widen what it compares against.
- **Window** — 30 days on both sides by default (`?days=`, 1–365).
  Same-window comparison only; local 30d vs community 90d would bias
  the delta toward whichever side saw a software upgrade first.

## Alternatives rejected

- **Fuzzy model matching** (prefix/stem match, dropping the quant
  suffix): produces cross-quant deltas that look like hardware or
  engine effects. Rejected — quant is identity.
- **Server-side compare endpoint on api.asiai.dev**: local
  *measurements* never leave the machine; the join happens locally.
  (The community fetch does send the selected model name and chip as
  query parameters — the same metadata a leaderboard filter or a
  submission already sends; the medians themselves stay local.)
- **Matching on chip family with RAM tolerance**: memory bandwidth
  varies within a family; deltas would mix machine classes.

## Consequences

- Fine-tuned or renamed local models will often see zero match — the
  honest outcome, surfaced by the empty state.
- The strict triple makes the panel trivially testable: matching is a
  pure function of two record sets.
- If community groups later become condition-partitioned, the pooled
  footnote and this ADR are the two places to revisit.
