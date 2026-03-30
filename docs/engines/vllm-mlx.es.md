---
description: "vLLM-MLX en Apple Silicon: API compatible con vLLM sobre MLX, puerto 8000, métricas Prometheus y datos de benchmark."
---

# vllm-mlx

vLLM-MLX trae el framework de serving vLLM a Apple Silicon vía MLX, ofreciendo batching continuo y una API compatible con OpenAI en el puerto 8000. Puede alcanzar 400+ tok/s en modelos optimizados, convirtiéndolo en una de las opciones más rápidas para inferencia concurrente en Mac.

[vllm-mlx](https://github.com/vllm-project/vllm) trae batching continuo a Apple Silicon vía MLX.

## Instalación

```bash
pip install vllm-mlx
vllm serve mlx-community/gemma-2-9b-it-4bit
```

## Detalles

| Propiedad | Valor |
|----------|-------|
| Puerto por defecto | 8000 |
| Tipo de API | Compatible con OpenAI |
| Reporte de VRAM | No |
| Formato de modelo | MLX (safetensors) |
| Detección | Endpoint `/version` o detección de procesos `lsof` |

## Notas

- vllm-mlx soporta batching continuo, haciéndolo adecuado para el manejo de solicitudes concurrentes.
- Puede alcanzar 400+ tok/s en Apple Silicon con modelos optimizados.
- Usa la API estándar compatible con OpenAI de vLLM.

## Ver también

Compara motores con `asiai bench --engines vllm-mlx` --- [aprende cómo](../benchmark-llm-mac.md)
