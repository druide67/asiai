---
description: "Benchmark de oMLX en Apple Silicon: caché KV en SSD, batching continuo, puerto 8000 y comparación de rendimiento."
---

# oMLX

oMLX es un servidor de inferencia nativo para macOS que usa caché KV paginada en SSD para manejar ventanas de contexto más grandes de lo que la memoria sola permitiría, con batching continuo para solicitudes concurrentes en el puerto 8000. Soporta APIs compatibles con OpenAI y Anthropic en Apple Silicon.

[oMLX](https://omlx.ai/) es un servidor de inferencia LLM nativo para macOS con caché KV paginada en SSD y batching continuo, gestionado desde la barra de menú. Construido sobre MLX para Apple Silicon.

## Instalación

```bash
brew tap jundot/omlx https://github.com/jundot/omlx
brew install omlx
```

O descarga el `.dmg` desde las [releases de GitHub](https://github.com/jundot/omlx/releases).

## Detalles

| Propiedad | Valor |
|----------|-------|
| Puerto por defecto | 8000 |
| Tipo de API | Compatible con OpenAI + Compatible con Anthropic |
| Reporte de VRAM | No |
| Formato de modelo | MLX (safetensors) |
| Detección | Endpoint JSON `/admin/info` o página HTML `/admin` |
| Requisitos | macOS 15+, Apple Silicon (M1+), 16 GB RAM mín. |

## Notas

- oMLX comparte el puerto 8000 con vllm-mlx. asiai usa el sondeo de `/admin/info` para distinguir entre ellos.
- La caché KV en SSD permite ventanas de contexto más grandes con menor presión de memoria.
- El batching continuo mejora el rendimiento bajo solicitudes concurrentes.
- Soporta LLMs de texto, modelos visión-lenguaje, modelos OCR, embeddings y rerankers.
- El panel de administración en `/admin` proporciona métricas del servidor en tiempo real.
- Actualización automática integrada cuando se instala vía `.dmg`.

## Ver también

Compara motores con `asiai bench --engines omlx` --- [aprende cómo](../benchmark-llm-mac.md)
