---
description: "Lista todos los modelos LLM cargados en los motores: consulta uso de VRAM, cuantización, longitud de contexto y formato de cada modelo."
---

# asiai models

Lista los modelos cargados en todos los motores detectados.

## Uso

```bash
asiai models
```

## Salida

```
ollama  v0.17.5  http://localhost:11434
  ● qwen3.5:35b-a3b                             26.0 GB Q4_K_M

lmstudio  v0.4.6  http://localhost:1234
  ● qwen3.5-35b-a3b                              9.2 GB    MLX
```

Muestra la versión del motor, nombre del modelo, uso de VRAM (cuando está disponible), formato y nivel de cuantización para cada motor.

La VRAM es reportada nativamente por Ollama y LM Studio. Para otros motores, asiai estima el uso de memoria mediante `ri_phys_footprint` (la huella física de macOS, igual que el Monitor de Actividad). Los valores estimados se etiquetan como "(est.)".
