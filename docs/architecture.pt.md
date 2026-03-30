---
description: Como o asiai detecta engines, coleta métricas de GPU via IOReport e armazena dados em séries temporais. Mergulho técnico.
---

# Arquitetura

Como os dados fluem pelo asiai — dos sensores de hardware até seu terminal, navegador e agentes de IA.

## Visão Geral

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Seu Mac (Apple Silicon)                      │
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
│  │  │ Engines  │  │  Coletores   │  │    Benchmark     │      │     │
│  │  │ adapters │  │  (GPU, CPU,  │  │  (warmup, runs,  │      │     │
│  │  │ (6 ABC   │  │   térmico,   │  │   mediana, CI95) │      │     │
│  │  │  impls)  │  │   memória)   │  │                  │      │     │
│  │  └────┬─────┘  └──────┬───────┘  └────────┬─────────┘      │     │
│  │       │               │                    │                 │     │
│  │       └───────┬───────┴────────────────────┘                 │     │
│  │               ▼                                              │     │
│  │  ┌──────────────────────────────────┐                       │     │
│  │  │    Armazenamento (SQLite WAL)    │                       │     │
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

## Arquivos-chave

| Camada | Arquivos | Papel |
|--------|----------|-------|
| **Engines** | `src/asiai/engines/` | ABC `InferenceEngine` + 7 adaptadores (Ollama, LM Studio, mlx-lm, llama.cpp, oMLX, vllm-mlx, Exo). Classe base `OpenAICompatEngine` para engines compatíveis com OpenAI. |
| **Coletores** | `src/asiai/collectors/` | Métricas do sistema: `gpu.py` (ioreg), `system.py` (CPU, memória, térmico), `processes.py` (atividade de inferência via lsof). |
| **Benchmark** | `src/asiai/benchmark/` | `runner.py` (warmup + N execuções, mediana, desvio padrão, CI95), `prompts.py` (prompts de teste), `card.py` (geração de card SVG). |
| **Armazenamento** | `src/asiai/storage/` | `db.py` (SQLite WAL, todo CRUD), `schema.py` (tabelas + migrações). |
| **CLI** | `src/asiai/cli.py` | Ponto de entrada argparse, todos os 12 comandos. |
| **Web** | `src/asiai/web/` | FastAPI + htmx + SSE + dashboard ApexCharts. Rotas em `routes/`. |
| **MCP** | `src/asiai/mcp/` | Servidor FastMCP, 11 ferramentas + 3 recursos. Transportes: stdio, SSE, streamable-http. |
| **Advisor** | `src/asiai/advisor/` | Recomendações baseadas em hardware (dimensionamento de modelos, seleção de engine). |
| **Display** | `src/asiai/display/` | Formatadores ANSI (`formatters.py`), renderizador CLI (`cli_renderer.py`), TUI (`tui.py`). |

## Fluxo de dados

### Monitoramento (modo daemon)

```
A cada 60s:
  coletores → dict snapshot → store_snapshot(db) → tabela models
                                                 → tabela metrics
  engines   → status da engine → store_engine_status(db)
```

### Benchmark

```
CLI --bench → detectar engines → escolher modelo → warmup → N execuções
           → calcular mediana/desvio/CI95 → store_benchmark(db)
           → renderizar tabela (ANSI ou JSON)
           → opcional: --share → POST para API comunitária
           → opcional: --card  → gerar card SVG
```

### Dashboard web

```
Navegador → FastAPI → template Jinja2 (renderização inicial)
          → htmx SSE → /api/v1/stream → atualizações em tempo real
          → ApexCharts → /api/v1/metrics?hours=N → gráficos históricos
```

### Servidor MCP

```
Agente IA → stdio/SSE/HTTP → FastMCP → chamada de ferramenta
          → executa coletor/benchmark em thread pool (asyncio.to_thread)
          → retorna JSON estruturado
```

## Princípios de design

1. **Zero dependências no core** — CLI, coletores, engines, armazenamento usam apenas a stdlib do Python. Extras opcionais (`[web]`, `[tui]`, `[mcp]`) adicionam dependências apenas quando necessário.
2. **Camada de dados compartilhada** — O mesmo banco SQLite serve CLI, web, MCP e Prometheus. Sem armazenamentos separados.
3. **Padrão adaptador** — Todas as 7 engines implementam a ABC `InferenceEngine`. Adicionar uma nova engine = 1 arquivo + registrar em `detect.py`.
4. **Imports lazy** — Cada comando CLI importa suas dependências localmente, mantendo o tempo de inicialização rápido.
5. **Nativo macOS** — `ioreg` para GPU, `launchd` para daemons, `lsof` para atividade de inferência. Sem abstrações Linux.
