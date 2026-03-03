# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased](https://github.com/druide67/asiai/compare/v0.2.0...HEAD) — v0.3.0-dev

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

