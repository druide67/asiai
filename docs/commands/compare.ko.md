---
description: 교차 모델 및 교차 엔진 벤치마크 매트릭스. 단일 실행으로 최대 8개 model@engine 조합 비교.
---

# asiai compare

로컬 벤치마크를 커뮤니티 데이터와 비교합니다.

## 사용법

```bash
asiai compare [options]
```

## 옵션

| 옵션 | 설명 |
|------|------|
| `--chip CHIP` | 비교할 Apple Silicon 칩 (기본: 자동 감지) |
| `--model MODEL` | 모델 이름으로 필터 |
| `--db PATH` | 로컬 벤치마크 데이터베이스 경로 |

## 예시

```bash
asiai compare --model qwen3.5
```

```
  Compare: qwen3.5 — M4 Pro

  Engine       Your tok/s   Community median   Delta
  ────────── ──────────── ────────────────── ────────
  lmstudio        72.6           70.1          +3.6%
  ollama          30.4           31.0          -1.9%

  Chip: Apple M4 Pro (auto-detected)
```

## 참고 사항

- `--chip`이 지정되지 않으면 asiai가 Apple Silicon 칩을 자동 감지합니다.
- 델타는 로컬 중앙값과 커뮤니티 중앙값의 차이를 백분율로 표시합니다.
- 양수 델타는 당신의 설정이 커뮤니티 평균보다 빠르다는 의미입니다.
- 로컬 결과는 벤치마크 이력 데이터베이스(기본: `~/.local/share/asiai/benchmarks.db`)에서 가져옵니다.
