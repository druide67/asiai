---
description: "Exo 분산 LLM 추론: 여러 Mac을 연결하여 벤치마크, 포트 52415, 클러스터 설정과 성능."
---

# Exo

Exo는 로컬 네트워크의 여러 Apple Silicon Mac에서 VRAM을 풀링하여 분산 LLM 추론을 가능하게 하며, 포트 52415에서 서비스합니다. 단일 머신에 맞지 않는 70B 이상의 파라미터 모델을 자동 피어 검색과 OpenAI 호환 API로 실행할 수 있습니다.

[Exo](https://github.com/exo-explore/exo)는 여러 Apple Silicon 기기 간 분산 추론을 가능하게 합니다. 여러 Mac에서 VRAM을 풀링하여 대규모 모델(70B 이상)을 실행할 수 있습니다.

## 설정

```bash
pip install exo-inference
exo
```

또는 소스에서 설치:

```bash
git clone https://github.com/exo-explore/exo.git
cd exo && pip install -e .
exo
```

## 세부 사항

| 속성 | 값 |
|------|-----|
| 기본 포트 | 52415 |
| API 유형 | OpenAI 호환 |
| VRAM 보고 | 예 (클러스터 노드 전체 집계) |
| 모델 포맷 | GGUF / MLX |
| 감지 | DEFAULT_URLs를 통한 자동 감지 |

## 벤치마크

```bash
asiai bench --engines exo -m llama3.3:70b
```

Exo는 다른 엔진과 동일하게 벤치마크됩니다. asiai가 포트 52415에서 자동 감지합니다.

## 참고 사항

- Exo는 로컬 네트워크에서 피어 노드를 자동으로 검색합니다.
- asiai에 표시되는 VRAM은 클러스터 전체 노드에서 집계된 총 메모리를 반영합니다.
- 단일 Mac에 맞지 않는 대규모 모델도 클러스터 전체에서 원활하게 실행할 수 있습니다.
- 벤치마크 실행 전에 클러스터의 각 Mac에서 `exo`를 시작하세요.

## 참고

`asiai bench --engines exo`로 엔진을 비교하세요 --- [자세히 보기](../benchmark-llm-mac.md)
