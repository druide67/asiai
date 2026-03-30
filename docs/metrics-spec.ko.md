---
description: "asiai 벤치마크 메트릭의 상세 정의: tok/s, TTFT, 전력 와트, 효율, VRAM, 안정성, 서멀 상태."
---

# 벤치마크 메트릭 사양

> **버전**: 0.4.0
> **상태**: 구현됨
> **범위**: `asiai bench` — 모든 엔진

## 배경

벤치마크 결과는 **엔진 간에 비교 가능**해야 합니다. 각 메트릭에는 모든 엔진 구현이 준수해야 하는 단일 정의가 있습니다. 구현은 다를 수 있지만(서버사이드 API vs 클라이언트사이드 측정), 의미는 동일해야 합니다.

## 메트릭

### M1. `tok_per_sec` — 생성 속도

**정의**: 프롬프트 처리(TTFT)를 제외한 **생성 시간만의** 초당 생성 토큰 수.

```
generation_s = total_duration_s - ttft_s
tok_per_sec  = tokens_generated / generation_s    (if generation_s >= 0.01)
             = 0.0                                 (otherwise)
```

| 엔진 | `generation_s` 소스 |
|------|-------------------|
| Ollama | `eval_duration / 1e9` (서버 API — 직접) |
| OpenAI 호환 | `elapsed_s - (ttft_ms / 1000)` (클라이언트사이드) |

**근거**: 대규모 컨텍스트 크기(예: 64k 토큰)에서 TTFT가 총 시간을 지배할 수 있습니다. tok/s에 TTFT를 포함하면 빠른 생성기가 느리게 보입니다(예: 42 tok/s 대신 3.2 tok/s).

### M2. `ttft_ms` — 첫 번째 토큰까지의 시간

**정의**: 요청 전송부터 첫 번째 출력 토큰 수신까지의 시간(밀리초).

| 엔진 | 소스 |
|------|------|
| Ollama | `prompt_eval_duration / 1e6` (서버 API) |
| OpenAI 호환 | `(time.monotonic() at 1st content chunk - t0) * 1000` (클라이언트) |

참고: 의미론이 약간 다릅니다(서버 vs 클라이언트 측정), 하지만 localhost에서의 차이는 ~1ms — 허용 범위입니다.

### M3. `total_duration_ms` — 총 시간

**정의**: 요청의 벽시계 총 시간(프롬프트 처리 + 생성), 밀리초.

**불변 조건**: `total_duration_ms >= ttft_ms` — 항상.

| 엔진 | 소스 |
|------|------|
| Ollama | `total_duration / 1e6` (서버 API) |
| OpenAI 호환 | `elapsed_s * 1000` (클라이언트 벽시계) |

### M4. `tokens_generated` — 토큰 수

**정의**: 모델이 생성한 출력 토큰 수.

**소스 (우선순위)**:
1. 서버 카운터: Ollama `eval_count`, OpenAI 호환 `usage.completion_tokens`
2. 텍스트 길이 추정: `max(1, len(text) // 4)` (휴리스틱: ~4 문자/토큰)
3. **절대** `len(text_parts)` 사용 금지 (SSE 청크 != 토큰)

### M5. `generation_duration_ms` — 생성 시간

**정의**: 생성 시간만(TTFT 제외), 밀리초.
분해 `total = ttft + generation`을 명시적이고 감사 가능하게 만듭니다.

| 엔진 | 소스 |
|------|------|
| Ollama | `eval_duration / 1e6` (서버 API — 직접) |
| OpenAI 호환 | `max(0, elapsed_s - ttft_s) * 1000` (계산값) |

### M6. `power_watts` — GPU 전력

**정의**: **이 특정 엔진** 실행 중 평균 GPU 전력(와트).

**범위**: 엔진당 1개의 `PowerMonitor`. 첫 프롬프트 전에 시작, 마지막 실행 후 중단. 각 엔진이 자체 측정을 받음 — 세션 전체 평균이 아님.

소스: `sudo powermetrics` (macOS).

### M7. `tok_per_sec_per_watt` — 에너지 효율

```
tok_per_sec_per_watt = tok_per_sec / power_watts
```

보정된 tok/s(M1)와 엔진별 전력(M6)을 사용.

### M8. `std_dev_tok_s` — 분산 (풀드)

**정의**: 풀드 프롬프트 내 표준편차 — 프롬프트 간 분산을 혼합하지 않고 실행 간 노이즈를 포착합니다.

```
For each prompt_type p with runs [v1, v2, ..., vn]:
    var_p = sum((vi - mean_p)^2) / n    (population variance)

pooled_variance = mean(var_p for all p with n >= 2)
std_dev_tok_s   = sqrt(pooled_variance)
```

**안정성 분류** (변경 없음):
- CV < 5% → `stable`
- CV < 10% → `variable`
- CV >= 10% → `unstable`

CV = `(std_dev_tok_s / avg_tok_s) * 100`

## 구현 맵

| 메트릭 | `base.py` | `ollama.py` | `openai_compat.py` | `runner.py` | `reporter.py` |
|--------|-----------|-------------|--------------------|-----------  |----------------|
| M1 tok/s | 필드 | 서버 API | 클라이언트 (TTFT 제외) | 패스스루 | 평균 |
| M2 ttft_ms | 필드 | 서버 API | 클라이언트 스트리밍 | 패스스루 | 평균 |
| M3 total_duration_ms | 필드 | 서버 API | 클라이언트 벽시계 | 패스스루 | 평균 |
| M4 tokens_generated | 필드 | 서버 API | 서버 또는 `len//4` | 패스스루 | 평균 |
| M5 generation_duration_ms | 필드 | 서버 API | 계산값 | dict에 저장 | — |
| M6 power_watts | — | — | — | 엔진별 모니터 | 패스스루 |
| M7 tok/s/W | — | — | — | 계산값 | 패스스루 |
| M8 std_dev | — | — | — | — | 풀드 프롬프트 내 |

## 벤치마크 프로토콜

1. **워밍업**: 엔진당 1회 비측정 생성 (`"Hello"`, max_tokens=1)으로 캐시 프라이밍.
2. **측정 실행**: 기본 프롬프트당/엔진당 3회 실행 (`--runs`로 설정 가능).
3. **샘플링**: 결정론적 출력을 위해 모든 엔진에서 `temperature=0` (그리디).
4. **보고**: 중앙값 tok/s를 기본 메트릭(SPEC 표준), 평균 +/- 표준편차를 보조로 사용.
5. **쓰로틀링**: 실행 중 `thermal_speed_limit < 100%`이면 경고 출력.
6. **메타데이터**: engine_version, model_format, model_quantization, hw_chip, os_version을 재현성을 위해 결과별로 저장.

전체 방법론 감사는 [benchmark-best-practices.md](benchmark-best-practices.md)를 참고하세요.
