---
description: Mac의 RAM, GPU 코어, 서멀 여유에 기반한 하드웨어 인식 모델 추천.
---

# asiai recommend

하드웨어와 용도에 기반한 엔진 추천을 받습니다.

## 사용법

```bash
asiai recommend [options]
```

## 옵션

| 옵션 | 설명 |
|------|------|
| `--model MODEL` | 추천을 받을 모델 |
| `--use-case USE_CASE` | 최적화 대상: `throughput`, `latency`, `efficiency` |
| `--community` | 커뮤니티 벤치마크 데이터를 추천에 포함 |
| `--db PATH` | 로컬 벤치마크 데이터베이스 경로 |

## 데이터 소스

추천은 사용 가능한 최선의 데이터에서 우선순위에 따라 구축됩니다:

1. **로컬 벤치마크** — 자신의 하드웨어에서의 실행 결과
2. **커뮤니티 데이터** — 유사한 칩의 집계 결과 (`--community` 사용 시)
3. **휴리스틱** — 벤치마크 데이터가 없을 때의 내장 규칙

## 신뢰도 수준

| 수준 | 기준 |
|------|------|
| High | 5회 이상의 로컬 벤치마크 실행 |
| Medium | 1-4회 로컬 실행, 또는 커뮤니티 데이터 사용 가능 |
| Low | 휴리스틱 기반, 벤치마크 데이터 없음 |

## 예시

```bash
asiai recommend --model qwen3.5 --use-case throughput
```

```
  Recommendation: qwen3.5 — M4 Pro — throughput

  #   Engine       tok/s    Confidence   Source
  ── ────────── ──────── ──────────── ──────────
  1   lmstudio    72.6     high         local (5 runs)
  2   ollama      30.4     high         local (5 runs)
  3   exo         18.2     medium       community

  Tip: lmstudio is 2.4x faster than ollama for this model.
```

## 참고 사항

- 가장 정확한 추천을 위해 먼저 `asiai bench`를 실행하세요.
- `--community`를 사용하여 특정 엔진을 로컬에서 벤치마크하지 않은 경우의 빈틈을 채울 수 있습니다.
- `efficiency` 용도는 전력 소비를 고려합니다 (이전 벤치마크의 `--power` 데이터 필요).
