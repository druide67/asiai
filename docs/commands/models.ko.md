---
description: "모든 엔진에 로드된 LLM 모델 목록: 각 모델의 VRAM 사용량, 양자화, 컨텍스트 길이, 포맷을 표시합니다."
---

# asiai models

감지된 모든 엔진에 로드된 모델을 나열합니다.

## 사용법

```bash
asiai models
```

## 출력

```
ollama  v0.17.5  http://localhost:11434
  ● qwen3.5:35b-a3b                             26.0 GB Q4_K_M

lmstudio  v0.4.6  http://localhost:1234
  ● qwen3.5-35b-a3b                              9.2 GB    MLX
```

각 엔진의 버전, 모델 이름, VRAM 사용량(가능한 경우), 포맷, 양자화 수준을 표시합니다.

VRAM은 Ollama와 LM Studio에서 네이티브로 보고됩니다. 다른 엔진에서는 asiai가 `ri_phys_footprint`(Activity Monitor와 동일한 macOS 물리 풋프린트)를 통해 메모리 사용량을 추정합니다. 추정값은 "(est.)"로 표시됩니다.
