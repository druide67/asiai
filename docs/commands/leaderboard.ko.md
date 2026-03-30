---
description: "asiai 커뮤니티 리더보드 탐색 및 조회: Apple Silicon 칩과 추론 엔진 간 벤치마크 결과를 비교합니다."
---

# asiai leaderboard

asiai 네트워크에서 커뮤니티 벤치마크 데이터를 탐색합니다.

## 사용법

```bash
asiai leaderboard [options]
```

## 옵션

| 옵션 | 설명 |
|------|------|
| `--chip CHIP` | Apple Silicon 칩으로 필터 (예: `M4 Pro`, `M2 Ultra`) |
| `--model MODEL` | 모델 이름으로 필터 |

## 예시

```bash
asiai leaderboard --chip "M4 Pro"
```

```
  Community Leaderboard — M4 Pro

  Model                  Engine      tok/s (median)   Runs   Contributors
  ──────────────────── ────────── ──────────────── ────── ──────────────
  qwen3.5:35b-a3b       ollama          30.4          42         12
  qwen3.5:35b-a3b       lmstudio        72.6          38         11
  llama3.3:70b           exo            18.2          15          4
  gemma2:9b              mlx-lm        105.3          27          9

  Source: api.asiai.dev — 122 results
```

## 참고 사항

- `api.asiai.dev`의 커뮤니티 API가 필요합니다.
- 결과는 익명화되어 있습니다. 개인 또는 머신 식별 데이터는 공유되지 않습니다.
- `asiai bench --share`로 자신의 결과를 제출할 수 있습니다.
