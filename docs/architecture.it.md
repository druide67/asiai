---
description: Come asiai rileva i motori, raccoglie le metriche GPU tramite IOReport e archivia dati in serie temporali. Approfondimento tecnico.
---

# Architettura

Come i dati fluiscono attraverso asiai — dai sensori hardware al terminale, al browser e agli agenti IA.

## Panoramica

![asiai architecture overview](assets/architecture.svg)

## File principali

| Livello | File | Ruolo |
|-------|-------|------|
| **Motori** | `src/asiai/engines/` | ABC `InferenceEngine` + 7 adapter (Ollama, LM Studio, mlx-lm, llama.cpp, oMLX, vllm-mlx, Exo). Classe base `OpenAICompatEngine` per motori compatibili con OpenAI. |
| **Collettori** | `src/asiai/collectors/` | Metriche di sistema: `gpu.py` (ioreg), `system.py` (CPU, memoria, termica), `processes.py` (attività di inferenza via lsof). |
| **Benchmark** | `src/asiai/benchmark/` | `runner.py` (warmup + N esecuzioni, mediana, stddev, CI95), `prompts.py` (prompt di test), `card.py` (generazione scheda SVG). |
| **Storage** | `src/asiai/storage/` | `db.py` (SQLite WAL, tutti i CRUD), `schema.py` (tabelle + migrazioni). |
| **CLI** | `src/asiai/cli.py` | Punto d'ingresso Argparse, tutti i 12 comandi. |
| **Web** | `src/asiai/web/` | Dashboard FastAPI + htmx + SSE + ApexCharts. Route in `routes/`. |
| **MCP** | `src/asiai/mcp/` | Server FastMCP, 11 strumenti + 3 risorse. Trasporti: stdio, SSE, streamable-http. |
| **Advisor** | `src/asiai/advisor/` | Raccomandazioni consapevoli dell'hardware (dimensionamento modelli, selezione motore). |
| **Display** | `src/asiai/display/` | Formattatori ANSI (`formatters.py`), renderer CLI (`cli_renderer.py`), TUI (`tui.py`). |

## Flusso dei dati

### Monitoraggio (modalità daemon)

```
Ogni 60s:
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

### Dashboard web

```
Browser → FastAPI → Jinja2 template (render iniziale)
       → htmx SSE → /api/v1/stream → aggiornamenti in tempo reale
       → ApexCharts → /api/v1/metrics?hours=N → grafici storici
```

### Server MCP

```
AI agent → stdio/SSE/HTTP → FastMCP → tool call
        → esegue collector/benchmark in thread pool (asyncio.to_thread)
        → restituisce JSON strutturato
```

## Principi di design

1. **Zero dipendenze per il core** — CLI, collettori, motori, storage usano solo la stdlib Python. Gli extra opzionali (`[web]`, `[tui]`, `[mcp]`) aggiungono dipendenze solo quando necessario.
2. **Livello dati condiviso** — Lo stesso database SQLite serve CLI, web, MCP e Prometheus. Nessun archivio dati separato.
3. **Pattern adapter** — Tutti i 7 motori implementano l'ABC `InferenceEngine`. Aggiungere un nuovo motore = 1 file + registrazione in `detect.py`.
4. **Import lazy** — Ogni comando CLI importa le sue dipendenze localmente, mantenendo veloce il tempo di avvio.
5. **Nativo macOS** — `ioreg` per la GPU, `launchd` per i daemon, `lsof` per l'attività di inferenza. Nessuna astrazione Linux.
