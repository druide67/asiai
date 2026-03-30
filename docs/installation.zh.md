---
description: 通过 pip、Homebrew 或源码安装 asiai。要求：macOS + Apple Silicon（M1+），Python 3.11+。
---

# 安装

## pipx（推荐）

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

## 免安装试用

```bash
uvx asiai detect           # 需要 uv
```

## 可选扩展

```bash
pip install "asiai[web]"   # Web 仪表板（FastAPI + 图表）
pip install "asiai[tui]"   # 终端仪表板（Textual）
pip install "asiai[mcp]"   # AI Agent MCP 服务器
pip install "asiai[all]"   # Web + TUI + MCP
```

## 从源码安装

```bash
git clone https://github.com/druide67/asiai.git
cd asiai
pip install -e ".[dev]"
```

## 验证安装

```bash
asiai --version
asiai setup                # 交互式向导
asiai detect               # 或直接检测引擎
```
