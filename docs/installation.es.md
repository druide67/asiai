---
description: Instala asiai mediante pip, Homebrew o desde el código fuente. Requisitos: macOS en Apple Silicon (M1+), Python 3.11+.
---

# Instalación

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

## Probar sin instalar

```bash
uvx asiai detect           # Requiere uv
```

## Extras opcionales

```bash
pip install "asiai[web]"   # Panel web (FastAPI + gráficos)
pip install "asiai[tui]"   # Panel de terminal (Textual)
pip install "asiai[mcp]"   # Servidor MCP para agentes de IA
pip install "asiai[all]"   # Web + TUI + MCP
```

## Desde el código fuente

```bash
git clone https://github.com/druide67/asiai.git
cd asiai
pip install -e ".[dev]"
```

## Verificar la instalación

```bash
asiai --version
asiai setup                # Asistente interactivo
asiai detect               # O detectar motores directamente
```
