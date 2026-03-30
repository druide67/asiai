---
description: "asiai 빠른 설정: 엔진 설정, 연결 테스트, Apple Silicon Mac이 LLM 벤치마크 준비가 되었는지 확인합니다."
---

# asiai setup

처음 사용하는 사용자를 위한 인터랙티브 설정 마법사입니다. 하드웨어를 감지하고, 추론 엔진을 확인하고, 다음 단계를 제안합니다.

## 사용법

```bash
asiai setup
```

## 수행 내용

1. **하드웨어 감지** — Apple Silicon 칩과 RAM 식별
2. **엔진 스캔** — 설치된 추론 엔진(Ollama, LM Studio, mlx-lm, llama.cpp, oMLX, vllm-mlx, Exo) 확인
3. **모델 확인** — 감지된 모든 엔진에 로드된 모델 나열
4. **데몬 상태** — 모니터링 데몬 실행 여부 표시
5. **다음 단계** — 설정 상태에 따른 명령어 제안

## 출력 예시

```
  Setup Wizard

  Hardware:  Apple M4 Pro, 64 GB RAM

  Engines:
    ✓ ollama (v0.17.7) — 3 models loaded
    ✓ lmstudio (v0.4.5) — 1 model loaded

  Daemon: running (monitor + web)

  Suggested next steps:
    • asiai bench              Run your first benchmark
    • asiai monitor --watch    Watch metrics live
    • asiai web                Open the dashboard
```

## 엔진이 발견되지 않은 경우

엔진이 감지되지 않으면 설정이 설치 안내를 제공합니다:

```
  Engines:
    No inference engines detected.

  To get started, install an engine:
    brew install ollama && ollama serve
    # or download LM Studio from https://lmstudio.ai
```
