---
description: "Apple Silicon에서 Ollama 속도는? 벤치마크 설정, 기본 포트(11434), 성능 팁, 다른 엔진과의 비교."
---

# Ollama

Ollama는 Mac에서 가장 인기 있는 LLM 추론 엔진으로, llama.cpp 백엔드를 사용하며 GGUF 모델을 포트 11434에서 제공합니다. M4 Pro 64GB 벤치마크에서 Qwen3-Coder-30B로 70 tok/s를 달성했지만, 처리량은 LM Studio(MLX)보다 46% 느립니다.

[Ollama](https://ollama.com)는 가장 인기 있는 로컬 LLM 실행기입니다. asiai는 네이티브 API를 사용합니다.

## 설정

```bash
brew install ollama
ollama serve
ollama pull gemma2:9b
```

## 세부 정보

| 속성 | 값 |
|------|-----|
| 기본 포트 | 11434 |
| API 유형 | 네이티브(비 OpenAI) |
| VRAM 보고 | 예 |
| 모델 형식 | GGUF |
| 로드 시간 측정 | 예(`/api/generate` 콜드 스타트) |

## 참고

- Ollama는 모델별 VRAM 사용량을 보고하며, asiai는 벤치마크 및 모니터 출력에 이를 표시합니다.
- 모델 이름은 `name:tag` 형식을 사용합니다(예: `gemma2:9b`, `qwen3.5:35b-a3b`).
- asiai는 결정적인 벤치마크 결과를 위해 `temperature: 0`을 전송합니다.

## 참고 항목

Ollama 비교 보기: [Ollama vs LM Studio 벤치마크](../ollama-vs-lmstudio.md)
