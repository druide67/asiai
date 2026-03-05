# AGENTS.md — asiai

Guidelines for AI agents contributing to this project.

## Project

**asiai** — open-source CLI to manage, benchmark, and monitor local LLM inference on Apple Silicon.

- **Language**: Python 3.11+, zero external dependencies for the core (stdlib only)
- **Target**: macOS Apple Silicon only (M1/M2/M3/M4). No Linux, no Windows.
- **License**: Apache 2.0

## Architecture

```
src/asiai/
├── cli.py              # CLI entry point (argparse)
├── doctor.py           # Installation and environment diagnostics
├── daemon.py           # launchd daemon management (continuous monitoring)
├── engines/            # Engine adapters (5 engines)
│   ├── base.py         # ABC InferenceEngine + dataclasses
│   ├── openai_compat.py # Base class for OpenAI-compatible engines (template method)
│   ├── detect.py       # Auto-detection (ports 11434, 1234, 8080, 8000)
│   ├── ollama.py       # Ollama adapter (native API)
│   ├── lmstudio.py     # LM Studio adapter (OpenAI-compatible)
│   ├── mlxlm.py        # mlx-lm adapter (OpenAI-compatible, Apple MLX native)
│   ├── llamacpp.py     # llama.cpp adapter (OpenAI-compatible, GGUF)
│   └── vllm_mlx.py     # vllm-mlx adapter (OpenAI-compatible, MLX)
├── collectors/         # Metric collectors (system, inference, power, macOS native)
│   └── power.py        # PowerMonitor (sudo powermetrics, GPU/CPU watts)
├── benchmark/          # Runner + standardized prompts + reporter + regression
│   └── regression.py   # Regression detection vs SQLite history
├── storage/            # SQLite (schema, migrations, dataclasses)
├── advisor/            # Hardware-aware recommendations
├── display/            # Renderers (CLI, TUI, Web)
│   ├── cli_renderer.py # CLI rendering (detect, bench, doctor, monitor)
│   ├── formatters.py   # Formatting helpers (ANSI, bytes, uptime)
│   ├── tui.py          # Textual dashboard (optional)
│   └── tui.tcss        # Textual styles
└── web/                # Web dashboard (optional: pip install asiai[web])
    ├── app.py          # FastAPI factory + lifespan + Jinja2
    ├── state.py        # AppState + BenchStatus dataclasses
    ├── routes/         # Route handlers (dashboard, bench, monitor, history, doctor)
    ├── templates/      # Jinja2 templates + partials
    └── static/         # CSS + JS (ApexCharts config)
```

**Key pattern**: Shared Data Layer — business logic (SQLite, engine APIs) is shared between CLI, TUI, and Web. Only the renderer differs.

## Dev commands

```bash
# Dev install
pip install -e ".[dev]"

# With TUI
pip install -e ".[dev,tui]"

# With web dashboard
pip install -e ".[dev,web]"

# Unit tests
pytest

# Integration tests (real engines required)
pytest --integration -v

# Lint
ruff check src/ tests/
ruff format src/ tests/
```

## Code rules

### Style

- **Language**: all English (code, comments, commits, README, docs)
- **Formatting**: ruff, line-length 100
- **Types**: type hints everywhere, no `Any` unless justified
- **Docstrings**: Google style, in English
- **Imports**: isort via ruff (I)

### Architecture

- **Zero core dependencies**: the core (engines, collectors, storage) depends only on the Python stdlib. Optional dependencies (rich, textual, fastapi) are extras.
- **Engine adapters**: each engine implements `InferenceEngine` (ABC). 4 OpenAI-compatible engines inherit from `OpenAICompatEngine` (template method). Adding an engine = adding a file in `engines/`.
- **macOS native**: use sysctl, vm_stat, pmset, IOReport for metrics. No psutil.
- **SQLite**: versioned schema with migrations. Automatic 90-day retention.

### Tests

- **pytest** required for all new code
- **Mocks**: mock HTTP calls (no real Ollama/LM Studio/mlx-lm server in CI)
- **No tests requiring Apple Silicon hardware** in CI (mark with `@pytest.mark.apple_silicon`)
- **Integration tests**: `pytest --integration -v` (real engines required, skipped by default)

### Commits

- **Format**: Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`)
- **Language**: English

### Security

- **Never add telemetry**: no network calls except to local engines
- **No secrets**: the tool does not manage tokens/keys
- **subprocess**: always use list of args (no `shell=True`)
- **SQLite**: use bound parameters (no f-strings in queries)

### Exception handling

- **Never silent `except: pass`**: always at least `logger.debug()` with the error message
- **Expected exceptions** (network, process): `except (URLError, OSError) as e: logger.debug(...)`
- **User errors**: descriptive messages with context (model, engine, URL) — no generic "request failed"
- **HTTP pattern**: `http_get_json` / `http_post_json` return `(None, {})` on failure with debug logging

### CLI output

- **Colors**: `red("✗")` errors, `yellow("⚠")` warnings, `green("✓"/"●")` success, `dim()` secondary info, `bold()` titles
- **NO_COLOR**: respected via `_supports_color()` in `formatters.py`
- **ANSI alignment**: always pad the string BEFORE applying color (`green(f"{text:<12}")` not `f"{green(text):<12}"`)
- **stderr**: errors and warnings to `sys.stderr`, normal data to stdout

### Locale safety

- **`ps aux`** and **`sysctl -n vm.loadavg`**: affected by locale (FR decimal comma). Always `.replace(",", ".")` before `float()`.
- **`vm_stat`, `powermetrics`**: use C/POSIX locale, no risk.
- **General rule**: any `float()` on system command output must handle the decimal separator.

### Web dashboard

- **Backend**: FastAPI with async routes, Jinja2 templates, auto-escaping enabled
- **Frontend**: htmx for partial updates, SSE for real-time, ApexCharts for charts
- **Security headers**: CSP, X-Frame-Options, X-Content-Type-Options via middleware
- **CDN resources**: must include SRI integrity hashes
- **No innerHTML**: use safe DOM methods (createElement, textContent) for dynamic content
- **Theme**: dark/light toggle via CSS custom properties and `data-theme` attribute
