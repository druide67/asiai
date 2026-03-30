---
description: Instale o asiai via pip, Homebrew ou a partir do código-fonte. Requisitos: macOS em Apple Silicon (M1+), Python 3.11+.
---

# Instalação

## pipx (recomendado)

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

## Testar sem instalar

```bash
uvx asiai detect           # Requer uv
```

## Extras opcionais

```bash
pip install "asiai[web]"   # Dashboard web (FastAPI + gráficos)
pip install "asiai[tui]"   # Dashboard no terminal (Textual)
pip install "asiai[mcp]"   # Servidor MCP para agentes de IA
pip install "asiai[all]"   # Web + TUI + MCP
```

## A partir do código-fonte

```bash
git clone https://github.com/druide67/asiai.git
cd asiai
pip install -e ".[dev]"
```

## Verificar instalação

```bash
asiai --version
asiai setup                # Assistente interativo
asiai detect               # Ou detecte motores diretamente
```
