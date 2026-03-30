---
description: Cómo asiai detecta motores, recopila métricas GPU vía IOReport y almacena datos de series temporales. Inmersión técnica.
---

# Arquitectura

Cómo fluyen los datos a través de asiai — desde los sensores de hardware hasta tu terminal, navegador y agentes IA.

## Descripción general

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Tu Mac (Apple Silicon)                       │
│                                                                      │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐               │
│  │   Ollama     │   │  LM Studio  │   │   mlx-lm    │  ...motores   │
│  └──────┬───────┘   └──────┬──────┘   └──────┬──────┘               │
│         │ HTTP              │ HTTP            │ HTTP                  │
│         └──────────┬────────┴────────────────┘                       │
│                    ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────┐     │
│  │                      asiai core                              │     │
│  │                                                              │     │
│  │  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐      │     │
│  │  │ Motores  │  │ Recolectores │  │    Benchmark     │      │     │
│  │  │ adapters │  │  (GPU, CPU,  │  │  (warmup, runs,  │      │     │
│  │  │ (6 ABC   │  │   térmico,   │  │   median, CI95)  │      │     │
│  │  │  impls)  │  │   memoria)   │  │                  │      │     │
│  │  └────┬─────┘  └──────┬───────┘  └────────┬─────────┘      │     │
│  │       │               │                    │                 │     │
│  │       └───────┬───────┴────────────────────┘                 │     │
│  │               ▼                                              │     │
│  │  ┌──────────────────────────────────┐                       │     │
│  │  │   Almacenamiento (SQLite WAL)    │                       │     │
│  │  │  metrics · models · benchmarks   │                       │     │
│  │  │  engine_status · alerts          │                       │     │
│  │  │  community_submissions           │                       │     │
│  │  └──────────────┬───────────────────┘                       │     │
│  │                 │                                            │     │
│  └─────────────────┼────────────────────────────────────────────┘     │
│                    │                                                  │
│         ┌──────────┼──────────┬─────────────┐                        │
│         ▼          ▼          ▼             ▼                         │
│  ┌───────────┐ ┌────────┐ ┌──────────┐ ┌──────────┐                │
│  │    CLI    │ │  Web   │ │   MCP    │ │Prometheus│                │
│  │  (ANSI,  │ │(htmx,  │ │ (stdio,  │ │ /metrics │                │
│  │  --json) │ │ SSE,   │ │  SSE,    │ │          │                │
│  │          │ │ charts)│ │  HTTP)   │ │          │                │
│  └───────────┘ └────────┘ └──────────┘ └──────────┘                │
│                                │                                     │
└────────────────────────────────┼─────────────────────────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
             ┌───────────┐ ┌─────────┐ ┌───────────┐
             │Claude Code│ │ Cursor  │ │ Agentes   │
             │  (MCP)    │ │  (MCP)  │ │ IA (HTTP) │
             └───────────┘ └─────────┘ └───────────┘
```

## Archivos clave

| Capa | Archivos | Función |
|------|----------|---------|
| **Motores** | `src/asiai/engines/` | ABC `InferenceEngine` + 7 adaptadores (Ollama, LM Studio, mlx-lm, llama.cpp, oMLX, vllm-mlx, Exo). Clase base `OpenAICompatEngine` para motores compatibles con OpenAI. |
| **Recolectores** | `src/asiai/collectors/` | Métricas del sistema: `gpu.py` (ioreg), `system.py` (CPU, memoria, térmico), `processes.py` (actividad de inferencia vía lsof). |
| **Benchmark** | `src/asiai/benchmark/` | `runner.py` (warmup + N ejecuciones, mediana, stddev, CI95), `prompts.py` (prompts de prueba), `card.py` (generación de tarjetas SVG). |
| **Almacenamiento** | `src/asiai/storage/` | `db.py` (SQLite WAL, todo el CRUD), `schema.py` (tablas + migraciones). |
| **CLI** | `src/asiai/cli.py` | Punto de entrada Argparse, los 12 comandos. |
| **Web** | `src/asiai/web/` | FastAPI + htmx + SSE + dashboard ApexCharts. Rutas en `routes/`. |
| **MCP** | `src/asiai/mcp/` | Servidor FastMCP, 11 herramientas + 3 recursos. Transportes: stdio, SSE, streamable-http. |
| **Asesor** | `src/asiai/advisor/` | Recomendaciones basadas en hardware (dimensionamiento de modelos, selección de motor). |
| **Visualización** | `src/asiai/display/` | Formateadores ANSI (`formatters.py`), renderizador CLI (`cli_renderer.py`), TUI (`tui.py`). |

## Flujo de datos

### Monitorización (modo daemon)

```
Cada 60s:
  recolectores → dict instantánea → store_snapshot(db) → tabla models
                                                       → tabla metrics
  motores      → estado del motor → store_engine_status(db)
```

### Benchmark

```
CLI --bench → detectar motores → elegir modelo → warmup → N ejecuciones
           → calcular mediana/stddev/CI95 → store_benchmark(db)
           → renderizar tabla (ANSI o JSON)
           → opcional: --share → POST a API comunitaria
           → opcional: --card  → generar tarjeta SVG
```

### Dashboard web

```
Navegador → FastAPI → plantilla Jinja2 (renderizado inicial)
         → htmx SSE → /api/v1/stream → actualizaciones en tiempo real
         → ApexCharts → /api/v1/metrics?hours=N → gráficos históricos
```

### Servidor MCP

```
Agente IA → stdio/SSE/HTTP → FastMCP → llamada a herramienta
         → ejecuta recolector/benchmark en pool de hilos (asyncio.to_thread)
         → devuelve JSON estructurado
```

## Principios de diseño

1. **Cero dependencias para el núcleo** — CLI, recolectores, motores, almacenamiento usan solo stdlib de Python. Los extras opcionales (`[web]`, `[tui]`, `[mcp]`) añaden dependencias solo cuando es necesario.
2. **Capa de datos compartida** — La misma base de datos SQLite sirve al CLI, web, MCP y Prometheus. Sin almacenes de datos separados.
3. **Patrón adaptador** — Los 7 motores implementan el ABC `InferenceEngine`. Añadir un nuevo motor = 1 archivo + registrar en `detect.py`.
4. **Imports perezosos** — Cada comando CLI importa sus dependencias localmente, manteniendo el tiempo de arranque rápido.
5. **Nativo de macOS** — `ioreg` para GPU, `launchd` para daemons, `lsof` para actividad de inferencia. Sin abstracciones Linux.
