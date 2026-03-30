---
description: "Benchmark del servidor mlx-lm en Mac: óptimo para modelos MoE, configuración del puerto 8080 y datos de rendimiento en Apple Silicon."
---

# mlx-lm

mlx-lm es el servidor de inferencia MLX de referencia de Apple, ejecutando modelos nativamente en GPU Metal a través del puerto 8080. Es particularmente eficiente para modelos MoE (Mixture of Experts) en Apple Silicon, aprovechando la memoria unificada para carga de modelos sin copia.

[mlx-lm](https://github.com/ml-explore/mlx-examples) ejecuta modelos nativamente en Apple MLX, proporcionando utilización eficiente de memoria unificada.

## Instalación

```bash
brew install mlx-lm
mlx_lm.server --model mlx-community/gemma-2-9b-it-4bit
```

## Detalles

| Propiedad | Valor |
|----------|-------|
| Puerto por defecto | 8080 |
| Tipo de API | Compatible con OpenAI |
| Reporte de VRAM | No |
| Formato de modelo | MLX (safetensors) |
| Detección | Endpoint `/version` o detección de procesos `lsof` |

## Notas

- mlx-lm comparte el puerto 8080 con llama.cpp. asiai usa sondeo de API y detección de procesos para distinguir entre ellos.
- Los modelos usan el formato HuggingFace/comunidad MLX (ej. `mlx-community/gemma-2-9b-it-4bit`).
- La ejecución nativa MLX típicamente proporciona excelente rendimiento en Apple Silicon.

## Ver también

Compara motores con `asiai bench --engines mlxlm` --- [aprende cómo](../benchmark-llm-mac.md)
