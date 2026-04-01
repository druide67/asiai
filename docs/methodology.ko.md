---
description: asiai가 tok/s, TTFT, 전력을 측정하는 방법. 워밍업, 통계 방법론, 결과의 재현성에 대해.
---

# 벤치마크 방법론

asiai는 확립된 벤치마크 표준([MLPerf](https://mlcommons.org/benchmarks/inference-server/), [SPEC CPU 2017](https://www.spec.org/cpu2017/), [NVIDIA GenAI-Perf](https://docs.nvidia.com/deeplearning/nemo/user-guide/docs/en/stable/benchmarking/genai_perf.html))을 따라 신뢰할 수 있고, 재현 가능하며, 비교 가능한 결과를 생성합니다.

## 프로토콜

1. **프리플라이트 게이트 체크**: 메모리 프레셔가 critical이거나 시스템이 크게 쓰로틀링(80% 미만)되면 시작 거부
2. **워밍업**: 엔진당 1회의 비측정 생성으로 JIT 컴파일러와 캐시 프라이밍
3. **측정 실행**: 기본 프롬프트당/엔진당 3회 실행 (`--runs`로 설정 가능)
4. **샘플링**: 결정론적 출력을 위해 `temperature=0` (그리디)
5. **모델 언로드**: 각 엔진 벤치마크 후 다음 엔진 시작 전에 모델을 언로드하여 유니파이드 메모리 해제. 대규모 모델 비교 시 메모리 누적과 스왑 방지
6. **적응형 쿨다운**: 언로드 후 macOS 메모리 프레셔가 "normal"로 돌아올 때까지 대기(최대 30초), 이후 최소 5초 서멀 쿨다운 추가
7. **건전성 검사**: tok/s ≤ 0인 결과는 폐기. TTFT > 60s 또는 tok/s > 500이면 경고 발생(스왑 또는 측정 오류 가능성)
8. **보고**: 중앙값 tok/s를 기본 메트릭(SPEC 표준)으로, 평균 ± 표준편차를 보조로 사용
9. **쓰로틀링**: 실행 중 `thermal_speed_limit < 100%`이면 경고 출력. 서멀 드리프트(실행 간 tok/s의 단조 감소, ≥ 5% 하락) 감지 및 보고
10. **메타데이터**: 엔진 버전, 모델 포맷, 양자화, 하드웨어 칩, macOS 버전을 결과별로 저장

## 메트릭

### tok/s — 생성 속도

프롬프트 처리(TTFT)를 제외한 **생성 시간만의** 초당 토큰 수.

**Ollama** (네이티브 API, `/api/generate`):
```
tok_per_sec = eval_count / (eval_duration_ns / 1e9)
```
소스: Ollama가 보고하는 내부 GPU 타이밍. 네트워크 오버헤드 없음. 가장 정확한 측정입니다.

**OpenAI 호환 엔진** (LM Studio, llama.cpp, mlx-lm, vllm-mlx):
```
generation_s = wall_clock_s - ttft_s
tok_per_sec  = completion_tokens / generation_s
```
소스: streaming SSE를 통한 클라이언트사이드 벽시계. 청크당 HTTP 오버헤드 포함(서버사이드 타이밍보다 ~1% 느림, 교차 검증으로 확인됨).

**토큰 카운트**: 서버 응답의 `usage.completion_tokens`에서 가져옴. 서버가 이 필드를 보고하지 않으면 asiai는 `len(text) // 4`로 폴백하고 경고를 기록합니다. 이 폴백은 ~25%까지 오차가 있을 수 있습니다.

**교차 검증** (2026년 4월, Qwen3.5-35B NVFP4, M4 Pro 64GB):

| 방법 | tok/s | 레퍼런스 대비 차이 |
|------|-------|--------------------|
| Ollama 네이티브 (내부 GPU) | 66.6 | 레퍼런스 |
| OpenAI streaming (클라이언트) | 66.1 | -0.8% |

대규모 컨텍스트 크기(예: 64k 토큰)에서는 TTFT가 총 시간을 지배할 수 있습니다. tok/s에서 TTFT를 제외하면 빠른 생성기가 느리게 보이는 것을 방지합니다.

### TTFT — 첫 번째 토큰까지의 시간

요청 전송부터 첫 번째 출력 토큰 수신까지의 시간(밀리초).

**Ollama**: `prompt_eval_duration`(내부 타이밍)을 통해 서버사이드에서 측정. 네트워크 오버헤드 없는 순수 프롬프트 처리 시간입니다. `ttft_source: server`로 보고됩니다.

**OpenAI 호환 엔진**: 첫 SSE 콘텐츠 청크에서 클라이언트사이드로 측정. HTTP 설정, 요청 전송, 서버 처리를 포함합니다. 일반적으로 서버사이드보다 10-100ms 높습니다. `ttft_source: client`로 보고됩니다.

!!! warning "TTFT 비교"
    차이를 고려하지 않고 Ollama의 서버사이드 TTFT와 OpenAI 호환 엔진의 클라이언트사이드 TTFT를 비교하지 마세요. 벤치마크 결과의 `ttft_source` 필드가 어떤 방법이 사용되었는지를 나타냅니다.

### Power — GPU 전력 (와트)

실행 중 평균 GPU 전력. Apple IOReport Energy Model 프레임워크로 측정(sudo 불필요). 엔진당 1회 측정 — 세션 전체 평균이 아닙니다.

### tok/s/W — 에너지 효율

```
tok_per_sec_per_watt = tok_per_sec / power_watts
```

### Variance — 풀드 표준편차

풀드 프롬프트 내 표준편차. 프롬프트 간 분산을 혼합하지 않고 실행 간 노이즈를 포착합니다. 베셀 보정(N-1 분모)을 사용하여 비편향 표본 분산을 산출합니다.

안정성 분류:

- CV < 5% → `stable`
- CV < 10% → `variable`
- CV >= 10% → `unstable`

CV = `(std_dev / mean) * 100`

### VRAM — 메모리 사용량

**기본**: 엔진 네이티브 API (Ollama `/api/ps`, LM Studio `/v1/models`).
**폴백**: ctypes를 통한 `ri_phys_footprint` (Activity Monitor와 동일). UI에서 "(est.)"로 표시.

## 환경 안전성

asiai는 벤치마크 전 검사를 수행합니다:

1. **메모리 프레셔**: critical이면 시작 거부
2. **서멀 쓰로틀링**: 속도 제한 < 80%이면 경고
3. **중복 프로세스**: 동일 엔진의 여러 인스턴스가 실행 중이면 경고 (예: 같은 포트의 두 `ollama serve` 프로세스)
4. **엔진 runner 타입**: Ollama의 경우 `--mlx-engine` 또는 `--ollama-engine` runner가 활성 상태인지 감지

이러한 검사는 리소스 경합이나 잘못된 라우팅으로 인한 측정 오류를 방지합니다.

## 준수 현황

| 실천 사항 | 상태 |
|----------|------|
| 프리플라이트 게이트 체크 (메모리 프레셔 + 서멀) | 구현됨 |
| 중복 프로세스 감지 | 구현됨 (v1.5.0) |
| Ollama runner 타입 감지 (MLX vs llama.cpp) | 구현됨 (v1.5.0) |
| TTFT를 tok/s에서 분리 | 구현됨 |
| TTFT 소스 라벨링 (server vs client) | 구현됨 (v1.5.0) |
| 결정론적 샘플링 (temperature=0) | 구현됨 |
| 서버 API의 토큰 카운트 (SSE 청크가 아님) | 구현됨 (폴백 시 경고) |
| 엔진별 전력 모니터링 (IOReport, sudo 불필요) | 구현됨 |
| 엔진당 1회 워밍업 생성 | 구현됨 |
| 기본 3회 실행 (SPEC 최솟값) | 구현됨 |
| 기본 메트릭으로 중앙값 (SPEC 표준) | 구현됨 |
| 풀드 프롬프트 내 표준편차 (Bessel N-1) | 구현됨 (v1.5.0에서 수정) |
| 엔진 간 모델 언로드 | 구현됨 |
| 적응형 쿨다운 (메모리 프레셔 인식) | 구현됨 |
| 건전성 검사 (tok/s, TTFT 경계값) | 구현됨 |
| 서멀 쓰로틀링 감지 + 경고 | 구현됨 |
| 서멀 드리프트 감지 (단조 감소) | 구현됨 |
| 엔진 버전 + runner 타입 결과별 저장 | 구현됨 (v1.5.0) |
| ri_phys_footprint를 통한 유니버설 VRAM | 구현됨 |
| 과거 리그레션 감지 | 구현됨 |
| 교차 검증 스크립트 (3가지 방법 비교) | 사용 가능 (scripts/cross-validate-bench.py) |

## Apple Silicon 관련 고려 사항

### 유니파이드 메모리

Apple Silicon은 CPU와 GPU가 메모리를 공유합니다. asiai는 엔진을 **순차적으로 실행**하고 **엔진 간 모델을 언로드**하여 메모리 경합과 스왑을 방지합니다. VRAM은 Ollama와 LM Studio에서 네이티브로 보고됩니다. 다른 엔진에서는 `ri_phys_footprint`(Activity Monitor와 동일한 macOS 물리 풋프린트 메트릭)를 통해 메모리 사용량을 추정합니다. 추정값은 UI에서 "(est.)"로 표시됩니다.

### 서멀 쓰로틀링

- **MacBook Air** (팬 없음): 지속 부하에서 심각한 쓰로틀링
- **MacBook Pro** (팬 있음): 경미한 쓰로틀링
- **Mac Mini/Studio/Pro**: 능동 냉각, 최소한의 쓰로틀링

asiai는 결과별로 `thermal_speed_limit`를 기록하고 쓰로틀링이 감지되면 경고합니다.

### KV 캐시

대규모 컨텍스트 크기(32k 이상)는 KV 캐시를 사전 할당하는 엔진에서 불안정할 수 있습니다. 공정한 결과를 위해 엔진의 컨텍스트 길이를 실제 테스트 크기에 맞추세요.

## 전력 측정

asiai는 Apple의 IOReport Energy Model 프레임워크를 통해 GPU, CPU, ANE, DRAM 전력 소비를 측정합니다 — **sudo 불필요**. 전력은 모든 벤치마크와 모니터링 스냅샷에서 자동으로 측정됩니다.

IOReport는 `sudo powermetrics`와 동일한 하드웨어 에너지 카운터를 읽지만 사용자 공간 API(ctypes를 통한 `libIOReport.dylib`)를 사용합니다. 이로써 패스워드 없는 sudo 설정이 불필요해집니다.

### 검증

M4 Pro 64GB에서 LLM 추론 부하 하에 엔진당 2초 간격으로 10개 페어 샘플을 사용하여 IOReport를 `sudo powermetrics`와 비교 검증했습니다:

| 엔진 | IOReport 평균 | powermetrics 평균 | 평균 차이 | 최대 차이 |
|------|-------------|-----------------|----------|----------|
| LM Studio (MLX) | 12.6 W | 12.6 W | 0.9% | 2.1% |
| Ollama (llama.cpp) | 15.6 W | 15.4 W | 1.3% | 4.1% |

두 엔진 모두 10/10 페어 샘플에서 평균 차이 1.5% 미만 확인. ANE 전력은 전체 20개 샘플에서 0.000W로, 현재 LLM 엔진이 Neural Engine을 사용하지 않음을 확인.

`--power` 플래그는 IOReport와 `sudo powermetrics`를 동시에 실행하는 추가 교차 검증을 활성화하여, 비교를 위해 두 읽기값을 모두 저장합니다.

### 전력 효율

전력 효율(와트당 tok/s)은 벤치마크 결과별로 `tok_per_sec / gpu_watts`로 계산됩니다. 이 메트릭을 통해 엔진과 하드웨어 간 추론 비용을 비교할 수 있습니다.

## 메타데이터

모든 벤치마크 결과에는 다음이 저장됩니다: engine, engine_version, model, model_format, model_quantization, hw_chip, os_version, thermal_level, thermal_speed_limit, power_watts, power_source, metrics_version. 이를 통해 공정한 리그레션 비교와 교차 머신 벤치마크가 가능합니다.
