---
description: "Apple Silicon에서 LM Studio 벤치마크: 가장 빠른 MLX 엔진, 포트 1234 설정, VRAM 사용량, Ollama와 비교."
---

# LM Studio

LM Studio는 Apple Silicon에서 가장 빠른 MLX 추론 엔진으로, 포트 1234에서 OpenAI 호환 API로 모델을 제공합니다. M4 Pro 64GB에서 Qwen3-Coder-30B(MLX)로 130 tok/s에 도달하며, MoE 모델에서 Ollama의 llama.cpp 백엔드보다 거의 2배 빠릅니다.

[LM Studio](https://lmstudio.ai)는 모델 관리용 GUI와 함께 OpenAI 호환 API를 제공합니다.

## 설정

```bash
brew install --cask lm-studio
```

LM Studio 앱에서 로컬 서버를 시작하고 모델을 로드하세요.

## 세부 사항

| 속성 | 값 |
|------|-----|
| 기본 포트 | 1234 |
| API 유형 | OpenAI 호환 |
| VRAM 보고 | 예 (`lms ps --json` CLI 경유) |
| 모델 포맷 | GGUF, MLX |
| 감지 | `/lms/version` 엔드포인트 또는 앱 번들 plist |

## VRAM 보고

v0.7.0부터 asiai는 LM Studio CLI(`~/.lmstudio/bin/lms ps --json`)에서 VRAM 사용량을 가져옵니다. OpenAI 호환 API가 노출하지 않는 정확한 모델 크기 데이터를 제공합니다.

`lms` CLI가 설치되지 않았거나 사용할 수 없으면, asiai는 VRAM을 0으로 보고하는 폴백 동작(v0.7.0 이전과 동일)으로 전환합니다.

## 참고 사항

- LM Studio는 GGUF와 MLX 모델 포맷을 모두 지원합니다.
- 버전 감지는 `/lms/version` API 엔드포인트를 사용하며, 폴백으로 디스크의 앱 번들 plist를 사용합니다.
- 모델 이름은 일반적으로 HuggingFace 형식(예: `gemma-2-9b-it`)을 사용합니다.

## 참고

LM Studio 비교 보기: [Ollama vs LM Studio 벤치마크](../ollama-vs-lmstudio.md)
