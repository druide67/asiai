---
description: "Servidor llama.cpp en Mac: control de bajo nivel, puerto 8080, métricas de caché KV y resultados de benchmark en Apple Silicon."
---

# llama.cpp

llama.cpp es el motor de inferencia fundamental en C++ para modelos GGUF, ofreciendo máximo control de bajo nivel sobre la caché KV, conteo de hilos y tamaño de contexto en el puerto 8080. Alimenta el backend de Ollama pero puede ejecutarse de forma independiente para ajuste fino en Apple Silicon.

[llama.cpp](https://github.com/ggml-org/llama.cpp) es un motor de inferencia C++ de alto rendimiento que soporta modelos GGUF.

## Instalación

```bash
brew install llama.cpp
llama-server -m model.gguf
```

## Detalles

| Propiedad | Valor |
|----------|-------|
| Puerto por defecto | 8080 |
| Tipo de API | Compatible con OpenAI |
| Reporte de VRAM | No |
| Formato de modelo | GGUF |
| Detección | Endpoints `/health` + `/props` o detección de procesos `lsof` |

## Notas

- llama.cpp comparte el puerto 8080 con mlx-lm. asiai lo detecta mediante los endpoints `/health` y `/props`.
- El servidor puede iniciarse con tamaños de contexto y conteos de hilos personalizados para ajuste.

## Ver también

Compara motores con `asiai bench --engines llamacpp` --- [aprende cómo](../benchmark-llm-mac.md)
