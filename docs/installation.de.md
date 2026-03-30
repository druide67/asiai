---
description: asiai installieren über pip, Homebrew oder aus dem Quellcode. Voraussetzungen: macOS auf Apple Silicon (M1+), Python 3.11+.
---

# Installation

## pipx (empfohlen)

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

## Ohne Installation testen

```bash
uvx asiai detect           # Erfordert uv
```

## Optionale Extras

```bash
pip install "asiai[web]"   # Web-Dashboard (FastAPI + Charts)
pip install "asiai[tui]"   # Terminal-Dashboard (Textual)
pip install "asiai[mcp]"   # MCP-Server für KI-Agenten
pip install "asiai[all]"   # Web + TUI + MCP
```

## Aus dem Quellcode

```bash
git clone https://github.com/druide67/asiai.git
cd asiai
pip install -e ".[dev]"
```

## Installation überprüfen

```bash
asiai --version
asiai setup                # Interaktiver Assistent
asiai detect               # Oder Engines direkt erkennen
```
