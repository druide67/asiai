---
description: "Wie schnell ist Ollama auf Apple Silicon? Benchmark-Setup, Standardport (11434), Leistungstipps und Vergleich mit anderen Engines."
---

# Ollama

Ollama ist die beliebteste LLM-Inferenz-Engine für Mac, die ein llama.cpp-Backend mit GGUF-Modellen auf Port 11434 verwendet. In unseren Benchmarks auf M4 Pro 64 GB erreicht es 70 tok/s bei Qwen3-Coder-30B, ist aber 46% langsamer als LM Studio (MLX) beim Durchsatz.

[Ollama](https://ollama.com) ist der beliebteste lokale LLM-Runner. asiai nutzt seine native API.

## Installation

```bash
brew install ollama
ollama serve
ollama pull gemma2:9b
```

## Details

| Eigenschaft | Wert |
|------------|------|
| Standardport | 11434 |
| API-Typ | Nativ (nicht-OpenAI) |
| VRAM-Berichterstattung | Ja |
| Modellformat | GGUF |
| Ladezeitmessung | Ja (über `/api/generate`-Kaltstart) |

## Hinweise

- Ollama meldet die VRAM-Nutzung pro Modell, die asiai in Benchmark- und Monitor-Ausgaben anzeigt.
- Modellnamen verwenden das `Name:Tag`-Format (z.B. `gemma2:9b`, `qwen3.5:35b-a3b`).
- asiai sendet `temperature: 0` für deterministische Benchmark-Ergebnisse.

## Siehe auch

Sehen Sie, wie Ollama abschneidet: [Ollama vs LM Studio Benchmark](../ollama-vs-lmstudio.md)
