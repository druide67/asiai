---
description: "Diagnostica problemi di inferenza LLM su Mac: asiai doctor verifica lo stato dei motori, conflitti di porta, caricamento modelli e stato GPU."
---

# asiai doctor

Diagnostica installazione, motori, stato del sistema e database.

## Uso

```bash
asiai doctor
```

## Output

```
Doctor

  System
    ✓ Apple Silicon       Mac Mini M4 Pro — Apple M4 Pro
    ✓ RAM                 64 GB total, 42% used
    ✓ Memory pressure     normal
    ✓ Thermal             nominal (100%)

  Engine
    ✓ Ollama              v0.17.5 — 1 model(s): qwen3.5:35b-a3b
    ✓ Ollama config       host=0.0.0.0:11434, num_parallel=1 (default), ...
    ✓ LM Studio           v0.4.6 — 1 model(s): qwen3.5-35b-a3b
    ✗ mlx-lm              not installed
    ✗ llama.cpp           not installed
    ✗ vllm-mlx            not installed

  Database
    ✓ SQLite              2.4 MB, last entry: 1m ago

  Daemon
    ✓ Monitoring daemon   running PID 1234
    ✓ Web dashboard       not installed

  Alerting
    ✓ Webhook URL         https://hooks.slack.com/services/...
    ✓ Webhook reachable   HTTP 200

  9 ok, 0 warning(s), 3 failed
```

## Controlli

- **Sistema**: Rilevamento Apple Silicon, RAM, pressione memoria, stato termico
- **Motore**: Raggiungibilità e versione per tutti i 7 motori supportati; parametri runtime di Ollama (host, num_parallel, max_loaded_models, keep_alive, flash_attention)
- **Database**: Versione schema SQLite, dimensione, timestamp dell'ultima entry
- **Daemon**: Stato LaunchAgent per i servizi di monitoraggio e web
- **Avvisi**: Configurazione URL webhook e connettività
