---
description: "Mac에서의 mlx-lm 서버 벤치마크: MoE 모델에 최적, 포트 8080 설정, Apple Silicon 성능 데이터."
---

# mlx-lm

mlx-lm은 Apple의 레퍼런스 MLX 추론 서버로, Metal GPU에서 모델을 네이티브로 실행하며 포트 8080을 사용합니다. 특히 Apple Silicon에서 MoE(Mixture of Experts) 모델에 효율적이며, 유니파이드 메모리를 활용한 제로카피 모델 로딩을 실현합니다.

[mlx-lm](https://github.com/ml-explore/mlx-examples)은 Apple MLX에서 모델을 네이티브로 실행하여 효율적인 유니파이드 메모리 활용을 제공합니다.

## 설정

```bash
brew install mlx-lm
mlx_lm.server --model mlx-community/gemma-2-9b-it-4bit
```

## 세부 정보

| 속성 | 값 |
|------|-----|
| 기본 포트 | 8080 |
| API 유형 | OpenAI 호환 |
| VRAM 보고 | 아니요 |
| 모델 형식 | MLX (safetensors) |
| 감지 방법 | `/version` 엔드포인트 또는 `lsof` 프로세스 감지 |

## 참고

- mlx-lm은 llama.cpp와 포트 8080을 공유합니다. asiai는 API 프로빙과 프로세스 감지를 사용하여 구별합니다.
- 모델은 HuggingFace/MLX 커뮤니티 형식을 사용합니다(예: `mlx-community/gemma-2-9b-it-4bit`).
- 네이티브 MLX 실행으로 Apple Silicon에서 뛰어난 성능을 제공합니다.

## 참고 항목

`asiai bench --engines mlxlm`으로 엔진 비교 --- [방법 알아보기](../benchmark-llm-mac.md)
