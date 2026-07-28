# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **`--code` stress suite: large-payload cell** — two turns that demand volume
  (a complete 60+ line HTML page with style and script blocks in one
  `write_file`, then four multi-line `edit_file` replacements), plus a per-turn
  `max_tokens` override so a turn that asks for a large file gets a budget to
  match. asiai already streams tool calls, so volume was the one dimension the
  suite never exercised — and reported tool-call corruptions on Qwen3.6 servers
  are specific to large or heavily-escaped arguments.
- **`content_head` on turns that emit no tool call** — the first 200 characters
  of the text channel are recorded, which distinguishes a model that narrated
  instead of calling ("I need to use the edit_file tool…") from one that
  returned nothing. The counters alone cannot tell the two apart.

### Fixed

- **MCP extra pinned below the 2.x SDK.** `mcp` 2.0.0 removed
  `mcp.server.fastmcp` (`FastMCP` became `mcp.server.MCPServer`), so a fresh
  `pip install asiai[mcp]` broke the MCP server outright — every import in
  `asiai.mcp` failed, and CI went red on `main` without a single line of our
  code changing. The extra now requires `mcp>=1.12,<2` so installs are working
  again; migrating to the 2.x API is a separate change.
- **Large-payload turns no longer score as parser failures for lack of budget.**
  The suite sent a flat 1024 `max_tokens` for every turn; a turn asking for a
  large file ran out mid-argument, and the truncated call surfaced as invalid
  JSON or as content leaking into the text channel — an artefact of the harness
  that looks exactly like an engine defect. Measured on MTPLX 2.3.0: 81.8% JSON
  validity at 1024 tokens versus 100% at 4096 on the same cell, with 5-7 KB
  argument payloads intact.

## [1.32.0](https://github.com/druide67/asiai/compare/v1.31.0...v1.32.0) — 2026-07-25

### Changed

- **Compare panel: growth-loop empty state** (#88): when this machine has
  local run groups but none has a community counterpart, the "This
  machine vs community" panel now says so and invites the user to be the
  first — with a copyable `asiai bench --share` snippet and a note on
  what a submission contains (chip, RAM, engine version, medians only).
  The populated state gains per-engine sample counts under each median
  and a neutral band for deltas under 2% (measurement noise, never a
  win); a local engine with no counterpart keeps the loop in place of
  its delta. The three pre-existing empty states (no local runs, no
  local match, fetch failed) keep their distinct messages, and the
  ADR 0002 matching rule is unchanged.
- **Leaderboard table on the docs site** (#87): rank pills as a CSS
  counter, top-3 podium, chip and RAM stacked in one cell (nine
  locales), tok/s as the hero column over full-width bars, and a sticky
  header — CSS only on the markdown-rendered table, light and dark. The
  #1 accent on tok/s only applies while the table is actually sorted by
  tok/s descending.

### Fixed

- **Compare panel: `community_matched` semantics.** The flag was true as
  soon as the community had data for this chip and model, even on
  engines this machine never ran — which rendered a "0 of N matched"
  grid instead of the share band. It is now derived from the built rows.
- **Compare panel: copy button on plain HTTP.** The Clipboard API needs
  a secure context and the dashboard is served over HTTP on the mesh and
  LAN, so the button did nothing there; it now falls back the same way
  the Bench page does.
- **`--code` tool-call suite: `empty_object_bug` no longer counts
  wrong-tool calls.** The per-turn scorer judged every call's arguments
  against the EXPECTED tool's schema, so a well-formed call to a
  different tool (e.g. `search_code` where `edit_file` was expected)
  raised the headline empty-object-bug count spuriously. The flag is now
  specific to the expected tool's argument collapse; tool-choice misses
  remain visible through `correct_tool` / `pct_correct_tool`.
  Empty-object-bug counts from earlier reports may mix the two
  categories when `pct_correct_tool` was below 100%.

## [1.31.0](https://github.com/druide67/asiai/compare/v1.30.0...v1.31.0) — 2026-07-18

### Added

- **"This machine vs community" panel on the Leaderboard** (#82): local
  medians (from this machine's benchmark history) next to community
  medians per engine, with signed deltas and sample counts, for one
  model over one window. Matching is strict on (chip, model, engine) —
  quantization is part of the identity — per ADR 0002; a zero match
  renders the local medians alone under an honest empty state. New
  `GET /api/v1/leaderboard/compare` endpoint behind the same rate
  limit, semaphore and cache discipline as the sibling community
  proxies.
- **Prefix-cache hits in code-suite results** (#80): `code_eval` reads
  `usage.prompt_tokens_details.cached_tokens` (with the flat
  `cached_tokens` fallback) per turn, so cache reuse on tool-call
  sessions is measurable instead of invisible.

### Changed

- **Bench page craft pass from the design handoff** (#81): the mode
  form's model picker is a grouped dropdown (loaded models, installed
  models tagged "will load", inline free-text entry) driving the same
  hidden form field; a failed run keeps its live log with the error
  line, a frozen progress bar, a Retry button and a Doctor link; the
  running state shows an eta; `extra_body` sits behind an "edit JSON
  detail" reveal. Form field contract unchanged.
- **Hardened release gates**: the release workflow now fails closed —
  before anything is built or published — when the tag, `pyproject.toml`
  and `__init__.py` versions disagree, or when `CHANGELOG.md` has no
  entry for the version being tagged (two releases had shipped with the
  changelog silently forgotten). The GitHub Release step is now
  idempotent (re-running a release run no longer fails on an existing
  release — the 2026-06-25 v1.14.1 incident class).

## [1.30.0](https://github.com/druide67/asiai/compare/v1.29.0...v1.30.0) — 2026-07-16

### Fixed

- **Bench suites forward the engine API key** (#78): the raw-HTTP bench
  paths (code/instruct/language/thinking suites, agentic, burst, the
  KV-cache probes and the auto-restart health wait) bypassed the
  adapters' Bearer auth — every mode except the standard throughput
  bench failed with 401 against a key-gated engine. All of them now
  send the key resolved from the engine config's `api_key_file`; the
  LLM judge keeps its own separate environment-only key. The key never
  appears in argv, logs or persisted results; engines without a key
  produce byte-identical unauthenticated requests.

## [1.29.0](https://github.com/druide67/asiai/compare/v1.28.0...v1.29.0) — 2026-07-16

### Fixed

- **Fleet: shared-port identity** (#77): the dashboard merge joined
  lifecycle states to HTTP-detected engines by port in last-one-wins
  order, so a standby manifest declaring the same port as the active
  engine (slot-switch pattern) clobbered the verified identity of the
  card. The merge now only accepts the manifest whose name is coherent
  with the detected engine (exact or family-prefix match), flags the
  port conflict, and renders unmatched manifests as separate cards.
- **WCAG AA contrast for accent-colored text** (#75, #73 follow-up):
  new `--accent-text` token — unchanged cyan in the dark theme, cyan-700
  in the light theme (4.87-5.36:1 measured) — applied to every
  `color:`-only use of the accent; borders and fills keep `--accent`.
- **Benchmark cards: long model names** (#76): the SVG title
  middle-ellipsizes names over 68 characters, preserving the family
  prefix and the quant suffix instead of overflowing the card header.

## [1.28.0](https://github.com/druide67/asiai/compare/v1.27.0...v1.28.0) — 2026-07-12

### Added

- **Per-engine API keys** (#74): new `api_key_file` field in the engines
  config (`asiai config add <engine> <url> --api-key-file PATH`) — the
  file's key is sent as `Authorization: Bearer` on every request to that
  engine's URL only. Detection, bench, the web dashboard, MCP tools and
  the /slots KV scraper all authenticate; auth-gated engines (MTPLX on
  non-loopback binds, llama.cpp with `--api-key`) are visible again.
  Fail-soft on a missing/empty file; the key never appears in the
  config, logs or error messages.

### Fixed

- **WCAG AA contrast** (#73): `--text-muted` cleared the 4.5:1 threshold
  in both themes (it sat at 2.0-2.6:1), light-theme semantic colors
  darkened one shade for text usage, light active borders reach the 3:1
  UI minimum.

## [1.27.0](https://github.com/druide67/asiai/compare/v1.26.0...v1.27.0) — 2026-07-11

### Added

- **Bench page v2** (#68): the Benchmark page is rebuilt as a guided flow — a
  one-click Quick Bench hero, the seven bench types as primary navigation,
  Target/Options/Advanced steps, live run states and a result panel; the
  ~600 lines of inline JS move to `static/bench.js`.
- **Docs homepage v2** (#69): asiai.dev landing rebuilt with real benchmark
  cards, a terminal-style install snippet, feature tiles and a leaderboard
  teaser; `<head>`/SEO and the nine locales untouched.
- **MTPLX engine adapter** (#70): auto-detection via its `/v1/models`
  `owned_by` signature, version through Homebrew, quality-gate and discovery
  wiring — engine count reaches 10.
- **`asiai bench --backfill-runs`** (#71): rebuild historic `bench_runs`
  sessions from raw benchmark rows — dry-run by default, insert-only,
  idempotent, NULL-safe on old or third-party databases.

### Fixed

- **Compare sessions persist real payloads** (#71): compare runs land in
  `bench_runs` with per-slot payloads for every session type; the multi-model
  compare card renders per-slot bars and an honest header instead of an empty
  "unknown model" frame.
- **Degenerate-output gate** (#71): gates the visible content when present and
  falls back to reasoning text only when content is empty — a healthy thinking
  run is not branded degenerate, and a long reasoning trace can no longer
  dilute a stuck loop in the actual answer.
- **Doctor under launchd** (#72): engine checks now resolve brew/pip/binaries
  independently of PATH, so the web dashboard no longer reports installed
  engines as missing; a third-party service answering `/version` on :8000 is
  no longer mistaken for a running vllm-mlx.

## [1.26.0](https://github.com/druide67/asiai/compare/v1.25.0...v1.26.0) — 2026-07-10

### Added

- **Model picker on the six bench modes** (#65): the mode forms gain a real model
  select — loaded models of the chosen engine, Ollama installed models tagged
  "will load", and a custom free-text fallback. Empty still means auto.
- **Leaderboard v2 in the dashboard** (#64, #67): sortable columns, engine chips,
  tok/s bars and a result counter; new Quant / W / tok-s-per-W / Last-seen columns
  with freshness badges; a 30/90/365-day window selector; and a per-row drill-down
  listing individual submissions (served by the community API v2) with a link to
  each shareable card. Defensive rendering throughout — absent fields show "—".
- **Stacked UMA bars** (#63): the install modal's memory advisory now shows two
  bars on one scale — current use (with the to-be-freed portion hatched) and the
  projected after-load state, the preset cost tinted by verdict with its
  low→high uncertainty band.

### Changed

- Docs leaderboard page: the style and script previously duplicated across all
  nine locales moved to shared assets; the page gains the v2 columns (#66).
- Docs JSON-LD now derives softwareVersion and dateModified from the build
  instead of hardcoded stale values (#62).

## [1.25.0](https://github.com/druide67/asiai/compare/v1.24.0...v1.25.0) — 2026-07-09

### Added

- **Advisory UMA pre-flight** (#61): `asiai.fleet.plan.cohabitation_verdict()` judges
  whether a preset's memory cost fits next to what a node is already running —
  `fits` / `tight` / `jetsam-risk` / `thermal-risk` / `unknown`, computed on the
  pessimistic cost bound. Fail-closed: any unknown input degrades the verdict,
  never inflates it. Advisory only — nothing blocks an install.
- `GET /api/v1/plan?preset=&engine=` (node-local): fetches the preset cost from the
  `aisctl serve` planner (asiai-inference-server ≥ 0.11) and returns the verdict with
  projected free memory, eviction set and reasons. Degrades cleanly (`unknown` + note)
  when the companion or its planner endpoint is absent.
- Cockpit install modal: the memory-advisory block is now live — each preset choice
  fetches the target node's plan through the hub proxy and renders the verdict badge,
  projected free memory and eviction set. The confirm button is never gated.
- `iogpu.wired_limit_mb` (unprivileged sysctl) collected into memory info and used as
  a second ceiling in the verdict (caps `fits` at `tight`).

### Changed

- Per-node read proxy: query params now validate against per-param patterns
  (digit-only for the six existing endpoints — behavior unchanged; identifier
  grammars for the new `plan` entry).

## [1.24.0](https://github.com/druide67/asiai/compare/v1.23.0...v1.24.0) — 2026-07-09

Every bench remembered, every bench reportable, every bench runnable
from the dashboard.

### Added

- **All 7 bench types are now persisted** (#55): new `bench_runs` table —
  one row per complete run (agentic, burst, code, language, instruct,
  thinking-ablation, plus a session row for the standard bench) with a
  normalized headline (`score_primary` + an explicit `score_label`,
  because scores of different types must never read as comparable),
  quality-gate failures, and the full self-describing payload. Kept
  forever, like the benchmark history. The standard rows also gain the
  provenance fields they always computed but silently dropped
  (`output_degenerate`, `ttft_source`, `vram_estimated`,
  `engine_runner`, `extra_body`, `asiai_version`).
- **Markdown reports for every bench type** (#56): `--export FILE.md`
  renders a complete, unbiased report — headline with its label,
  metrics with ±CI95 and sample counts ("n=1 — no noise estimate" is
  printed, never hidden), run conditions including `extra_body`,
  quality gates (including refused rankings and judge-offline status),
  and provenance. `--export FILE.json` keeps the exact previous
  behavior; the per-mode `--*-output` flags become soft-deprecated
  aliases.
- **History goes multi-type** (#57): type chips on the History page
  chart any bench type's headline over time (one series per
  model × score label, red markers on gate-failed runs) with a per-run
  payload drill-down, backed by `GET /api/bench-runs` +
  `GET /api/bench-runs/{id}`.
- **Bench page v2** (#58): the six non-standard bench modes are now
  runnable from the dashboard with adaptive forms (suites, scenarios,
  burst sizes, optional loopback LLM judge — the judge API key comes
  from the server environment, never the form). Results persist
  automatically and render as a markdown report with copy/download,
  served by `GET /bench/report/{run_id}.md` for any persisted run.

### Changed

- `benchmark_process` rows (engine CPU/RSS per run) are no longer
  purged after 7 days — their volume matches the benchmark history
  they annotate, and the short window destroyed engine-RSS history.

## [1.23.0](https://github.com/druide67/asiai/compare/v1.22.0...v1.23.0) — 2026-07-08

Fleet polish: per-node Doctor in the cockpit, a local Community
Leaderboard page, a terminal view of the audit journal, and
design-system convergence.

### Added

- **Per-node Doctor drawer in the cockpit** (#51): every node's detail
  panel gains a "Doctor →" button that runs the node's health checks
  through the hub read proxy and renders them grouped by category
  (system / engine / database) with pass/warn/fail dots and
  click-to-copy fix commands. Web-safe category subset only.
- **Community Leaderboard page** (#52): `/leaderboard` renders the
  public community leaderboard in the local dashboard with "All" /
  "This machine" chip filters (matched on the local chip) and a
  debounced model filter. Backed by `GET /api/v1/leaderboard`
  (server-side 5-minute cache per chip/model, bounded key space,
  bounded query params).
- **`asiai fleet audit`** (#54): read the local fleet audit journal
  from the terminal — `--limit` (cap 1000), `--actor
  {machine,operator,loopback}`, `--status {ok,denied,error}`,
  `--since 30m/2h/1d`, `--json` (newest first; table is oldest first,
  `tail`-style). Malformed journal lines render instead of crashing,
  control characters are neutralized, and filtered views disclose
  their 1000-event search window. No redaction: this is the file's
  owner reading their own `0600` journal — the metadata whitelist
  remains exclusive to the MCP one-shot exchange (ADR 0001).

### Changed

- **Design-system convergence** (#50): the shared `--fl-*` tokens
  (track, subtle/elevated/hover borders) are now derived from the base
  palette instead of hardcoded twins — pixel-identical in dark and
  light, one source of truth for future theme work.

### Documentation

- Fleet guide: operator login scopes, agent audit access (MCP), and
  the four journal read paths by audience; MCP tool count caught up
  to 14 across README/FAQ/agent docs (#53).

## [1.22.0](https://github.com/druide67/asiai/compare/v1.21.0...v1.22.0) — 2026-07-07

Install preset picker — ending the silent-baseline trap.

### Added

- The cockpit's Install modal now offers a preset `<select>`: when the
  node ships tuned presets for the engine, the first is preselected, so
  the generic base manifest (wrong binary/context on tuned nodes) becomes
  an explicit choice rather than the accidental default. The confirm
  button waits for the preset list to load, so a fast confirmation can
  never fire an install with no preset. New `GET /api/v1/presets`
  (proxies the node's `aisctl serve`); the fleet command funnel accepts
  `args.preset` for `install` only. Companion:
  asiai-inference-server 0.10.0.

## [1.21.0](https://github.com/druide67/asiai/compare/v1.20.0...v1.21.0) — 2026-07-07

Per-node History and Doctor across the fleet.

### Added

- `GET /api/v1/doctor` (JSON twin of the `/doctor` page, web-safe
  category subset) and hub read proxies `GET /api/v1/fleet/{nickname}/{endpoint}`
  for history/benchmarks/engine-history/benchmark-process/doctor — each a
  single hardcoded node path with a digit-only query allowlist (no
  SSRF/write reach), rate-limited and concurrency-bounded. The History
  and Doctor pages gain a node picker that re-sources every chart/card
  through the proxy when a fleet is configured.

## [1.20.0](https://github.com/druide67/asiai/compare/v1.19.2...v1.20.0) — 2026-07-07

Fleet visibility for MCP agents, with a scoped audit-read path.

### Added

- Three read-only MCP tools — `get_fleet_snapshot`, `get_fleet_health`,
  `fleet_audit_tail` — so an agent can see the fleet, not just the local
  node.
- Scoped operator login codes: `asiai auth login --scope full|audit:read`.
  The scope is bound to the code at mint and cannot be widened at
  exchange; an `audit:read` code buys exactly one redacted, bounded,
  rate-limited audit-journal read (via `POST /api/v1/fleet/audit-tail` /
  the `fleet_audit_tail` tool) and can never open a write session. See
  `docs/adr/0001-audit-journal-read-for-local-agents.md`.

## [1.19.2](https://github.com/druide67/asiai/compare/v1.19.1...v1.19.2) — 2026-07-07

Live KV occupancy and observed throughput on the Monitor.

### Added

- Per-engine KV-cache occupancy read from llama.cpp `/slots` (the modern
  builds dropped the KV gauges from `/metrics`), filling the existing KV
  fields with a numbers-only privacy guard, and an observed decode-rate
  readout (`~N t/s`) next to the rolling token counter, averaged over a
  sliding window so a per-request counter bump doesn't misreport.

## [1.19.1](https://github.com/druide67/asiai/compare/v1.19.0...v1.19.1) — 2026-07-07

Monitor goes live — the page now visibly distinguishes itself from the
Dashboard's inventory view.

### Added

- Rolling per-engine token counters (rAF tween at the observed decode
  rate), an `INFERRING` pulse, TCP connection and request counts, a KV
  mini-bar, CPU+GPU sparklines, and a power total with GPU/CPU/ANE/DRAM
  breakdown — so an inferring engine is visible at a glance and an idle
  one sits still. Poll cadence 6 s on Monitor, 12 s on Dashboard.

### Fixed

- Prometheus parser truncated metric names at the namespace colon
  (`llamacpp:tokens_predicted_total`), so every llama.cpp activity metric
  read as zero fleet-wide. Names are now captured with the colon and
  normalized, covering both exposition styles.

## [1.19.0](https://github.com/druide67/asiai/compare/v1.18.0...v1.19.0) — 2026-07-07

Multi-node Dashboard and Monitor ("direction D"): both pages show the
whole fleet, not just the local node.

### Added

- A fleet ribbon (parc-wide aggregates) above every node rendered as its
  own read-only detail block, with multi-select chips to hide/show nodes
  and a per-block freshness badge (fresh/slow/stale on the poll time).
- `ui.css` — shared design-system primitives (tokens, status dots,
  badges, keyframes) extracted from the cockpit stylesheet so the pages
  and the cockpit stay visually consistent.

### Changed

- Dashboard and Monitor are read-only across the fleet; write actions
  stay in the Fleet cockpit ("manage in Fleet →"). The mono node-select
  in the topbar is gone (the chips replace it).

## [1.18.0](https://github.com/druide67/asiai/compare/v1.17.4...v1.18.0) — 2026-07-06

Global shell across the dashboard pages.

### Added

- A shared topbar (operator session + logout + Fleet link), a
  cross-page alert dot fed by a reduced `GET /api/v1/fleet/health-summary`,
  and cold-standby verbs (`enable`/`disable`) wired into the write funnel
  with a Standby/Enable menu.

### Changed

- Vendor scripts (htmx/SSE/ApexCharts) load per page instead of on every
  page — the cockpit, journal and login no longer carry unused payloads.

## [1.17.0](https://github.com/druide67/asiai/compare/v1.16.0...v1.17.4) — 2026-07-06

Rich engine lifecycle states in the fleet snapshot (companion to
asiai-inference-server 0.8), plus a cockpit dogfooding round.

### Added

- The snapshot joins the node's `aisctl serve` state so cards show the
  real lifecycle (running/stopped/disabled/available/not_installed) and
  the model a provisioned-but-idle engine would serve, not just an
  HTTP reachable/unreachable split. `AVAILABLE` badge + preset line for
  provisioned engines.

### Fixed

- Observed reality wins over launchd's paper state; cards sort by
  urgency and fold `not_installed`; honest Install verb; the model name
  behind a preset symlink is resolved for display.

## [1.16.0](https://github.com/druide67/asiai/compare/v1.15.0...v1.16.0) — 2026-07-05

The fleet cockpit — the human write surface for fleet mode.

### Added

- `GET /fleet`: a master-detail cockpit with live write actions
  (start/stop/restart/purge/load/unload/install/uninstall), a
  type-to-confirm gate on destructive verbs, and an audit-journal
  drawer. Writes go through the operator same-origin proxy
  (`POST /fleet/{nickname}/action`), which authenticates the operator
  session + CSRF and forwards to the target node holding its Bearer
  server-side — it never executes locally.

## [1.15.0](https://github.com/druide67/asiai/compare/v1.14.1...v1.15.0) — 2026-07-02

Fleet groundwork: one shared write-command spec, and a human operator
login for the dashboard. Purely additive — no breaking changes.

### Added

- `asiai.fleet.command_spec` — the single source of truth for fleet
  write-command timeouts and the command whitelist. Each command has one
  authoritative work budget; the edge/client HTTP deadlines are *derived*
  (budget + a margin per hop), so the nesting invariant
  `client > edge > loopback` holds by construction and the layers can no
  longer drift apart and kill a long-running command mid-write.
- Operator login for the web dashboard (`asiai auth login` + `/login`):
  ephemeral shell-bound authentication. The CLI mints a single-use,
  short-TTL, high-entropy code (only its salted hash touches disk); the
  operator pastes it into the login form and receives a server-side
  session behind an `HttpOnly; SameSite=Lax` cookie, with per-form CSRF
  and failure-only rate limiting. No human password is ever stored.
  Browser-facing write routes can now depend on
  `require_operator` / `require_operator_csrf`; the node-to-node Bearer
  path is unchanged.
- Audit log entries carry an `actor_type` field
  (`machine` / `operator` / `loopback`) so a human click and an
  orchestrator push are always distinguishable.
- Research: Qwen-AgentWorld-35B world-model evaluation brief (docs, 9
  locales).

## [1.14.1](https://github.com/druide67/asiai/compare/v1.14.0...v1.14.1) — 2026-06-24

OSS hygiene and a web dashboard fix.

### Fixed

- Web dashboard "models loaded" panel: a local engine that reports a
  symlinked `--model` path (e.g. `active.gguf`) now resolves to the real
  GGUF filename, and model sizes use the engine-reported `meta.size` rather
  than an identical-per-model footprint estimate. A remote engine surfaces
  the path basename only — its path is never `realpath`'d against the local
  filesystem.

### Changed

- Test fixtures use a neutral `testuser` login in simulated `ps` output
  instead of a personal username.
- The agentic-fixture anonymization gate now scans every git-tracked file
  under the fixtures tree (recursive, any extension) rather than only the
  top-level `*.json`, and rejects home paths (`/Users/`, `/home/`), RFC-1918
  LAN IPs, Claude Code internals (`/.claude/`) and the capturing user's login
  name. It previously missed nested session captures and `.log` files.

## [1.14.0](https://github.com/druide67/asiai/compare/v1.13.0...v1.14.0) — 2026-06-13

Audit follow-up (2026-06-11/12). Correctness, hardening and accuracy; no
breaking changes.

### Added

- Language bench: the documented accent-density floor is now implemented —
  `accent_stripped` per probe and `pct_accent_stripped` in the summary flag
  in-language answers that dropped their diacritics.
- Engine docs for vMLX and Rapid-MLX (the two adapters previously missing
  a page).

### Changed

- Benchmark CI95 reports `null` for a single run instead of a fake
  zero-width interval; the t-quantile uses the degrees of freedom pooled
  across prompt groups, consistent with the pooled standard deviation.
- Recommendation advisor compares only `metrics_version: 3` rows (the
  1.11.0 metrics generation) and its percentile is aligned on the
  reporter's linear interpolation, so p99 agrees across both surfaces.
- Docs accuracy: engine count corrected to 9 (adds vMLX + Rapid-MLX),
  manifest versions to 1.13.0, and the bench-modes page reframed as three
  *performance* modes plus four *quality* modes.

### Fixed

- Standard-runner SSE parser ignored `delta.reasoning` (mlx-lm spelling),
  starting the TTFT clock late and miscounting throughput under thinking
  mode.
- Burst mode: the timeout path double-counted already-consumed futures
  (inflating `n` and percentiles), silently dropped never-completing calls
  (now synthetic errors), and the pool context manager re-blocked on the
  abandoned futures — the very hang the timeout existed to prevent.
- The duplicate-process gate was inert for the `mlx-lm` / `omlx` / aux
  engine spellings (keys now normalized; patterns corrected).
- The IOReport power sampler leaked CoreFoundation objects on every
  sample — unbounded growth in the long-lived `asiai web` daemon — and
  raced across threads. All Create/Copy-rule objects are now released and
  `sample()`/`close()` are lock-guarded.
- `/api/v1/snapshot`, `/status` and `/metrics` ran the full (subprocess +
  per-engine HTTP) collection on the event loop; now off-loaded with
  `asyncio.to_thread`.
- 90-day retention is finally enforced: `purge_old()` is wired at monitor
  start. Benchmark history is exempt and kept forever.
- Agentic repeats: the cold phase is no longer contaminated by the
  previous repetition's cache.
- Fleet: `upsert_node` no longer wipes a stored `auth_token` on update;
  the `poll_all` aggregate timeout is no longer neutralized by the pool's
  blocking shutdown.
- `daemon_stop` surfaces a launchctl failure instead of reporting
  "stopped".
- Smaller correctness fixes: webhook HTTP status recorded, `engines.json`
  read-modify-write under a file lock, `--prompts` validated against known
  names, loopback TCP connection double-count, MCP tools moved off the
  event loop.

### Tests

- The suite is now hermetic: an autouse fixture isolates every
  user-facing path (DB, configs, fleet/auth state, daemon plists, cards,
  audit log) to a throwaway home, and a guard test (`test_hermetic.py`)
  fails loudly if a future change re-exposes a real path. Running the
  suite no longer migrates the real `metrics.db`.

## [1.13.0](https://github.com/druide67/asiai/compare/v1.12.0...v1.13.0) — 2026-06-07

### Added

- `asiai bench --instruct` loop-search scenarios — a perfectionist
  research-loop instruction-following evaluation (#27).

## [1.12.0](https://github.com/druide67/asiai/compare/v1.11.0...v1.12.0) — 2026-06-05

### Added

- Quality bench modes — `asiai bench --code`, `--language`, `--instruct`,
  `--thinking-ablation`: deterministic correctness and language-retention
  evaluations that need no LLM judge for the core signal (#25).
- Apple Silicon agentic inference comparison panel (research page).

## [1.11.0](https://github.com/druide67/asiai/compare/v1.10.0...v1.11.0) — 2026-06-02

Major benchmark instrumentation overhaul (`metrics_version: 3`).

### Added

- SoC (full package) power as the headline, with per-rail energy in the
  IOReport probe and decode-scoped energy across all modes.
- Deterministic output-validity gates, a cross-family-safe prefix-cache
  reuse signal, a SOLO clean-table gate, an `enable_thinking` guard, and
  the burst-mode probe.
- Agentic ≥5-run variance with a Student-t confidence interval, a live
  thermal signal, and decode warmup.

### Changed

- Unified samplers with an `ExitStack` / try-finally probe lifecycle,
  corrected token counting on a single decode formula, and a shared
  engine registry. Adversarial-review findings addressed.

## [1.10.0](https://github.com/druide67/asiai/compare/v1.9.1...v1.10.0) — 2026-06-01

### Added

- Unified power / thermal / memory instrumentation across every bench
  mode (#20).
- Per-engine memory footprint and KV-cache occupancy, with RSS as the
  cross-family headline and `phys_footprint` as a second column
  (#18, #19).

## [1.9.1](https://github.com/druide67/asiai/compare/v1.9.0...v1.9.1) — 2026-05-30

### Fixed

- Rapid-MLX is now a managed engine; fleet poll timeout honored;
  `asiai versions` show-all output (#17).

## [1.9.0](https://github.com/druide67/asiai/compare/v1.8.0...v1.9.0) — 2026-05-30

### Added

- `asiai versions` — running / installed / available engine versions,
  plus `aisctl upgrade` integration and a `/versions` web page (#15).

## [1.8.0](https://github.com/druide67/asiai/compare/v1.6.0...v1.8.0) — 2026-05-28

No 1.7.0 release was tagged.

### Added

- Fleet Phase 2 — authenticated cross-host writes (#13).
- Fleet Phase 1 — `/fleet` page and `/api/v1/fleet/*` endpoints, config,
  parallel polling, and CLI.
- Rapid-MLX engine adapter and `asiai bench --burst-mode`
  (US-METHOD-003).

### Fixed

- Fleet: dropped `0.0.0.0` from the TrustedHost allowlist (bandit B104);
  de-flaked the MemoryWatcher tests with active polling.

## [1.6.0](https://github.com/druide67/asiai/compare/v1.5.0...v1.6.0) — 2026-05-20

### Added — Agentic Bench Mode

`asiai bench --agentic-mode` introduces an 8-phase prefix cache reuse
protocol that measures the dominant cost pattern of multi-turn agent
workloads (long shared system prompt + per-turn user message). The
verdict (`yes`/`partial`/`no`) uses `cached_tokens` from streaming usage
where available and falls back to a TTFT cold/prefix-hit ratio for
engines that don't expose it.

Three independent quality gates run alongside the bench and emit their
findings under `result["quality_gates"]`:

- **`early_stop`** — flags phases where `completion_tokens` drops below
  50% of the requested `max_tokens` on two or more runs. Catches engines
  that accept a speculatively-drafted EOS token incorrectly under prefix
  cache reuse (the response still parses as valid OpenAI-compat but
  the engine silently returns truncated answers).
- **`memory_pressure`** — a background thread polls `vm_stat` and
  `vm.swapusage` every 15s. Alerts when swap usage grows >500 MB or
  swapouts grow >1000 from baseline — both signs that the OS is paging
  the model or KV cache to disk and the measured `tok/s` no longer
  represents the engine itself.
- **`duplicate_processes`** — a single `ps` snapshot before the bench
  rejects runs where two instances of the same engine are bound.

The JSON output bumps to `schema_version: agentic-v2` to carry the new
`quality_gates` block.

### Added — Reproducible cold starts via aisctl

`--agentic-auto-restart` calls `aisctl restart <engine>` before the
first phase and polls `/health` until ready. Useful for engines without
a model-unload API (llama.cpp, oMLX, TurboQuant). Strictly opt-in;
warns and proceeds when `aisctl` isn't available, or aborts when paired
with `--agentic-auto-restart-required`. Supported managed engines:
ollama, llamacpp, llamacpp-aux, lmstudio, omlx, turboquant, vmlx,
mlx-lm.

### Added — Methodology documentation

`docs/methodology.md` and `docs/methodology.fr.md` gain a dedicated
"Agentic Mode" section explaining the protocol, the verdict computation,
each quality gate, and the opt-in `aisctl` integration. The other seven
language editions will catch up in v1.6.1.

### Added — Integration fixtures

`tests/fixtures/agentic/` ships eight anonymized fixtures captured
against Qwen3.6 MTP variants on M4 Pro 64 GB and M5 Max 128 GB
(llama.cpp + mlx-lm × 27B + 35B-A3B). The integration test suite
replays each fixture through the gate detectors and verifies the
expected verdicts hold. The anonymization gate refuses fixtures
containing absolute home paths, `.local` hostname suffixes, or LAN IP
prefixes.

### Changed

- `agentic-mode` previously only printed the verdict line; now surfaces
  the three quality gates underneath with red warning markers when any
  trips.

### Tests

51 tests in the agentic suite (15 + 14 + 9 + 13). `ruff` clean.

## [1.5.0](https://github.com/druide67/asiai/compare/v1.4.1...v1.5.0) — 2026-04-01

### Added

- TurboQuant KV cache support — `--kv-cache` flag, detection, and a card
  chip — plus TurboQuant branding on benchmark cards.
- TurboQuant benchmark page (Llama 70B at 6.3 tok/s on M4 Pro 64 GB).

## [1.4.1](https://github.com/druide67/asiai/compare/v1.4.0...v1.4.1) — 2026-03-31

### Added

- Full i18n translations for all 35 documentation pages in 8 languages.

### Changed

- Unified "Precision Instrument" brand identity; WCAG accessibility pass;
  Mermaid diagrams.

### Fixed

- hreflang URLs on translated pages; remaining GEO/AEO meta-description
  gaps.

## [1.4.0](https://github.com/druide67/asiai/compare/v1.3.0...v1.4.0) — 2026-03-28

### Added

- Model unloading between benchmarks, with gate checks and adaptive
  cooldown.
- Universal VRAM estimate via `ri_phys_footprint` (footprint-based, all
  engines).
- Power metrics on the web Monitor and History pages.

## [1.3.0](https://github.com/druide67/asiai/compare/v1.2.0...v1.3.0) — 2026-03-27

### Added

- Redesigned web dashboard with self-hosted fonts and a demo video.

### Fixed

- Dashboard crash on `Undefined` values; winner display.

## [1.2.0](https://github.com/druide67/asiai/compare/v1.1.1...v1.2.0) — 2026-03-24

### Added

- Continuous power monitoring via IOReport without sudo, dual-source
  power in benchmarks with cross-validation, and always-on power.
- Bench page improvements — model dropdown and compare mode.

### Changed

- SEO: unique meta descriptions across all doc pages; homepage title,
  version, and Twitter card fixes.

## [1.1.1](https://github.com/druide67/asiai/compare/v1.1.0...v1.1.1) — 2026-03-22

### Fixed

- Packaging hotfix; no functional change.

## [1.1.0](https://github.com/druide67/asiai/compare/v1.0.1...v1.1.0) — 2026-03-22

### Added

- Cross-model benchmark comparison (`asiai bench --compare`).
- GitHub social preview image.

### Fixed

- Community client handles 429 rate-limit and 409 duplicate responses
  gracefully.

## [1.0.1](https://github.com/druide67/asiai/compare/v1.0.0...v1.0.1) — 2026-03-13

### Added

- `asiai bench --quick` / `-Q` — single prompt, single run (~15 seconds)
- `asiai bench --card` — shareable benchmark card (SVG locally, PNG with `--share`)
- `asiai setup` — interactive first-launch wizard (hardware, engines, models, next steps)
- `asiai version` subcommand — enriched output with chip, RAM, engines, daemon status
- MCP tool `compare_engines` — ranked engine comparison with verdict for a given model
- MCP tool `refresh_engines` — re-detect engines without restarting the server
- Architecture documentation page with data flow diagrams
- API versioned `/api/v1/` with backward-compatible 302 redirect from `/api/`
- Dynamic SVG badges on community API (`/badge/benchmarks`, `/badge/top-speed`)
- Enriched JSON-LD structured data on asiai.dev
- GitHub Actions `release.yml` — auto-publish to PyPI on git tag
- `pip-audit` in CI pipeline
- Dependabot for pip and GitHub Actions dependencies
- HSTS header on community API
- SQL injection test suite for community API (`tests/test_sql_injection.sh`)
- `asiai mcp --register` — opt-in anonymous agent network registration (ADR-001)
- `asiai unregister` — remove local agent credentials
- Agent network status in `asiai version` output ("Agent network: registered (#N)")
- Agent badge SVG in README (`/api/v1/agent-badge`)
- Benchmark card design v2c — hero number 72px, engine version labels, dynamic frame height
- Quick Bench on web dashboard (`/bench`) — 1-click benchmark with SSE progress + card + share
- Web dashboard share section — copy link, download PNG, share on X
- GPU observability: gpu_cores, context_size, ram_gb in benchmark data pipeline
- Web dashboard history page with engine activity charts and benchmark results
- Web dashboard process metrics (CPU/memory per engine)

### Changed

- PyPI classifier: `Development Status :: 5 - Production/Stable`
- CORS restricted to `https://asiai.dev` (was `*`)
- Install instructions: `pipx install asiai` recommended first in README
- Better error messages when no engines detected ("Try: brew install ollama && ollama serve")
- Silent migration failures now logged via `logging.warning()`
- Swagger API docs mentioned in README (`/docs` endpoint)
- CDN libs vendored locally (htmx, ApexCharts) — web dashboard works fully offline
- CSP tightened — no external `script-src`

### Fixed

- N+1 query in `query_history()` — single LEFT JOIN instead of 10K+ individual queries

## [1.0.0](https://github.com/druide67/asiai/compare/v0.7.0...v1.0.0) — 2026-03-08

### Added

- **Community Benchmark Database** — share and compare results with the community
  - `asiai bench --share` — opt-in anonymous submission to `api.asiai.dev`
  - `asiai leaderboard` — browse community benchmarks by chip and model
  - `asiai compare` — compare your results against community medians (delta tok/s, %)
  - Zero-dependency client (stdlib `urllib`), offline-first (network failures never block benchmarks)
  - Local audit trail in SQLite (`community_submissions` table)
- **Smart Recommendations** — `asiai recommend` suggests the best engine for your hardware
  - Three data sources by priority: local benchmarks → community data → heuristics
  - Scoring by use-case: `--use-case throughput|latency|efficiency`
  - RAM-aware model filtering (16 GB → 7B, 64 GB → 35B, 128 GB → 70B)
  - Confidence levels: high (5+ local runs), medium (1-4 runs), low (heuristic only)
- **Exo engine** — 6th inference engine for distributed inference across Apple Silicon devices
  - `OpenAICompatEngine` pattern (shared with 4 other engines), port 52415
  - Cluster topology display (node count, total VRAM)
  - `asiai doctor` checks Exo reachability
- **Community API backend** — `api.asiai.dev` (PHP 8 + MySQL)
  - 3 endpoints: POST /benchmarks, GET /leaderboard, GET /compare
  - Defense-in-depth: rate limiting (10/day), payload validation, IP anonymization (daily-salt SHA256), PDO prepared statements
  - Anonymous by design — no accounts, no tracking, GDPR-friendly

### Changed

- Homepage: 3 new feature cards (Community Leaderboard, Smart Recommendations, Distributed Inference) in 9 languages

## [0.7.0](https://github.com/druide67/asiai/compare/v0.6.0...v0.7.0) — 2026-03-07

### Added

- **Alert webhooks**: `asiai monitor --alert-webhook URL` — POST JSON alerts on state transitions (memory pressure, thermal throttling, engine down)
  - Transition-based alerting (fires on state change, not absolute value) with 5-minute cooldown per alert type
  - Fire-and-forget HTTP POST, alert history stored in SQLite
  - `asiai daemon start monitor --alert-webhook URL` — persistent alerting via launchd
- **LM Studio VRAM**: retrieves real VRAM usage via `~/.lmstudio/bin/lms ps --json` (API returns 0)
  - Fallback to `lms ls --json` for lazy-loading scenarios (model available but not yet actively loaded)
  - Graceful degradation: falls back to 0 if `lms` CLI is unavailable
  - VRAM data propagates automatically to monitor, benchmark, web dashboard, and Prometheus metrics
- `asiai doctor` now checks alerting webhook configuration and connectivity (new "alerting" category)
- `asiai doctor` now displays Ollama runtime parameters (host, num_parallel, max_loaded_models, keep_alive, flash_attention)
- `asiai models` now shows engine version alongside engine name (e.g., `ollama v0.17.5`)

## [0.6.0](https://github.com/druide67/asiai/compare/v0.5.1...v0.6.0) — 2026-03-07

### Added

- Multi-service LaunchAgent: `asiai daemon start web` — persistent web dashboard via launchd (`KeepAlive`, auto-restart on crash)
- `asiai daemon stop --all` — stop all services at once
- `asiai daemon status` — shows all registered services (monitor + web) with PID, port, interval
- `asiai daemon logs web` — separate log files per service
- `asiai doctor` now reports LaunchAgent status for each service (daemon category)
- `--port` and `--host` options for `asiai daemon start web`
- Security warning when binding web dashboard to non-localhost

## [0.5.1](https://github.com/druide67/asiai/compare/v0.5.0...v0.5.1) — 2026-03-07

### Fixed

- `__version__` now correctly reports 0.5.1 (was stuck at 0.4.0 in v0.5.0 package)

## [0.5.0](https://github.com/druide67/asiai/compare/v0.4.0...v0.5.0) — 2026-03-07

### Added

- REST API endpoints: `GET /api/snapshot`, `GET /api/status`, `GET /api/metrics` (Prometheus exposition format)
- Prometheus native metrics — 15 gauges covering system, engine, model, and benchmark data
- `asiai monitor --json` and `asiai models --json` for scripting and machine-to-machine integration
- Engine reachability persistence in SQLite (`engine_status` table) with uptime tracking
- Snapshot cache with configurable TTL in AppState for sub-500ms API responses
- `asiai web` — interactive web dashboard (FastAPI + htmx + ApexCharts), optional `pip install asiai[web]`
  - Dashboard with system info, engines, models, last benchmark summary
  - Real-time monitor with SSE (CPU sparkline, memory gauge, thermal, models)
  - Run benchmarks from the browser with live progress
  - History page with time-series charts and filterable data table
  - Doctor page with health check cards and refresh
  - Dark/light theme toggle with localStorage persistence
- `asiai bench --export FILE` — export benchmark results as JSON (schema_version, machine metadata, stats, raw runs)
- `context_length` in ModelInfo — displayed in `asiai models` output (Ollama via `/api/show`, llama.cpp via `/props`)
- Thermal drift detection — warns if tok/s decreases monotonically over 3+ runs (>5% drop)
- Statistics section in benchmark output — CI 95%, P50/P90/P99, IQR outlier detection
- Cooldown (3s) between engines during benchmark + token ratio warning
- Marketing homepage for docs site with i18n (6 languages: EN, FR, DE, ES, IT, PT)

## [0.4.0](https://github.com/druide67/asiai/compare/v0.3.0...v0.4.0) — 2026-03-04

### Added

- GitHub Actions CI (Python 3.11–3.13, macOS, lint + tests)
- GitHub issue and PR templates
- pytest-cov configuration with coverage reporting
- Tests for `cli_renderer.py` (all 9 render functions)
- MkDocs documentation site with mkdocs-material theme

### Fixed

- `--context-size` overflow: input tokens + max_tokens no longer exceeds the target context window

## [0.3.2](https://github.com/druide67/asiai/compare/v0.3.0...v0.3.2) — 2026-03-04

### Fixed

- Case-insensitive model matching for mlx-lm paths.
- Regression detection compares only matching prompt types.
- sudo capability check uses `powermetrics` directly instead of
  `sudo -n true`.

## [0.3.0](https://github.com/druide67/asiai/compare/v0.2.0...v0.3.0) — 2026-03-04

### Added

- **llama.cpp** engine adapter (5th engine, GGUF format, port 8080)
- **vllm-mlx** engine adapter (continuous batching, port 8000)
- `OpenAICompatEngine` base class — shared by LM Studio, mlx-lm, llama.cpp, vllm-mlx
- `asiai bench --runs N` — multi-run variance with mean +/- stddev and stability classification
- `asiai bench --power` — GPU power measurement via powermetrics (tok/s per watt)
- Model load time measurement (cold load vs warm)
- Regression detection — automatic comparison against historical baselines after each benchmark
- Process detection via `lsof` to distinguish OpenAI-compatible engines on shared ports
- Model availability pre-check with descriptive error messages (loaded/available model lists)

### Fixed

- French locale decimal comma crash in `ps aux` and `sysctl vm.loadavg` parsing
- Improved HTTP error messages (timeout, connection refused, connection error)
- ANSI color alignment in benchmark table (pad before coloring)
- Multi-engine monitor display (engines listed individually, models show engine column)

### Security

- Bounded HTTP response body reads (10 MB max) to prevent memory exhaustion
- Input validation: `--watch` minimum 1s, `--runs` capped at 100

## [0.2.0](https://github.com/druide67/asiai/compare/v0.1.0...v0.2.0) — 2026-03-01

### Added

- **mlx-lm** engine adapter (3rd engine, Apple MLX native, port 8080)
- `asiai doctor` — diagnostic checks for engines, system health, and database
- `asiai daemon start|stop|status|logs` — continuous monitoring via launchd
- `asiai tui` — interactive Textual dashboard (optional: `pip install asiai[tui]`)
- Integration test framework (`pytest --integration`)
- LM Studio version detection via app bundle plist fallback

## [0.1.0](https://github.com/druide67/asiai/releases/tag/v0.1.0) — 2026-02-28

### Added

- Initial release
- `asiai detect` — auto-detect Ollama and LM Studio engines
- `asiai models` — list loaded models across engines
- `asiai monitor` — system + inference snapshot with SQLite storage
- `asiai bench` — cross-engine benchmark with standardized prompts (code, tool_call, reasoning, long_gen)
- Per-process CPU% and RSS metrics in benchmark output
- Machine context header (chip, RAM, memory pressure)
- Cross-engine model name resolution (gemma2:9b vs gemma-2-9b)
- SQLite persistence with schema migrations and 90-day retention
- Zero external dependencies for core
- Homebrew tap distribution (`druide67/tap`)
