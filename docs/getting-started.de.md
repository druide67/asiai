# Erste Schritte

**Apple Silicon AI** — Multi-Engine LLM-Benchmark- und Monitoring-CLI.

asiai vergleicht Inferenz-Engines direkt auf Ihrem Mac. Laden Sie dasselbe Modell auf Ollama und LM Studio, starten Sie `asiai bench` und erhalten Sie die Zahlen. Kein Raten, kein Bauchgefühl — nur tok/s, TTFT, Energieeffizienz und Stabilität pro Engine.

## Schnellstart

```bash
brew tap druide67/tap
brew install asiai
```

Oder mit pip:

```bash
pip install asiai
```

Dann erkennen Sie Ihre Engines:

```bash
asiai detect
```

Und benchmarken:

```bash
asiai bench -m qwen3.5 --runs 3 --power
```

## Was wir messen

| Metrik | Beschreibung |
|--------|-------------|
| **tok/s** | Generierungsgeschwindigkeit (Tokens/Sek.), ohne Prompt-Verarbeitung |
| **TTFT** | Time to First Token — Prompt-Verarbeitungslatenz |
| **Power** | GPU-Leistungsaufnahme in Watt (`sudo powermetrics`) |
| **tok/s/W** | Energieeffizienz — Tokens pro Sekunde pro Watt |
| **Stability** | Lauf-zu-Lauf-Varianz: stabil (<5%), variabel (<10%), instabil (>10%) |
| **VRAM** | Speicherbedarf — nativ (Ollama, LM Studio) oder geschätzt via `ri_phys_footprint` (alle Engines) |
| **Thermal** | CPU-Throttling-Status und Geschwindigkeitsbegrenzung |

## Unterstützte Engines

| Engine | Port | API |
|--------|------|-----|
| [Ollama](https://ollama.com) | 11434 | Nativ |
| [LM Studio](https://lmstudio.ai) | 1234 | OpenAI-kompatibel |
| [mlx-lm](https://github.com/ml-explore/mlx-examples) | 8080 | OpenAI-kompatibel |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | 8080 | OpenAI-kompatibel |
| [oMLX](https://github.com/jundot/omlx) | 8000 | OpenAI-kompatibel |
| [vllm-mlx](https://github.com/vllm-project/vllm) | 8000 | OpenAI-kompatibel |

## Voraussetzungen

- macOS auf Apple Silicon (M1 / M2 / M3 / M4)
- Python 3.11+
- Mindestens eine lokal laufende Inferenz-Engine

## Keine Abhängigkeiten

Der Kern verwendet ausschließlich die Python-Standardbibliothek — `urllib`, `sqlite3`, `subprocess`, `argparse`. Kein `requests`, kein `psutil`, kein `rich`.

Optionale Extras:

- `asiai[tui]` — Textual Terminal-Dashboard
- `asiai[dev]` — pytest, ruff, pytest-cov
