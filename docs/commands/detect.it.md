---
description: Rilevamento automatico dei motori di inferenza LLM sul tuo Mac. Cascata a 3 livelli — configurazione, scansione porte, rilevamento processi.
---

# asiai detect

Rilevamento automatico dei motori di inferenza con cascata a 3 livelli.

## Uso

```bash
asiai detect                      # Rilevamento automatico (cascata a 3 livelli)
asiai detect --url http://host:port  # Scansiona solo URL specifici
```

## Output

```
Detected engines:

  ● ollama 0.17.4
    URL: http://localhost:11434

  ● lmstudio 0.4.5
    URL: http://localhost:1234
    Running: 1 model(s)
      - qwen3.5-35b-a3b  MLX

  ● omlx 0.9.2
    URL: http://localhost:8800
```

## Come funziona: rilevamento a 3 livelli

asiai utilizza una cascata di tre livelli di rilevamento, dal più veloce al più approfondito:

### Livello 1: Configurazione (più veloce, ~100ms)

Legge `~/.config/asiai/engines.json` — motori scoperti nelle esecuzioni precedenti. Questo rileva motori su porte non standard (es. oMLX su 8800) senza dover riscansionare.

### Livello 2: Scansione porte (~200ms)

Scansiona le porte predefinite più un range esteso:

| Porta | Motore |
|------|--------|
| 11434 | Ollama |
| 1234 | LM Studio |
| 8080 | mlx-lm o llama.cpp |
| 8000-8009 | oMLX o vllm-mlx |
| 52415 | Exo |

### Livello 3: Rilevamento processi (fallback)

Usa `ps` e `lsof` per trovare processi motore in ascolto su qualsiasi porta. Rileva motori in esecuzione su porte completamente inaspettate.

### Persistenza automatica

Qualsiasi motore scoperto al Livello 2 o 3 viene automaticamente salvato nel file di configurazione (Livello 1) per un rilevamento più rapido la volta successiva. Le entry autodiscoverte vengono eliminate dopo 7 giorni di inattività.

Quando più motori condividono una porta (es. mlx-lm e llama.cpp su 8080), asiai usa il probing degli endpoint API per identificare il motore corretto.

## URL espliciti

Usando `--url`, vengono scansionati solo gli URL specificati. Nessuna configurazione viene letta o scritta — utile per controlli una tantum.

```bash
asiai detect --url http://192.168.0.16:11434,http://localhost:8800
```

## Vedi anche

- [config](config.md) — Gestire la configurazione persistente dei motori
