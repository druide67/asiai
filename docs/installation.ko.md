---
description: asiai를 pip, Homebrew 또는 소스에서 설치합니다. 요구 사항: Apple Silicon (M1+)의 macOS, Python 3.11 이상.
---

# 설치

## pipx (권장)

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

## 설치 없이 사용해 보기

```bash
uvx asiai detect           # uv 필요
```

## 선택적 extras

```bash
pip install "asiai[web]"   # 웹 대시보드 (FastAPI + 차트)
pip install "asiai[tui]"   # 터미널 대시보드 (Textual)
pip install "asiai[mcp]"   # AI 에이전트용 MCP 서버
pip install "asiai[all]"   # Web + TUI + MCP
```

## 소스에서 설치

```bash
git clone https://github.com/druide67/asiai.git
cd asiai
pip install -e ".[dev]"
```

## 설치 확인

```bash
asiai --version
asiai setup                # 대화형 마법사
asiai detect               # 또는 엔진을 직접 감지
```
