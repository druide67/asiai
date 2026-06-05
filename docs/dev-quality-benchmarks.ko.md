---
description: Apple Silicon에서의 개발 품질 및 다국어 유지 벤치마크 결과 — tool-call 신뢰성(JSON 인자 절단 / 빈 객체 버그), 에이전트 오류 복구, thinking 규율, 언어 유지. 결정론적이며 핵심 신호에는 LLM 심판이 필요 없다. 지속적으로 갱신되는 결과 페이지.
---

# 개발 품질 및 언어 벤치마크

throughput은 품질이 아니다. 모델은 빠르게 decode하면서도 에이전트 코딩에는
사용 불가능할 수 있다 — tool-call 인자를 절단하거나, 오류에서 루프에 빠지거나,
파인튜닝이 다른 언어를 조용히 망가뜨렸을 수 있다. 이 페이지는 실제
`asiai bench --code` 및 `asiai bench --language` 결과를 보고한다: 모델이 실제로
동작하는지를 측정하는 **결정론적** 신호(핵심에는 LLM 심판이 필요 없다)이며,
토큰을 얼마나 빨리 내뱉는지가 아니다.

> **지속 갱신 문서.** 수치는 모델 리비전, 엔진, 템플릿이 바뀜에 따라 갱신된다.
> 각 블록은 정확한 모델 파일과 서빙 구성을 기재하므로 결과는 재현 가능하다.

## 무엇을 측정하는가

`asiai bench --code` (결정론적, 심판 불필요):

- **tool-call** — 컨텍스트가 누적되는 8턴 에이전트 파일 편집 세션. tool-call
  발생, JSON 유효성, 비절단, 올바른 tool, 스키마 적합성, 그리고 **빈 객체 버그**:
  `edit_file.edits` 배열을 `{}` / `[]` 로 붕괴시키는 `|items` 템플릿 절단을
  채점한다.
- **tool-call-stress** — 동일하되 더 어렵다: 더 깊은 컨텍스트, 8–10개 요소의
  편집 배열, JSON 이스케이프 압박(개행, 따옴표, 백슬래시, 유니코드). 베이스라인을
  완벽히 통과하는 모델들을 가려내는 데 쓰인다.
- **recovery** — 세션 도중 합성 tool 오류를 주입; 교정 동작 대 막힌 루프(실패한
  호출을 재발생)를 채점한다.
- **thinking** — thinking-mode 규율: content로의 `<think>` 누출 없음, 짧은 budget
  에서 비어 있지 않은 출력, `enable_thinking=false` 준수.
- **coding** / **coding-hard** *(선택적 심판)* — `--judge-url`(OpenAI 호환
  엔드포인트 무엇이든)의 LLM 심판이 1–5로 채점하는 멀티턴 코딩 작업.

`asiai bench --instruct` (결정론적 지시 따르기):

- **verifiable** — 프로그램적으로 검증 가능한 지시(단어/문장/섹션 수, 키워드,
  JSON 전용, 대소문자, 쉼표 금지, 끝맺음 문구, `<<>>` 안의 제목, 언어…)를 갖춘
  IFEval 스타일 단일 턴 프롬프트. prompt 수준과 instruction 수준에서 strict/loose
  정확도로 보고된다 — 공개 리더보드 형식. IFEval 패러다임(Zhou et al. 2023)의
  asiai-native 재구현이며, IFEval 코드나 데이터는 포함하지 않는다.
- **research-brief** — 에이전트 작업: tool로 여러 주제를 조사한 뒤, 여러 섹션의
  브리핑을 작성하고, 그다음 2차 tool 동작(저장)을 **마지막** 에 수행한다. 모델은
  주요 브리핑을 산출하는가, 아니면 tool 작업만 하고 2차 단계 확인만 반환하는가?
  모델은 tool-call 신뢰성을 완벽히 통과하고도 핵심 산출물을 건너뛸 수 있다 —
  tool 턴 이후 필수 섹션이 나타나는지 확인하여 결정론적으로 채점한다.
  **order-control** 은 진단을 위해 순서를 뒤바꾼다(2차를 먼저).

`asiai bench --language <code>` (결정론적, 8개 언어):

- **adherence** — 모델이 대상 언어를 유지하는가? (라틴 문자에는 대상 대 영어
  기능어 비율; ja/ko/zh에는 대상 문자 비율).
- **diacritics** — 정답에 특정 악센트 토큰(`café`, `préféré`)이 반드시 포함되어야
  하는 함정 프롬프트; ASCII로 벗겨진 답은 실패한다.

세 모드 모두 JSON 전용이며 출력을 diff하여 모델 간 비교한다.

## 실제 예시 — Qwen3.6-35B-A3B vs Qwopus3.6-35B-A3B vs Qwen3.6-27B 밀집형

파인튜닝(`Qwopus3.6`, `Qwen3.6-35B-A3B` MoE의 Opus-distilled 파인튜닝) 대 그 베이스,
대 절반 크기의 밀집형 모델. 동일한 llama.cpp, **동일한 chat 템플릿 고정**(모델
파일만 교체), thinking 비활성화, 3회 반복. Apple Silicon M5 Max, High Power Mode.

### tool-call 신뢰성

| model · quant | tool-call clean | empty-object bug | under stress |
|---|--:|--:|--:|
| Qwen3.6-35B-A3B base · Q4 / Q5 | 87.5% | **3** | 87.5% · **3 bugs** |
| **Qwopus3.6-35B-A3B · Q4** | **100%** | **0** | **100% · 0** |
| Qwen3.6-27B dense · Q5 | 100% | 0 | 88.9% · **3 bugs** |

- **베이스 35B MoE에는 템플릿 수정으로 완전히 막지 못하는 잔존 tool-call 결함이
  있다.** 깊은 컨텍스트 턴에서 `edit_file.edits` 를 빈 객체 버그로 3/3 붕괴시킨다 —
  **Q4와 Q5** quant 모두에서(즉 양자화가 아니라 생성 동작이다). 단순 호출에서
  `|items` 버그를 고치는 커뮤니티 `froggeric` 템플릿도 컨텍스트 깊숙한 곳의 베이스
  MoE는 구하지 못한다.
- **Opus-distilled 파인튜닝은 이를 완전히 복구한다** — 버그 0개, 100% clean —
  그것도 *더 낮은* quant(Q4 vs Q5)에서이므로 승리가 더 확실하다.
- **스트레스에서는 파인튜닝이 밀집형 27B보다 더 견고한 에이전트다**: 27B는
  무너지지만(더 어려운 스위트에서 빈 객체 버그 3개) 파인튜닝은 0에 머문다.
  베이스라인에서는 동률; 스트레스 스위트가 둘을 가른다.

### 코드 정확성 (LLM 심판 하드 작업)

더 까다로운 두 멀티턴 코딩 작업에서 둘은 **갈린다**: sliding-window rate limiter
에서는 둘 다 경계/축출 엣지 케이스를 처리한다; 표현식 평가기에서는 **밀집형 27B가
연산자 우선순위를 맞게** 처리하지만(`-2**2 == -4`, 적절한 연산자로서의 단항 마이너스)
**파인튜닝은 그렇지 못하다**(단항 마이너스를 숫자에 접어 넣음 → `4.0`). tool-call
견고성과 알고리즘 정확성은 *서로 다른* 축이다 — 둘 다 측정하라.

### 언어 유지

파인튜닝과 그 베이스에 동일 quant으로 `--language fr` 을 실행:

| model | adherence | diacritic traps | ASCII-stripped |
|---|--:|--:|--:|
| Qwen3.6-35B-A3B base | 100% | 4/4 | 0 |
| **Qwopus3.6-35B-A3B** | 100% | 4/4 | 0 |

**프랑스어 퇴행 제로.** 코딩 지향 파인튜닝이 베이스 모델의 프랑스어를 온전히
유지했다(adherence, diacritics, ASCII 벗겨짐 없음) — 작업별 파인튜닝이 다른 언어를
희생시키지 *않았다*. 이는 가정하기보다 검증할 가치가 있다.

## 이 페이지 읽는 법

- **속도 우선이 아니라 판정 우선.** 이들은 정확성/신뢰성 신호다. throughput은
  [에이전트 벤치마크](agentic-benchmarks.md)를 참조하라.
- **결정론적 핵심, 선택적 심판.** tool-call / recovery / thinking / adherence /
  diacritics는 LLM 심판이 필요 없다 — 재현 가능하다. `coding`/`fluency` 등급은 LLM
  심판이 매긴다(주관적, 선택적).
- **통제된 변경 내에서 비교하라.** 예시는 템플릿을 고정하고 모델만 변화시키므로,
  차이는 하네스가 아니라 모델의 것이다.

## 방법론 및 주의사항

- `asiai bench --code` / `--language`, thinking 비활성화
  (`chat_template_kwargs.enable_thinking=false`), 한 번에 하나의 엔진만 상주.
- **예시 전반에서 quant이 다름**(파인튜닝 Q4 vs Qwen 모델 Q5): 헤드라인인 빈 객체
  버그는 템플릿/생성에서 비롯되며 베이스에서는 **두** quant 모두에서 확인되었으므로
  quant이 격차를 설명하지 않는다 — 게다가 파인튜닝은 더 낮은 quant에서 이긴다.
- 여기서 **코드 품질 심판은 엄밀히 블라인드가 아니다**(프런티어 모델이 그 자체의
  근거로 트랜스크립트를 읽었다); 결정론적 tool-call/stress 수치는 객관적이다.
- **recovery는 가중치에 민감하며**, 깨끗한 모델 간 신호가 아니다 — 헤드라인은
  반복 전반에서 안정적인 tool-call/빈 객체 신뢰성이다.

같이 보기: [에이전트 벤치마크](agentic-benchmarks.md) ·
[벤치마크 방법론](methodology.md) · [메트릭 명세](metrics-spec.md).
