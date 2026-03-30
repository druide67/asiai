---
title: "Preguntas frecuentes"
description: "Preguntas frecuentes sobre asiai: motores compatibles, requisitos de Apple Silicon, benchmarks de LLMs en Mac, requisitos de RAM y más."
type: faq
faq:
  - q: "¿Qué es asiai?"
    a: "asiai es una herramienta CLI de código abierto que realiza benchmarks y monitorea motores de inferencia LLM en Macs con Apple Silicon. Soporta 7 motores (Ollama, LM Studio, mlx-lm, llama.cpp, oMLX, vllm-mlx, Exo) y mide tok/s, TTFT, consumo de energía y uso de VRAM."
  - q: "¿Cuál es el motor LLM más rápido en Apple Silicon?"
    a: "En benchmarks con M4 Pro 64GB y Qwen3-Coder-30B, LM Studio (backend MLX) alcanza 102 tok/s frente a los 70 tok/s de Ollama — un 46% más rápido en generación de tokens. Sin embargo, Ollama tiene menor latencia de tiempo al primer token."
  - q: "¿Funciona asiai en Macs Intel?"
    a: "No. asiai requiere Apple Silicon (M1, M2, M3 o M4). Utiliza APIs específicas de macOS para métricas de GPU, monitoreo de energía con IOReport y detección de hardware que solo están disponibles en chips Apple Silicon."
  - q: "¿Cuánta RAM necesito para ejecutar LLMs localmente?"
    a: "Para un modelo 7B cuantizado en Q4: 8 GB mínimo. Para 13B: 16 GB. Para 30B: 32-64 GB. Los modelos MoE como Qwen3.5-35B-A3B solo usan unos 7 GB de parámetros activos, lo que los hace ideales para Macs de 16 GB."
  - q: "¿Es mejor Ollama o LM Studio para Mac?"
    a: "Depende de tu caso de uso. LM Studio (MLX) es más rápido en rendimiento y más eficiente energéticamente. Ollama (llama.cpp) tiene menor latencia al primer token y maneja mejor las ventanas de contexto grandes (>32K). Consulta la comparación detallada en asiai.dev/ollama-vs-lmstudio."
  - q: "¿Requiere asiai sudo o acceso root?"
    a: "No. Todas las funciones, incluida la observabilidad de GPU (ioreg) y el monitoreo de energía (IOReport), funcionan sin sudo. La opción --power para validación cruzada con powermetrics es la única función que usa sudo."
  - q: "¿Cómo instalo asiai?"
    a: "Instala mediante pip (pip install asiai) o Homebrew (brew tap druide67/tap && brew install asiai). Requiere Python 3.11+."
  - q: "¿Pueden los agentes de IA usar asiai?"
    a: "Sí. asiai incluye un servidor MCP con 11 herramientas y 3 recursos. Instala con pip install asiai[mcp] y configúralo como asiai mcp en tu cliente MCP (Claude Code, Cursor, etc.)."
  - q: "¿Qué tan precisas son las mediciones de energía?"
    a: "Las lecturas de energía de IOReport tienen menos del 1,5% de diferencia comparadas con sudo powermetrics, validado en 20 muestras tanto en LM Studio (MLX) como en Ollama (llama.cpp)."
  - q: "¿Puedo hacer benchmark de varios modelos a la vez?"
    a: "Sí. Usa asiai bench --compare para ejecutar benchmarks cruzados entre modelos. Soporta la sintaxis modelo@motor para control preciso, con hasta 8 slots de comparación."
  - q: "¿Cómo comparto mis resultados de benchmark?"
    a: "Ejecuta asiai bench --share para enviar resultados anónimamente a la tabla de clasificación comunitaria. Añade --card para generar una imagen de tarjeta de benchmark de 1200x630."
  - q: "¿Qué métricas mide asiai?"
    a: "Siete métricas principales: tok/s (velocidad de generación), TTFT (tiempo al primer token), potencia (vatios GPU+CPU), tok/s/W (eficiencia energética), uso de VRAM, estabilidad entre ejecuciones y estado de throttling térmico."
---

# Preguntas frecuentes

## General

**¿Qué es asiai?**

asiai es una herramienta CLI de código abierto que realiza benchmarks y monitorea motores de inferencia LLM en Macs con Apple Silicon. Soporta 7 motores (Ollama, LM Studio, mlx-lm, llama.cpp, oMLX, vllm-mlx, Exo) y mide tok/s, TTFT, consumo de energía y uso de VRAM sin dependencias externas.

**¿Funciona asiai en Macs Intel o Linux?**

No. asiai requiere Apple Silicon (M1, M2, M3 o M4). Utiliza APIs específicas de macOS (`sysctl`, `vm_stat`, `ioreg`, `IOReport`, `launchd`) que solo están disponibles en Macs con Apple Silicon.

**¿Requiere asiai sudo o acceso root?**

No. Todas las funciones, incluida la observabilidad de GPU (`ioreg`) y el monitoreo de energía (`IOReport`), funcionan sin sudo. La opción `--power` para validación cruzada con `powermetrics` es la única función que usa sudo.

## Motores y rendimiento

**¿Cuál es el motor LLM más rápido en Apple Silicon?**

En nuestros benchmarks con M4 Pro 64GB y Qwen3-Coder-30B (Q4_K_M), LM Studio (backend MLX) alcanza **102 tok/s** frente a los **70 tok/s** de Ollama — un 46% más rápido en generación de tokens. LM Studio también es un 82% más eficiente energéticamente (8,23 vs 4,53 tok/s/W). Consulta nuestra [comparación detallada](ollama-vs-lmstudio.md).

**¿Es mejor Ollama o LM Studio para Mac?**

Depende de tu caso de uso:

- **LM Studio (MLX)**: Ideal para rendimiento (generación de código, respuestas largas). Más rápido, más eficiente, menor VRAM.
- **Ollama (llama.cpp)**: Ideal para latencia (chatbots, uso interactivo). TTFT más rápido. Mejor para ventanas de contexto grandes (>32K tokens).

**¿Cuánta RAM necesito para ejecutar LLMs localmente?**

| Tamaño del modelo | Cuantización | RAM necesaria |
|-----------|-------------|-----------|
| 7B | Q4_K_M | 8 GB mínimo |
| 13B | Q4_K_M | 16 GB mínimo |
| 30B | Q4_K_M | 32-64 GB |
| 35B MoE (3B activos) | Q4_K_M | 16 GB (solo se cargan los parámetros activos) |

## Benchmarking

**¿Cómo ejecuto mi primer benchmark?**

Tres comandos:

```bash
pip install asiai     # Instalar
asiai detect          # Buscar motores
asiai bench           # Ejecutar benchmark
```

**¿Cuánto tarda un benchmark?**

Un benchmark rápido (`asiai bench --quick`) tarda unos 2 minutos. Una comparación completa entre motores con múltiples prompts y 3 ejecuciones tarda 10-15 minutos.

**¿Qué tan precisas son las mediciones de energía?**

Las lecturas de energía de IOReport tienen menos del 1,5% de diferencia comparadas con `sudo powermetrics`, validado en 20 muestras tanto en LM Studio (MLX) como en Ollama (llama.cpp).

**¿Puedo comparar mis resultados con otros usuarios de Mac?**

Sí. Ejecuta `asiai bench --share` para enviar resultados anónimamente a la [tabla de clasificación comunitaria](leaderboard.md). Usa `asiai compare` para ver cómo se compara tu Mac.

## Integración con agentes de IA

**¿Pueden los agentes de IA usar asiai?**

Sí. asiai incluye un servidor MCP con 11 herramientas y 3 recursos. Instala con `pip install "asiai[mcp]"` y configúralo como `asiai mcp` en tu cliente MCP (Claude Code, Cursor, Windsurf). Consulta la [Guía de integración con agentes](agent.md).

**¿Qué herramientas MCP están disponibles?**

11 herramientas: `check_inference_health`, `get_inference_snapshot`, `list_models`, `detect_engines`, `run_benchmark`, `get_recommendations`, `diagnose`, `get_metrics_history`, `get_benchmark_history`, `refresh_engines`, `compare_engines`.

3 recursos: `asiai://status`, `asiai://models`, `asiai://system`.
