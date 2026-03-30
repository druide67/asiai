---
description: "Mac에서 LLM 추론 문제 진단: asiai doctor가 엔진 상태, 포트 충돌, 모델 로딩, GPU 상태를 확인합니다."
---

# asiai doctor

설치, 엔진, 시스템 상태, 데이터베이스를 진단합니다.

## 사용법

```bash
asiai doctor
```

## 출력

```
Doctor

  System
    ✓ Apple Silicon       Mac Mini M4 Pro — Apple M4 Pro
    ✓ RAM                 64 GB total, 42% used
    ✓ Memory pressure     normal
    ✓ Thermal             nominal (100%)

  Engine
    ✓ Ollama              v0.17.5 — 1 model(s): qwen3.5:35b-a3b
    ✓ Ollama config       host=0.0.0.0:11434, num_parallel=1 (default), ...
    ✓ LM Studio           v0.4.6 — 1 model(s): qwen3.5-35b-a3b
    ✗ mlx-lm              not installed
    ✗ llama.cpp           not installed
    ✗ vllm-mlx            not installed

  Database
    ✓ SQLite              2.4 MB, last entry: 1m ago

  Daemon
    ✓ Monitoring daemon   running PID 1234
    ✓ Web dashboard       not installed

  Alerting
    ✓ Webhook URL         https://hooks.slack.com/services/...
    ✓ Webhook reachable   HTTP 200

  9 ok, 0 warning(s), 3 failed
```

## 검사 항목

- **System**: Apple Silicon 감지, RAM, 메모리 프레셔, 서멀 상태
- **Engine**: 7개 지원 엔진의 접근성과 버전; Ollama 런타임 파라미터 (host, num_parallel, max_loaded_models, keep_alive, flash_attention)
- **Database**: SQLite 스키마 버전, 크기, 마지막 항목 타임스탬프
- **Daemon**: monitor 및 web 서비스의 LaunchAgent 상태
- **Alerting**: 웹훅 URL 설정 및 연결성
