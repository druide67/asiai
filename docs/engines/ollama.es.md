---
description: "¿Qué tan rápido es Ollama en Apple Silicon? Configuración de benchmark, puerto por defecto (11434), consejos de rendimiento y comparación con otros motores."
---

# Ollama

Ollama es el motor de inferencia LLM más popular para Mac, usando un backend llama.cpp con modelos GGUF en el puerto 11434. En nuestros benchmarks con M4 Pro 64GB, alcanza 70 tok/s con Qwen3-Coder-30B pero es un 46% más lento que LM Studio (MLX) en rendimiento.

[Ollama](https://ollama.com) es el ejecutor de LLM local más popular. asiai usa su API nativa.

## Instalación

```bash
brew install ollama
ollama serve
ollama pull gemma2:9b
```

## Detalles

| Propiedad | Valor |
|----------|-------|
| Puerto por defecto | 11434 |
| Tipo de API | Nativa (no OpenAI) |
| Reporte de VRAM | Sí |
| Formato de modelo | GGUF |
| Medición de tiempo de carga | Sí (vía arranque en frío de `/api/generate`) |

## Notas

- Ollama reporta el uso de VRAM por modelo, que asiai muestra en la salida de benchmark y monitor.
- Los nombres de modelos usan el formato `name:tag` (ej. `gemma2:9b`, `qwen3.5:35b-a3b`).
- asiai envía `temperature: 0` para resultados de benchmark deterministas.

## Ver también

Mira cómo se compara Ollama: [Benchmark Ollama vs LM Studio](../ollama-vs-lmstudio.md)
