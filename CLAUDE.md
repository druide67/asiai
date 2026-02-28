# CLAUDE.md — asiai

## Projet

**asiai** — CLI open-source pour gérer, benchmarker et monitorer l'inférence LLM locale sur Apple Silicon.

- **Repo** : `druide67/asiai` (privé, passage public à v0.1)
- **Langage** : Python 3.11+, zéro dépendance externe (stdlib) pour le core
- **Cible** : macOS Apple Silicon uniquement (M1/M2/M3/M4). Pas de Linux, pas de Windows.
- **License** : Apache 2.0

## Architecture

```
asiai/
├── src/asiai/
│   ├── cli.py              # Point d'entrée CLI (argparse)
│   ├── engines/            # Adapters moteurs (Ollama, LM Studio, MLX, OpenAI-compat)
│   ├── collectors/         # Collecteurs métriques (system, inference, macOS natif)
│   ├── benchmark/          # Runner + prompts standardisés + reporter
│   ├── storage/            # SQLite (schema, migrations, dataclasses)
│   ├── advisor/            # Recommandations hardware-aware
│   └── display/            # Renderers (CLI, TUI Textual, Web FastAPI+htmx)
├── tests/                  # pytest
├── docs/                   # MkDocs-Material
└── pyproject.toml          # hatchling build
```

**Pattern clé** : Shared Data Layer — le code métier (SQLite, API moteurs) est partagé entre CLI, TUI et Web. Seul le renderer diffère.

## Stack technique

| Composant | Techno | Phase |
|-----------|--------|-------|
| Core CLI | stdlib Python (argparse, urllib, sqlite3, subprocess) | v0.1 |
| Formatage | rich (optionnel) | v0.1 |
| TUI | Textual | v0.2 |
| API web | FastAPI + uvicorn | v0.3 |
| Frontend web | htmx + Jinja2 + ApexCharts | v0.3 |
| Docs site | MkDocs-Material | v0.1 |
| Distribution | PyPI (pipx) + Homebrew Tap (druide67/tap) | v0.1 |

## Commandes de dev

```bash
# Installation dev
pip install -e ".[dev]"

# Tests
pytest

# Lint
ruff check src/ tests/
ruff format src/ tests/

# Vérifier le package
pip install -e . && asiai --version && asiai detect
```

## Règles de code

### Style
- **Langue** : tout en anglais (code, commentaires, commits, README, docs)
- **Formatage** : ruff, line-length 100
- **Types** : type hints partout, pas de `Any` sauf justifié
- **Docstrings** : Google style, en anglais
- **Imports** : isort via ruff (I)

### Architecture
- **Zéro dépendance core** : le cœur (engines, collectors, storage) ne dépend que de la stdlib Python. Les dépendances optionnelles (rich, textual, fastapi) sont des extras.
- **Engine adapters** : chaque moteur implémente `InferenceEngine` (ABC). Ajouter un moteur = ajouter un fichier dans `engines/`.
- **macOS natif** : utiliser sysctl, vm_stat, pmset, IOReport pour les métriques. Pas de psutil.
- **SQLite** : schéma versionné avec migrations. Rétention automatique 90 jours.

### Tests
- **pytest** obligatoire pour tout nouveau code
- **Mocks** : mocker les appels HTTP (pas de vrai serveur Ollama/LM Studio en CI)
- **Pas de tests qui nécessitent du hardware Apple Silicon** en CI (marquer avec `@pytest.mark.apple_silicon`)

### Commits
- **Format** : Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`)
- **Langue** : anglais
- **Pas de co-author automatique**

### Sécurité
- **Jamais de télémétrie** : aucun appel réseau sauf vers les moteurs locaux
- **Pas de secrets** : l'outil ne gère pas de tokens/clés
- **subprocess** : toujours avec liste d'args (pas de shell=True)
- **SQLite** : paramètres liés (pas de f-string dans les requêtes)

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
- Le nom "asiai" (ASI + AI) n'est pas encore verrouillé. Si le nom change, renommer le package, le repo, et les références.

## Roadmap

| Version | Scope | Statut |
|---------|-------|--------|
| v0.1 | detect + bench + monitor (CLI, stdlib only) | En cours |
| v0.2 | recommend + analyze + TUI (Textual) | Planifié |
| v0.3 | Dashboard web (FastAPI + htmx + ApexCharts) | Planifié |
| v1.0 | Multi-serveur, plugins, Homebrew Core | Planifié |
