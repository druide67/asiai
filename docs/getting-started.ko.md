---
description: asiai를 설치하고 2분 안에 첫 번째 LLM 벤치마크를 실행하세요. 명령어 하나, 의존성 제로, 모든 Apple Silicon Mac에서 작동합니다.
---

# 시작하기

**Apple Silicon AI** — 멀티엔진 LLM 벤치마크 및 모니터링 CLI.

asiai는 Mac에서 추론 엔진을 나란히 비교합니다. 동일한 모델을 Ollama와 LM Studio에 로드하고 `asiai bench`를 실행하면 결과를 얻을 수 있습니다. 추측도 없고, 감도 없습니다 — tok/s, TTFT, 전력 효율, 엔진별 안정성만 확인합니다.

## 빠른 시작

```bash
pipx install asiai        # 권장: 격리 설치
```

또는 Homebrew로:

```bash
brew tap druide67/tap
brew install asiai
```

기타 옵션:

```bash
uvx asiai detect           # 설치 없이 실행 (uv 필요)
pip install asiai           # 표준 pip 설치
```

### 첫 실행

```bash
asiai setup                # 대화형 마법사 — 하드웨어, 엔진, 모델 감지
asiai detect               # 또는 엔진 감지로 바로 이동
```

그 다음 벤치마크:

```bash
asiai bench -m qwen3.5 --runs 3 --power
```

출력 예시:

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

## 측정 항목

| 메트릭 | 설명 |
|--------|-------------|
| **tok/s** | 생성 속도 (토큰/초), 프롬프트 처리 제외 |
| **TTFT** | 첫 번째 토큰까지의 시간 — 프롬프트 처리 지연 시간 |
| **Power** | GPU 전력 소비 (와트) (`sudo powermetrics`) |
| **tok/s/W** | 에너지 효율 — 와트당 초당 토큰 수 |
| **Stability** | 실행 간 편차: stable (<5%), variable (<10%), unstable (>10%) |
| **VRAM** | 메모리 사용량 — 네이티브 (Ollama, LM Studio) 또는 `ri_phys_footprint`를 통한 추정 (모든 엔진) |
| **Thermal** | CPU 스로틀링 상태 및 속도 제한 백분율 |

## 지원 엔진

| 엔진 | 포트 | API |
|--------|------|-----|
| [Ollama](https://ollama.com) | 11434 | 네이티브 |
| [LM Studio](https://lmstudio.ai) | 1234 | OpenAI 호환 |
| [mlx-lm](https://github.com/ml-explore/mlx-examples) | 8080 | OpenAI 호환 |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | 8080 | OpenAI 호환 |
| [oMLX](https://github.com/jundot/omlx) | 8000 | OpenAI 호환 |
| [vllm-mlx](https://github.com/vllm-project/vllm) | 8000 | OpenAI 호환 |
| [Exo](https://github.com/exo-explore/exo) | 52415 | OpenAI 호환 |

## 커스텀 포트

엔진이 비표준 포트에서 실행 중인 경우, asiai는 보통 프로세스 감지를 통해 자동으로 찾습니다. 수동으로 등록할 수도 있습니다:

```bash
asiai config add omlx http://localhost:8800 --label mac-mini
```

수동으로 추가된 엔진은 영구 저장되며 자동 삭제되지 않습니다. 자세한 내용은 [config](commands/config.md)를 참조하세요.

## 요구 사항

- Apple Silicon (M1 / M2 / M3 / M4)의 macOS
- Python 3.11 이상
- 로컬에서 실행 중인 추론 엔진 최소 1개

## 의존성 제로

코어는 Python 표준 라이브러리만 사용합니다 — `urllib`, `sqlite3`, `subprocess`, `argparse`. `requests` 없음, `psutil` 없음, `rich` 없음.

선택적 extras:

- `asiai[web]` — 차트가 포함된 FastAPI 웹 대시보드
- `asiai[tui]` — Textual 터미널 대시보드
- `asiai[mcp]` — AI 에이전트 통합을 위한 MCP 서버
- `asiai[all]` — Web + TUI + MCP
- `asiai[dev]` — pytest, ruff, pytest-cov
