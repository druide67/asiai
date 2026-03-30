---
title: "Cómo hacer benchmark de LLMs en Mac"
description: "Cómo hacer benchmark de inferencia LLM en Mac: guía paso a paso para medir tok/s, TTFT, potencia y VRAM en Apple Silicon con múltiples motores."
type: howto
date: 2026-03-28
updated: 2026-03-29
duration: PT5M
steps:
  - name: "Instalar asiai"
    text: "Instala asiai vía pip (pip install asiai) o Homebrew (brew tap druide67/tap && brew install asiai)."
  - name: "Detectar tus motores"
    text: "Ejecuta 'asiai detect' para encontrar automáticamente los motores de inferencia en ejecución (Ollama, LM Studio, llama.cpp, mlx-lm, oMLX, vLLM-MLX, Exo) en tu Mac."
  - name: "Ejecutar un benchmark"
    text: "Ejecuta 'asiai bench' para auto-detectar el mejor modelo entre motores y ejecutar una comparación cruzada midiendo tok/s, TTFT, potencia y VRAM."
---

# Cómo hacer benchmark de LLMs en Mac

¿Ejecutas un LLM local en tu Mac? Aquí tienes cómo medir el rendimiento real — no impresiones, no "parece rápido", sino tok/s reales, TTFT, consumo de potencia y uso de memoria.

## ¿Por qué hacer benchmark?

El mismo modelo se ejecuta a velocidades muy diferentes según el motor de inferencia. En Apple Silicon, los motores basados en MLX (LM Studio, mlx-lm, oMLX) pueden ser **2x más rápidos** que los motores basados en llama.cpp (Ollama) para el mismo modelo. Sin medir, estás dejando rendimiento sobre la mesa.

## Inicio rápido (2 minutos)

### 1. Instalar asiai

```bash
pip install asiai
```

O vía Homebrew:

```bash
brew tap druide67/tap
brew install asiai
```

### 2. Detectar tus motores

```bash
asiai detect
```

asiai encuentra automáticamente los motores en ejecución (Ollama, LM Studio, llama.cpp, mlx-lm, oMLX, vLLM-MLX, Exo) en tu Mac.

### 3. Ejecutar un benchmark

```bash
asiai bench
```

Eso es todo. asiai auto-detecta el mejor modelo entre tus motores y ejecuta una comparación cruzada.

## Qué se mide

| Métrica | Qué significa |
|---------|--------------|
| **tok/s** | Tokens generados por segundo (solo generación, excluye procesamiento del prompt) |
| **TTFT** | Time to First Token — latencia antes de que comience la generación |
| **Potencia** | Vatios GPU + CPU durante la inferencia (vía IOReport, sin sudo) |
| **tok/s/W** | Eficiencia energética — tokens por segundo por vatio |
| **VRAM** | Memoria usada por el modelo (API nativa o estimada vía `ri_phys_footprint`) |
| **Estabilidad** | Varianza entre ejecuciones: estable (<5% CV), variable (<10%), inestable (>10%) |
| **Térmico** | Si tu Mac sufrió throttling durante el benchmark |

## Salida de ejemplo

```
Mac16,11 — Apple M4 Pro  RAM: 64.0 GB  Pressure: normal

Benchmark: qwen3-coder-30b

  Engine        tok/s   Tokens Duration     TTFT       VRAM    Thermal
  lmstudio      102.2      537    7.00s    0.29s    24.2 GB    nominal
  ollama         69.8      512   17.33s    0.18s    32.0 GB    nominal

  Winner: lmstudio (+46% tok/s)

  Power Efficiency
    lmstudio     102.2 tok/s @ 12.4W = 8.23 tok/s/W
    ollama        69.8 tok/s @ 15.4W = 4.53 tok/s/W
```

*Salida de ejemplo de un benchmark real en M4 Pro 64GB. Tus números variarán según hardware y modelo. [Ver más resultados →](ollama-vs-lmstudio.md)*

## Opciones avanzadas

### Comparar motores específicos

```bash
asiai bench --engines ollama,lmstudio,omlx
```

### Múltiples prompts y ejecuciones

```bash
asiai bench --prompts code,reasoning,tool_call --runs 3
```

### Benchmark de contexto grande

```bash
asiai bench --context-size 64K
```

### Generar una tarjeta compartible

```bash
asiai bench --card --share
```

Crea una imagen de tarjeta de benchmark y comparte los resultados con la [tabla de clasificación comunitaria](leaderboard.md).

## Consejos para Apple Silicon

### La memoria importa

En un Mac de 16GB, limítate a modelos por debajo de 14GB (cargados). Los modelos MoE (Qwen3.5-35B-A3B, 3B activos) son ideales — ofrecen calidad de clase 35B con uso de memoria de clase 7B.

### La elección de motor importa más de lo que crees

Los motores MLX son significativamente más rápidos que llama.cpp en Apple Silicon para la mayoría de modelos. [Consulta nuestra comparación Ollama vs LM Studio](ollama-vs-lmstudio.md) para números reales.

### Throttling térmico

El MacBook Air (sin ventilador) sufre throttling después de 5-10 minutos de inferencia sostenida. Mac Mini/Studio/Pro manejan cargas sostenidas sin throttling. asiai detecta y reporta el throttling térmico automáticamente.

## Compara con la comunidad

Mira cómo tu Mac se compara con otras máquinas Apple Silicon:

```bash
asiai compare
```

O visita la [tabla de clasificación en línea](leaderboard.md).

## FAQ

**P: ¿Cuál es el motor de inferencia LLM más rápido en Apple Silicon?**
R: En nuestros benchmarks en M4 Pro 64GB, LM Studio (backend MLX) es el más rápido para generación de tokens — 46% más rápido que Ollama (llama.cpp). Sin embargo, Ollama tiene menor TTFT (time to first token). Consulta nuestra [comparación detallada](ollama-vs-lmstudio.md).

**P: ¿Cuánta RAM necesito para ejecutar un modelo 30B en Mac?**
R: Un modelo 30B cuantizado Q4_K_M usa 24-32 GB de memoria unificada según el motor. Necesitas al menos 32 GB de RAM, idealmente 64 GB para evitar presión de memoria. Los modelos MoE como Qwen3.5-35B-A3B solo usan ~7 GB de parámetros activos.

**P: ¿asiai funciona en Macs Intel?**
R: No. asiai requiere Apple Silicon (M1/M2/M3/M4). Usa APIs específicas de macOS para métricas GPU, monitorización de potencia y detección de hardware que solo están disponibles en Apple Silicon.

**P: ¿Ollama o LM Studio es más rápido en M4?**
R: LM Studio es más rápido para rendimiento (102 tok/s vs 70 tok/s en Qwen3-Coder-30B). Ollama es más rápido para latencia de primer token (0.18s vs 0.29s) y para ventanas de contexto grandes (>32K tokens) donde el prefill de llama.cpp es hasta 3x más rápido.

**P: ¿Cuánto tiempo dura un benchmark?**
R: Un benchmark rápido toma unos 2 minutos. Una comparación completa entre motores con múltiples prompts y ejecuciones toma 10-15 minutos. Usa `asiai bench --quick` para una prueba rápida de una sola ejecución.

**P: ¿Puedo comparar mis resultados con otros usuarios de Mac?**
R: Sí. Ejecuta `asiai bench --share` para enviar anónimamente resultados a la [tabla de clasificación comunitaria](leaderboard.md). Usa `asiai compare` para ver cómo se compara tu Mac con otras máquinas Apple Silicon.

## Lectura adicional

- [Metodología de benchmark](methodology.md) — cómo asiai asegura mediciones fiables
- [Buenas prácticas de benchmark](benchmark-best-practices.md) — consejos para resultados precisos
- [Comparación de motores](ollama-vs-lmstudio.md) — Ollama vs LM Studio cara a cara
