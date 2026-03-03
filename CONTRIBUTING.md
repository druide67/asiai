# Contributing to asiai

Thanks for your interest in contributing!

## Scope

asiai targets **macOS Apple Silicon only** (M1/M2/M3/M4). We don't accept PRs for Linux or Windows support.

## Setup

```bash
git clone https://github.com/druide67/asiai.git
cd asiai
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

For TUI development:
```bash
pip install -e ".[dev,tui]"
```

## Development workflow

```bash
# Run tests
pytest

# Run linter
ruff check src/ tests/
ruff format src/ tests/

# Integration tests (requires running engines)
pytest --integration -v
```

## Code conventions

- **Language**: all code, comments, docstrings, and commits in English
- **Style**: ruff, line-length 100, Google-style docstrings
- **Types**: type hints everywhere, no `Any` unless justified
- **Dependencies**: zero external dependencies for core. Optional extras only.
- **Security**: no `shell=True`, parameterized SQL, no telemetry

## Commits

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation
- `test:` tests
- `chore:` maintenance

## Pull requests

1. Fork the repo and create a branch from `main`
2. Add tests for new functionality
3. Ensure `pytest` and `ruff check` pass
4. Open a PR with a clear description

## Adding a new engine

1. Create `src/asiai/engines/yourengine.py` inheriting `OpenAICompatEngine` (or `InferenceEngine` for non-OpenAI APIs)
2. Add the engine to `cli.py` engine_map and `doctor.py`
3. Add detection logic in `detect.py`
4. Add tests in `tests/test_engines.py`
