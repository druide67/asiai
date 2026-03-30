---
title: "Mac에서 LLM 벤치마크하는 방법"
description: "Mac에서 LLM 추론을 벤치마크하는 방법: Apple Silicon에서 여러 엔진을 사용하여 tok/s, TTFT, 전력, VRAM을 측정하는 단계별 가이드."
type: howto
date: 2026-03-28
updated: 2026-03-29
duration: PT5M
steps:
  - name: "asiai 설치"
    text: "pip (pip install asiai) 또는 Homebrew (brew tap druide67/tap && brew install asiai)로 asiai를 설치합니다."
  - name: "엔진 감지"
    text: "'asiai detect'를 실행하여 Mac에서 실행 중인 추론 엔진(Ollama, LM Studio, llama.cpp, mlx-lm, oMLX, vLLM-MLX, Exo)을 자동으로 감지합니다."
  - name: "벤치마크 실행"
    text: "'asiai bench'를 실행하여 엔진 전체에서 최적 모델을 자동 감지하고 tok/s, TTFT, 전력, VRAM을 측정하는 교차 엔진 비교를 실행합니다."
---

# Mac에서 LLM 벤치마크하는 방법

Mac에서 로컬 LLM을 실행하고 있습니까? 실제 성능을 측정하는 방법을 알려드립니다 — 느낌이 아닌, "빠른 것 같다"가 아닌, 실제 tok/s, TTFT, 전력 소비, 메모리 사용량입니다.

## 왜 벤치마크가 필요합니까?

같은 모델이라도 추론 엔진에 따라 속도가 크게 달라집니다. Apple Silicon에서 MLX 기반 엔진(LM Studio, mlx-lm, oMLX)은 llama.cpp 기반 엔진(Ollama)보다 같은 모델에서 **2배 빠를** 수 있습니다. 측정하지 않으면 성능을 최대한 활용할 수 없습니다.

## 빠른 시작 (2분)

### 1. asiai 설치

```bash
pip install asiai
```

또는 Homebrew로:

```bash
brew tap druide67/tap
brew install asiai
```

### 2. 엔진 감지

```bash
asiai detect
```

asiai는 Mac에서 실행 중인 엔진(Ollama, LM Studio, llama.cpp, mlx-lm, oMLX, vLLM-MLX, Exo)을 자동으로 감지합니다.

### 3. 벤치마크 실행

```bash
asiai bench
```

이게 전부입니다. asiai가 엔진 전체에서 최적 모델을 자동 감지하고 교차 엔진 비교를 실행합니다.

## 측정 항목

| 메트릭 | 의미 |
|--------|------|
| **tok/s** | 초당 생성 토큰 수 (생성만, 프롬프트 처리 제외) |
| **TTFT** | 첫 번째 토큰까지의 시간 — 생성 시작 전 지연 시간 |
| **Power** | 추론 중 GPU + CPU 전력 (IOReport 경유, sudo 불필요) |
| **tok/s/W** | 에너지 효율 — 와트당 초당 토큰 수 |
| **VRAM** | 모델이 사용하는 메모리 (네이티브 API 또는 `ri_phys_footprint`로 추정) |
| **Stability** | 실행 간 변동: stable (CV 5% 미만), variable (10% 미만), unstable (10% 이상) |
| **Thermal** | 벤치마크 중 Mac이 쓰로틀링되었는지 여부 |

## 출력 예시

```
Mac16,11 — Apple M4 Pro  RAM: 64.0 GB  Pressure: normal

Benchmark: qwen3-coder-30b

  Engine        tok/s   Tokens Duration     TTFT       VRAM    Thermal
  lmstudio      102.2      537    7.00s    0.29s    24.2 GB    nominal
  ollama         69.8      512   17.33s    0.18s    32.0 GB    nominal

  Winner: lmstudio (+46% tok/s)

  Power Efficiency
    lmstudio     102.2 tok/s @ 12.4W = 8.23 tok/s/W
    ollama        69.8 tok/s @ 15.4W = 4.53 tok/s/W
```

*M4 Pro 64GB에서의 실제 벤치마크 출력 예시. 하드웨어와 모델에 따라 결과가 달라집니다. [더 많은 결과 보기 →](ollama-vs-lmstudio.md)*

## 고급 옵션

### 특정 엔진 비교

```bash
asiai bench --engines ollama,lmstudio,omlx
```

### 여러 프롬프트와 실행 횟수

```bash
asiai bench --prompts code,reasoning,tool_call --runs 3
```

### 대규모 컨텍스트 벤치마크

```bash
asiai bench --context-size 64K
```

### 공유 가능한 카드 생성

```bash
asiai bench --card --share
```

벤치마크 카드 이미지를 생성하고 결과를 [커뮤니티 리더보드](leaderboard.md)에 공유합니다.

## Apple Silicon 팁

### 메모리가 중요합니다

16GB Mac에서는 14GB 이하의 모델(로드 시)을 사용하세요. MoE 모델(Qwen3.5-35B-A3B, 3B 활성)이 이상적입니다 — 7B급 메모리 사용량으로 35B급 품질을 제공합니다.

### 엔진 선택이 생각보다 중요합니다

MLX 엔진은 대부분의 모델에서 Apple Silicon의 llama.cpp보다 상당히 빠릅니다. 실제 수치는 [Ollama vs LM Studio 비교](ollama-vs-lmstudio.md)를 참고하세요.

### 서멀 쓰로틀링

MacBook Air(팬 없음)는 5-10분의 지속 추론 후 쓰로틀링이 발생합니다. Mac Mini/Studio/Pro는 쓰로틀링 없이 지속 워크로드를 처리합니다. asiai는 서멀 쓰로틀링을 자동으로 감지하고 보고합니다.

## 커뮤니티와 비교

다른 Apple Silicon 머신과 자신의 Mac을 비교할 수 있습니다:

```bash
asiai compare
```

또는 [온라인 리더보드](leaderboard.md)를 방문하세요.

## FAQ

**Q: Apple Silicon에서 가장 빠른 LLM 추론 엔진은?**
A: M4 Pro 64GB 벤치마크에서 LM Studio(MLX 백엔드)가 토큰 생성에서 가장 빠릅니다 — Ollama(llama.cpp)보다 46% 빠릅니다. 다만 Ollama가 TTFT(첫 번째 토큰까지의 시간)는 더 낮습니다. [상세 비교](ollama-vs-lmstudio.md)를 참고하세요.

**Q: Mac에서 30B 모델을 실행하려면 RAM이 얼마나 필요합니까?**
A: Q4_K_M 양자화된 30B 모델은 엔진에 따라 24-32 GB의 유니파이드 메모리를 사용합니다. 최소 32 GB RAM이 필요하며, 메모리 프레셔를 피하려면 64 GB가 이상적입니다. Qwen3.5-35B-A3B 같은 MoE 모델은 활성 파라미터가 약 7 GB에 불과합니다.

**Q: asiai는 Intel Mac에서 작동합니까?**
A: 아닙니다. asiai는 Apple Silicon(M1/M2/M3/M4)이 필요합니다. Apple Silicon에서만 사용 가능한 GPU 메트릭, 전력 모니터링, 하드웨어 감지용 macOS 전용 API를 사용합니다.

**Q: M4에서 Ollama와 LM Studio 중 어느 것이 빠릅니까?**
A: LM Studio가 처리량에서 빠릅니다 (Qwen3-Coder-30B에서 102 tok/s vs 70 tok/s). Ollama는 첫 번째 토큰 지연(0.18s vs 0.29s)과 대규모 컨텍스트 윈도우(32K 토큰 이상)에서 빠르며, llama.cpp 프리필은 최대 3배 빠릅니다.

**Q: 벤치마크는 얼마나 걸립니까?**
A: 빠른 벤치마크는 약 2분입니다. 여러 프롬프트와 실행 횟수를 포함한 전체 교차 엔진 비교는 10-15분 소요됩니다. 빠른 단일 실행 테스트에는 `asiai bench --quick`을 사용하세요.

**Q: 다른 Mac 사용자와 결과를 비교할 수 있습니까?**
A: 예. `asiai bench --share`를 실행하여 결과를 익명으로 [커뮤니티 리더보드](leaderboard.md)에 제출할 수 있습니다. `asiai compare`로 다른 Apple Silicon 머신과 비교할 수 있습니다.

## 더 읽기

- [벤치마크 방법론](methodology.md) — asiai가 신뢰할 수 있는 측정을 보장하는 방법
- [벤치마크 모범 사례](benchmark-best-practices.md) — 정확한 결과를 위한 팁
- [엔진 비교](ollama-vs-lmstudio.md) — Ollama vs LM Studio 직접 비교
