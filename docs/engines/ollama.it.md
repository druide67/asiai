---
description: "Quanto è veloce Ollama su Apple Silicon? Configurazione benchmark, porta predefinita (11434), consigli prestazioni e confronto con altri motori."
---

# Ollama

Ollama è il motore di inferenza LLM più popolare per Mac, usando un backend llama.cpp con modelli GGUF sulla porta 11434. Nei nostri benchmark su M4 Pro 64GB, raggiunge 70 tok/s con Qwen3-Coder-30B ma è il 46% più lento di LM Studio (MLX) nel throughput.

[Ollama](https://ollama.com) è il runner LLM locale più popolare. asiai usa la sua API nativa.

## Installazione

```bash
brew install ollama
ollama serve
ollama pull gemma2:9b
```

## Dettagli

| Proprietà | Valore |
|----------|-------|
| Porta predefinita | 11434 |
| Tipo API | Nativa (non OpenAI) |
| Report VRAM | Sì |
| Formato modello | GGUF |
| Misurazione tempo di caricamento | Sì (via avvio a freddo `/api/generate`) |

## Note

- Ollama riporta l'utilizzo VRAM per modello, che asiai mostra nell'output di benchmark e monitor.
- I nomi dei modelli usano il formato `name:tag` (es. `gemma2:9b`, `qwen3.5:35b-a3b`).
- asiai invia `temperature: 0` per risultati benchmark deterministici.

## Vedi anche

Guarda come si confronta Ollama: [Benchmark Ollama vs LM Studio](../ollama-vs-lmstudio.md)
