---
description: "Configurazione rapida di asiai: configura motori, testa connessioni e verifica che il tuo Mac Apple Silicon sia pronto per i benchmark LLM."
---

# asiai setup

Procedura guidata interattiva per i nuovi utenti. Rileva il tuo hardware, cerca i motori di inferenza e suggerisce i passi successivi.

## Uso

```bash
asiai setup
```

## Cosa fa

1. **Rilevamento hardware** — identifica il tuo chip Apple Silicon e la RAM
2. **Scansione motori** — cerca i motori di inferenza installati (Ollama, LM Studio, mlx-lm, llama.cpp, oMLX, vllm-mlx, Exo)
3. **Controllo modelli** — elenca i modelli caricati su tutti i motori rilevati
4. **Stato daemon** — mostra se il daemon di monitoraggio è in esecuzione
5. **Passi successivi** — suggerisce comandi in base allo stato della configurazione

## Output di esempio

```
  Setup Wizard

  Hardware:  Apple M4 Pro, 64 GB RAM

  Engines:
    ✓ ollama (v0.17.7) — 3 models loaded
    ✓ lmstudio (v0.4.5) — 1 model loaded

  Daemon: running (monitor + web)

  Suggested next steps:
    • asiai bench              Run your first benchmark
    • asiai monitor --watch    Watch metrics live
    • asiai web                Open the dashboard
```

## Quando non vengono trovati motori

Se non vengono rilevati motori, la procedura guidata fornisce indicazioni per l'installazione:

```
  Engines:
    No inference engines detected.

  To get started, install an engine:
    brew install ollama && ollama serve
    # or download LM Studio from https://lmstudio.ai
```
