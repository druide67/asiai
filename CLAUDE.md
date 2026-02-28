# CLAUDE.md — asiai

## Projet

**asiai** — CLI open-source pour gerer, benchmarker et monitorer l'inference LLM locale sur Apple Silicon.

- **Repo** : `druide67/asiai` (prive, passage public a v0.1)
- **Langage** : Python 3.11+, zero dependance externe (stdlib) pour le core
- **Cible** : macOS Apple Silicon uniquement (M1/M2/M3/M4). Pas de Linux, pas de Windows.
- **License** : Apache 2.0

## Architecture

```
asiai/
├── src/asiai/
│   ├── cli.py              # Point d'entree CLI (argparse)
│   ├── engines/            # Adapters moteurs (Ollama, LM Studio, MLX, OpenAI-compat)
│   ├── collectors/         # Collecteurs metriques (system, inference, macOS natif)
│   ├── benchmark/          # Runner + prompts standardises + reporter
│   ├── storage/            # SQLite (schema, migrations, dataclasses)
│   ├── advisor/            # Recommandations hardware-aware
│   └── display/            # Renderers (CLI, TUI Textual, Web FastAPI+htmx)
├── tests/                  # pytest
├── docs/                   # MkDocs-Material
└── pyproject.toml          # hatchling build
```

**Pattern cle** : Shared Data Layer — le code metier (SQLite, API moteurs) est partage entre CLI, TUI et Web. Seul le renderer differe.

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

# Verifier le package
pip install -e . && asiai --version && asiai detect
```

## Regles de code

### Style
- **Langue** : tout en anglais (code, commentaires, commits, README, docs)
- **Formatage** : ruff, line-length 100
- **Types** : type hints partout, pas de `Any` sauf justifie
- **Docstrings** : Google style, en anglais
- **Imports** : isort via ruff (I)

### Architecture
- **Zero dependance core** : le coeur (engines, collectors, storage) ne depend que de la stdlib Python. Les dependances optionnelles (rich, textual, fastapi) sont des extras.
- **Engine adapters** : chaque moteur implemente `InferenceEngine` (ABC). Ajouter un moteur = ajouter un fichier dans `engines/`.
- **macOS natif** : utiliser sysctl, vm_stat, pmset, IOReport pour les metriques. Pas de psutil.
- **SQLite** : schema versionne avec migrations. Retention automatique 90 jours.

### Tests
- **pytest** obligatoire pour tout nouveau code
- **Mocks** : mocker les appels HTTP (pas de vrai serveur Ollama/LM Studio en CI)
- **Pas de tests qui necessitent du hardware Apple Silicon** en CI (marquer avec `@pytest.mark.apple_silicon`)

### Commits
- **Format** : Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`)
- **Langue** : anglais
- **Pas de co-author automatique**

### Securite
- **Jamais de telemetrie** : aucun appel reseau sauf vers les moteurs locaux
- **Pas de secrets** : l'outil ne gere pas de tokens/cles
- **subprocess** : toujours avec liste d'args (pas de shell=True)
- **SQLite** : parametres lies (pas de f-string dans les requetes)

## Contexte projet

### Origine
Spin-off du projet OpenClaw (swarm multi-agents IA sur Mac Mini M4 Pro 64 Go). Le code du health agent v1.1 (650 lignes, production) et des scripts de benchmark sont la base de l'extraction.

### Docs strategie
Les documents de strategie (etude de marche, SWOT, plan marketing, reseaux sociaux) sont dans le vault OpenClaw, PAS dans ce repo : `openclaw-macos-hardened/docs/obsidian-vault/07 - Projets Annexes/inference-pilot/`

### Identite
- GitHub : `druide67`
- X : `@druide67`
- LinkedIn : Jean-Marc Nahlovsky
- Le nom "asiai" (ASI + AI) n'est pas encore verrouille. Si le nom change, renommer le package, le repo, et les references.

## Roadmap

| Version | Scope | Statut |
|---------|-------|--------|
| v0.1 | detect + bench + monitor (CLI, stdlib only) | En cours |
| v0.2 | recommend + analyze + TUI (Textual) | Planifie |
| v0.3 | Dashboard web (FastAPI + htmx + ApexCharts) | Planifie |
| v1.0 | Multi-serveur, plugins, Homebrew Core | Planifie |
