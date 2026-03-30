---
title: "Ollama vs LM Studio: Benchmark en Apple Silicon"
description: "Benchmark Ollama vs LM Studio en Apple Silicon: tok/s, TTFT, potencia, VRAM comparados lado a lado en M4 Pro con mediciones reales."
type: article
date: 2026-03-28
updated: 2026-03-29
dataset:
  name: "Benchmark Ollama vs LM Studio en Apple Silicon M4 Pro"
  description: "Benchmark directo comparando Ollama (llama.cpp) y LM Studio (MLX) en Mac Mini M4 Pro 64GB con Qwen3-Coder-30B. Métricas: tok/s, TTFT, potencia GPU, eficiencia, VRAM."
  date: "2026-03"
---

# Ollama vs LM Studio: Benchmark en Apple Silicon

¿Qué motor de inferencia es más rápido en tu Mac? Comparamos Ollama (backend llama.cpp) y LM Studio (backend MLX) cara a cara con el mismo modelo y hardware usando asiai 1.4.0 en marzo de 2026.

## Configuración de prueba

| | |
|---|---|
| **Hardware** | Mac Mini M4 Pro, 64 GB de memoria unificada |
| **Modelo** | Qwen3-Coder-30B (arquitectura MoE, Q4_K_M / MLX 4-bit) |
| **Versión de asiai** | 1.4.0 |
| **Metodología** | 1 calentamiento + 1 ejecución medida por motor, temperature=0, modelo descargado entre motores ([metodología completa](methodology.md)) |

## Resultados

| Métrica | LM Studio (MLX) | Ollama (llama.cpp) | Diferencia |
|--------|-----------------|-------------------|------------|
| **Rendimiento** | 102,2 tok/s | 69,8 tok/s | **+46%** |
| **TTFT** | 291 ms | 175 ms | Ollama más rápido |
| **Potencia GPU** | 12,4 W | 15,4 W | **-20%** |
| **Eficiencia** | 8,2 tok/s/W | 4,5 tok/s/W | **+82%** |
| **Memoria del proceso** | 21,4 GB (RSS) | 41,6 GB (RSS) | -49% |

!!! note "Sobre los números de memoria"
    Ollama pre-asigna la caché KV para toda la ventana de contexto (262K tokens), lo que infla su huella de memoria. LM Studio asigna la caché KV bajo demanda. El RSS del proceso refleja la memoria total utilizada por el proceso del motor, no solo los pesos del modelo.

## Hallazgos clave

### LM Studio gana en rendimiento (+46%)

La optimización nativa de Metal de MLX extrae más ancho de banda de la memoria unificada de Apple Silicon. En arquitecturas MoE, la ventaja es significativa. Con la variante más grande Qwen3.5-35B-A3B, medimos una brecha aún mayor: **71,2 vs 30,3 tok/s (2,3x)**.

### Ollama gana en TTFT

El backend llama.cpp de Ollama procesa el prompt inicial más rápido (175ms vs 291ms). Para uso interactivo con prompts cortos, esto hace que Ollama se sienta más ágil. Para tareas de generación más largas, la ventaja de rendimiento de LM Studio domina el tiempo total.

### LM Studio es más eficiente energéticamente (+82%)

Con 8,2 tok/s por vatio frente a 4,5, LM Studio genera casi el doble de tokens por julio. Esto importa para portátiles con batería y para cargas de trabajo sostenidas en servidores siempre encendidos.

### Uso de memoria: el contexto importa

La gran brecha en la memoria del proceso (21,4 vs 41,6 GB) se debe en parte a que Ollama pre-asigna la caché KV para su ventana de contexto máxima. Para una comparación justa, considera el contexto realmente utilizado durante tu carga de trabajo, no el RSS máximo.

## Cuándo usar cada uno

| Caso de uso | Recomendado | Por qué |
|----------|------------|-----|
| **Máximo rendimiento** | LM Studio (MLX) | +46% de generación más rápida |
| **Chat interactivo (baja latencia)** | Ollama | Menor TTFT (175 vs 291 ms) |
| **Batería / eficiencia** | LM Studio | 82% más tok/s por vatio |
| **Docker / compatibilidad API** | Ollama | Ecosistema más amplio, API compatible con OpenAI |
| **Memoria limitada (Mac 16GB)** | LM Studio | Menor RSS, caché KV bajo demanda |
| **Servir múltiples modelos** | Ollama | Gestión de modelos integrada, keep_alive |

## Otros modelos

La brecha de rendimiento varía según la arquitectura del modelo:

| Modelo | LM Studio (MLX) | Ollama (llama.cpp) | Brecha |
|-------|-----------------|-------------------|-----|
| Qwen3-Coder-30B (MoE) | 102,2 tok/s | 69,8 tok/s | +46% |
| Qwen3.5-35B-A3B (MoE) | 71,2 tok/s | 30,3 tok/s | +135% |

Los modelos MoE muestran las mayores diferencias porque MLX maneja el enrutamiento disperso de expertos de forma más eficiente en Metal.

## Ejecuta tu propio benchmark

```bash
pip install asiai
asiai bench --engines ollama,lmstudio --prompts code --runs 3 --card
```

asiai compara motores lado a lado con el mismo modelo, los mismos prompts y el mismo hardware. Los modelos se descargan automáticamente entre motores para prevenir contención de memoria.

[Ver la metodología completa](methodology.md) · [Ver la tabla de clasificación comunitaria](leaderboard.md) · [Cómo hacer benchmark de LLMs en Mac](benchmark-llm-mac.md)
