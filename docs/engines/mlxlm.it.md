---
description: "Benchmark server mlx-lm su Mac: ottimale per modelli MoE, configurazione porta 8080 e dati prestazioni su Apple Silicon."
---

# mlx-lm

mlx-lm è il server di inferenza MLX di riferimento di Apple, che esegue modelli nativamente sulla GPU Metal tramite la porta 8080. È particolarmente efficiente per modelli MoE (Mixture of Experts) su Apple Silicon, sfruttando la memoria unificata per il caricamento a zero-copy dei modelli.

[mlx-lm](https://github.com/ml-explore/mlx-examples) esegue modelli nativamente su Apple MLX, fornendo un utilizzo efficiente della memoria unificata.

## Installazione

```bash
brew install mlx-lm
mlx_lm.server --model mlx-community/gemma-2-9b-it-4bit
```

## Dettagli

| Proprietà | Valore |
|----------|-------|
| Porta predefinita | 8080 |
| Tipo API | Compatibile con OpenAI |
| Report VRAM | No |
| Formato modello | MLX (safetensors) |
| Rilevamento | Endpoint `/version` o rilevamento processi `lsof` |

## Note

- mlx-lm condivide la porta 8080 con llama.cpp. asiai usa il probing API e il rilevamento processi per distinguere tra loro.
- I modelli usano il formato HuggingFace/community MLX (es. `mlx-community/gemma-2-9b-it-4bit`).
- L'esecuzione nativa MLX fornisce tipicamente eccellenti prestazioni su Apple Silicon.

## Vedi anche

Confronta motori con `asiai bench --engines mlxlm` --- [scopri come](../benchmark-llm-mac.md)
