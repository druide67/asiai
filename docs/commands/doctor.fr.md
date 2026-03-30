---
description: "Diagnostiquer les problèmes d'inférence LLM sur Mac : asiai doctor vérifie la santé des moteurs, les conflits de ports, le chargement des modèles et l'état du GPU."
---

# asiai doctor

Diagnostiquer l'installation, les moteurs, la santé du système et la base de données.

## Utilisation

```bash
asiai doctor
```

## Sortie

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

## Vérifications

- **Système** : Détection Apple Silicon, RAM, pression mémoire, état thermique
- **Moteurs** : Accessibilité et version des 7 moteurs supportés ; paramètres d'exécution Ollama (host, num_parallel, max_loaded_models, keep_alive, flash_attention)
- **Base de données** : Version du schéma SQLite, taille, horodatage de la dernière entrée
- **Daemon** : Statut du LaunchAgent pour les services monitor et web
- **Alertes** : Configuration et connectivité de l'URL webhook
