---
description: "Diagnostica problemas de inferencia LLM en Mac: asiai doctor verifica el estado de los motores, conflictos de puertos, carga de modelos y estado de la GPU."
---

# asiai doctor

Diagnostica la instalación, motores, estado del sistema y base de datos.

## Uso

```bash
asiai doctor
```

## Salida

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

## Verificaciones

- **Sistema**: Detección de Apple Silicon, RAM, presión de memoria, estado térmico
- **Motor**: Accesibilidad y versión de los 7 motores soportados; parámetros de ejecución de Ollama (host, num_parallel, max_loaded_models, keep_alive, flash_attention)
- **Base de datos**: Versión del esquema SQLite, tamaño, marca de tiempo de la última entrada
- **Daemon**: Estado del LaunchAgent para los servicios de monitoreo y web
- **Alertas**: Configuración de URL del webhook y conectividad
