---
description: AI 에이전트가 추론 엔진을 모니터링하고 벤치마크를 실행하며 하드웨어 기반 추천을 받을 수 있는 11개 도구를 노출하는 MCP 서버.
---

# asiai mcp

MCP(Model Context Protocol) 서버를 시작하여 AI 에이전트가 추론 인프라를 모니터링하고 벤치마크할 수 있도록 합니다.

## 사용법

```bash
asiai mcp                          # stdio 트랜스포트 (Claude Code)
asiai mcp --transport sse          # SSE 트랜스포트 (네트워크 에이전트)
asiai mcp --transport sse --port 9000
```

## 옵션

| 옵션 | 설명 |
|------|------|
| `--transport` | 트랜스포트 프로토콜: `stdio` (기본), `sse`, `streamable-http` |
| `--host` | 바인드 주소 (기본: `127.0.0.1`) |
| `--port` | SSE/HTTP 트랜스포트 포트 (기본: `8900`) |
| `--register` | asiai 에이전트 네트워크에 옵트인 등록 (익명) |

## 도구 (11)

| 도구 | 설명 | 읽기 전용 |
|------|------|----------|
| `check_inference_health` | 빠른 상태 확인: 엔진 가동/중단, 메모리 프레셔, 서멀, GPU | 예 |
| `get_inference_snapshot` | 전체 메트릭을 포함한 전체 시스템 스냅샷 | 예 |
| `list_models` | 모든 엔진의 로드된 모델 목록 | 예 |
| `detect_engines` | 추론 엔진 재스캔 | 예 |
| `run_benchmark` | 벤치마크 또는 교차 모델 비교 실행 (레이트 제한: 1회/분) | 아니오 |
| `get_recommendations` | 하드웨어 기반 엔진/모델 추천 | 예 |
| `diagnose` | 진단 검사 실행 (`asiai doctor`와 동일) | 예 |
| `get_metrics_history` | 과거 메트릭 조회 (1-168시간) | 예 |
| `get_benchmark_history` | 필터로 과거 벤치마크 결과 조회 | 예 |
| `compare_engines` | 모델에 대한 엔진 성능을 판정과 함께 비교; 이력 기반 멀티 모델 비교 지원 | 예 |
| `refresh_engines` | 서버 재시작 없이 엔진 재감지 | 예 |

## 리소스 (3)

| 리소스 | URI | 설명 |
|--------|-----|------|
| 시스템 상태 | `asiai://status` | 현재 시스템 상태 (메모리, 서멀, GPU) |
| 모델 | `asiai://models` | 모든 엔진의 로드된 모델 |
| 시스템 정보 | `asiai://system` | 하드웨어 정보 (칩, RAM, 코어, OS, 가동 시간) |

## Claude Code 통합

Claude Code MCP 설정(`~/.claude/claude_desktop_config.json`)에 추가:

```json
{
  "mcpServers": {
    "asiai": {
      "command": "asiai",
      "args": ["mcp"]
    }
  }
}
```

그 다음 Claude에게 "추론 상태를 확인해줘" 또는 "qwen3.5로 Ollama와 LM Studio를 비교해줘"라고 물어보세요.

## 벤치마크 카드

`run_benchmark` 도구는 `card` 파라미터로 카드 생성을 지원합니다. `card=true`일 때 1200x630 SVG 벤치마크 카드가 생성되고 응답에 `card_path`가 반환됩니다.

```json
{"tool": "run_benchmark", "arguments": {"model": "qwen3.5", "card": true}}
```

교차 모델 비교 (`model`과 배타적, 최대 8 슬롯):

```json
{"tool": "run_benchmark", "arguments": {"compare": ["qwen3.5:4b", "deepseek-r1:7b"], "card": true}}
```

PNG + 공유의 CLI 동등:

```bash
asiai bench --quick --card --share    # 빠른 벤치 + 카드 + 공유 (~15초)
```

자세한 내용은 [벤치마크 카드](../benchmark-card.md) 페이지를 참고하세요.

## 에이전트 등록

asiai 에이전트 네트워크에 참여하여 커뮤니티 기능(리더보드, 비교, 백분위 통계)을 이용하세요:

```bash
asiai mcp --register                  # 첫 실행 시 등록, 이후 하트비트
asiai unregister                      # 로컬 자격 증명 제거
```

등록은 **옵트인이며 익명**입니다 — 하드웨어 정보(칩, RAM)와 엔진 이름만 전송됩니다. IP, 호스트명, 개인 데이터는 저장되지 않습니다. 자격 증명은 `~/.local/share/asiai/agent.json` (chmod 600)에 저장됩니다.

이후 `asiai mcp --register` 호출 시 재등록 대신 하트비트가 전송됩니다. API에 접근할 수 없으면 MCP 서버가 등록 없이 정상 시작합니다.

등록 상태는 `asiai version`으로 확인할 수 있습니다.

## 네트워크 에이전트

다른 머신의 에이전트용(예: 헤드리스 Mac Mini 모니터링):

```bash
asiai mcp --transport sse --host 0.0.0.0 --port 8900
```

자세한 설정 안내는 [에이전트 통합 가이드](../agent.md)를 참고하세요.
