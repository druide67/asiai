---
description: Apple Silicon에서의 에이전트 모드 벤치마크 결과 — Qwen3.6 및 Qwopus3.6 (27B 밀집형 vs 35B-A3B MoE), MTP speculative decoding 적용/미적용, llama.cpp 및 MLX 엔진 제품군 전반. Decode, TTFT, 전력, RAM, 유효성. 지속적으로 갱신되는 결과 페이지.
---

# 에이전트 벤치마크 결과

이 페이지는 Apple Silicon에서의 실제 `asiai bench --agentic-mode` 결과를 보고한다.
에이전트 프로토콜은 8단계의 prefix-cache 인식 대화(분산 측정을 위한 `--runs 5`)를
실행하며, 이는 에이전트가 모델을 실제로 사용하는 방식 — 멀티턴, 긴 시스템 prefix,
50K 토큰 long-context 단계 — 을 한 번의 one-shot 생성이 아니라 그대로 구동한다.

**왜 에이전트 모드인가 — 누구를 위한 것인가?** 에이전트 프레임워크는 모델을 챗봇처럼
구동하지 않는다. 큰 시스템 prefix를 여러 턴에 걸쳐 재사용하고, tool call을 발생시키며,
긴 컨텍스트를 유지한다. one-shot throughput 수치는 이 모든 것을 놓친다 — 그리고
순위가 뒤집힐 수도 있다(원시 decode는 뛰어나지만 TTFT가 수 초에 달하거나 prefix
cache가 깨진 엔진은 에이전트에는 사용 불가능하다). 에이전트 모드는 모델이 **에이전트
오케스트레이터와 코딩 어시스턴트** — 예컨대
[Hermes Agent](https://github.com/nousresearch/hermes-agent),
[OpenClaw](https://github.com/openclaw/openclaw),
[opencode](https://github.com/sst/opencode), Aider, Cline, Continue — 에 의해
실제로 구동되는 방식 그대로 측정한다. 따라서 결과는 벤치마크 인공물이 아니라 실제
에이전트 워크로드를 반영한다.

> **지속 갱신 문서.** 이 수치들은 엔진 버전, 모델 리비전, 계측(예: peak-RAM 캡처)이
> 개선됨에 따라 갱신된다. 각 행은 정확한 엔진 버전과 모델 파일을 기재하므로 결과는
> 항상 재현 가능하다.

**2026-06-03 캠페인.** 모델: Qwen3.6 및 Qwopus3.6 파인튜닝, 두 가지 아키텍처 —
**27B 밀집형** 과 **35B-A3B MoE** (Mixture-of-Experts, 토큰당 약 3B 활성 파라미터).
엔진: llama.cpp (b9430) 및 MLX 제품군 (mlx-lm, mlx_vlm, omlx, rapid-mlx, vllm-mlx).
MTP = speculative decoding에 사용되는 모델 내장 Multi-Token Prediction head
(`--spec-type draft-mtp`). 하드웨어: **MacBook Pro M5 Max (128 GB)** 및
**Mac mini M4 Pro (64 GB)**, 둘 다 High Power Mode.

## 표 읽는 법

판정 우선. 행은 단순 정렬이 아니라 결정론적 게이트 결과로 그룹화된다:

- **★** 블록 내 최고 검증 throughput · **✓** 사용 가능 · **⚠** 예비
  (하드 게이트는 통과하나 지연이 평범) · **✗** 탈락(게이트 실패).
- 게이트: `valid ≥ 80%` · `TTFT ≤ 1500 ms` (하드 실패 > 3000) · `prefix-cache reuse > 0`.
- **dec** = 지속 웜 decode (tok/s) · **50K** = 50K 컨텍스트에서의 decode ·
  **TTFT** = time-to-first-token (ms) · **t/s/W** = SoC 와트당 초당 토큰 수
  (효율, 높을수록 좋음) · **RAMpk** = 엔진 RSS 최대치 (GB, 메모리 적합성을 좌우하는
  수치) · `—` = 미측정 (0이 아님).
- ★ 는 *throughput만* 으로 순위를 매긴다. 실제 업무용 모델 선택은 throughput이
  포착하지 못하는 출력 품질(dev/code 평가 참조)도 함께 고려한다.

> M4 Pro와 M5 Max는 여기서 절대값으로 비교 **불가** 하다 — quant가 다르다
> (Q5_K_XL vs Q4_K_S). 머신 블록 내에서 비교하라.

## MacBook Pro M5 Max 128 GB · Q4

<div class="wide-table" markdown>

| | model · engine · MTP | dec t/s | peak | 50K | TTFT ms | reuse | t/s/W | RAMpk GB | valid% |
|:--|---|--:|--:|--:|--:|--:|--:|--:|--:|
| **★ Tier 1 — 우승 + 빠름** |||||||||| |
| ★ | Qwopus-35B · llamacpp b9430 ▲MTP | 123.3 | 127.5 | 83.8 | 67 | 0.8 | 1.590 | — | 100 |
| ✓ | Qwen-35B · llamacpp b9430 ▲MTP | 118.3 | 123.5 | 82.9 | 62 | 0.8 | 1.513 | — | 100 |
| ✓ | Qwopus-35B · llamacpp b9430 | 105.7 | 108.3 | 76.1 | 63 | 0.8 | 1.507 | — | 100 |
| ✓ | Qwen-35B · llamacpp b9430 | 85.5 | 90.8 | 66.7 | 59 | 0.8 | 1.403 | — | 100 |
| **✓ Tier 2 — 사용 가능 (느림)** |||||||||| |
| ✓ | Qwen-27B · llamacpp b9430 ▲MTP | 28.0 | 29.5 | 22.9 | 118 | 0.8 | 0.378 | 32.2 | 100 |
| ✓ | Qwopus-27B · llamacpp b9430 ▲MTP | 26.7 | 29.8 | 22.0 | 118 | 0.8 | 0.367 | 31.5 | 100 |
| ✓ | Qwopus-27B · llamacpp b9430 | 25.9 | 27.1 | 20.8 | 110 | 0.8 | 0.342 | 28.4 | 100 |
| ✓ | Qwen-27B · llamacpp b9430 | 23.8 | 24.0 | 19.2 | 111 | 0.8 | 0.340 | 28.9 | 100 |
| **⚠ Tier 3 — 예비 (지연 불량)** |||||||||| |
| ⚠ | Qwopus-27B · mlx-lm 0.31.3 | 29.2 | 29.3 | 24.3 | 600 | 1.0 | 0.461 | 26.4 | 100 |
| ⚠ | Qwen-27B · rapid-mlx 0.6.71 | 20.6 | 20.7 | 17.9 | 798 | — | 0.357 | — | 85 |
| ⚠ | Qwen-27B · omlx 0.4.0 | 20.0 | 20.2 | 17.5 | 2150 | 0.82 | 0.346 | 26.7 | 100 |
| **✗ Tier 4 — 탈락** |||||||||| |
| ✗ | ~~Qwen-27B · mlx_vlm 0.6.0 ▲MTP~~ | ~~41.0~~ | — | — | ~~10879~~ | 0.0 | — | — | 75 |
| ✗ | ~~Qwen-27B · mlx_vlm 0.6.0~~ | ~~31.9~~ | — | 26.0 | ~~9578~~ | 0.0 | — | — | 100 |
| ✗ | ~~Qwen-27B · vllm-mlx 0.3.0~~ | ~~20.5~~ | — | 18.1 | ~~9578~~ | — | — | 24.3 | 100 |

</div>

탈락: mlx_vlm+MTP는 유효성(75%)에 실패하고 long-context를 깨뜨린다. mlx_vlm 두 실행과
vllm-mlx는 TTFT가 약 9.6 s(에이전트 턴당 사용 불가)다.

## Mac mini M4 Pro 64 GB · Q5

<div class="wide-table" markdown>

| | model · engine · MTP | dec t/s | peak | 50K | TTFT ms | reuse | t/s/W | RAMpk GB | valid% |
|:--|---|--:|--:|--:|--:|--:|--:|--:|--:|
| **★ Tier 1** |||||||||| |
| ★ | Qwen-35B · llamacpp b9430 ▲MTP | 44.6 | 50.7 | 32.6 | 143 | 0.8 | 1.557 | 33.0 | 100 |
| ✓ | Qwen-35B · llamacpp b9430 | 36.3 | 45.6 | 29.6 | 133 | 0.8 | 1.553 | 30.8 | 100 |
| **✓ Tier 2** |||||||||| |
| ✓ | Qwen-27B · llamacpp b9430 | 10.4 | 10.4 | 7.2 | 397 | 0.8 | 0.279 | 31.9 | 100 |
| ✓ | Qwen-27B · llamacpp b9430 ▲MTP | 9.7 | 9.8 | 7.5 | 409 | 0.8 | 0.272 | 35.4 | 100 |

</div>

## 주요 발견

- **35B-A3B MoE는 두 머신 모두에서 모든 throughput 축에 걸쳐 27B 밀집형을 능가한다** —
  토큰당 약 3B 파라미터만 활성화하므로 밀집형 27B보다 약 4× 빠르게 decode하고
  약 3.5× 더 에너지 효율적이다 (1.5 vs 약 0.4 tok/s/W). 다만 throughput은 품질이
  아니다 — 아래 주의사항 참조.
- **throughput은 에이전트 적합성이 아니다.** 모호한 검색 작업 — `loop-search`
  시나리오(`asiai bench --instruct`, [dev/code 평가](dev-quality-benchmarks.md) 참조) —
  에서 35B-A3B **MoE는 완벽주의적으로 루프에 빠진다**: 해결 불가능한 사실에 대해
  의미적으로 동등한 쿼리를 무진전 가드레일이 멈출 때까지 재발행하며, 산출물을 결코
  내놓지 않는다. 이는 **Q4와 Q8 모두에서** 나타나며(양자화 인공물이 아니라 아키텍처적),
  반면 **dense 27B는 결코 루프에 빠지지 않는다**. NousResearch의 Hermes Agent 같은
  에이전트 하네스에서는 이 루프 저항성이 MoE의 원시 decode 우위를 능가할 수 있다 —
  즉 가장 빠른 모델이 항상 올바른 에이전트는 아니다.
- **MTP 이득은 아키텍처 × 하드웨어에 따라 달라진다.** 측정된 decode 향상:
  MoE +38% (M5) / +23% (M4); 밀집형 +16% (M5) 이지만 **−7% (M4)** — 더 느린 M4
  GPU에서는 밀집형 draft 오버헤드가 상각되지 않는다. 따라서 MTP는 보편적 승리가 아니라
  모델별·머신별 측정 사안이다.
- **여기서 MLX 서버 제품군은 throughput 전용이다**: mlx-lm은 최고의 MLX decode를
  내지만 600 ms TTFT 바닥을 갖는다. mlx_vlm, vllm-mlx, omlx는 TTFT(2–11 s) 및/또는
  깨진 prefix-cache로 탈락한다. llama.cpp는 first-token 지연(약 60–120 ms)을 압도한다.
- **Peak vs 안정 RAM.** mlx-lm의 RSS는 안정 상태에서 약 14.5 GB이지만 **26.4 GB에서
  peak에 도달한다** (지연 KV 할당 + 컴팩트한 MLX-4bit 가중치). llama.cpp는 전체 컨텍스트
  KV를 사전에 미리 할당한다 (약 29 GB로 평탄). peak에서는 둘이 비슷하다 — 메모리 적합성
  판단에는 안정값이 아니라 **RAMpk** 를 사용하라.

## 방법론 및 주의사항

- `asiai bench --agentic-mode --runs 5`, thinking 비활성화
  (`chat_template_kwargs.enable_thinking=false`), 서버 컨텍스트 ≥ 65536.
- 한 번에 하나의 엔진만 상주(SOLO); 파일을 공유하는 GGUF 실행 사이에는 페이지 캐시를
  purge한다.
- **quant이 머신별로 다름** (M5 Q4_K_S/Q4_K_XL, M4 Q5_K_XL) → 절대 수치는 머신 간
  비교 불가, 블록 내에서만 비교 가능.
- M5 노트북에서는 **High Power Mode** 가 필요하다(그렇지 않으면 지속 GPU가 약 40%
  throttle된다); M4 mini 데스크톱은 이에 대체로 중립적이다.
- **알려진 계측 공백** (수정 진행 중): 수동으로 기동한 일부 llama.cpp 서버에서는 peak
  RAM이 누락된다(`—`); 엔진 버전이 아직 실행별로 스탬프되지 않는다(여기서는 버전 맵에서
  표시); prefix-cache `reuse`는 실제 hit-rate가 나오기 전까지 거친 분수값이다.

같이 보기: [벤치마크 방법론](methodology.md) · [메트릭 명세](metrics-spec.md)
· [커뮤니티 리더보드](leaderboard.md).
