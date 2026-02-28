# asiai

> Multi-engine LLM benchmark & monitoring CLI for Apple Silicon.

**asiai** (ASI + AI) turns your Mac into a professional inference station: one tool to manage Ollama, LM Studio, and vLLM, benchmark your models, and monitor your VRAM in real-time.

## Status

Pre-alpha. Not yet functional.

## Features (planned)

- **`asiai detect`** — Auto-detect installed inference engines
- **`asiai bench`** — Cross-engine benchmark (tok/s, TTFT, VRAM, thermal)
- **`asiai monitor`** — Real-time monitoring with SQLite history
- **`asiai models`** — List loaded models across all engines
- **`asiai recommend`** — Hardware-aware engine + model recommendation

## Requirements

- macOS on Apple Silicon (M1/M2/M3/M4)
- Python 3.11+
- At least one inference engine: [Ollama](https://ollama.com), [LM Studio](https://lmstudio.ai), or mlx-lm

## Install

```bash
# From PyPI (when published)
pipx install asiai

# From source
git clone https://github.com/druide67/asiai.git
cd asiai
pip install -e .
```

## License

Apache 2.0
