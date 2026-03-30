---
description: "LLM-Inferenzprobleme auf dem Mac diagnostizieren: asiai doctor prüft Engine-Gesundheit, Port-Konflikte, Modell-Laden und GPU-Status."
---

# asiai doctor

Installation, Engines, Systemgesundheit und Datenbank diagnostizieren.

## Verwendung

```bash
asiai doctor
```

## Ausgabe

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

## Prüfungen

- **System**: Apple-Silicon-Erkennung, RAM, Speicherdruck, thermischer Zustand
- **Engines**: Erreichbarkeit und Version aller 7 unterstützten Engines; Ollama-Laufzeitparameter (host, num_parallel, max_loaded_models, keep_alive, flash_attention)
- **Datenbank**: SQLite-Schemaversion, Größe, Zeitstempel des letzten Eintrags
- **Daemon**: LaunchAgent-Status für Monitor- und Web-Dienste
- **Alerting**: Webhook-URL-Konfiguration und Konnektivität
