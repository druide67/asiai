# Architecture

How data flows through asiai — from hardware sensors to your terminal, browser, and AI agents.

## Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Your Mac (Apple Silicon)                     │
│                                                                      │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐               │
│  │   Ollama     │   │  LM Studio  │   │   mlx-lm    │  ...engines   │
│  └──────┬───────┘   └──────┬──────┘   └──────┬──────┘               │
│         │ HTTP              │ HTTP            │ HTTP                  │
│         └──────────┬────────┴────────────────┘                       │
│                    ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────┐     │
│  │                      asiai core                              │     │
│  │                                                              │     │
│  │  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐      │     │
│  │  │ Engines  │  │  Collectors  │  │    Benchmark     │      │     │
│  │  │ adapters │  │  (GPU, CPU,  │  │  (warmup, runs,  │      │     │
│  │  │ (6 ABC   │  │   thermal,   │  │   median, CI95)  │      │     │
│  │  │  impls)  │  │   memory)    │  │                  │      │     │
│  │  └────┬─────┘  └──────┬───────┘  └────────┬─────────┘      │     │
│  │       │               │                    │                 │     │
│  │       └───────┬───────┴────────────────────┘                 │     │
│  │               ▼                                              │     │
│  │  ┌──────────────────────────────────┐                       │     │
│  │  │       Storage (SQLite WAL)       │                       │     │
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
             │Claude Code│ │ Cursor  │ │ AI agents │
             │  (MCP)    │ │  (MCP)  │ │  (HTTP)   │
             └───────────┘ └─────────┘ └───────────┘
```

## Key files

| Layer | Files | Role |
|-------|-------|------|
| **Engines** | `src/asiai/engines/` | ABC `InferenceEngine` + 6 adapters (Ollama, LM Studio, mlx-lm, llama.cpp, vllm-mlx, Exo). `OpenAICompatEngine` base class for OpenAI-compatible engines. |
| **Collectors** | `src/asiai/collectors/` | System metrics: `gpu.py` (ioreg), `system.py` (CPU, memory, thermal), `processes.py` (inference activity via lsof). |
| **Benchmark** | `src/asiai/benchmark/` | `runner.py` (warmup + N runs, median, stddev, CI95), `prompts.py` (test prompts), `card.py` (SVG card generation). |
| **Storage** | `src/asiai/storage/` | `db.py` (SQLite WAL, all CRUD), `schema.py` (tables + migrations). |
| **CLI** | `src/asiai/cli.py` | Argparse entry point, all 12 commands. |
| **Web** | `src/asiai/web/` | FastAPI + htmx + SSE + ApexCharts dashboard. Routes in `routes/`. |
| **MCP** | `src/asiai/mcp/` | FastMCP server, 10 tools + 3 resources. Transports: stdio, SSE, streamable-http. |
| **Advisor** | `src/asiai/advisor/` | Hardware-aware recommendations (model sizing, engine selection). |
| **Display** | `src/asiai/display/` | ANSI formatters (`formatters.py`), CLI renderer (`cli_renderer.py`), TUI (`tui.py`). |

## Data flow

### Monitoring (daemon mode)

```
Every 60s:
  collectors → snapshot dict → store_snapshot(db) → models table
                                                  → metrics table
  engines    → engine status → store_engine_status(db)
```

### Benchmark

```
CLI --bench → detect engines → pick model → warmup → N runs
           → compute median/stddev/CI95 → store_benchmark(db)
           → render table (ANSI or JSON)
           → optional: --share → POST to community API
           → optional: --card  → generate SVG card
```

### Web dashboard

```
Browser → FastAPI → Jinja2 template (initial render)
       → htmx SSE → /api/v1/stream → real-time updates
       → ApexCharts → /api/v1/metrics?hours=N → historical graphs
```

### MCP server

```
AI agent → stdio/SSE/HTTP → FastMCP → tool call
        → runs collector/benchmark in thread pool (asyncio.to_thread)
        → returns structured JSON
```

## Design principles

1. **Zero dependencies for core** — CLI, collectors, engines, storage use only stdlib Python. Optional extras (`[web]`, `[tui]`, `[mcp]`) add dependencies only when needed.
2. **Shared Data Layer** — The same SQLite database serves CLI, web, MCP, and Prometheus. No separate data stores.
3. **Adapter pattern** — All 6 engines implement `InferenceEngine` ABC. Adding a new engine = 1 file + register in `detect.py`.
4. **Lazy imports** — Each CLI command imports its dependencies locally, keeping startup time fast.
5. **macOS-native** — `ioreg` for GPU, `launchd` for daemons, `lsof` for inference activity. No Linux abstractions.
