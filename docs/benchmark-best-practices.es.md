---
description: "Cómo obtener resultados precisos de benchmark LLM en Mac: gestión térmica, aplicaciones en segundo plano, número de ejecuciones y consejos de reproducibilidad."
---

# Buenas prácticas de benchmark

> **Versión**: 0.3.2
> **Estado**: Documento vivo — actualizado a medida que la metodología evoluciona
> **Referencias**: MLPerf Inference, SPEC CPU 2017, NVIDIA GenAI-Perf

## Descripción general

`asiai bench` sigue estándares de benchmarking establecidos para producir resultados **fiables, reproducibles
y comparables** entre motores de inferencia en Apple Silicon. Este documento registra
qué buenas prácticas están implementadas, planificadas o excluidas intencionalmente.

## Resumen de conformidad

| Categoría | Práctica | Estado | Desde |
|-----------|----------|--------|-------|
| **Métricas** | TTFT separado de tok/s | Implementado | v0.3.1 |
| | Muestreo determinístico (temperature=0) | Implementado | v0.3.2 |
| | Conteo de tokens desde API del servidor (no chunks SSE) | Implementado | v0.3.1 |
| | Monitorización de potencia por motor | Implementado | v0.3.1 |
| | Campo explícito generation_duration_ms | Implementado | v0.3.1 |
| **Warmup** | 1 generación de warmup por motor (no medida) | Implementado | v0.3.2 |
| **Ejecuciones** | 3 ejecuciones por defecto (mínimo SPEC) | Implementado | v0.3.2 |
| | Mediana como métrica principal (estándar SPEC) | Implementado | v0.3.2 |
| | Media + stddev como secundarias | Implementado | v0.3.0 |
| **Varianza** | Stddev intra-prompt agrupada | Implementado | v0.3.1 |
| | Clasificación de estabilidad basada en CV | Implementado | v0.3.0 |
| **Entorno** | Ejecución secuencial de motores (aislamiento de memoria) | Implementado | v0.1 |
| | Detección de throttling térmico + advertencia | Implementado | v0.3.2 |
| | Nivel térmico + speed_limit registrados | Implementado | v0.1 |
| **Reproducibilidad** | Versión del motor almacenada por benchmark | Implementado | v0.3.2 |
| | Formato del modelo + cuantización almacenados | Implementado | v0.3.2 |
| | Chip de hardware + versión de macOS almacenados | Implementado | v0.3.2 |
| | Código de benchmark open-source | Implementado | v0.1 |
| **Regresión** | Comparación con baseline histórico (SQLite) | Implementado | v0.3.0 |
| | Comparación por (motor, modelo, tipo_prompt) | Implementado | v0.3.1 |
| | Filtrado por metrics_version | Implementado | v0.3.1 |
| **Prompts** | 4 tipos de prompts diversos + relleno de contexto | Implementado | v0.1 |
| | max_tokens fijo por prompt | Implementado | v0.1 |

## Mejoras planificadas

### P1 — Rigor estadístico

| Práctica | Descripción | Estándar |
|----------|-------------|----------|
| **Intervalos de confianza 95%** | CI = media +/- 2*SE. Más informativo que +/- stddev. | Académico |
| **Percentiles (P50/P90/P99)** | Para TTFT especialmente — la latencia de cola importa. | NVIDIA GenAI-Perf |
| **Detección de outliers (IQR)** | Marcar ejecuciones fuera de [Q1 - 1.5*IQR, Q3 + 1.5*IQR]. | Estándar estadístico |
| **Detección de tendencias** | Detectar degradación monótona del rendimiento entre ejecuciones (deriva térmica). | Académico |

### P2 — Reproducibilidad

| Práctica | Descripción | Estándar |
|----------|-------------|----------|
| **Enfriamiento entre motores** | Pausa de 3-5s entre motores para estabilizar temperaturas. | Benchmark GPU |
| **Verificación de ratio de tokens** | Advertir si tokens_generated < 90% de max_tokens. | MLPerf |
| **Formato de exportación** | `asiai bench --export` JSON para envíos comunitarios. | Envíos MLPerf |

### P3 — Avanzado

| Práctica | Descripción | Estándar |
|----------|-------------|----------|
| **Opción `ignore_eos`** | Forzar generación hasta max_tokens para benchmarks de rendimiento. | NVIDIA |
| **Prueba de peticiones concurrentes** | Probar rendimiento por lotes (relevante para vllm-mlx). | NVIDIA |
| **Auditoría de procesos en segundo plano** | Advertir si hay procesos pesados ejecutándose durante el benchmark. | SPEC |

## Desviaciones intencionales

| Práctica | Razón de la desviación |
|----------|----------------------|
| **Duración mínima de 600s de MLPerf** | Diseñado para GPUs de centro de datos. La inferencia local en Apple Silicon con 3 ejecuciones + 4 prompts ya toma ~2-5 minutos. Suficiente para resultados estables. |
| **2 cargas de warmup no medidas de SPEC** | Usamos 1 generación de warmup (no 2 cargas completas). Un solo warmup es suficiente para motores de inferencia locales donde el warmup JIT es mínimo. |
| **Stddev poblacional vs muestral** | Usamos stddev poblacional (divisor N) en lugar de muestral (divisor N-1). Con N pequeño (3-5 ejecuciones), la diferencia es mínima y poblacional es más conservador. |
| **Control de escalado de frecuencia** | Apple Silicon no expone controles de governor de CPU. Registramos thermal_speed_limit en su lugar para detectar throttling. |

## Consideraciones específicas de Apple Silicon

### Arquitectura de memoria unificada

Apple Silicon comparte memoria entre CPU y GPU. Dos implicaciones clave:

1. **Nunca hacer benchmark de dos motores simultáneamente** — compiten por el mismo pool de memoria.
   `asiai bench` ejecuta motores secuencialmente por diseño.
2. **Reporte de VRAM** — Ollama y LM Studio reportan `size_vram` nativamente. Para otros motores
   (llama.cpp, mlx-lm, oMLX, vLLM-MLX, Exo), asiai usa `ri_phys_footprint` vía libproc como
   estimación alternativa. Esto es lo que muestra el Monitor de Actividad e incluye asignaciones Metal/GPU.
   Los valores estimados se etiquetan como "(est.)" en la interfaz.

### Throttling térmico

- **MacBook Air** (sin ventilador): throttling severo bajo carga sostenida. Los resultados se degradan después de 5-10 min.
- **MacBook Pro** (ventilador): throttling leve y generalmente gestionado por el ventilador.
- **Mac Mini/Studio/Pro**: refrigeración activa, throttling mínimo.

`asiai bench` registra `thermal_speed_limit` por resultado y advierte si se detecta throttling
(speed_limit < 100%) durante cualquier ejecución.

### KV Cache y longitud de contexto

Tamaños de contexto grandes (32k+) pueden causar inestabilidad de rendimiento en motores que pre-asignan
KV cache al cargar el modelo. Ejemplo: LM Studio por defecto usa `loaded_context_length: 262144`
(256k), lo que asigna ~15-25 GB de KV cache para un modelo 35B, pudiendo saturar
64 GB de memoria unificada.

**Recomendaciones**:
- Al hacer benchmark con contextos grandes, configura la longitud de contexto del motor para que coincida con el tamaño real de la prueba
  (por ejemplo, `lms load model --context-length 65536` para pruebas de 64k).
- Compara motores con configuraciones de longitud de contexto equivalentes para resultados justos.

## Metadatos almacenados por benchmark

Cada resultado de benchmark en SQLite incluye:

| Campo | Ejemplo | Propósito |
|-------|---------|-----------|
| `engine` | "ollama" | Identificación del motor |
| `engine_version` | "0.17.4" | Detectar cambios de rendimiento entre actualizaciones |
| `model` | "qwen3.5:35b-a3b" | Identificación del modelo |
| `model_format` | "gguf" | Diferenciar variantes de formato |
| `model_quantization` | "Q4_K_M" | Diferenciar niveles de cuantización |
| `hw_chip` | "Apple M4 Pro" | Identificación de hardware |
| `os_version` | "15.3" | Seguimiento de versión de macOS |
| `thermal_level` | "nominal" | Condición del entorno |
| `thermal_speed_limit` | 100 | Detección de throttling |
| `metrics_version` | 2 | Versión de la fórmula (previene regresiones entre versiones) |

Estos metadatos permiten:
- **Comparación justa de regresiones**: solo comparar resultados con metadatos coincidentes
- **Benchmarks entre máquinas**: identificar diferencias de hardware
- **Compartir datos comunitarios**: resultados auto-descriptivos (planificado para v1.x)
