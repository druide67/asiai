# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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
