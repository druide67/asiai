---
description: asiai가 엔진을 감지하고, IOReport로 GPU 메트릭을 수집하며, 시계열 데이터를 저장하는 방법. 기술 심층 분석.
---

# 아키텍처

asiai의 데이터 흐름 — 하드웨어 센서에서 터미널, 브라우저, AI 에이전트까지.

## 개요

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Your Mac (Apple Silicon)                     │
│                                                                      │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐               │
│  │   Ollama     │   │  LM Studio  │   │   mlx-lm    │  ...engines   │
│  └──────┬───────┘   └──────┬──────┘   └──────┬──────┘               │
│         │ HTTP              │ HTTP            │ HTTP                  │
│         └──────────┬────────┴────────────────┘                       │
│                    ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────┐     │
│  │                      asiai core                              │     │
│  │                                                              │     │
│  │  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐      │     │
│  │  │ Engines  │  │  Collectors  │  │    Benchmark     │      │     │
│  │  │ adapters │  │  (GPU, CPU,  │  │  (warmup, runs,  │      │     │
│  │  │ (6 ABC   │  │   thermal,   │  │   median, CI95)  │      │     │
│  │  │  impls)  │  │   memory)    │  │                  │      │     │
│  │  └────┬─────┘  └──────┬───────┘  └────────┬─────────┘      │     │
│  │       │               │                    │                 │     │
│  │       └───────┬───────┴────────────────────┘                 │     │
│  │               ▼                                              │     │
│  │  ┌──────────────────────────────────┐                       │     │
│  │  │       Storage (SQLite WAL)       │                       │     │
│  │  │  metrics · models · benchmarks   │                       │     │
│  │  │  engine_status · alerts          │                       │     │
│  │  │  community_submissions           │                       │     │
│  │  └──────────────┬───────────────────┘                       │     │
│  │                 │                                            │     │
│  └─────────────────┼────────────────────────────────────────────┘     │
│                    │                                                  │
│         ┌──────────┼──────────┬─────────────┐                        │
│         ▼          ▼          ▼             ▼                         │
│  ┌───────────┐ ┌────────┐ ┌──────────┐ ┌──────────┐                │
│  │    CLI    │ │  Web   │ │   MCP    │ │Prometheus│                │
│  │  (ANSI,  │ │(htmx,  │ │ (stdio,  │ │ /metrics │                │
│  │  --json) │ │ SSE,   │ │  SSE,    │ │          │                │
│  │          │ │ charts)│ │  HTTP)   │ │          │                │
│  └───────────┘ └────────┘ └──────────┘ └──────────┘                │
│                                │                                     │
└────────────────────────────────┼─────────────────────────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
             ┌───────────┐ ┌─────────┐ ┌───────────┐
             │Claude Code│ │ Cursor  │ │ AI agents │
             │  (MCP)    │ │  (MCP)  │ │  (HTTP)   │
             └───────────┘ └─────────┘ └───────────┘
```

## 주요 파일

| 레이어 | 파일 | 역할 |
|-------|-------|------|
| **엔진** | `src/asiai/engines/` | ABC `InferenceEngine` + 7개 어댑터 (Ollama, LM Studio, mlx-lm, llama.cpp, oMLX, vllm-mlx, Exo). OpenAI 호환 엔진을 위한 `OpenAICompatEngine` 기본 클래스. |
| **수집기** | `src/asiai/collectors/` | 시스템 메트릭: `gpu.py` (ioreg), `system.py` (CPU, 메모리, 서멀), `processes.py` (lsof를 통한 추론 활동). |
| **벤치마크** | `src/asiai/benchmark/` | `runner.py` (워밍업 + N회 실행, 중앙값, 표준편차, CI95), `prompts.py` (테스트 프롬프트), `card.py` (SVG 카드 생성). |
| **스토리지** | `src/asiai/storage/` | `db.py` (SQLite WAL, 모든 CRUD), `schema.py` (테이블 + 마이그레이션). |
| **CLI** | `src/asiai/cli.py` | Argparse 진입점, 전체 12개 명령어. |
| **Web** | `src/asiai/web/` | FastAPI + htmx + SSE + ApexCharts 대시보드. 라우트는 `routes/` 내부. |
| **MCP** | `src/asiai/mcp/` | FastMCP 서버, 11개 도구 + 3개 리소스. 트랜스포트: stdio, SSE, streamable-http. |
| **어드바이저** | `src/asiai/advisor/` | 하드웨어 기반 추천 (모델 사이징, 엔진 선택). |
| **디스플레이** | `src/asiai/display/` | ANSI 포매터 (`formatters.py`), CLI 렌더러 (`cli_renderer.py`), TUI (`tui.py`). |

## 데이터 흐름

### 모니터링 (데몬 모드)

```
60초마다:
  collectors → snapshot dict → store_snapshot(db) → models table
                                                  → metrics table
  engines    → engine status → store_engine_status(db)
```

### 벤치마크

```
CLI --bench → detect engines → pick model → warmup → N runs
           → compute median/stddev/CI95 → store_benchmark(db)
           → render table (ANSI or JSON)
           → optional: --share → POST to community API
           → optional: --card  → generate SVG card
```

### 웹 대시보드

```
Browser → FastAPI → Jinja2 template (initial render)
       → htmx SSE → /api/v1/stream → real-time updates
       → ApexCharts → /api/v1/metrics?hours=N → historical graphs
```

### MCP 서버

```
AI agent → stdio/SSE/HTTP → FastMCP → tool call
        → runs collector/benchmark in thread pool (asyncio.to_thread)
        → returns structured JSON
```

## 설계 원칙

1. **코어 의존성 제로** — CLI, 수집기, 엔진, 스토리지는 Python 표준 라이브러리만 사용합니다. 선택적 extras (`[web]`, `[tui]`, `[mcp]`)는 필요할 때만 의존성을 추가합니다.
2. **공유 데이터 레이어** — 동일한 SQLite 데이터베이스가 CLI, Web, MCP, Prometheus에 사용됩니다. 별도의 데이터 저장소가 없습니다.
3. **어댑터 패턴** — 7개 엔진 모두 `InferenceEngine` ABC를 구현합니다. 새 엔진 추가 = 파일 1개 + `detect.py`에 등록.
4. **지연 임포트** — 각 CLI 명령어는 의존성을 로컬에서 임포트하여 시작 시간을 빠르게 유지합니다.
5. **macOS 네이티브** — GPU용 `ioreg`, 데몬용 `launchd`, 추론 활동용 `lsof`. Linux 추상화 없음.
