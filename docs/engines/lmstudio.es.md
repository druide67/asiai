---
description: "Benchmark de LM Studio en Apple Silicon: motor MLX más rápido, configuración del puerto 1234, uso de VRAM y cómo se compara con Ollama."
---

# LM Studio

LM Studio es el motor de inferencia MLX más rápido en Apple Silicon, sirviendo modelos en el puerto 1234 con una API compatible con OpenAI. En M4 Pro 64GB, alcanza 130 tok/s con Qwen3-Coder-30B (MLX), casi 2x más rápido que el backend llama.cpp de Ollama para modelos MoE.

[LM Studio](https://lmstudio.ai) proporciona una API compatible con OpenAI con una interfaz gráfica para gestión de modelos.

## Instalación

```bash
brew install --cask lm-studio
```

Inicia el servidor local desde la app LM Studio, luego carga un modelo.

## Detalles

| Propiedad | Valor |
|----------|-------|
| Puerto por defecto | 1234 |
| Tipo de API | Compatible con OpenAI |
| Reporte de VRAM | Sí (vía CLI `lms ps --json`) |
| Formato de modelo | GGUF, MLX |
| Detección | Endpoint `/lms/version` o plist del bundle de la app |

## Reporte de VRAM

Desde v0.7.0, asiai obtiene el uso de VRAM del CLI de LM Studio (`~/.lmstudio/bin/lms ps --json`). Esto proporciona datos precisos del tamaño del modelo que la API compatible con OpenAI no expone.

Si el CLI `lms` no está instalado o no está disponible, asiai reporta la VRAM como 0 (mismo comportamiento que antes de v0.7.0).

## Notas

- LM Studio soporta formatos de modelo GGUF y MLX.
- La detección de versión usa el endpoint API `/lms/version`, con respaldo al plist del bundle de la app en disco.
- Los nombres de modelos típicamente usan el formato HuggingFace (ej. `gemma-2-9b-it`).

## Ver también

Mira cómo se compara LM Studio: [Benchmark Ollama vs LM Studio](../ollama-vs-lmstudio.md)
