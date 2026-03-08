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

## Translations

The homepage and documentation are available in 9 languages: EN, FR, DE, ES, IT, PT, ZH, JA, KO.

Chinese, Japanese, and Korean translations were machine-generated and **need native speaker review**. If you're a native speaker, we'd love your help:

1. Open the relevant [translation review issue](https://github.com/druide67/asiai/issues?q=label%3Atranslation)
2. Review the ~90 strings in `overrides/home.html` (search for `"zh":`, `"ja":`, or `"ko":`)
3. Submit a PR with corrections

This is a great `good first issue` — no code knowledge required, just language skills.

## Adding a new engine

1. Create `src/asiai/engines/yourengine.py` inheriting `OpenAICompatEngine` (or `InferenceEngine` for non-OpenAI APIs)
2. Add the engine to `cli.py` engine_map and `doctor.py`
3. Add detection logic in `detect.py`
4. Add tests in `tests/test_engines.py`
