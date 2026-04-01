---
description: Cómo asiai mide tok/s, TTFT y energía. Calentamiento, metodología estadística y por qué los resultados son reproducibles.
---

# Metodología de benchmark

asiai sigue estándares de benchmarking establecidos ([MLPerf](https://mlcommons.org/benchmarks/inference-server/), [SPEC CPU 2017](https://www.spec.org/cpu2017/), [NVIDIA GenAI-Perf](https://docs.nvidia.com/deeplearning/nemo/user-guide/docs/en/stable/benchmarking/genai_perf.html)) para producir resultados fiables, reproducibles y comparables.

## Protocolo

1. **Verificación previa**: Rechaza iniciar si la presión de memoria es crítica o el sistema está severamente limitado (<80%)
2. **Calentamiento**: 1 generación no cronometrada por motor para preparar compiladores JIT y cachés
3. **Ejecuciones medidas**: Por defecto 3 ejecuciones por prompt por motor (configurable con `--runs`)
4. **Muestreo**: `temperature=0` (greedy) para salida determinista
5. **Descarga de modelo**: Después del benchmark de cada motor, el modelo se descarga para liberar memoria unificada antes de iniciar el siguiente motor. Esto previene la acumulación de memoria y el swapping al comparar múltiples motores con modelos grandes
6. **Enfriamiento adaptativo**: Tras la descarga, asiai espera a que la presión de memoria de macOS vuelva a "normal" (máx. 30s), luego añade un mínimo de 5s de enfriamiento térmico
7. **Verificaciones de cordura**: Los resultados con tok/s ≤ 0 se descartan. TTFT > 60s o tok/s > 500 generan advertencias (probable swapping o errores de medición)
8. **Reporte**: Mediana de tok/s como métrica principal (estándar SPEC), media ± desviación estándar como secundaria
9. **Throttling**: Advertencia emitida si `thermal_speed_limit < 100%` durante cualquier ejecución. La degradación térmica (disminución monótona de tok/s entre ejecuciones, caída ≥ 5%) se detecta e informa
10. **Metadatos**: Versión del motor, formato del modelo, cuantización, chip de hardware, versión de macOS almacenados por resultado

## Métricas

### tok/s — Velocidad de generación

Tokens por segundo de **tiempo de generación únicamente**, excluyendo el procesamiento del prompt (TTFT).

**Ollama** (API nativa, `/api/generate`):
```
tok_per_sec = eval_count / (eval_duration_ns / 1e9)
```
Fuente: timing GPU interno reportado por Ollama. Sin sobrecarga de red. Es la medición más precisa.

**Motores compatibles con OpenAI** (LM Studio, llama.cpp, mlx-lm, vllm-mlx):
```
generation_s = wall_clock_s - ttft_s
tok_per_sec  = completion_tokens / generation_s
```
Fuente: reloj de pared del lado del cliente vía streaming SSE. Incluye sobrecarga HTTP por fragmento (~1% más lento que el timing del servidor, validado por validación cruzada).

**Conteo de tokens**: desde `usage.completion_tokens` en la respuesta del servidor. Si el servidor no reporta este campo, asiai recurre a `len(text) // 4` y registra una advertencia. Este respaldo puede desviarse ~25%.

**Validación cruzada** (abril 2026, Qwen3.5-35B NVFP4, M4 Pro 64GB):

| Método | tok/s | Delta vs referencia |
|--------|-------|--------------------|
| Ollama nativo (GPU interno) | 66.6 | referencia |
| OpenAI streaming (cliente) | 66.1 | -0.8% |

Con tamaños de contexto grandes (ej. 64k tokens), el TTFT puede dominar la duración total. Excluirlo de tok/s evita que generadores rápidos parezcan lentos.

### TTFT — Tiempo al primer token

Tiempo entre el envío de la solicitud y la recepción del primer token de salida, en milisegundos.

**Ollama**: medido del lado del servidor vía `prompt_eval_duration` (timing interno). Es el tiempo puro de procesamiento del prompt sin sobrecarga de red. Reportado como `ttft_source: server`.

**Motores compatibles con OpenAI**: medido del lado del cliente en el primer fragmento SSE con contenido. Incluye configuración HTTP, transmisión de solicitud y procesamiento del servidor. Típicamente 10-100ms más alto que del lado del servidor. Reportado como `ttft_source: client`.

!!! warning "Comparación de TTFT"
    No compare el TTFT del lado del servidor de Ollama con el TTFT del lado del cliente de motores compatibles con OpenAI sin tener en cuenta la diferencia. El campo `ttft_source` en los resultados de benchmark indica qué método se utilizó.

### Power — Vatios de GPU

Potencia promedio de GPU durante la ejecución, medida mediante el framework Apple IOReport Energy Model (sin necesidad de sudo). Una medición por motor — sin promedios a nivel de sesión.

### tok/s/W — Eficiencia energética

```
tok_per_sec_per_watt = tok_per_sec / power_watts
```

### Varianza — Desviación estándar combinada

Desviación estándar combinada intra-prompt que captura el ruido entre ejecuciones **sin** mezclar la varianza entre prompts. Utiliza la corrección de Bessel (denominador N-1) para varianza muestral insesgada.

Clasificación de estabilidad:

- CV < 5% → `stable`
- CV < 10% → `variable`
- CV >= 10% → `unstable`

Donde CV = `(std_dev / mean) * 100`.

### VRAM — Uso de memoria

**Primario**: API nativa del motor (Ollama `/api/ps`, LM Studio `/v1/models`).
**Respaldo**: `ri_phys_footprint` vía ctypes (igual que el Monitor de Actividad). Marcado como "(est.)" en la interfaz.

## Seguridad del entorno

asiai realiza verificaciones previas al benchmark:

1. **Presión de memoria**: rechaza iniciar si es crítica
2. **Throttling térmico**: advierte si el límite de velocidad < 80%
3. **Procesos duplicados**: advierte si hay múltiples instancias del mismo motor ejecutándose (ej. dos procesos `ollama serve` en el mismo puerto)
4. **Tipo de runner del motor**: para Ollama, detecta si el runner `--mlx-engine` o `--ollama-engine` está activo

Estas verificaciones previenen errores de medición causados por contención de recursos o enrutamiento incorrecto.

## Conformidad

| Práctica | Estado |
|----------|--------|
| Verificación previa (presión de memoria + térmica) | Implementado |
| Detección de procesos duplicados | Implementado (v1.5.0) |
| Detección de tipo de runner Ollama (MLX vs llama.cpp) | Implementado (v1.5.0) |
| TTFT separado de tok/s | Implementado |
| Etiquetado de fuente TTFT (server vs client) | Implementado (v1.5.0) |
| Muestreo determinista (temperature=0) | Implementado |
| Conteo de tokens desde API del servidor (no fragmentos SSE) | Implementado (advertencia en respaldo) |
| Monitoreo de energía por motor (IOReport, sin sudo) | Implementado |
| 1 generación de calentamiento por motor | Implementado |
| 3 ejecuciones por defecto (mínimo SPEC) | Implementado |
| Mediana como métrica principal (estándar SPEC) | Implementado |
| Desviación estándar combinada intra-prompt (Bessel N-1) | Implementado (corregido v1.5.0) |
| Descarga de modelo entre motores | Implementado |
| Enfriamiento adaptativo (sensible a presión de memoria) | Implementado |
| Verificaciones de cordura (tok/s, límites TTFT) | Implementado |
| Detección de throttling térmico + advertencia | Implementado |
| Detección de degradación térmica (disminución monótona) | Implementado |
| Versión del motor + tipo de runner almacenados por resultado | Implementado (v1.5.0) |
| VRAM universal vía ri_phys_footprint | Implementado |
| Detección de regresión histórica | Implementado |
| Script de validación cruzada (3 métodos comparados) | Disponible (scripts/cross-validate-bench.py) |

## Consideraciones sobre Apple Silicon

### Memoria unificada

Apple Silicon comparte memoria entre CPU y GPU. asiai ejecuta los motores **secuencialmente** y **descarga los modelos entre motores** para evitar contención de memoria y swapping. La VRAM es reportada nativamente por Ollama y LM Studio; para otros motores, asiai estima el uso de memoria mediante `ri_phys_footprint` (la métrica de huella física de macOS, igual que el Monitor de Actividad). Los valores estimados se etiquetan como "(est.)" en la interfaz.

### Throttling térmico

- **MacBook Air** (sin ventilador): throttling severo bajo carga sostenida
- **MacBook Pro** (con ventilador): throttling leve
- **Mac Mini/Studio/Pro**: refrigeración activa, throttling mínimo

asiai registra `thermal_speed_limit` por resultado y advierte si se detecta throttling.

### Caché KV

Tamaños de contexto grandes (32k+) pueden causar inestabilidad en motores que pre-asignan la caché KV. Configura la longitud de contexto del motor para que coincida con el tamaño real de la prueba para obtener resultados justos.

## Medición de energía

asiai mide el consumo de energía de GPU, CPU, ANE y DRAM mediante el framework Apple IOReport Energy Model — **sin necesidad de sudo**. La energía se mide automáticamente en cada benchmark y cada snapshot de monitoreo.

IOReport lee los mismos contadores de energía del hardware que `sudo powermetrics`, pero a través de una API de espacio de usuario (`libIOReport.dylib` vía ctypes). Esto elimina la necesidad de configuración de sudo sin contraseña.

### Validación

Validamos cruzadamente IOReport contra `sudo powermetrics` bajo carga de inferencia LLM en M4 Pro 64GB, usando 10 muestras pareadas por motor a intervalos de 2 segundos:

| Motor | Promedio IOReport | Promedio powermetrics | Delta medio | Delta máximo |
|--------|-------------|-----------------|------------|-----------|
| LM Studio (MLX) | 12.6 W | 12.6 W | 0.9% | 2.1% |
| Ollama (llama.cpp) | 15.6 W | 15.4 W | 1.3% | 4.1% |

Ambos motores confirmaron un delta promedio <1,5% con 10/10 muestras pareadas. La energía de ANE fue 0.000W en las 20 muestras, confirmando que ningún motor LLM utiliza actualmente el Neural Engine.

La opción `--power` habilita validación cruzada adicional ejecutando simultáneamente IOReport y `sudo powermetrics`, almacenando ambas lecturas para comparación.

### Eficiencia energética

La eficiencia energética (tok/s por vatio) se calcula como `tok_per_sec / gpu_watts` para cada resultado de benchmark. Esta métrica permite comparar el costo de inferencia entre motores y hardware.

## Metadatos

Cada resultado de benchmark almacena: engine, engine_version, model, model_format, model_quantization, hw_chip, os_version, thermal_level, thermal_speed_limit, power_watts, power_source, metrics_version. Esto permite una comparación de regresión justa y benchmarks entre máquinas.
