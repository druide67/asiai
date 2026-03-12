# Installation

## pipx (recommended)

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

## Try without installing

```bash
uvx asiai detect           # Requires uv
```

## Optional extras

```bash
pip install "asiai[web]"   # Web dashboard (FastAPI + charts)
pip install "asiai[tui]"   # Terminal dashboard (Textual)
pip install "asiai[mcp]"   # MCP server for AI agents
pip install "asiai[all]"   # Web + TUI + MCP
```

## From source

```bash
git clone https://github.com/druide67/asiai.git
cd asiai
pip install -e ".[dev]"
```

## Verify installation

```bash
asiai --version
asiai setup                # Interactive wizard
asiai detect               # Or detect engines directly
```
