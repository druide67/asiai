---
description: Comment asiai détecte les moteurs, collecte les métriques GPU via IOReport et stocke les données en séries temporelles. Plongée technique.
---

# Architecture

Comment les données circulent dans asiai — des capteurs matériels à votre terminal, navigateur et agents IA.

## Vue d'ensemble

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Votre Mac (Apple Silicon)                    │
│                                                                      │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐               │
│  │   Ollama     │   │  LM Studio  │   │   mlx-lm    │  ...moteurs   │
│  └──────┬───────┘   └──────┬──────┘   └──────┬──────┘               │
│         │ HTTP              │ HTTP            │ HTTP                  │
│         └──────────┬────────┴────────────────┘                       │
│                    ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────┐     │
│  │                      asiai core                              │     │
│  │                                                              │     │
│  │  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐      │     │
│  │  │ Moteurs  │  │ Collecteurs  │  │    Benchmark     │      │     │
│  │  │ adapters │  │  (GPU, CPU,  │  │  (warmup, runs,  │      │     │
│  │  │ (6 ABC   │  │   thermal,   │  │   median, CI95)  │      │     │
│  │  │  impls)  │  │   mémoire)   │  │                  │      │     │
│  │  └────┬─────┘  └──────┬───────┘  └────────┬─────────┘      │     │
│  │       │               │                    │                 │     │
│  │       └───────┬───────┴────────────────────┘                 │     │
│  │               ▼                                              │     │
│  │  ┌──────────────────────────────────┐                       │     │
│  │  │       Stockage (SQLite WAL)      │                       │     │
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
             │Claude Code│ │ Cursor  │ │ Agents IA │
             │  (MCP)    │ │  (MCP)  │ │  (HTTP)   │
             └───────────┘ └─────────┘ └───────────┘
```

## Fichiers clés

| Couche | Fichiers | Rôle |
|--------|----------|------|
| **Moteurs** | `src/asiai/engines/` | ABC `InferenceEngine` + 7 adaptateurs (Ollama, LM Studio, mlx-lm, llama.cpp, oMLX, vllm-mlx, Exo). Classe de base `OpenAICompatEngine` pour les moteurs compatibles OpenAI. |
| **Collecteurs** | `src/asiai/collectors/` | Métriques système : `gpu.py` (ioreg), `system.py` (CPU, mémoire, thermal), `processes.py` (activité d'inférence via lsof). |
| **Benchmark** | `src/asiai/benchmark/` | `runner.py` (warmup + N exécutions, médiane, stddev, CI95), `prompts.py` (prompts de test), `card.py` (génération de cartes SVG). |
| **Stockage** | `src/asiai/storage/` | `db.py` (SQLite WAL, tout le CRUD), `schema.py` (tables + migrations). |
| **CLI** | `src/asiai/cli.py` | Point d'entrée argparse, les 12 commandes. |
| **Web** | `src/asiai/web/` | FastAPI + htmx + SSE + ApexCharts dashboard. Routes dans `routes/`. |
| **MCP** | `src/asiai/mcp/` | Serveur FastMCP, 11 outils + 3 ressources. Transports : stdio, SSE, streamable-http. |
| **Conseiller** | `src/asiai/advisor/` | Recommandations adaptées au matériel (dimensionnement modèles, sélection moteur). |
| **Affichage** | `src/asiai/display/` | Formateurs ANSI (`formatters.py`), rendu CLI (`cli_renderer.py`), TUI (`tui.py`). |

## Flux de données

### Monitoring (mode daemon)

```
Toutes les 60s :
  collecteurs → snapshot dict → store_snapshot(db) → table models
                                                   → table metrics
  moteurs     → état moteur   → store_engine_status(db)
```

### Benchmark

```
CLI --bench → détecter moteurs → choisir modèle → warmup → N exécutions
           → calculer médiane/stddev/CI95 → store_benchmark(db)
           → afficher tableau (ANSI ou JSON)
           → optionnel : --share → POST vers l'API communautaire
           → optionnel : --card  → générer une carte SVG
```

### Dashboard web

```
Navigateur → FastAPI → template Jinja2 (rendu initial)
          → htmx SSE → /api/v1/stream → mises à jour temps réel
          → ApexCharts → /api/v1/metrics?hours=N → graphiques historiques
```

### Serveur MCP

```
Agent IA → stdio/SSE/HTTP → FastMCP → appel d'outil
        → exécute collecteur/benchmark dans un thread pool (asyncio.to_thread)
        → retourne du JSON structuré
```

## Principes de conception

1. **Zéro dépendance pour le cœur** — CLI, collecteurs, moteurs, stockage n'utilisent que la stdlib Python. Les extras optionnels (`[web]`, `[tui]`, `[mcp]`) ajoutent des dépendances uniquement quand c'est nécessaire.
2. **Couche de données partagée** — La même base SQLite sert au CLI, au web, au MCP et à Prometheus. Pas de stockage séparé.
3. **Pattern adaptateur** — Les 7 moteurs implémentent l'ABC `InferenceEngine`. Ajouter un nouveau moteur = 1 fichier + enregistrement dans `detect.py`.
4. **Imports paresseux** — Chaque commande CLI importe ses dépendances localement, gardant le temps de démarrage rapide.
5. **Natif macOS** — `ioreg` pour le GPU, `launchd` pour les daemons, `lsof` pour l'activité d'inférence. Pas d'abstractions Linux.
