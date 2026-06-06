# Apple Silicon 에이전트 추론 패널

> Apple Silicon M 시리즈에서 Qwen 3.6 제품군 모델을 구동하는 추론 엔진
> (llama.cpp, mlx-lm, LM Studio, Rapid-MLX, vLLM-MLX, oMLX, vMLX, Ollama) 전반에 걸친
> 비교 벤치마크 패널이며, `asiai bench --agentic-mode` 및 `asiai bench --burst-mode` 로
> 측정했다.
>
> **워크로드 목표**: 에이전트-오케스트레이터 클래스 — 턴당 약 60-80개의 tool call,
> 약 7 KB의 동일한 시스템 prompt, 호출마다 바뀌는 user 메시지. 이는 순진한 prefix
> 캐싱에 최악의 경우다: 동일 prompt에 대한 캐시가 아니라 진정한 cross-USER 캐시 재사용이
> 필요하다.
>
> **throughput 수치 읽는 법**: 1절의 decode 수치는 Qwen3 기본 chat 템플릿
> (thinking ON)을 사용하므로 reasoning 토큰을 포함한다 — thinking 모델에서의 유효
> 에이전트 throughput은 더 낮다. thinking은 전역 on/off가 아니라 작업별 trade-off다
> (주의사항 1).
>
> 2026-06 발행 · 기여와 수정은
> [github.com/druide67/asiai](https://github.com/druide67/asiai/issues) 로 환영한다.

## ⚠️ 더 읽기 전에 알아야 할 주의사항

1. **Thinking 모드는 작업별 trade-off다.** Qwen3 기본 템플릿(thinking ON)에서는
   Qwen 3.6 / Qwopus가 토큰을 약 6-7× 더 많이 내보내므로, 1절의 decode 수치는
   **reasoning 토큰을 포함**하고 유효 에이전트 throughput은 더 낮다. thinking ON은
   여러 섹션으로 구성된 서면 산출물에 **필수**(thinking-OFF 모델은 산출물을 건너뛴다)지만
   원자적 tool-call 청결성을 **희생**한다(asiai 측정 기준 thinking OFF에서 약 100% 청결한
   tool call, thinking ON + `preserve_thinking` ON에서 약 77.8%, 실행 간 결정론적;
   `enable_thinking=on` + `preserve_thinking=off`는 사용 불가 — reasoning이 컨텍스트에
   누적되면 결정론적 HTTP 500). thinking은 단일 전역 플래그가 아니라 **작업 차원별**로
   설정하라.
2. **Rapid-MLX와 vLLM-MLX는 엔진을 공유한다.** Rapid-MLX는 `waybarrios/vllm-mlx`의
   커뮤니티 fork다; 버전과 기능이 갈라졌기 때문에 아래에서 별도 행으로 나타나지만,
   prefix-cache 스냅샷 메커니즘은 같은 계보다.
3. **MTP: Qwen 3.6에는 실제 head가 있다; backend가 중요하다.** Qwen 3.6의 공식
   `config.json`은 `mtp_num_hidden_layers=1`을 담고 있다(Qwen 명명 — DeepSeek의
   `num_nextn_predict_layers` 키가 **아니므로**, `nextn`만 확인하면 "head 없음"이라고
   잘못 결론낸다). 일부 재양자화된 GGUF/MLX 아티팩트는 config 플래그는 유지한 채 MTP
   텐서를 누락한다 — 플래그만 보지 말고 가중치 인덱스에서 텐서를 검증하라.
   llama.cpp 네이티브 MTP(`--spec-type draft-mtp`)는 head를 내장한 **`-MTP-GGUF`를
   요구**한다; 일반 GGUF는 draft할 수 없다. 릴리스된 mlx-lm은 head를 네이티브
   speculative decoding으로 실행하지 않는다(PR
   [ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990)이 이를 추가한다).
   LM Studio는 GGUF를 llama.cpp 파생 backend로, MLX를 `mlx-engine`으로 라우팅한다.
4. **단일 패스 측정, 분산 보고 없음** — 1절 / 2절 수치는 단일 관측이다. 분산 보고
   (N회 패스에 걸친 median + min + max)는 `--burst-runs N`으로 지원되지만 재벤치는
   아직 보류 중이다.

| 섹션 | 주제 | 상태 |
|---------|-------|--------|
| 1 | Single-call performance | 🟡 8 cells, thinking-mode ON (decode includes reasoning tokens) |
| 2 | Concurrent burst (30/60/80 parallel calls) | 🟡 smoke cell + 2 partial concurrent points; no normalized 30/60/80 panel |
| 3 | Caches & optimizations | ✅ 8 engines covered |
| 4 | Memory & resources | ✅ idle + under-load swap (+0) + footprint measured |
| 5 | Model quality (public leaderboards) | 🟡 vendor/self-reported figures (llm-stats) |
| — | **asiai direct measurements** | ✅ dev-quality, thinking ablation, MTP, instruction-following |
| 6 | Operational (license, endpoints, maintenance) | ✅ 8 engines covered |
| 7 | Quality benchmark weighting | 🟡 default weighting, override via `--weights` planned |
| 8 | Custom long-horizon eval (proposal) | 🟡 scoped, not yet built |

---

## 1절 — Single-call performance

> ⚠️ **위의 주의사항 1과 함께 읽으라**: 이 표의 모든 수치는 Qwen3 기본 thinking-mode
> 토큰(reasoning_content)을 포함한다. 유효 에이전트 throughput을 얻으려면
> `chat_template_kwargs={"enable_thinking": false}`로 재실행해야 한다. 이 열은
> "유효 throughput"이 아니라 "decode (t/s)"로 표기되어 있다.
>
> "lower-bound estimate" 열은 `60 × (TTFT + max_tokens/decode)`이며, 순차 dispatch
> (Rapid-MLX single-slot이 강제하는)를 가정한다. 이는 프로덕션 tick 예측이 **아니다** —
> 방법론적 주의사항은 [7절](#section-7)을 참조하라.
>
> 📌 **테스트된 버전 (2026년 5월)**: Rapid-MLX 0.6.66, LM Studio 0.4.14,
> llama.cpp b9270. 엔진 버전은 Apple Silicon에서 매주 바뀐다 — 각 수치를 현재가 아니라
> 날짜가 찍힌 것으로 취급하라. (asiai 측정 섹션은 llama.cpp b9430을 사용한다.)

| # | Engine | Model | Format | Warm decode (t/s) ¹ | TTFT warm (ms) | TTFT prefix-test median (ms) | TTFT cold (ms) | Lower-bound estimate (60 calls × single-call, optimistic) | Source fixture |
|---|--------|-------|--------|--------------------:|---------------:|----------------------------:|---------------:|----------------------------------------------------------:|----------------|
| 1 | Rapid-MLX 0.6.66 (fork of vllm-mlx) | Qwopus 3.6-35B-A3B-v1 (zaydiscold MLX-4bit) | MLX-4bit | **109.1** ¹ | 139 | **131** | 2074 | ~3.6 min | `cell-rapidmlx-qwopus35b.json` |
| 2 | Rapid-MLX 0.6.66 | Qwen 3.6-35B-A3B-UD (MLX-4bit) | MLX-4bit | 106.9 ¹ | 321 | 319 | 2095 | ~4 min | `cell-rapidmlx-35b-a3b.json` |
| 3 | Rapid-MLX 0.6.66 | Qwopus 3.6-27B-v2 (Jackrong MLX-4bit) | MLX-4bit | 31.8 ¹ | 323 | 323 | 8647 | ~13 min | `cell-rapidmlx-qwopus.json` |
| 4 | Rapid-MLX 0.6.66 | Qwen 3.6-27B-UD (MLX-4bit) | MLX-4bit | 20.5 ¹ | 527 | 527 | 8954 | ~23 min | `cell-rapidmlx-full-27bud.json` |
| 5 | LM Studio 0.4.14 (GGUF backend) ² | Qwen 3.6-35B-A3B-MTP (Unsloth GGUF) | GGUF Q4 + MTP | **123.9** ¹ ² | 309 | 5965 | 6063 | ~3.5 min warm / ~9.2 min prefix-changing | `cell-lmstudio-mtp-qwen35b.json` |
| 6 | LM Studio 0.4.14 (GGUF backend) ² | Qwopus 3.6-35B-A3B-v1 (Jackrong GGUF) | GGUF Q4_K_S | 105.6 ¹ | 292 | 5785 | 5624 | ~3.5 min warm / ~9.6 min prefix-changing | `cell-lmstudio-qwopus35b.json` |
| 7 | llama.cpp b9270 | Qwen 3.6-35B-A3B (UD Q5_K_XL) | GGUF Q5_K_XL | 80.9 ¹ | 3000 | 3000 | n/a | ~8 min | (baseline reference) |
| 8 | llama.cpp b9270 | Qwopus 3.6-27B-v2 (Jackrong GGUF Q4) | GGUF Q4 | 25.3 ¹ | 13000 | 13000 | n/a | ~30 min | (baseline reference) |

¹ **Thinking-mode 주의사항**: 수치는 기본 chat 템플릿(thinking ON)으로 캡처했다.
reasoning 토큰이 출력을 6-7× 부풀릴 때, tool-call 워크로드에서 Qwopus/Qwen3.6
파인튜닝의 실제 유효 throughput은 일반적으로 4-12 t/s다. 이 decode 수치를 재현하려면
요청 payload에 `chat_template_kwargs={"enable_thinking": false}`를 전달하라.

² **LM Studio backend**: 5-6행은 GGUF 파일을 사용했으며, 이는 LM Studio의 llama.cpp
파생 backend(MLX 런타임 `mlx-engine`이 아님)로 라우팅된다. 5행의 MTP 주장은
mlx-engine speculative decoding이 아니라 이 backend의 구현을 반영한다. 릴리스된
mlx-lm은 MTP head를 네이티브 speculative decoding으로 실행하지 않으며(과거 `sanitize()`가
변환 중 MTP 가중치를 누락했다; 네이티브 지원은 PR
[ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990)에 있다),
따라서 가상의 MLX-format MTP 모델은 릴리스된 mlx-engine에서도 이득을 보지 못한다.

### 주요 관찰

- 현실적인 에이전트 패턴(동일 시스템 + 바뀌는 user prompt)에서,
  **Rapid-MLX + Qwopus 35B-A3B-v1**은 LM Studio GGUF backend의 5965 ms 대비
  131 ms median TTFT prefix-test를 낸다(**약 44× 빠름**). 이 우위는 vllm-mlx
  prefix-cache 스냅샷 메커니즘에서 비롯된다(소스 코드 모호성 해소는 3절 참조).
- 순수 decode throughput(웜 경로)에서, **Unsloth MTP를 적용한 LM Studio GGUF
  backend**는 Rapid-MLX 109.1 t/s 대비 123.9 t/s를 기록한다(+13.5%). 이 차이는
  Apple-MLX 이득이 아니라 MTP head를 담은 GGUF에서 LM Studio의 llama.cpp 파생
  backend가 수행하는 speculative decoding을 반영한다(릴리스된 mlx-engine은 head를
  실행하지 않는다 — 각주 2 참조). 네이티브 llama.cpp 경로에서는 MTP가 MoE 35B-A3B에서
  순이익이다 — 3절 참조.
- 모든 `Qwen 3.6 family` 구성(hybrid DeltaNet + full-attention)은 **Rapid-MLX를
  제외하고** cross-USER prefix cache에 실패하며, Rapid-MLX는 RNN-state 스냅샷을
  유지한다. llama.cpp / LM Studio GGUF에서는 `llama_memory_can_shift=false`다;
  mlx-lm / oMLX에서는 recurrent/SSM state를 임의의 토큰 경계에서 분할할 수 없다.
  이 아키텍처에 대한 upstream llama.cpp 수정은 머지되지 않았다
  ([#23121](https://github.com/ggml-org/llama.cpp/pull/23121) closed;
  `preserve_thinking`은 이를 해결하지 못한다,
  [#22615](https://github.com/ggml-org/llama.cpp/issues/22615)).
- **단일 슬롯 직렬화 확인됨**: smoke burst 테스트(2절)는 Rapid-MLX 0.6.66이 동시 호출을
  FIFO로 직렬화함을 보여준다(burst=5에서 p50 ≈ p95 ≈ max). 턴당 60-80 호출의 경우,
  이 엔진에서 총 wall-time은 burst 크기에 선형으로 비례한다. 멀티 슬롯 엔진
  (예: llama.cpp `--parallel N`)은 다르게 동작하겠지만, Qwen3.6 hybrid에서
  `--parallel N`은 슬롯별로 prefix cache를 비활성화한다(아키텍처적 한계).

---

## 2절 — Concurrent burst (30/60/80 parallel calls)

> 패턴: 약 200 ms 윈도우 내에서 30 ~ 80개의 동시 `POST /v1/chat/completions` 호출.
> 여러 MCP/tool call을 병렬로 dispatch하는 에이전트 루프를 시뮬레이션한다.
> `asiai bench --burst-mode`로 네이티브 측정.
>
> 🟡 **상태**: smoke cell 1개 측정됨(Rapid-MLX burst-5). 전체 패널 보류 중.

### Smoke cell (Rapid-MLX 0.6.66 + Qwopus 35B-A3B-v1, burst=5)

| burst N | wall-time (s) | p50 latency (ms) | p95 latency (ms) | max latency (ms) | agg throughput (t/s) |
|--------:|--------------:|-----------------:|-----------------:|-----------------:|---------------------:|
| 5 | 2.8 | 2615 | 2792 | 2812 | 88.8 |

**Smoke 발견**: `p50 ≈ p95 ≈ max`는 5개 호출이 **서버 측에서 직렬화**되었음을
나타낸다(단일 슬롯 엔진). Rapid-MLX 0.6.66은 동시 요청 스케줄링을 지원하지 **않는** 것으로
보인다 — 호출이 내부적으로 FIFO 큐잉된다. 60/80 호출 규모에서 검증 필요.

### 전체 동시 패널 — 아직 미측정

정규화된 30/60/80-concurrent 패널은 실행되지 않았다(여기서의 측정은 동시 burst가 아니라
순차 agentic-mode다). 다른 곳에 존재하는 두 개의 부분 동시 데이터 포인트:

- **TurboQuant** (K=`q8_0` V=`turbo2`, Qwen3-4B, M4 Pro): single-stream은 −8%임에도
  **4-parallel에서 aggregate +9%** (68.5 → 74.7 t/s) — KV 압축이 병렬 여유분을 되사온다.
- **oMLX** 연속 배칭(mlx-lm `BatchGenerator`): **burst-8에서 aggregate ×1.8**
  (12.8 → 22.9 t/s)이지만, 27B-dense가 RAM을 swap으로 포화시키면 **burst-30에서 붕괴**
  한다(17.3 t/s) — 크래시는 0.

모든 엔진에 걸친 전용 burst-mode 패널은 연기되었다.

---

## 3절 — Caches & optimizations

| # | Couple | Cache reuse cross-USER | Snapshot persists cross-restart | MTP support | MTP accept rate | TurboQuant compat | KV cache native types | Native parallel slots |
|---|--------|---|---|---|---|---|---|---|
| 1 | Rapid-MLX + Qwopus 35B-A3B-v1 | ✅ YES (RNN-state snapshot, see ³ below) | ✅ persistent in `~/.cache/vllm-mlx/` | ❌ released MLX runtime doesn't run the MTP head as speculative decode (mlx-lm PR #990 pending) | n/a | ❌ MLX only | MLX native (no quant flag exposed) | ⚠️ single slot (smoke burst confirms FIFO serialization) |
| 2 | Rapid-MLX + Qwen 35B-A3B-UD | ✅ YES ³ | ✅ persistent | ❌ | n/a | ❌ | MLX native | ⚠️ single slot |
| 3 | LM Studio + Qwen 35B-A3B-MTP | ❌ NO (architectural hybrid limitation) | n/a | ✅ via mlx-engine v1.8.1 | **82.1 %** (on coding task) | ❌ | mlx-engine v1.8.1 (4bit MLX) | configurable via GUI |
| 4 | LM Studio + Qwopus 35B-A3B-v1 | ❌ NO | n/a | ❌ no heads | n/a | ❌ | mlx-engine v1.8.1 (Q4_K_S GGUF) | configurable via GUI |
| 5 | llama.cpp + Qwen 3.6-35B-A3B | ❌ NO (architectural hybrid limitation) | n/a | ✅ `--spec-type draft-mtp` on a `-MTP-GGUF` (a plain GGUF cannot draft). Net-positive on the MoE 35B-A3B — asiai measures **+38%** decode (base) / **+17%** (Qwopus) on M5 Max (see § asiai measurements) | benefit = intra-session decode delta (no acceptance rate logged) | ✅ turbo2/3/4 V cache | `fp16`, `q8_0`, `q5_0`, `turbo2/3/4` | ⚠️ `--parallel N` works mechanically but **disables prefix cache per slot on hybrid arch** (each slot owns its KV, the `--cache-reuse N` flag is already silently disabled here). Use with caution. |
| 6 | mlx-lm | ❌ NO (PRs #923, #188, #192 pending upstream) | n/a | ❌ broken on hybrid arch | n/a | ❌ | MLX native | ❌ (single slot) |
| 7 | oMLX | ❌ NO (tool calling lost post-cache-hit, issue #825) | partial | ❌ | n/a | ❌ | MLX native + tiered SSD cache | ❌ |
| 8 | vLLM-MLX (`waybarrios`, upstream of Rapid-MLX) | ⚠️ trie prefix-cache, no documented hybrid/DeltaNet support (Rapid-MLX rows 1-2 add the RNN-state snapshot on top) | n/a | ⚠️ MTP added in prerelease 0.4.0rc1 | n/a | ❌ | MLX + paged-attention | ✅ |

³ **Rapid-MLX prefix cache**: 캐시는 hybrid-attention KV slab + RNN-state 스냅샷을
저장하며, `<repo>--<sys_prompt_hash>`별로 키잉되어 `~/.cache/vllm-mlx/` 아래에 영속화된다.
관측된 약 131 ms TTFT prefix-test는 디스크에서의 재로드가 아니라 in-RAM KV slab 재부착 +
바뀐 user의 forward pass다.

**oMLX large-context cache.** oMLX의 2-tier paged SSD KV 캐시는 동일 prompt cache-hit에서
55K 토큰 prefill을 약 115 s에서 약 **3.5 s** TTFT로 바꾼다(×33; 55,296 / 55,837 토큰
캐싱됨). 작은 prompt(약 7.5K)에서는 이점이 없으며(약 2-5 s, = mlx-lm) decode는 약
19 t/s다(raw-speed 이득 없음). 이는 cross-USER가 아니라 동일 prompt 재사용이다(oMLX는
cross-USER를 하지 않는다); cross-restart 영속성은 문서화되어 있으나 아직 A/B 테스트되지
않았다.

**TurboQuant KV 압축** (llama.cpp). K=`q8_0` V=`turbo2`는 KV RAM을 약 **28%** 줄이며
(4B 모델, M4 Pro에서 22.9 → 16.4 GB) tool-call 유효성은 변하지 않고(10/10),
single-stream −8%에도 불구하고 **4-parallel에서 aggregate +9%**를 얻는다. 대칭형
K=`turbo3` V=`turbo3`는 RAM 약 −56%에 도달하지만 품질을 저하시킨다(early-stop, 반복) —
비대칭 `q8_0`/`turbo2`가 사용 가능한 구성이다.

---

## 4절 — Memory & resources (Apple Silicon M5 Max 128 GB)

| # | Couple | Working-set RAM (GB) | Disk footprint (GB) | Swap Δ idle | Swap Δ under load | SOLO required? | Cohabitation safe? |
|---|--------|---|---|---|---|---|---|
| 1 | Rapid-MLX + Qwopus 35B-A3B-v1 | ~22 | 19.9 (MLX-4bit) | +0 | **+0 MB** | ⚠️ SOLO (cohabit thrash to 0.4 t/s) | ❌ |
| 2 | Rapid-MLX + Qwen 35B-A3B-UD | ~24 | 20.0 (MLX-4bit) | +0 | **+0 MB** | ⚠️ SOLO | ❌ |
| 3 | LM Studio + Qwen 35B-A3B-MTP | 21.6 | 23.2 (Q4 + MTP heads) | +0 | **+0 MB** | not tested | not tested |
| 4 | LM Studio + Qwopus 35B-A3B-v1 | 18.5 | 19.9 (Q4_K_S) | +0 | **+0 MB** | not tested | not tested |
| 5 | llama.cpp + Qwen 3.6-35B-A3B (reference) | ~16 | ~16 (Q5_K_XL) | +0 | **+0 MB** | ❌ | ✅ with `--parallel 2/3` |

> **"Under load"** = 50K 토큰 prefill을 포함하는 8단계 agentic 벤치(측정된 가장 무거운
> *순차* 메모리 스트레스), M5 Max 128 GB, SOLO: **모든 엔진에서 swap delta
> 0 MB / 0 swapouts** — 모델 + KV가 100 GB 이상의 여유와 함께 free/inactive 메모리에
> 들어간다. 이는 60-concurrent 메모리(2절 참조)가 **아니라** 순차-load 메모리다.
> Working-set RAM은 추정치다; 측정된 RSS는 mmap된 GGUF / wired MLX 페이지를 포함하므로
> 실제 증분 footprint는 더 낮다(MTP head는 약 +3 GB를 더한다).

### 관찰

- **Rapid-MLX는 GPU에서 SOLO 운영을 요구한다**: 능동적으로 decode 중인 다른 엔진과의
  공존은 5.4 → 14.2 GB의 swap delta와 0.4 t/s로의 decode 붕괴를 유발한다. 같은 Apple
  Silicon GPU에서 두 번째 엔진을 시작하지 말라.
- **LM Studio MTP** 디스크 footprint는 MTP 가중치 블록 때문에 MTP head가 없는 Q4_K_S
  대비 +13%다. +17% decode 이득에 비하면 무시할 만한 비용이다.
- M5 Max 128 GB 통합 메모리에서: 테스트된 모든 35B-A3B 구성은 load 후 100 GB 이상의
  여유를 남긴다 — RAM은 제약 요인이 아니다.
- M4 Pro 64 GB에서: `Q5_K_XL`은 보조 모델과 함께 들어가지 **않는다**(프로덕션에서 swap
  thrash 관찰됨). `Q4_K_S`는 들어간다.

---

## 5절 — Model quality

> 여기의 공개 벤치마크 수치는 **벤더 / 자체 보고**이며 리더보드(llm-stats)가 집계한
> 것으로, 독립적으로 검증되지 않았다. 의존하기 전에
> [llm-stats](https://llm-stats.com) · [LiveBench](https://livebench.ai) ·
> [SWE-bench](https://swebench.com) 에서 교차 검증하라. Apple Silicon에서의 asiai 자체
> 직접 측정은 다음 섹션에 있다.
>
> 저자 단독 주장(Jackrong/Qwopus, Unsloth 자체 평가)은 별도로 표시하며 공개 리더보드
> 열에서 제외한다.
>
> 🔴 **중대 발견**: 여러 커뮤니티 모델 카드에 인용된 "Hessling agentic" 벤치마크는
> **독립적으로 재현 불가능**하다 — 16개 prompt, 단일 큐레이터, 중립 리더보드 통합 없음.
> 세 자문가 모두 이를 smoke test로만 취급할 것을 권고한다.

### 오픈 가중치 Qwen 3.6 base 모델

> 공개 리더보드 수치(llm-stats), 자체 보고. 27B-dense는 SWE-bench에서 35B-A3B MoE를
> 능가한다 — 아래 asiai 자체 dev-quality 발견과 일치한다(MoE base가 tool-call
> empty-object 버그를 겪는 쪽이다). MTP head는 decode-speed 기능이며 모델의 품질 점수를
> 바꾸지 않는다.

| Model | Architecture | SWE-bench Verified | GPQA Diamond | MMLU-Pro | Terminal-Bench 2.0 | BFCL |
|-------|--------------|-------------------:|-------------:|---------:|-------------------:|------|
| Qwen 3.6-35B-A3B-Instruct | MoE 35B / 3B active | 73.4% | 86.0% | 85.2% | 24.6% | absent from board |
| Qwen 3.6-27B-Dense Instruct | Dense 27B hybrid | 77.2% | 87.8% | 86.2% | 59.3% (vendor) | absent from board |

> Terminal-Bench **2.0**은 구형 Terminal-Bench v1보다 훨씬 어렵다(커뮤니티 카드는
> 35B-A3B의 v1 점수로 약 51.5%를 인용한다); 여기의 24.6%는 2.0 세대다.

### Qwopus 3.6 제품군 — 저자 보고만, **독립적으로 검증되지 않음**

Jackrong이 HuggingFace에 발행한 Qwopus 3.6 파인튜닝은 Qwen base 대비 상당한 이득을
주장한다. 2026년 5월 기준 이 주장들은 중립 리더보드에서 **독립적으로 재현되지 않았다**.
제3자에 의한 BFCL / SWE-bench 재실행이 가능해질 때까지 실험적인 것으로 취급하라.

| Model (author claims) | MMLU-Pro | SWE-bench Verified | Hessling agentic (16 prompts) |
|-----------------------|---------:|-------------------:|------------------------------:|
| Qwopus 3.6-35B-A3B-v1 (Jackrong) | claimed 88+ | claimed 75+ | claimed 88.6 ⚠ non-reproducible |
| Qwopus 3.6-27B-v2 (Jackrong) | claimed 87.43 | claimed 75.25 | n/a |

⚠ Jackrong 모델 카드에 인용된 "Hessling agentic" 벤치마크는 중립 리더보드 통합이 없는
16-prompt 큐레이터 전용 평가로 보인다. 질의한 세 자문(Grok-4, GPT-5, Gemini Advanced)
모두 이를 smoke test로만 취급할 것을 권고한다.

### Frontier 기준점 (2026년 중반)

> 모든 수치는 **벤더 / 자체 보고**이며 llm-stats가 집계한 것으로 — 거기서 독립적으로
> 검증된 것은 없다. **Terminal-Bench 2.0**은 예외다(tbench 팀이 제출물을 재실행한다;
> 행은 peak agent×model 점수다). GPQA는 벤더 "Diamond" 수치이며 세트가 거의 포화 상태다 —
> 근사치로 취급하라.

| Model | SWE-bench Verified | GPQA Diamond | MMLU-Pro | Terminal-Bench 2.0 | Source |
|-------|-------------------:|-------------:|---------:|-------------------:|--------|
| Claude Opus 4.8 | 88.6% | 93.6% | n/a | — (no TB submission) | llm-stats / Anthropic |
| Claude Opus 4.7 | 87.6% | 94.2% | n/a | **90.2%** | llm-stats / tbench |
| Claude Sonnet 4.6 | 79.6% | 89.9% | n/a | 53.4% | llm-stats / tbench |
| GPT-5.5 | n/a\* (SWE-Pro 58.6%) | 93.6% | n/a | 84.7% | OpenAI / tbench |
| GPT-5 (base) | 74.9% | 85.7% | n/a | 49.6% | llm-stats / tbench |
| Gemini 3.1 Pro | 80.6% | ~94.4% | n/a | 80.2% | llm-stats / tbench |
| DeepSeek-V4-Pro-Max | 80.6% | 90.1% | 87.5% | n/a | vendor (DeepSeek) |
| Llama-3.3-70B-Instruct | n/a | n/a | 68.9% | n/a | Meta (baseline) |

\* GPT-5.5는 공개 SWE-bench *Verified* 점수가 없다(OpenAI는 SWE-bench Pro Public
58.6%를 보고한다); 떠도는 "88.7% SWE-bench" 수치는 어떤 1차 출처에도 없다. 참고:
**Qwen 3.6에는 235B-A22B가 없다** — 오픈 제품군은 27B-dense와 35B-A3B다(아래);
235B-A22B는 이전 Qwen3 세대다.

### 동급 오픈 가중치 기준선

| Model | MMLU-Pro | SWE-bench Verified | Notes |
|-------|---------:|-------------------:|-------|
| Llama-3.3-70B-Instruct | ~75-80 | ~40-50 | Older but well-characterized baseline |
| Mistral Codestral 25.05 / Devstral | high (coding-specialized) | medium-high | Strong editor-style completion fidelity, weaker on reasoning |
| GLM-4.6-Coder (Zhipu) | vendor claims very high | disputed | Significant skepticism around evaluation methodology (consensus) |

### 이 의사결정에서 폐기한 품질 벤치마크

- **HumanEval / HumanEval+** — 2026년 포화, 모든 frontier 모델이 90% 이상, 남은 신호 없음.
- **GSM8K** — 포화, 코딩 에이전트에 신호 없음.
- **MMLU (original)** — MMLU-Pro로 대체됨.
- **저자 보고 "Hessling agentic" 16-prompt** — 재현 불가능, smoke test로만 취급.

### 미해결 품질 질문 (연구 공백)

1. **Quality-per-GB-RAM 벤치마크**: 표준이 존재하지 않는다. 제안 프록시 공식:
   `AgentScorePerGB = (0.5·SWE + 0.3·BFCL + 0.2·TerminalBench) / RAM_resident`.
2. **Long-horizon 안정성 (60+ tool call)**: 가장 근접한 기존 벤치마크는 τ-bench,
   PencilPuzzleBench (>1000 turns), MultiAgentBench, TRAIL이다. 그중 어느 것도
   "60-80개 순차 tool call에 걸친 스키마 정확성과 전략적 일관성"을 구체적으로 측정하지
   않는다 — 그 벤치마크 공백은 세 자문가 모두가 인정한다.
3. **Conversion-aware 평가 (MLX-4bit vs GGUF Q4_K_M vs Q5_K_XL)**: 표준화된 리더보드가
   없다. 커뮤니티 보고는 갈린다 — 일부는 MLX-4bit가 GGUF Q5_K_M보다 tool-calling
   안정성을 더 나쁘게 보존한다고 주장하고, 다른 일부는 반대라고 말한다.
   **실용 조언**: 커밋하기 전에 각 quant에 대해 자신의 프로덕션 워크로드를 직접 실행하라.
4. **Qwopus 3.6 제품군 품질 검증**: 제3자 BFCL + SWE-bench 재실행이 필요하다. 저자
   주장이 프로덕션 의사결정을 주도해서는 안 된다.

---

## asiai 직접 측정 — Apple Silicon, 2026년 중반

> 위 공개 리더보드가 보여주지 않는 것: asiai가 Apple Silicon(High Power Mode의 M5 Max
> 128 GB, M4 Pro 64 GB)에서 직접 실행한 측정, llama.cpp b9430, 결정론적(temp 0),
> 공개 Qwen 3.6 제품군과 Opus-distilled **Qwopus** 파인튜닝에 대해. 주의: M5 노트북의
> cross-session 절대 throughput은 ±15%다(thermal/load); **intra-session ±MTP 연속
> 델타**만 타이트하며, M5↔M4 절대값은 비교 불가다(quant이 다름).

### Dev-quality / tool-call (`asiai bench --code`)

- **base Qwen 3.6-35B-A3B (MoE)**는 deep-context 턴에서 `edit_file.edits`를 빈 객체로
  붕괴시킨다 — **Q4_K_S와 Q5_K_XL 양쪽에서 3/3 실행**, 동일 chat 템플릿. Tool-call 청결
  **87.5%**, edit-turn 청결 **66.7%**. 이는 quant도 템플릿도 아닌 MoE base의 tool-call
  생성 동작이다.
- **dense 27B** (Q5_K_XL)와 **Qwopus-35B-A3B** (Q4_K_S)는 둘 다 **100% 청결 / 0 bug**를
  기록한다 — Qwopus는 MoE의 약 4× decode 속도로 dense-27B tool-call 신뢰성에 도달한다.
- 더 어려운 tool-call 스트레스 suite에서, Qwopus는 **100% / 0**을 유지하는 반면 dense
  27B는 **88.9% / 3 bug**로 떨어진다(동일한 empty-object 실패). 그러나 식 평가기 함정
  (`**` vs 단항 마이너스의 우선순위)에서는 **dense 27B가 정답이고 Qwopus가 오답이다** —
  둘이 갈린다. (Recovery rate는 가중치에 민감하고 노이즈가 많다 — 헤드라인이 아니다.)

### Thinking ablation (`asiai bench --thinking-ablation`, Qwopus-35B-A3B, 결정론적 3회 실행)

| Config | Tool-call clean | Note |
|--------|----------------:|------|
| `enable_thinking=off` | **100%** | the only fully-clean config |
| `enable_thinking=on` + `preserve_thinking=on` | 77.8% | 2/9 turns dirty |
| `enable_thinking=on` + `preserve_thinking=off` | 11.1% | turns 2-8 → HTTP 500 (context corruption); avoid |

### MTP throughput (`--spec-type draft-mtp`, warm decode, intra-session ±MTP)

| Model / hardware | MTP off | MTP on | Δ |
|------------------|--------:|-------:|--:|
| 35B-A3B base · M5 Max | 85.5 t/s | **118.4 t/s** | **+38%** |
| Qwopus 35B-A3B · M5 Max | 105.7 t/s | 123.3 t/s | +17% |
| 27B-dense · M5 Max | 23.8 t/s | 28.0 t/s | +18% |
| Qwopus 27B · M5 Max | 25.9 t/s | 26.7 t/s | +3% |
| 35B-A3B MoE · M4 Pro | 36.3 t/s | 44.6 t/s | +23% |
| 27B-dense · M4 Pro | 10.4 t/s | 9.7 t/s | **−6%** |

MTP 이득은 **(MoE > dense) × (M5 > M4)**로 스케일한다 — MoE에서 강하게 양(+),
느린 dense 경로에서는 미미~음(−)이다(draft 오버헤드가 상각되지 않는다). Qwopus 파인튜닝의 MTP head 역시 base보다 약하다(Qwopus 27B +3% / 35B +17%, base 27B-dense +18% / 35B-A3B +38% 대비) — 파인튜닝이 draft head를 침식한다. MLX 측 MTP
(mlx_vlm)는 탈락한다: long context를 깨뜨린다(빈 출력, 75% 유효). 헤드라인: llama.cpp의
35B-A3B MoE + MTP는 M5 Max에서 **약 118 t/s** decode를 지속한다(M4 Pro에서 약 44 t/s),
27B-dense의 약 4×, 약 1.5 tok/s/W, TTFT 약 62 ms, 100% 출력 유효성.

### Instruction-following (`asiai bench --instruct`, research-brief)

thinking trade-off는 다단계 산출물에서 위력을 발휘한다: `enable_thinking=false`에서
Qwopus-35B는 tool 작업은 하지만 요청된 여러 섹션 brief를 **0%** 전달한다(2차 단계에서
멈춘다); thinking on에서는 base 모델이 이를 **100%** 전달한다(5/5 섹션). 이는 위의
tool-call 결과와 반대 방향으로 당긴다 — thinking-off는 원자적 tool call에 가장 깨끗하지만
서면 산출물을 억제한다 — 그래서 asiai는 thinking을 단일 전역 스위치가 아니라 **작업
차원별**로 설정한다.

### 완벽주의적 연구 루프 (`asiai bench --instruct loop-search`)

단일 턴 IFEval과 research-brief는 이 모델들 전반에서 100%로 포화되므로, 둘 다
*완벽주의적 연구 루프*를 드러내지 못한다: 모호하고 확인 불가능한 검색 결과를 받아들이지
않고, 무진전 가드레일이 멈출 때까지 의미적으로 동등한 쿼리를 재발행하며 결코 산출물을
내놓지 않는 모델이다. `loop-search` 스윕(9개 구성, M5, b9430, thinking on/off, 두 가지
모호성 모드)이 이를 분리해낸다:

- **35B-A3B MoE는 한도까지 루프에 빠진다** — **base와 Qwopus 파인튜닝 모두, Q4와 Q8
  똑같이** 그렇다. 더 높은 quant도 이를 고치지 못하므로, 루프는 양자화 인공물이 아니라
  **A3B MoE의 아키텍처적** 특성이다.
- **dense 27B는 결코 루프에 빠지지 않는다**(Q4 / Q5 / Q8): 모호한 결과를 받아들이고
  브리핑을 작성한다.

따라서 throughput 선두(MoE, 약 118-123 t/s)와 에이전트-적합성 선두(dense 27B, 약 25 t/s)는
*서로 다른 모델*이다. NousResearch의 Hermes Agent 같은 하네스에서는 루프 저항성이 원시
decode를 능가할 수 있다 — 가장 빠른 모델이 항상 올바른 에이전트는 아니다. (이는 MoE
파인튜닝이 더 견고한 에이전트였던 tool-call 결과의 정반대다: **적합성은 실패 모드별이므로,
여러 가지를 측정하라.**)

---

## 6절 — Operational

> 📌 역량 스냅샷 (2026년 중반). 엔진 버전은 Apple Silicon에서 매주 바뀐다 — 이 셀들은
> 버전 고정 보증이 아니라 특정 시점의 것이다.

| # | Engine | License | Stream OAI-compat | `/v1/models` | `/health` | `/metrics` (Prometheus) | Tool calling | Auto-DL HF | Persisted prefix cache | Maintainer activity |
|---|--------|---------|---|---|---|---|---|---|---|---|
| 1 | Rapid-MLX 0.6.66 | Apache-2.0 | ✅ | ✅ | ✅ (HTML page) | ❌ (logs only) | ✅ | ✅ HF Hub auto-DL on serve | ✅ `~/.cache/vllm-mlx/prefix_cache/` | community (raullenchai) |
| 2 | LM Studio 0.4.14 | proprietary | ✅ | ✅ | partial (websocket) | ❌ | ✅ | ✅ via `lms get` CLI | ❌ | Element Labs |
| 3 | llama.cpp b9270 | MIT | ✅ | ✅ | ✅ | ✅ `--metrics` | ✅ | manual (GGUF on disk) | ❌ (`--cache-reuse N` arch-disabled on hybrid) | ggerganov very active |
| 4 | mlx-lm | MIT | ✅ | ✅ | ✅ | ❌ | partial | ✅ HF auto | ❌ | Apple ml-explore active |
| 5 | oMLX | MIT | ✅ | ✅ | ✅ | ❌ | ✅ (caveat: post-cache-hit bug) | ✅ | partial (tiered SSD) | jundot active |
| 6 | vLLM-MLX | Apache-2.0 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ paged-attention | vllm-project active |
| 7 | vMLX (Mamba/SSM) | Apache-2.0 | ✅ | ✅ | ✅ | partial | untested | partial | untested | community |
| 8 | Ollama | MIT | ✅ | partial | ✅ `/api/version` | ❌ | partial | ✅ `ollama pull` | ❌ | Ollama Inc. very active |

---

## 7절 — 에이전트-코딩 워크로드를 위한 품질 벤치마크 가중치

> 이는 오케스트레이터 클래스 워크로드(턴당 60-80개 순차 tool call, 스키마 검증된 출력,
> long-context 시스템 prompt)에 대한 **asiai 기본 가중치**다. 2026년 5월에 질의한 세
> frontier-LLM 자문(Grok-4, GPT-5, Gemini Advanced)에 기반하지만 **커뮤니티 합의가
> 아니다** — 권위가 아니라 출발점으로 취급하라. 향후 `--weights` 플래그(예정)로 재정의.

| Benchmark | What it measures | Why it matters here | Consensus weight |
|-----------|------------------|---------------------|-----------------:|
| **SWE-bench Verified** | Real GitHub repo navigation + patch + test repair | Best proxy for code-editing fidelity inside an agent loop | **35 %** |
| **BFCL v3** (Berkeley Function Calling Leaderboard) | Multi-turn function-call accuracy, argument fidelity, schema adherence | Direct predictor of orchestrator stability across many tool calls | **25 %** |
| **TerminalBench 2.0 / MCP-Atlas** | CLI and MCP task execution autonomy | "Does the agent survive 40+ actions without derailing" | **20 %** |
| **LiveBench Coding** | Contamination-resistant coding tasks (refreshed monthly) | Catches train-test leakage that inflates HumanEval-class scores | **10 %** |
| **Custom long-horizon stability eval** | 60-80 sequential tool calls with cumulative context growth, malformed JSON recovery | The benchmark that does not exist yet in public form — see Section 8 | **10 %** |

### 가중치에서 의식적으로 제외한 벤치마크

- MMLU-Pro, GPQA Diamond, HumanEval+ — 일반 역량 신호로는 유용하지만, 2026년 증거에
  따르면 에이전트-루프 신뢰성과 **약하게 상관**한다. Frontier-lab 확인은 single-shot
  reasoning 점수가 충분한 세분성으로 자율 에이전트 성공을 더 이상 예측하지 못함을
  시사한다.
- 제3자 재실행 없는 저자 보고 집계(Jackrong Hessling, Unsloth 자체 평가, GLM-4.6-Coder
  벤더 주장).

---

## 8절 — 커스텀 "endurance" 벤치마크 제안 (연구 기회)

세 자문가 모두 같은 공백에 수렴한다: **오케스트레이터 워크로드를 가장 잘 특징짓는
벤치마크가 아직 공개적으로 존재하지 않는다**. 그것을 만드는 것이 누락된 신호를 얻는
유일한 방법이다.

### 제안 범위

- 궤적당 **80개 순차 tool call**
- **매 턴 스키마 검증** (엄격한 JSON / 구조화 출력)
- **누적 컨텍스트 증가** (궤적에 걸쳐 10K → 50K 토큰)
- **중단 / 복구 테스트** (궤적 중간 cancel + resume)
- **malformed XML/JSON 복구** (에이전트가 스스로 교정하는가?)
- **Repo-edit 영속성** (턴 N에서 한 편집이 턴 60에서도 유지되는가?)

이는 asiai 로드맵에 있다(burst-mode 이후의 long-horizon endurance 모드). 구축된다면
이 특정 niche에서 최초의 공개 벤치마크가 될 것이다.

---

## 방법론

- **하드웨어**: MacBook Pro M5 Max 128 GB 통합 메모리, macOS 26.4.1.
- **워크로드**: 오케스트레이터 클래스 — 시스템 prompt 약 7 KB, user prompt 약 150-200
  토큰, 턴당 60-80 호출.
- **측정 단계** (single-call, agentic-mode v1.6.0):
  - `cold`: 신규 시작 후 첫 호출
  - `warm`: cold와 정확히 동일한 prompt (웜 캐시)
  - `prefix-test-1/2/3`: 동일 시스템, user 변경 — cross-USER 캐시 재사용 측정
  - `cold-prefix`: 동일 시스템, 재시작 후 — 영속 캐시 측정
- **prefix cache 재사용 판정**: `median(prefix-test) / cold < 0.2`이면 `YES`,
  아니면 `NO`.
- **반(反)편향 조치**: SOLO 모드(공존 엔진 없음), thermal idle 기준선, mmap 워밍업 단계.
- **품질 게이트** (asiai bench가 자동 추적):
  - `early_stop`: median completion `<0.5×`인 실행이 2회 이상
  - `memory_pressure`: swap delta `>500 MB` OR swapouts delta `>1000`
  - `duplicate_processes`: 벤치 중 다수의 엔진 프로세스 감지됨

전체 프로토콜은 `asiai bench --agentic-mode` / `--burst-mode` 계측(power/thermal,
엔진 footprint, KV occupancy, prefix-cache 단계)이다 — asiai CLI 문서 참조.

---

## 미해결 질문

1. **vLLM-MLX/Rapid-MLX의 MTP — 부분적으로 답함.** vLLM-MLX는 prerelease
   **0.4.0rc1** (2026-05-21)에서 MTP를 추가했다; 이론적 조합 "MLX + MTP 장착 Qwopus
   35B-A3B + cross-USER 스냅샷"은 Rapid-MLX fork가 0.4.x를 추적하면 decode와 TTFT 양쪽에서
   이길 수 있다. Rapid-MLX가 MTP 경로를 채택하는 시점을 추적하라.
2. **MLX 런타임의 MTP — 현재 상태.** 릴리스된 mlx-lm은 MTP head를 네이티브 speculative
   decoding으로 실행하지 않는다(`sanitize()`가 변환 중 MTP 가중치를 누락한다; 네이티브
   지원은 머지되지 않은 PR
   [ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990)에 있다).
   LM Studio의 `mlx-engine`은 mlx-lm을 래핑하므로 이를 상속한다 — 1절 5행의 +13.5%
   decode 이득은 mlx-engine speculative decoding이 아니라 LM Studio의 **llama.cpp 파생
   backend**에서 비롯된다(파일이 GGUF다).
3. **Rapid-MLX/vllm-mlx의 60-80 호출 규모 burst 동작**: smoke test는 burst=5에서
   단일 슬롯 FIFO를 확인한다. 전체 패널 보류 중(2절). 관련 upstream 쟁점은 vllm-mlx가
   hybrid arch 모델에 대해 continuous-batching / 멀티 슬롯 스케줄링을 계획하는지 여부다.
4. **Qwen 3.6 hybrid의 `llama_memory_can_shift=false`** — upstream에서 여전히 깨져
   있다. [#18497](https://github.com/ggml-org/llama.cpp/issues/18497)은 closed(전체
   재처리를 문서화); [#22384](https://github.com/ggml-org/llama.cpp/issues/22384)는
   머지된 수정이 **아니라** *issue*(closed-as-completed)다; 실제 수정 PR
   [#23121](https://github.com/ggml-org/llama.cpp/pull/23121)은 **머지되지 않고
   closed**되었다(패치는 fork에만 존재). "그냥 `preserve_thinking`을 켜라"는 우회책은
   open issue [#22615](https://github.com/ggml-org/llama.cpp/issues/22615)로 반박된다
   (0.67× 속도 향상 = 캐시가 비활성 상태로 유지됨). hybrid DeltaNet 레이어는 구조상
   shift 가능한 캐시 상태를 노출하지 않는다.
5. **Qwopus 3.6 품질 독립 재현**: 제3자 BFCL / SWE-bench 재실행이 필요하다. 저자
   발행 수치는 교차 검증되기 전까지 프로덕션 의사결정을 주도해서는 안 된다.
6. **vllm-mlx vs Rapid-MLX 계보 — 답함.** Rapid-MLX는 얇은 래퍼가 아니라
   `waybarrios/vllm-mlx`의 커뮤니티 **하드 fork**다: 엔진을 in-tree로 vendoring하고
   (패키지 이름은 여전히 `vllm_mlx`), upstream 패키지에 pip-depend하지 않으며, 상당히
   갈라졌다(Rapid-MLX 0.6.74 vs upstream 0.3.0). 공유된 `vllm_mlx` 패키지 이름과
   `~/.cache/vllm-mlx/` 디렉터리는 빈번한 출처 혼동의 원인이다(3절, 주의사항 2 참조).

---

*이 패널은 살아있는 문서다. 기여, 수정, 추가 벤치 셀은
[github.com/druide67/asiai](https://github.com/druide67/asiai/issues) 로 환영한다.*
