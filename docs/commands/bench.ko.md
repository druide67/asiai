---
description: Apple Silicon에서 나란히 LLM 벤치마크를 실행합니다. 엔진 비교, tok/s, TTFT, 전력 효율 측정. 결과 공유.
---

# asiai bench

표준화 프롬프트를 사용한 교차 엔진 벤치마크.

## 사용법

```bash
asiai bench [options]
```

## 옵션

| 옵션 | 설명 |
|------|------|
| `-m, --model MODEL` | 벤치마크할 모델 (기본: 자동 감지) |
| `-e, --engines LIST` | 엔진 필터 (예: `ollama,lmstudio,mlxlm`) |
| `-p, --prompts LIST` | 프롬프트 유형: `code`, `tool_call`, `reasoning`, `long_gen` |
| `-r, --runs N` | 프롬프트당 실행 횟수 (기본: 3, 중앙값 + 표준편차용) |
| `--power` | sudo powermetrics로 전력 교차 검증 (IOReport는 항상 활성) |
| `--context-size SIZE` | 컨텍스트 필 프롬프트: `4k`, `16k`, `32k`, `64k` |
| `--export FILE` | 결과를 JSON 파일로 내보내기 |
| `-H, --history PERIOD` | 과거 벤치마크 표시 (예: `7d`, `24h`) |
| `-Q, --quick` | 빠른 벤치마크: 1 프롬프트(code), 1회 실행 (~15초) |
| `--compare MODEL [MODEL...]` | 교차 모델 비교 (2-8 모델, `-m`과 배타적) |
| `--card` | 공유 가능한 벤치마크 카드 생성 (로컬 SVG, `--share`로 PNG) |
| `--share` | 커뮤니티 벤치마크 데이터베이스에 결과 공유 |

## 예시

```bash
asiai bench -m qwen3.5 --runs 3 --power
```

```
  Mac Mini M4 Pro — Apple M4 Pro  RAM: 64.0 GB (42% used)  Pressure: normal

Benchmark: qwen3.5

  Engine       tok/s (±stddev)    Tokens   Duration     TTFT       VRAM    Thermal
  ────────── ───────────────── ───────── ────────── ──────── ────────── ──────────
  lmstudio    72.6 ± 0.0 (stable)   435    6.20s    0.28s        —    nominal
  ollama      30.4 ± 0.1 (stable)   448   15.28s    0.25s   26.0 GB   nominal

  Winner: lmstudio (2.4x faster)
  Power: lmstudio 13.2W (5.52 tok/s/W) — ollama 16.0W (1.89 tok/s/W)
```

## 프롬프트

4개의 표준화 프롬프트가 다른 생성 패턴을 테스트합니다:

| 이름 | 토큰 | 테스트 내용 |
|------|------|-----------|
| `code` | 512 | 구조화된 코드 생성 (Python BST) |
| `tool_call` | 256 | JSON 함수 호출 / 지시 따르기 |
| `reasoning` | 384 | 다단계 수학 문제 |
| `long_gen` | 1024 | 지속 처리량 (bash 스크립트) |

`--context-size`를 사용하면 대규모 컨텍스트 필 프롬프트로 테스트할 수 있습니다.

## 교차 엔진 모델 매칭

러너는 엔진 간 모델 이름을 자동 해석합니다 — `gemma2:9b`(Ollama)와 `gemma-2-9b`(LM Studio)는 같은 모델로 매칭됩니다.

## JSON 내보내기

결과를 공유 및 분석용으로 내보내기:

```bash
asiai bench -m qwen3.5 --export bench.json
```

JSON에는 머신 메타데이터, 엔진별 통계(중앙값, CI 95%, P50/P90/P99), 원시 실행별 데이터, 전방 호환성을 위한 스키마 버전이 포함됩니다.

## 리그레션 감지

각 벤치마크 후, asiai는 지난 7일간의 이력과 비교하여 성능 리그레션(엔진 업데이트나 macOS 업그레이드 후 등)을 경고합니다.

## 빠른 벤치마크

1 프롬프트, 1회 실행의 빠른 벤치마크 (~15초):

```bash
asiai bench --quick
asiai bench -Q -m qwen3.5
```

데모, GIF, 빠른 확인에 이상적입니다. 기본적으로 `code` 프롬프트가 사용됩니다. 필요하면 `--prompts`로 재정의할 수 있습니다.

## 교차 모델 비교

`--compare`로 여러 모델을 단일 세션에서 비교:

```bash
# 사용 가능한 모든 엔진으로 자동 확장
asiai bench --compare qwen3.5:4b deepseek-r1:7b

# 특정 엔진으로 필터
asiai bench --compare qwen3.5:4b deepseek-r1:7b -e ollama

# @로 각 모델을 엔진에 고정
asiai bench --compare qwen3.5:4b@lmstudio deepseek-r1:7b@ollama
```

`@` 표기는 문자열의 **마지막** `@`에서 분리하므로, `@`를 포함하는 모델 이름도 올바르게 처리됩니다.

### 규칙

- `--compare`와 `--model`은 **배타적** — 둘 중 하나만 사용.
- 2-8 모델 슬롯을 허용.
- `@` 없이, 각 모델은 사용 가능한 모든 엔진으로 확장됩니다.

### 세션 유형

슬롯 목록에 따라 세션 유형이 자동 감지됩니다:

| 유형 | 조건 | 예시 |
|------|------|------|
| **engine** | 같은 모델, 다른 엔진 | `--compare qwen3.5:4b@lmstudio qwen3.5:4b@ollama` |
| **model** | 다른 모델, 같은 엔진 | `--compare qwen3.5:4b deepseek-r1:7b -e ollama` |
| **matrix** | 모델과 엔진 혼합 | `--compare qwen3.5:4b@lmstudio deepseek-r1:7b@ollama` |

### 다른 플래그와 조합

`--compare`는 모든 출력 및 실행 플래그와 함께 사용 가능:

```bash
asiai bench --compare qwen3.5:4b deepseek-r1:7b --quick
asiai bench --compare qwen3.5:4b deepseek-r1:7b --card --share
asiai bench --compare qwen3.5:4b deepseek-r1:7b --runs 5 --power
```

## 벤치마크 카드

공유 가능한 벤치마크 카드 생성:

```bash
asiai bench --card                    # SVG를 로컬에 저장
asiai bench --card --share            # SVG + PNG (커뮤니티 API 경유)
asiai bench --quick --card --share    # 빠른 벤치 + 카드 + 공유
```

카드는 1200x630 다크 테마 이미지로 다음을 포함합니다:
- 모델 이름과 하드웨어 칩 뱃지
- 스펙 배너: 양자화, RAM, GPU 코어, 컨텍스트 크기
- 엔진별 tok/s 터미널 스타일 막대 차트
- 델타 포함 승자 하이라이트 (예: "2.4x")
- 메트릭 칩: tok/s, TTFT, 안정성, VRAM, 전력 (W + tok/s/W), 엔진 버전
- asiai 브랜딩

SVG는 `~/.local/share/asiai/cards/`에 저장됩니다. `--share` 사용 시 API에서 PNG도 다운로드됩니다.

## 커뮤니티 공유

결과를 익명으로 공유:

```bash
asiai bench --share
```

커뮤니티 리더보드는 `asiai leaderboard`로 볼 수 있습니다.

## 서멀 드리프트 감지

3회 이상 실행 시, asiai는 연속 실행 간 tok/s의 단조 감소를 감지합니다. tok/s가 일관되게 하락하면(5% 초과), 서멀 쓰로틀링 축적 가능성을 나타내는 경고가 출력됩니다.
