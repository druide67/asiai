---
title: "Ollama vs LM Studio: Apple Silicon 벤치마크"
description: "Apple Silicon에서의 Ollama vs LM Studio 벤치마크: M4 Pro 실측값으로 tok/s, TTFT, 전력, VRAM을 나란히 비교."
type: article
date: 2026-03-28
updated: 2026-03-29
dataset:
  name: "Apple Silicon M4 Pro에서의 Ollama vs LM Studio 벤치마크"
  description: "Mac Mini M4 Pro 64GB에서 Qwen3-Coder-30B를 사용한 Ollama(llama.cpp)와 LM Studio(MLX) 직접 비교 벤치마크. 메트릭: tok/s, TTFT, GPU 전력, 효율, VRAM."
  date: "2026-03"
---

# Ollama vs LM Studio: Apple Silicon 벤치마크

Mac에서 어떤 추론 엔진이 더 빠를까요? 2026년 3월 asiai 1.4.0을 사용하여 Ollama(llama.cpp 백엔드)와 LM Studio(MLX 백엔드)를 동일 모델, 동일 하드웨어에서 직접 비교했습니다.

## 테스트 설정

| | |
|---|---|
| **하드웨어** | Mac Mini M4 Pro, 64 GB 유니파이드 메모리 |
| **모델** | Qwen3-Coder-30B (MoE 아키텍처, Q4_K_M / MLX 4-bit) |
| **asiai 버전** | 1.4.0 |
| **방법론** | 1회 워밍업 + 엔진당 1회 측정, temperature=0, 엔진 간 모델 언로드 ([전체 방법론](methodology.md)) |

## 결과

| 메트릭 | LM Studio (MLX) | Ollama (llama.cpp) | 차이 |
|--------|-----------------|-------------------|------|
| **처리량** | 102.2 tok/s | 69.8 tok/s | **+46%** |
| **TTFT** | 291 ms | 175 ms | Ollama가 빠름 |
| **GPU 전력** | 12.4 W | 15.4 W | **-20%** |
| **효율** | 8.2 tok/s/W | 4.5 tok/s/W | **+82%** |
| **프로세스 메모리** | 21.4 GB (RSS) | 41.6 GB (RSS) | -49% |

!!! note "메모리 수치에 대해"
    Ollama는 전체 컨텍스트 윈도우(262K 토큰)에 대한 KV 캐시를 사전 할당하여 메모리 풋프린트가 부풀어 오릅니다. LM Studio는 KV 캐시를 온디맨드로 할당합니다. 프로세스 RSS는 모델 가중치만이 아닌 엔진 프로세스가 사용하는 총 메모리를 반영합니다.

## 주요 발견

### LM Studio가 처리량에서 승리 (+46%)

MLX의 네이티브 Metal 최적화가 Apple Silicon 유니파이드 메모리에서 더 많은 대역폭을 추출합니다. MoE 아키텍처에서 그 차이는 상당합니다. 더 큰 Qwen3.5-35B-A3B 변형에서는 더 넓은 격차를 측정했습니다: **71.2 vs 30.3 tok/s (2.3배)**.

### Ollama가 TTFT에서 승리

Ollama의 llama.cpp 백엔드가 초기 프롬프트를 더 빠르게 처리합니다(175ms vs 291ms). 짧은 프롬프트로의 인터랙티브 사용에서는 Ollama가 더 민첩하게 느껴집니다. 긴 생성 작업에서는 LM Studio의 처리량 우위가 총 시간을 지배합니다.

### LM Studio가 전력 효율에서 우수 (+82%)

8.2 tok/s/W vs 4.5로, LM Studio는 줄당 거의 2배의 토큰을 생성합니다. 배터리로 구동되는 노트북과 상시 가동 서버의 지속 워크로드에 중요합니다.

### 메모리 사용량: 컨텍스트가 중요

프로세스 메모리의 큰 차이(21.4 vs 41.6 GB)는 부분적으로 Ollama가 최대 컨텍스트 윈도우에 대해 KV 캐시를 사전 할당하기 때문입니다. 공정한 비교를 위해 피크 RSS가 아닌 워크로드 중 실제 사용 컨텍스트를 고려하세요.

## 각 엔진 권장 용도

| 용도 | 권장 | 이유 |
|------|------|------|
| **최대 처리량** | LM Studio (MLX) | 46% 빠른 생성 |
| **인터랙티브 채팅 (저지연)** | Ollama | 낮은 TTFT (175 vs 291 ms) |
| **배터리 수명 / 효율** | LM Studio | 와트당 82% 더 많은 tok/s |
| **Docker / API 호환성** | Ollama | 넓은 생태계, OpenAI 호환 API |
| **메모리 제약 (16GB Mac)** | LM Studio | 낮은 RSS, 온디맨드 KV 캐시 |
| **멀티 모델 서빙** | Ollama | 내장 모델 관리, keep_alive |

## 다른 모델

처리량 격차는 모델 아키텍처에 따라 달라집니다:

| 모델 | LM Studio (MLX) | Ollama (llama.cpp) | 격차 |
|------|-----------------|-------------------|------|
| Qwen3-Coder-30B (MoE) | 102.2 tok/s | 69.8 tok/s | +46% |
| Qwen3.5-35B-A3B (MoE) | 71.2 tok/s | 30.3 tok/s | +135% |

MoE 모델에서 가장 큰 차이가 나타납니다. MLX가 Metal에서 희소 전문가 라우팅을 더 효율적으로 처리하기 때문입니다.

## 직접 벤치마크 실행

```bash
pip install asiai
asiai bench --engines ollama,lmstudio --prompts code --runs 3 --card
```

asiai는 동일 모델, 동일 프롬프트, 동일 하드웨어로 엔진을 나란히 비교합니다. 메모리 경합을 방지하기 위해 엔진 간에 모델이 자동으로 언로드됩니다.

[전체 방법론 보기](methodology.md) · [커뮤니티 리더보드 보기](leaderboard.md) · [Mac에서 LLM 벤치마크하는 방법](benchmark-llm-mac.md)
