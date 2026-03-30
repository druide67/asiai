---
description: Mac에서 실행 중인 LLM 추론 엔진을 자동 감지합니다. 3계층 캐스케이드 — 설정, 포트 스캔, 프로세스 감지.
---

# asiai detect

3계층 캐스케이드를 사용하여 실행 중인 추론 엔진을 자동 감지합니다.

## 사용법

```bash
asiai detect                      # 자동 감지 (3계층 캐스케이드)
asiai detect --url http://host:port  # 지정 URL만 스캔
```

## 출력

```
Detected engines:

  ● ollama 0.17.4
    URL: http://localhost:11434

  ● lmstudio 0.4.5
    URL: http://localhost:1234
    Running: 1 model(s)
      - qwen3.5-35b-a3b  MLX

  ● omlx 0.9.2
    URL: http://localhost:8800
```

## 작동 방식: 3계층 감지

asiai는 가장 빠른 것에서 가장 철저한 것까지 3개 감지 레이어의 캐스케이드를 사용합니다:

### 레이어 1: 설정 (가장 빠름, ~100ms)

`~/.config/asiai/engines.json` 읽기 — 이전 실행에서 감지된 엔진. 비표준 포트(예: oMLX의 8800)의 엔진을 재스캔 없이 감지.

### 레이어 2: 포트 스캔 (~200ms)

기본 포트와 확장 범위를 스캔:

| 포트 | 엔진 |
|------|------|
| 11434 | Ollama |
| 1234 | LM Studio |
| 8080 | mlx-lm 또는 llama.cpp |
| 8000-8009 | oMLX 또는 vllm-mlx |
| 52415 | Exo |

### 레이어 3: 프로세스 감지 (폴백)

`ps`와 `lsof`를 사용하여 임의의 포트에서 수신 대기 중인 엔진 프로세스를 찾습니다. 완전히 예상치 못한 포트에서 실행되는 엔진도 감지합니다.

### 자동 저장

레이어 2 또는 3에서 감지된 엔진은 다음 감지를 빠르게 하기 위해 설정 파일(레이어 1)에 자동 저장됩니다. 자동 감지 항목은 7일 비활성 후 정리됩니다.

여러 엔진이 포트를 공유하는 경우(예: mlx-lm과 llama.cpp의 8080), asiai는 API 엔드포인트 프로빙으로 올바른 엔진을 식별합니다.

## 명시적 URL

`--url` 사용 시 지정된 URL만 스캔됩니다. 설정 읽기/쓰기가 수행되지 않습니다 — 일회성 확인에 유용합니다.

```bash
asiai detect --url http://192.168.0.16:11434,http://localhost:8800
```

## 참고

- [config](config.md) — 영구적인 엔진 설정 관리
