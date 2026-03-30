---
description: "vLLM-MLX su Apple Silicon: API compatibile vLLM su MLX, porta 8000, metriche Prometheus e dati benchmark."
---

# vllm-mlx

vLLM-MLX porta il framework di serving vLLM su Apple Silicon via MLX, offrendo batching continuo e un'API compatibile con OpenAI sulla porta 8000. Può raggiungere 400+ tok/s su modelli ottimizzati, rendendolo una delle opzioni più veloci per l'inferenza concorrente su Mac.

[vllm-mlx](https://github.com/vllm-project/vllm) porta il batching continuo su Apple Silicon via MLX.

## Installazione

```bash
pip install vllm-mlx
vllm serve mlx-community/gemma-2-9b-it-4bit
```

## Dettagli

| Proprietà | Valore |
|----------|-------|
| Porta predefinita | 8000 |
| Tipo API | Compatibile con OpenAI |
| Report VRAM | No |
| Formato modello | MLX (safetensors) |
| Rilevamento | Endpoint `/version` o rilevamento processi `lsof` |

## Note

- vllm-mlx supporta il batching continuo, rendendolo adatto alla gestione di richieste concorrenti.
- Può raggiungere 400+ tok/s su Apple Silicon con modelli ottimizzati.
- Usa l'API standard compatibile con OpenAI di vLLM.

## Vedi anche

Confronta motori con `asiai bench --engines vllm-mlx` --- [scopri come](../benchmark-llm-mac.md)
