---
description: "Configuración rápida de asiai: configura motores, prueba conexiones y verifica que tu Mac con Apple Silicon está listo para benchmarks de LLMs."
---

# asiai setup

Asistente de configuración interactivo para nuevos usuarios. Detecta tu hardware, busca motores de inferencia y sugiere los siguientes pasos.

## Uso

```bash
asiai setup
```

## Qué hace

1. **Detección de hardware** — identifica tu chip Apple Silicon y RAM
2. **Escaneo de motores** — busca motores de inferencia instalados (Ollama, LM Studio, mlx-lm, llama.cpp, oMLX, vllm-mlx, Exo)
3. **Verificación de modelos** — lista los modelos cargados en todos los motores detectados
4. **Estado del daemon** — muestra si el daemon de monitoreo está en ejecución
5. **Siguientes pasos** — sugiere comandos basados en el estado de tu configuración

## Ejemplo de salida

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

## Cuando no se encuentran motores

Si no se detectan motores, el asistente proporciona guía de instalación:

```
  Engines:
    No inference engines detected.

  To get started, install an engine:
    brew install ollama && ollama serve
    # or download LM Studio from https://lmstudio.ai
```
