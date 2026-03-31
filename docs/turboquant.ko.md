---
title: "Apple Silicon에서의 TurboQuant Benchmark: Mac에서 70B 모델 실행하기"
description: "Mac Mini M4 Pro 64GB에서 TurboQuant KV cache 압축 실측 benchmark: Llama 70B가 6.3 tok/s, 메모리 5배 절약. 설정 가이드 및 결과."
type: article
date: 2026-03-31
updated: 2026-03-31
faq:
  - q: "64GB RAM Mac에서 70B 모델을 실행할 수 있습니까?"
    a: "네, TurboQuant를 사용하면 가능합니다. KV cache가 5배 압축되므로 Llama 70B Q4_K_M(40GB 가중치)이 32K 컨텍스트에서 64GB에 여유 있게 들어갑니다. Mac Mini M4 Pro에서 6.3 tok/s를 측정했습니다."
  - q: "TurboQuant가 품질을 저하시킵니까?"
    a: "측정 가능한 품질 저하는 없습니다. q8_0 대비 퍼플렉시티 증가가 1% 미만이며, Needle-in-a-Haystack 검색은 32K 컨텍스트 전체에서 100% 점수를 기록합니다."
  - q: "어떤 TurboQuant 포맷을 사용해야 합니까?"
    a: "비대칭 방식을 권장합니다: keys에 q8_0(압축에 민감), values에 turbo3(5배 압축, 품질 영향 없음). 이는 turboquant_plus 프로젝트의 연구 결과를 기반으로 합니다."
  - q: "TurboQuant가 MLX 엔진에서 작동합니까?"
    a: "커뮤니티 MLX 구현이 있지만 llama.cpp fork만큼 성숙하지 않습니다. Apple Silicon 프로덕션 환경에서는 Metal kernels를 갖춘 TheTom/llama-cpp-turboquant를 권장합니다."
  - q: "TurboQuant는 얼마나 빠릅니까?"
    a: "디코드 속도는 q8_0의 약 0.9배(토큰당 약간 느림)이지만, 긴 컨텍스트에서는 메모리 대역폭 부하 감소로 prefill이 더 빠를 수 있습니다. 진정한 이점은 동일한 RAM에서 더 큰 모델과 더 긴 컨텍스트를 실행할 수 있다는 것입니다."
---

# Apple Silicon에서의 TurboQuant Benchmark

TurboQuant(Google Research, ICLR 2026)는 LLM의 KV cache를 품질 저하 없이 5배 압축하여, 64GB RAM의 Mac Mini에서 70B 모델 실행을 가능하게 합니다. 다음은 [asiai](/)를 사용하여 실제 하드웨어에서 측정한 benchmark 결과입니다.

## 결과

**Llama-3.1-70B-Instruct Q4_K_M, Mac Mini M4 Pro 64GB 기준**

| 지표 | 값 |
|------|-----|
| **Throughput** | 6.3 tok/s (안정적, 95% 신뢰구간: 6.3-6.3) |
| **TTFT** | 196 ms (중앙값) |
| **GPU Power** | 23.8 W |
| **Model VRAM** | 44.1 GB (40 GB 가중치 + 4 GB KV turbo3) |
| **Context** | 32,768 tokens |
| **GPU Offload** | Metal에 81/81 레이어 |
| **Thermal** | 정상 (스로틀링 없음) |
| **Stability** | 안정적 (3회 실행 표준편차 0.04 tok/s) |

KV cache 구성: keys는 q8_0(고정밀도), values는 turbo3(3-bit, 5배 압축).

## TurboQuant 적용 전후 비교

| | TurboQuant 미적용 | TurboQuant 적용 (turbo3) |
|--|-------------------|--------------------------|
| **KV cache (32K ctx)** | ~20 GB (q8_0) | ~4 GB (turbo3) |
| **필요 RAM 총량** | 60+ GB (64GB에서 OOM) | 44 GB (64GB에 수용 가능) |
| **64GB에서 70B 실행 가능?** | 불가 | **가능** |
| **품질** | Baseline | -1% PPL (무시할 수준) |
| **NIAH retrieval** | 100% | 100% |

## TurboQuant란 무엇입니까?

TurboQuant는 Google Research의 KV cache 압축 알고리즘으로, ICLR 2026에서 발표되었습니다. LLM 추론 중 KV cache는 중간 어텐션 상태를 저장하며 컨텍스트 길이에 비례하여 선형적으로 증가합니다. FP16에서 128K 컨텍스트의 70B 모델의 경우, 이 cache만으로도 20-40 GB의 RAM을 소비할 수 있습니다.

TurboQuant는 다음 기술을 사용하여 cache를 값당 3 bit로 압축합니다:

- **랜덤 회전** (Walsh-Hadamard 변환)으로 데이터를 가우시안화
- **최적 스칼라 양자화** (PolarQuant)로 Shannon 한계에 근접
- **QJL** (Quantized Johnson-Lindenstrauss)로 내적 보존

결과: 메모리 5배 감소, fine-tuning 불필요, 품질 저하 거의 제로입니다.

## 설정 가이드

### 하드웨어

- Mac Mini M4 Pro, 64 GB 유니파이드 메모리 ($2,700)
- 32+ GB Apple Silicon Mac이면 작동합니다 (모델 크기를 적절히 조정하십시오)

### TurboQuant llama.cpp 설치

```bash
# 빌드 도구 설치
brew install cmake

# TurboQuant fork 클론
git clone https://github.com/TheTom/llama-cpp-turboquant.git
cd llama-cpp-turboquant
git checkout feature/turboquant-kv-cache

# Metal(Apple Silicon GPU)로 빌드
cmake -B build -DGGML_METAL=ON -DGGML_METAL_EMBED_LIBRARY=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(sysctl -n hw.ncpu)
```

### 모델 다운로드

```bash
# Llama 3.1 70B Q4_K_M (~40 GB)
curl -L -o llama-3.1-70b-q4_k_m.gguf \
  "https://huggingface.co/bartowski/Meta-Llama-3.1-70B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-70B-Instruct-Q4_K_M.gguf"
```

### macOS GPU 메모리 제한 상향

```bash
sudo sysctl iogpu.wired_limit_mb=61440
```

### 서버 실행

```bash
./build/bin/llama-server \
  -m llama-3.1-70b-q4_k_m.gguf \
  --cache-type-k q8_0 --cache-type-v turbo3 \
  -c 32768 \
  --port 8081 \
  --host 0.0.0.0 \
  -fa 1 \
  -ngl 99 \
  -t 10 \
  --no-mmap \
  --chat-template chatml
```

### 구성 설명

| 파라미터 | 값 | 이유 |
|---------|-----|------|
| `--cache-type-k q8_0` | Keys를 8-bit로 | Keys는 압축에 민감합니다 |
| `--cache-type-v turbo3` | Values를 3-bit로 | Values는 극단적 압축(5배)을 견딥니다 |
| `-fa 1` | Flash Attention | TurboQuant에 필수입니다 |
| `-ngl 99` | 완전 GPU offload | 전체 81 레이어를 Metal에 배치 |
| `-t 10` | 10 스레드 | M4 Pro는 10개의 퍼포먼스 코어를 탑재 |
| `--no-mmap` | 메모리 매핑 미사용 | 부팅 시 전부 로드하여 page faults 방지 |
| `--chat-template chatml` | ChatML 포맷 | 이 fork와의 호환성이 최상 |

## asiai로 Benchmark 실행

```bash
pip install asiai
asiai detect --url http://localhost:8081
asiai bench --engines llamacpp --prompts code --runs 3 --kv-cache turbo3 --card
```

## TurboQuant로 64GB에 수용 가능한 모델

| 모델 | 가중치 (Q4_K_M) | KV Cache (32K, turbo3) | 합계 | 상태 |
|------|-----------------|----------------------|------|------|
| Llama 3.1 70B | 40 GB | ~4 GB | 44 GB | **테스트 완료: 6.3 tok/s** |
| Qwen2.5 72B | 40 GB | ~4 GB | 44 GB | 작동 예상 |
| Llama 70B 128K ctx | 40 GB | ~16 GB (turbo3) | 56 GB | 빠듯하지만 가능 |
| Command-R+ 104B | 58 GB | ~4 GB | 62 GB | 매우 빠듯함 |

## FAQ

**64GB RAM Mac에서 70B 모델을 실행할 수 있습니까?**

네, TurboQuant를 사용하면 가능합니다. KV cache가 5배 압축되므로 Llama 70B Q4_K_M(40GB 가중치)이 32K 컨텍스트에서 64GB에 여유 있게 들어갑니다. Mac Mini M4 Pro에서 6.3 tok/s를 측정했습니다.

**TurboQuant가 품질을 저하시킵니까?**

측정 가능한 품질 저하는 없습니다. q8_0 대비 퍼플렉시티 증가가 1% 미만이며, Needle-in-a-Haystack 검색은 32K 컨텍스트 전체에서 100% 점수를 기록합니다.

**어떤 TurboQuant 포맷을 사용해야 합니까?**

비대칭: keys에 q8_0 + values에 turbo3. Keys는 압축에 민감합니다(모든 품질 저하는 K 압축에서 비롯됩니다). Values는 2-3 bit까지 압축해도 어텐션 품질에 전혀 영향이 없습니다.

**TurboQuant가 MLX에서 작동합니까?**

커뮤니티 구현이 있습니다([turboquant-mlx](https://github.com/helgklaizar/turboquant_mlx)), 그러나 llama.cpp fork만큼 성숙하지 않습니다. 프로덕션 환경에서는 [TheTom/llama-cpp-turboquant](https://github.com/TheTom/llama-cpp-turboquant)를 권장합니다.

**표준 llama.cpp와 비교하면 어떻습니까?**

디코드 속도는 q8_0의 ~0.9배(토큰당 약간 느림)이지만, 진정한 이점은 이전에는 수용할 수 없었던 모델과 컨텍스트를 실행할 수 있다는 것입니다. 메모리 대역폭 부하 감소로 인해 긴 컨텍스트에서의 prefill은 실제로 더 빠를 수 있습니다.

## 참고 자료

- [Google Research Blog — TurboQuant](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/)
- [TurboQuant Paper (ICLR 2026)](https://arxiv.org/abs/2504.19874)
- [TheTom/turboquant_plus](https://github.com/TheTom/turboquant_plus) — Sparse V를 포함한 확장 구현
- [TheTom/llama-cpp-turboquant](https://github.com/TheTom/llama-cpp-turboquant) — Metal kernels를 갖춘 llama.cpp fork
- [llama.cpp Discussion #20969](https://github.com/ggml-org/llama.cpp/discussions/20969) — 커뮤니티 토론 스레드
