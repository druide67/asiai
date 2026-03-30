---
description: "LM Studio Benchmark auf Apple Silicon: schnellste MLX-Engine, Port 1234 Setup, VRAM-Nutzung und Vergleich mit Ollama."
---

# LM Studio

LM Studio ist die schnellste MLX-Inferenz-Engine auf Apple Silicon und bedient Modelle auf Port 1234 mit einer OpenAI-kompatiblen API. Auf M4 Pro 64 GB erreicht es 130 tok/s bei Qwen3-Coder-30B (MLX), fast 2x schneller als Ollamas llama.cpp-Backend für MoE-Modelle.

[LM Studio](https://lmstudio.ai) bietet eine OpenAI-kompatible API mit einer GUI zur Modellverwaltung.

## Installation

```bash
brew install --cask lm-studio
```

Starten Sie den lokalen Server aus der LM Studio App und laden Sie ein Modell.

## Details

| Eigenschaft | Wert |
|------------|------|
| Standardport | 1234 |
| API-Typ | OpenAI-kompatibel |
| VRAM-Berichterstattung | Ja (über `lms ps --json` CLI) |
| Modellformat | GGUF, MLX |
| Erkennung | `/lms/version`-Endpunkt oder App-Bundle-Plist |

## VRAM-Berichterstattung

Seit v0.7.0 ruft asiai die VRAM-Nutzung über das LM Studio CLI ab (`~/.lmstudio/bin/lms ps --json`). Dies liefert genaue Modellgrößendaten, die die OpenAI-kompatible API nicht bereitstellt.

Wenn das `lms`-CLI nicht installiert oder nicht verfügbar ist, fällt asiai elegant auf VRAM 0 zurück (gleiches Verhalten wie vor v0.7.0).

## Hinweise

- LM Studio unterstützt sowohl GGUF- als auch MLX-Modellformate.
- Die Versionserkennung nutzt den `/lms/version`-API-Endpunkt, mit Fallback auf die App-Bundle-Plist auf der Festplatte.
- Modellnamen verwenden typischerweise das HuggingFace-Format (z.B. `gemma-2-9b-it`).

## Siehe auch

Sehen Sie, wie LM Studio abschneidet: [Ollama vs LM Studio Benchmark](../ollama-vs-lmstudio.md)
