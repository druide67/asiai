# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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
