# CLAUDE.md — asiai

## Projet

**asiai** — CLI open-source pour gérer, benchmarker et monitorer l'inférence LLM locale sur Apple Silicon.

- **Repo** : `druide67/asiai`
- **Langage** : Python 3.11+, zéro dépendance externe (stdlib) pour le core
- **Cible** : macOS Apple Silicon uniquement (M1/M2/M3/M4). Pas de Linux, pas de Windows.
- **License** : Apache 2.0

## Architecture

```
asiai/
├── src/asiai/
│   ├── cli.py              # Point d'entrée CLI (argparse)
│   ├── doctor.py           # Diagnostic installation et environnement
│   ├── daemon.py           # Gestion daemon launchd (monitoring continu)
│   ├── engines/            # Adapters moteurs (5 moteurs)
│   │   ├── base.py         # ABC InferenceEngine + dataclasses
│   │   ├── openai_compat.py # Base class OpenAI-compatible (template method)
│   │   ├── detect.py       # Auto-détection moteurs (ports 11434, 1234, 8080, 8000)
│   │   ├── ollama.py       # Adapter Ollama (API native)
│   │   ├── lmstudio.py     # Adapter LM Studio (OpenAI-compatible)
│   │   ├── mlxlm.py        # Adapter mlx-lm (OpenAI-compatible, Apple MLX natif)
│   │   ├── llamacpp.py     # Adapter llama.cpp (OpenAI-compatible, GGUF)
│   │   └── vllm_mlx.py     # Adapter vllm-mlx (OpenAI-compatible, MLX)
│   ├── collectors/         # Collecteurs métriques (system, inference, power, macOS natif)
│   │   └── power.py        # PowerMonitor (sudo powermetrics, GPU/CPU watts)
│   ├── benchmark/          # Runner + prompts standardisés + reporter + regression
│   │   └── regression.py   # Détection de régression vs historique SQLite
│   ├── storage/            # SQLite (schema, migrations, dataclasses)
│   ├── advisor/            # Recommandations hardware-aware
│   └── display/            # Renderers (CLI, TUI Textual, Web FastAPI+htmx)
│       ├── cli_renderer.py # Rendu CLI (detect, bench, doctor, monitor)
│       ├── formatters.py   # Helpers formatage (ANSI, bytes, uptime)
│       ├── tui.py          # Dashboard Textual (optionnel)
│       └── tui.tcss        # Styles Textual
├── tests/                  # pytest (201 unit + 7 integration)
│   ├── conftest.py         # Flag --integration
│   └── test_integration.py # Tests end-to-end (vrais moteurs, skip par défaut)
├── docs/                   # MkDocs-Material
└── pyproject.toml          # hatchling build
```

**Pattern clé** : Shared Data Layer — le code métier (SQLite, API moteurs) est partagé entre CLI, TUI et Web. Seul le renderer diffère.

## Stack technique

| Composant | Techno | Phase | Statut |
|-----------|--------|-------|--------|
| Core CLI | stdlib Python (argparse, urllib, sqlite3, subprocess) | v0.1 | Done |
| Engines | Ollama + LM Studio + mlx-lm + llama.cpp + vllm-mlx adapters | v0.1-v0.3 | Done |
| Benchmark | Runner + prompts standardisés + reporter | v0.1 | Done |
| Doctor | Diagnostic installation et environnement | v0.2 | Done |
| Daemon | launchd monitoring continu (plistlib) | v0.2 | Done |
| TUI | Textual (optionnel) | v0.2 | Done |
| API web | FastAPI + uvicorn | v0.3 | Planifié |
| Frontend web | htmx + Jinja2 + ApexCharts | v0.3 | Planifié |
| Docs site | MkDocs-Material | v0.1 | Planifié |
| Distribution | PyPI (pipx) + Homebrew Tap (druide67/tap) | v0.1 | Done |

## Commandes de dev

```bash
# Installation dev
pip install -e ".[dev]"

# Installation avec TUI
pip install -e ".[dev,tui]"

# Tests unitaires
pytest

# Tests d'intégration (vrais moteurs requis)
pytest --integration -v

# Lint
ruff check src/ tests/
ruff format src/ tests/

# Vérifier le package
pip install -e . && asiai --version && asiai detect
```

## Commandes CLI

| Commande | Description | Phase |
|----------|-----------|-------|
| `asiai detect` | Auto-détection 5 moteurs (Ollama, LM Studio, mlx-lm, llama.cpp, vllm-mlx) | v0.1 |
| `asiai models` | Liste des modèles chargés par moteur | v0.1 |
| `asiai monitor` | Snapshot système + inférence, stocké en SQLite | v0.1 |
| `asiai bench` | Benchmark cross-engine avec prompts standardisés | v0.1 |
| `asiai bench --runs N` | Multi-run benchmark avec mean ± stddev et classification stabilité | v0.3 |
| `asiai bench --power` | Mesure tok/s per watt via powermetrics (sudo requis) | v0.3 |
| `asiai doctor` | Diagnostic installation, 5 moteurs, système, DB | v0.2 |
| `asiai daemon start\|stop\|status\|logs` | Monitoring continu via launchd | v0.2 |
| `asiai tui` | Dashboard interactif Textual (optionnel) | v0.2 |

## Règles de code

### Style
- **Langue** : tout en anglais (code, commentaires, commits, README, docs)
- **Formatage** : ruff, line-length 100
- **Types** : type hints partout, pas de `Any` sauf justifié
- **Docstrings** : Google style, en anglais
- **Imports** : isort via ruff (I)

### Architecture
- **Zéro dépendance core** : le cœur (engines, collectors, storage) ne dépend que de la stdlib Python. Les dépendances optionnelles (rich, textual, fastapi) sont des extras.
- **Engine adapters** : chaque moteur implémente `InferenceEngine` (ABC). 4 moteurs OpenAI-compatible héritent de `OpenAICompatEngine` (template method). Ajouter un moteur = ajouter un fichier dans `engines/`. Moteurs actuels : Ollama, LM Studio, mlx-lm, llama.cpp, vllm-mlx.
- **macOS natif** : utiliser sysctl, vm_stat, pmset, IOReport pour les métriques. Pas de psutil.
- **SQLite** : schéma versionné avec migrations. Rétention automatique 90 jours.

### Tests
- **pytest** obligatoire pour tout nouveau code
- **Mocks** : mocker les appels HTTP (pas de vrai serveur Ollama/LM Studio/mlx-lm en CI)
- **Pas de tests qui nécessitent du hardware Apple Silicon** en CI (marquer avec `@pytest.mark.apple_silicon`)
- **Tests d'intégration** : `pytest --integration -v` (vrais moteurs requis, skippés par défaut)

### Commits
- **Format** : Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`)
- **Langue** : anglais
- **Pas de co-author automatique**

### Sécurité
- **Jamais de télémétrie** : aucun appel réseau sauf vers les moteurs locaux
- **Pas de secrets** : l'outil ne gère pas de tokens/clés
- **subprocess** : toujours avec liste d'args (pas de shell=True)
- **SQLite** : paramètres liés (pas de f-string dans les requêtes)

### Exception handling
- **Jamais de `except: pass` silencieux** : toujours au minimum `logger.debug()` avec le message d'erreur
- **Exceptions attendues** (réseau, process) : `except (URLError, OSError) as e: logger.debug(...)`
- **Erreurs utilisateur** : messages descriptifs avec contexte (modèle, moteur, URL) — pas de "request failed" générique
- **Pattern HTTP** : `http_get_json` / `http_post_json` retournent `(None, {})` en cas d'échec, avec log debug. `http_post_json` retourne `{"error": "message spécifique"}` pour TimeoutError, ConnectionRefused, URLError.

### CLI output
- **Couleurs** : `red("✗")` erreurs, `yellow("⚠")` warnings, `green("✓"/"●")` succès, `dim()` info secondaire, `bold()` titres
- **NO_COLOR** : respecté via `_supports_color()` dans `formatters.py`
- **Alignement ANSI** : toujours padder la string AVANT d'appliquer la couleur (`green(f"{text:<12}")` pas `f"{green(text):<12}"`)
- **stderr** : erreurs et warnings vers `sys.stderr`, données normales vers stdout

### Locale safety
- **`ps aux`** et **`sysctl -n vm.loadavg`** : affectés par la locale (virgule décimale FR). Toujours `.replace(",", ".")` avant `float()`.
- **`vm_stat`, `powermetrics`** : utilisent la locale C/POSIX, pas de risque.
- **Règle générale** : tout `float()` sur une sortie de commande système doit gérer le séparateur décimal.

## Contexte projet

### Origine
Spin-off du projet OpenClaw (swarm multi-agents IA sur Mac Mini M4 Pro 64 Go). Le code du health agent v1.1 (650 lignes, production) et des scripts de benchmark sont la base de l'extraction.

### Docs stratégie
Les documents de stratégie (étude de marché, SWOT, plan marketing, réseaux sociaux) sont dans le vault OpenClaw, PAS dans ce repo. Ils sont accessibles via le working directory supplémentaire configuré dans `.claude/settings.json` :
- Chemin : `/Users/jmn/projets/openclaw-macos-hardened/docs/obsidian-vault/07 - Projets Annexes/inference-pilot/`
- Fichiers : 00-Vision, 01-Etude-Marche, 02-Fonctionnalites, 03-Architecture, 04-Securite, 05-SWOT, 06-Plan-Communication, 07-Plan-Marketing, 08-Questions-Ouvertes, 09-Reseaux-Sociaux
- **Ne jamais copier ces fichiers dans ce repo** — ils contiennent la stratégie privée

### Identité
- GitHub : `druide67`
- X : `@jmn67`
- LinkedIn : Jean-Marc Nahlovsky
- Nom "asiai" validé (ASI + AI)

## Roadmap

| Version | Scope | Statut |
|---------|-------|--------|
| **v0.1** | detect + bench + monitor + models (CLI, stdlib) | **Done** |
| **v0.2** | mlx-lm + doctor + daemon launchd + TUI (Textual) | **Done** |
| **v0.3** | vllm-mlx + llama.cpp + tok/s per watt + variance + regression + load time | **En cours** |
| v1.0 | Multi-serveur, plugins, Homebrew Core | Planifié |

### v0.3 — Scope détaillé

**P0 — Must have** :
- ~~vllm-mlx adapter (5ème moteur, 400+ tok/s, continuous batching)~~ **Done**
- ~~tok/s per watt (puissance GPU via powermetrics — killer feature)~~ **Done**
- ~~Stabilité benchmark (multi-runs, mean ± stddev)~~ **Done**

**P1 — Should have** :
- ~~llama.cpp server adapter (4ème moteur, `brew install llama.cpp`)~~ **Done**
- ~~Temps de chargement modèle (cold load vs warm)~~ **Done**
- ~~Détection moteurs par processus (`lsof -i :PORT`)~~ **Done**
- ~~Détection de régression (comparaison auto après update moteur/OS)~~ **Done**

**P2 — Could have** :
- Dashboard web (FastAPI + htmx + ApexCharts)
- Export Prometheus
- Débit concurrent (batching vllm-mlx)

**Détection moteurs OpenAI-compatible** : cascade `/lms/version` → `/health`+`/props` → `/version` → fallback mlx-lm. Signal complémentaire : `lsof -i :PORT`. Ports à scanner : 11434, 1234, 8080, 8000, 8081.
