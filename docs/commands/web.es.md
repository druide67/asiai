---
description: Panel de monitoreo de LLMs en tiempo real en tu navegador. Métricas de GPU, estado de motores, historial de rendimiento. Sin configuración necesaria.
---

# asiai web

Lanza el panel web para monitoreo visual y benchmarking.

## Uso

```bash
asiai web
asiai web --port 9000
asiai web --host 0.0.0.0
asiai web --no-open
```

## Opciones

| Opción | Por defecto | Descripción |
|--------|---------|-------------|
| `--port` | `8899` | Puerto HTTP de escucha |
| `--host` | `127.0.0.1` | Host de enlace |
| `--no-open` | | No abrir el navegador automáticamente |
| `--db` | `~/.local/share/asiai/asiai.db` | Ruta a la base de datos SQLite |

## Requisitos

El panel web requiere dependencias adicionales:

```bash
pip install asiai[web]
# o instalar todo:
pip install asiai[all]
```

## Páginas

### Panel principal (`/`)

Vista general del sistema con estado de motores, modelos cargados, uso de memoria y últimos resultados de benchmark.

### Benchmark (`/bench`)

Ejecuta benchmarks entre motores directamente desde el navegador:

- Botón **Quick Bench** — 1 prompt, 1 ejecución, ~15 segundos
- Opciones avanzadas: motores, prompts, ejecuciones, tamaño de contexto (4K/16K/32K/64K), potencia
- Progreso en tiempo real vía SSE
- Tabla de resultados con resaltado del ganador
- Gráficos de rendimiento y TTFT
- **Tarjeta compartible** — generada automáticamente tras el benchmark (PNG vía API, SVG como respaldo)
- **Sección de compartir** — copiar enlace, descargar PNG/SVG, compartir en X/Reddit, exportar JSON

### Historial (`/history`)

Visualiza benchmarks y métricas del sistema a lo largo del tiempo:

- Gráficos del sistema: carga de CPU, % de memoria, utilización de GPU (con desglose renderer/tiler)
- Actividad de motores: conexiones TCP, solicitudes procesándose, % de uso de caché KV
- Gráficos de benchmark: rendimiento (tok/s) y TTFT por motor
- Métricas de proceso: CPU % del motor y memoria RSS durante ejecuciones de benchmark
- Filtrar por rango de tiempo (1h / 24h / 7d / 30d / 90d) o rango de fechas personalizado
- Tabla de datos con indicación de tamaño de contexto (ej. "code (64K ctx)")

### Monitor (`/monitor`)

Monitoreo del sistema en tiempo real con actualización cada 5 segundos:

- Sparkline de carga de CPU
- Indicador de memoria
- Estado térmico
- Lista de modelos cargados

### Doctor (`/doctor`)

Verificación interactiva de estado del sistema, motores y base de datos. Mismas verificaciones que `asiai doctor` con interfaz visual.

## Endpoints API

El panel web expone endpoints de API REST para acceso programático.

### `GET /api/status`

Verificación rápida de estado. Caché de 10s, responde en < 500ms.

```json
{
  "status": "ok",
  "ts": 1709700000,
  "uptime": 86400,
  "engines": {"ollama": true, "lmstudio": false},
  "memory_pressure": "normal",
  "thermal_level": "nominal"
}
```

Valores de estado: `ok` (todos los motores accesibles), `degraded` (algunos caídos), `error` (todos caídos).

### `GET /api/snapshot`

Snapshot completo del sistema + motores. Caché de 5s. Incluye carga de CPU, memoria, estado térmico y estado por motor con modelos cargados.

### `GET /api/benchmarks`

Resultados de benchmark con filtros. Devuelve datos por ejecución incluyendo tok/s, TTFT, potencia, context_size, engine_version.

| Parámetro | Por defecto | Descripción |
|-----------|---------|-------------|
| `hours` | `168` | Rango de tiempo en horas (0 = todo) |
| `model` | | Filtrar por nombre de modelo |
| `engine` | | Filtrar por nombre de motor |
| `since` / `until` | | Rango de timestamps Unix (anula hours) |

### `GET /api/engine-history`

Historial de estado de motores (accesibilidad, conexiones TCP, caché KV, tokens predichos).

| Parámetro | Por defecto | Descripción |
|-----------|---------|-------------|
| `hours` | `168` | Rango de tiempo en horas |
| `engine` | | Filtrar por nombre de motor |

### `GET /api/benchmark-process`

Métricas de CPU y memoria a nivel de proceso de las ejecuciones de benchmark (retención de 7 días).

| Parámetro | Por defecto | Descripción |
|-----------|---------|-------------|
| `hours` | `168` | Rango de tiempo en horas |
| `engine` | | Filtrar por nombre de motor |

### `GET /api/metrics`

Formato de exposición de Prometheus. Indicadores que cubren métricas de sistema, motor, modelo y benchmark.

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'asiai'
    static_configs:
      - targets: ['localhost:8899']
    metrics_path: '/api/metrics'
    scrape_interval: 30s
```

Las métricas incluyen:

| Métrica | Tipo | Descripción |
|--------|------|-------------|
| `asiai_cpu_load_1m` | gauge | Promedio de carga de CPU (1 min) |
| `asiai_memory_used_bytes` | gauge | Memoria utilizada |
| `asiai_thermal_speed_limit_pct` | gauge | Límite de velocidad de CPU % |
| `asiai_engine_reachable{engine}` | gauge | Accesibilidad del motor (0/1) |
| `asiai_engine_models_loaded{engine}` | gauge | Cantidad de modelos cargados |
| `asiai_engine_tcp_connections{engine}` | gauge | Conexiones TCP establecidas |
| `asiai_engine_requests_processing{engine}` | gauge | Solicitudes en procesamiento |
| `asiai_engine_kv_cache_usage_ratio{engine}` | gauge | Ratio de llenado de caché KV (0-1) |
| `asiai_engine_tokens_predicted_total{engine}` | counter | Total acumulado de tokens predichos |
| `asiai_model_vram_bytes{engine,model}` | gauge | VRAM por modelo |
| `asiai_bench_tok_per_sec{engine,model}` | gauge | Último benchmark tok/s |

## Notas

- El panel se enlaza a `127.0.0.1` por defecto (solo localhost)
- Usa `--host 0.0.0.0` para exponer en la red (ej. para monitoreo remoto)
- El puerto `8899` se elige para evitar conflictos con los puertos de motores de inferencia
