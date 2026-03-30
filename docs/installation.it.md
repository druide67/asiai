---
description: Installa asiai tramite pip, Homebrew o dal codice sorgente. Requisiti: macOS su Apple Silicon (M1+), Python 3.11+.
---

# Installazione

## pipx (raccomandato)

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

## Prova senza installare

```bash
uvx asiai detect           # Richiede uv
```

## Extra opzionali

```bash
pip install "asiai[web]"   # Dashboard web (FastAPI + grafici)
pip install "asiai[tui]"   # Dashboard terminale (Textual)
pip install "asiai[mcp]"   # Server MCP per agenti IA
pip install "asiai[all]"   # Web + TUI + MCP
```

## Dal codice sorgente

```bash
git clone https://github.com/druide67/asiai.git
cd asiai
pip install -e ".[dev]"
```

## Verifica l'installazione

```bash
asiai --version
asiai setup                # Procedura guidata interattiva
asiai detect               # Oppure rileva i motori direttamente
```
