---
description: "Consulta la versión de asiai, el entorno Python y el estado de registro del agente con un solo comando."
---

# asiai version

Muestra información de versión y del sistema.

## Uso

```bash
asiai version
asiai --version
```

## Salida

El subcomando `version` muestra contexto enriquecido del sistema:

```
asiai 1.0.1
  Apple M4 Pro, 64 GB RAM
  Engines: ollama, lmstudio
  Daemon: monitor, web
```

La opción `--version` muestra solo la cadena de versión:

```
asiai 1.0.1
```

## Casos de uso

- Verificación rápida del sistema en issues y reportes de bugs
- Recopilación de contexto del agente (chip, RAM, motores disponibles)
- Scripting: `VERSION=$(asiai version | head -1)`
