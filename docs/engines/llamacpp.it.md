---
description: "Server llama.cpp su Mac: controllo di basso livello, porta 8080, metriche cache KV e risultati benchmark su Apple Silicon."
---

# llama.cpp

llama.cpp è il motore di inferenza C++ fondamentale per modelli GGUF, che offre il massimo controllo di basso livello su cache KV, conteggio thread e dimensione contesto sulla porta 8080. Alimenta il backend di Ollama ma può essere eseguito in modo indipendente per un tuning fine su Apple Silicon.

[llama.cpp](https://github.com/ggml-org/llama.cpp) è un motore di inferenza C++ ad alte prestazioni che supporta modelli GGUF.

## Installazione

```bash
brew install llama.cpp
llama-server -m model.gguf
```

## Dettagli

| Proprietà | Valore |
|----------|-------|
| Porta predefinita | 8080 |
| Tipo API | Compatibile con OpenAI |
| Report VRAM | No |
| Formato modello | GGUF |
| Rilevamento | Endpoint `/health` + `/props` o rilevamento processi `lsof` |

## Note

- llama.cpp condivide la porta 8080 con mlx-lm. asiai lo rileva tramite gli endpoint `/health` e `/props`.
- Il server può essere avviato con dimensioni di contesto e conteggi thread personalizzati per il tuning.

## Vedi anche

Confronta motori con `asiai bench --engines llamacpp` --- [scopri come](../benchmark-llm-mac.md)
