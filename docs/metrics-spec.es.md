---
description: "Definiciones detalladas de todas las métricas de benchmark de asiai: tok/s, TTFT, vatios de potencia, eficiencia, VRAM, estabilidad, estado térmico."
---

# Especificación de métricas de benchmark

> **Versión**: 0.4.0
> **Estado**: Implementado
> **Alcance**: `asiai bench` — todos los motores

## Motivación

Los resultados de benchmark deben ser **comparables entre motores**. Cada métrica tiene una única definición
que todas las implementaciones de motores deben respetar. La implementación puede variar (API del servidor vs
medición del lado del cliente), pero la semántica debe ser idéntica.

## Métricas

### M1. `tok_per_sec` — Velocidad de generación

**Definición**: Tokens producidos por segundo de **tiempo de generación únicamente**, excluyendo el
procesamiento del prompt (TTFT).

```
generation_s = total_duration_s - ttft_s
tok_per_sec  = tokens_generated / generation_s    (if generation_s >= 0.01)
             = 0.0                                 (otherwise)
```

| Motor | Fuente de `generation_s` |
|--------|----------------------|
| Ollama | `eval_duration / 1e9` (API del servidor — directo) |
| OpenAI-compat | `elapsed_s - (ttft_ms / 1000)` (lado del cliente) |

**Justificación**: Con tamaños de contexto grandes (ej. 64k tokens), el TTFT puede dominar la duración total.
Incluirlo en tok/s hace que generadores rápidos parezcan lentos (ej. 3,2 tok/s en lugar de 42 tok/s).

### M2. `ttft_ms` — Tiempo al primer token

**Definición**: Tiempo entre el envío de la solicitud y la recepción del primer token de salida, en ms.

| Motor | Fuente |
|--------|--------|
| Ollama | `prompt_eval_duration / 1e6` (API del servidor) |
| OpenAI-compat | `(time.monotonic() at 1st content chunk - t0) * 1000` (cliente) |

Nota: La semántica difiere ligeramente (medición servidor vs cliente), pero en localhost la diferencia es
~1ms — aceptable.

### M3. `total_duration_ms` — Duración total

**Definición**: Tiempo total de reloj de la solicitud (procesamiento del prompt + generación), en ms.

**Invariante**: `total_duration_ms >= ttft_ms` — siempre.

| Motor | Fuente |
|--------|--------|
| Ollama | `total_duration / 1e6` (API del servidor) |
| OpenAI-compat | `elapsed_s * 1000` (reloj de pared del cliente) |

### M4. `tokens_generated` — Conteo de tokens

**Definición**: Número de tokens de salida producidos por el modelo.

**Fuente (por prioridad)**:
1. Contador del servidor: Ollama `eval_count`, OpenAI-compat `usage.completion_tokens`
2. Estimación por longitud de texto: `max(1, len(text) // 4)` (heurística: ~4 caracteres/token)
3. **Nunca** `len(text_parts)` (fragmentos SSE != tokens)

### M5. `generation_duration_ms` — Duración de generación

**Definición**: Tiempo de generación únicamente (excluyendo TTFT), en ms.
Hace explícita y auditable la descomposición `total = ttft + generation`.

| Motor | Fuente |
|--------|--------|
| Ollama | `eval_duration / 1e6` (API del servidor — directo) |
| OpenAI-compat | `max(0, elapsed_s - ttft_s) * 1000` (calculado) |

### M6. `power_watts` — Potencia de GPU

**Definición**: Potencia promedio de GPU durante la ejecución de **este motor específico**, en vatios.

**Alcance**: Un `PowerMonitor` por motor. Iniciado antes del primer prompt, detenido después
de la última ejecución. Cada motor obtiene su propia medición — sin promedios a nivel de sesión.

Fuente: `sudo powermetrics` (macOS).

### M7. `tok_per_sec_per_watt` — Eficiencia energética

```
tok_per_sec_per_watt = tok_per_sec / power_watts
```

Usa el tok/s corregido (M1) y la potencia por motor (M6).

### M8. `std_dev_tok_s` — Varianza (combinada)

**Definición**: Desviación estándar combinada intra-prompt — captura el ruido entre ejecuciones
**sin** mezclar la varianza entre prompts.

```
For each prompt_type p with runs [v1, v2, ..., vn]:
    var_p = sum((vi - mean_p)^2) / n    (population variance)

pooled_variance = mean(var_p for all p with n >= 2)
std_dev_tok_s   = sqrt(pooled_variance)
```

**Clasificación de estabilidad** (sin cambios):
- CV < 5% → `stable`
- CV < 10% → `variable`
- CV >= 10% → `unstable`

Donde CV = `(std_dev_tok_s / avg_tok_s) * 100`.

## Mapa de implementación

| Métrica | `base.py` | `ollama.py` | `openai_compat.py` | `runner.py` | `reporter.py` |
|--------|-----------|-------------|--------------------|-----------  |----------------|
| M1 tok/s | field | server API | client (excl. TTFT) | passthrough | avg |
| M2 ttft_ms | field | server API | client streaming | passthrough | avg |
| M3 total_duration_ms | field | server API | client wall-clock | passthrough | avg |
| M4 tokens_generated | field | server API | server or `len//4` | passthrough | avg |
| M5 generation_duration_ms | field | server API | computed | stored in dict | — |
| M6 power_watts | — | — | — | per-engine monitor | passthrough |
| M7 tok/s/W | — | — | — | computed | passthrough |
| M8 std_dev | — | — | — | — | pooled intra-prompt |

## Protocolo de benchmark

1. **Calentamiento**: 1 generación no cronometrada por motor (`"Hello"`, max_tokens=1) para preparar cachés.
2. **Ejecuciones medidas**: Por defecto 3 ejecuciones por prompt por motor (configurable con `--runs`).
3. **Muestreo**: `temperature=0` (greedy) en todos los motores para salida determinista.
4. **Reporte**: Mediana de tok/s como métrica principal (estándar SPEC), media +/- desviación estándar como secundaria.
5. **Throttling**: Advertencia emitida si `thermal_speed_limit < 100%` durante cualquier ejecución.
6. **Metadatos**: engine_version, model_format, model_quantization, hw_chip, os_version
   almacenados por resultado para reproducibilidad.

Consulta [benchmark-best-practices.md](benchmark-best-practices.md) para la auditoría completa de metodología.
