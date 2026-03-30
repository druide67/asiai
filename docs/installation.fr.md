---
description: Installer asiai via pip, Homebrew ou depuis les sources. Prérequis : macOS sur Apple Silicon (M1+), Python 3.11+.
---

# Installation

## pipx (recommandé)

```bash
pipx install asiai
```

## Homebrew

```bash
brew tap druide67/tap
brew install asiai
```

## pip

```bash
pip install asiai
```

## Essayer sans installer

```bash
uvx asiai detect           # Nécessite uv
```

## Extras optionnels

```bash
pip install "asiai[web]"   # Dashboard web (FastAPI + graphiques)
pip install "asiai[tui]"   # Dashboard terminal (Textual)
pip install "asiai[mcp]"   # Serveur MCP pour agents IA
pip install "asiai[all]"   # Web + TUI + MCP
```

## Depuis les sources

```bash
git clone https://github.com/druide67/asiai.git
cd asiai
pip install -e ".[dev]"
```

## Vérifier l'installation

```bash
asiai --version
asiai setup                # Assistant interactif
asiai detect               # Ou détecter les moteurs directement
```
