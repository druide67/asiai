---
description: asiaiをpip、Homebrew、またはソースからインストール。要件：Apple Silicon（M1以降）搭載のmacOS、Python 3.11以上。
---

# インストール

## pipx（推奨）

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

## インストールせずに試す

```bash
uvx asiai detect           # uvが必要
```

## オプションのエクストラ

```bash
pip install "asiai[web]"   # Webダッシュボード（FastAPI + チャート）
pip install "asiai[tui]"   # ターミナルダッシュボード（Textual）
pip install "asiai[mcp]"   # AIエージェント用MCPサーバー
pip install "asiai[all]"   # Web + TUI + MCP
```

## ソースから

```bash
git clone https://github.com/druide67/asiai.git
cd asiai
pip install -e ".[dev]"
```

## インストールの確認

```bash
asiai --version
asiai setup                # インタラクティブウィザード
asiai detect               # またはエンジンを直接検出
```
