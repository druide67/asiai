---
description: "Apple Silicon에서의 vLLM-MLX: MLX 기반 vLLM 호환 API, 포트 8000, Prometheus 메트릭, 벤치마크 데이터."
---

# vllm-mlx

vLLM-MLX는 MLX를 통해 vLLM 서빙 프레임워크를 Apple Silicon으로 가져와 연속 배치 처리와 OpenAI 호환 API(포트 8000)를 제공합니다. 최적화된 모델에서 400+ tok/s를 달성할 수 있어 Mac에서 동시 추론을 위한 가장 빠른 옵션 중 하나입니다.

[vllm-mlx](https://github.com/vllm-project/vllm)는 MLX를 통해 Apple Silicon에 연속 배치 처리를 제공합니다.

## 설정

```bash
pip install vllm-mlx
vllm serve mlx-community/gemma-2-9b-it-4bit
```

## 세부 정보

| 속성 | 값 |
|------|-----|
| 기본 포트 | 8000 |
| API 유형 | OpenAI 호환 |
| VRAM 보고 | 아니요 |
| 모델 형식 | MLX (safetensors) |
| 감지 방법 | `/version` 엔드포인트 또는 `lsof` 프로세스 감지 |

## 참고

- vllm-mlx는 연속 배치 처리를 지원하여 동시 요청 처리에 적합합니다.
- Apple Silicon에서 최적화된 모델로 400+ tok/s를 달성할 수 있습니다.
- 표준 vLLM OpenAI 호환 API를 사용합니다.

## 참고 항목

`asiai bench --engines vllm-mlx`로 엔진 비교 --- [방법 알아보기](../benchmark-llm-mac.md)
