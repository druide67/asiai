---
description: "Benchmark oMLX su Apple Silicon: cache KV su SSD, batching continuo, porta 8000 e confronto prestazioni."
---

# oMLX

oMLX è un server di inferenza nativo per macOS che usa la cache KV paginata su SSD per gestire finestre di contesto più grandi di quanto la sola memoria consentirebbe, con batching continuo per richieste concorrenti sulla porta 8000. Supporta API compatibili con OpenAI e Anthropic su Apple Silicon.

[oMLX](https://omlx.ai/) è un server di inferenza LLM nativo per macOS con cache KV paginata su SSD e batching continuo, gestito dalla barra dei menu. Costruito su MLX per Apple Silicon.

## Installazione

```bash
brew tap jundot/omlx https://github.com/jundot/omlx
brew install omlx
```

Oppure scarica il `.dmg` dalle [release GitHub](https://github.com/jundot/omlx/releases).

## Dettagli

| Proprietà | Valore |
|----------|-------|
| Porta predefinita | 8000 |
| Tipo API | Compatibile con OpenAI + Compatibile con Anthropic |
| Report VRAM | No |
| Formato modello | MLX (safetensors) |
| Rilevamento | Endpoint JSON `/admin/info` o pagina HTML `/admin` |
| Requisiti | macOS 15+, Apple Silicon (M1+), 16 GB RAM min. |

## Note

- oMLX condivide la porta 8000 con vllm-mlx. asiai usa il probing di `/admin/info` per distinguere tra loro.
- La cache KV su SSD consente finestre di contesto più grandi con minore pressione di memoria.
- Il batching continuo migliora il throughput sotto richieste concorrenti.
- Supporta LLM testuali, modelli visione-linguaggio, modelli OCR, embedding e reranker.
- La dashboard admin su `/admin` fornisce metriche del server in tempo reale.
- Aggiornamento automatico integrato quando installato via `.dmg`.

## Vedi anche

Confronta motori con `asiai bench --engines omlx` --- [scopri come](../benchmark-llm-mac.md)
