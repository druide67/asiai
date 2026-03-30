---
description: "Benchmark LM Studio su Apple Silicon: motore MLX più veloce, configurazione porta 1234, utilizzo VRAM e confronto con Ollama."
---

# LM Studio

LM Studio è il motore di inferenza MLX più veloce su Apple Silicon, servendo modelli sulla porta 1234 con un'API compatibile con OpenAI. Su M4 Pro 64GB, raggiunge 130 tok/s con Qwen3-Coder-30B (MLX), quasi 2x più veloce del backend llama.cpp di Ollama per i modelli MoE.

[LM Studio](https://lmstudio.ai) fornisce un'API compatibile con OpenAI con una GUI per la gestione dei modelli.

## Installazione

```bash
brew install --cask lm-studio
```

Avvia il server locale dall'app LM Studio, poi carica un modello.

## Dettagli

| Proprietà | Valore |
|----------|-------|
| Porta predefinita | 1234 |
| Tipo API | Compatibile con OpenAI |
| Report VRAM | Sì (via CLI `lms ps --json`) |
| Formato modello | GGUF, MLX |
| Rilevamento | Endpoint `/lms/version` o plist del bundle dell'app |

## Report VRAM

Dalla v0.7.0, asiai recupera l'utilizzo VRAM dal CLI di LM Studio (`~/.lmstudio/bin/lms ps --json`). Questo fornisce dati accurati sulla dimensione del modello che l'API compatibile con OpenAI non espone.

Se il CLI `lms` non è installato o non è disponibile, asiai riporta la VRAM come 0 (stesso comportamento prima della v0.7.0).

## Note

- LM Studio supporta formati modello GGUF e MLX.
- Il rilevamento della versione usa l'endpoint API `/lms/version`, con fallback al plist del bundle dell'app su disco.
- I nomi dei modelli usano tipicamente il formato HuggingFace (es. `gemma-2-9b-it`).

## Vedi anche

Guarda come si confronta LM Studio: [Benchmark Ollama vs LM Studio](../ollama-vs-lmstudio.md)
