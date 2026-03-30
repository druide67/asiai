---
description: "Mac에서 llama.cpp 서버: 저수준 제어, 포트 8080, KV 캐시 메트릭, Apple Silicon 벤치마크 결과."
---

# llama.cpp

llama.cpp는 GGUF 모델용 기초적인 C++ 추론 엔진으로, 포트 8080에서 KV 캐시, 스레드 수, 컨텍스트 크기에 대한 최대한의 저수준 제어를 제공합니다. Ollama의 백엔드로 작동하지만, Apple Silicon에서 세밀한 튜닝을 위해 스탠드얼론으로 실행할 수도 있습니다.

[llama.cpp](https://github.com/ggml-org/llama.cpp)는 GGUF 모델을 지원하는 고성능 C++ 추론 엔진입니다.

## 설정

```bash
brew install llama.cpp
llama-server -m model.gguf
```

## 세부 사항

| 속성 | 값 |
|------|-----|
| 기본 포트 | 8080 |
| API 유형 | OpenAI 호환 |
| VRAM 보고 | 없음 |
| 모델 포맷 | GGUF |
| 감지 | `/health` + `/props` 엔드포인트 또는 `lsof` 프로세스 감지 |

## 참고 사항

- llama.cpp는 mlx-lm과 포트 8080을 공유합니다. asiai는 `/health`와 `/props` 엔드포인트로 감지합니다.
- 서버는 튜닝을 위해 커스텀 컨텍스트 크기와 스레드 수로 시작할 수 있습니다.

## 참고

`asiai bench --engines llamacpp`로 엔진을 비교하세요 --- [자세히 보기](../benchmark-llm-mac.md)
