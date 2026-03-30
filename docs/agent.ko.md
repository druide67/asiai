---
description: AI 에이전트에 LLM 추론에 대한 실시간 가시성을 제공합니다. 자율 엔진 모니터링을 위한 11개 도구를 갖춘 MCP 서버입니다.
type: faq
faq:
  - q: "asiai에 root/sudo 권한이 필요합니까?"
    a: "아닙니다. GPU 관측성은 ioreg(권한 불필요)를 사용합니다. 전력 메트릭은 sudo가 필요 없는 IOReport를 사용합니다. 교차 검증용 선택적 --power 플래그만 sudo powermetrics를 사용합니다."
  - q: "API 응답 시간은 어떻게 됩니까?"
    a: "/api/status는 500ms 이내에 응답합니다(10초 캐시). /api/snapshot은 모든 엔진에서 실시간 데이터를 수집하므로 1-3초 소요됩니다."
  - q: "asiai를 Linux에서 실행할 수 있습니까?"
    a: "아닙니다. asiai는 macOS Apple Silicon 전용입니다. sysctl, vm_stat, ioreg, IOReport, launchd 등 모두 macOS 전용 API를 사용합니다."
  - q: "여러 Mac을 모니터링하려면 어떻게 합니까?"
    a: "각 Mac에서 asiai daemon start web --host 0.0.0.0을 실행하고, Prometheus로 /api/metrics를 스크레이프한 후 Grafana에서 시각화합니다."
  - q: "엔진이 크래시되면 어떻게 합니까?"
    a: "asiai는 엔진 장애를 자동으로 감지합니다. 진단에는 asiai doctor를 사용하세요. 자동 알림을 위해 asiai alert add로 웹훅 알림을 설정할 수 있습니다."
---

# 에이전트 통합 가이드

> **AI 에이전트를 위한 안내**: 프레임워크가 MCP를 지원하는 경우 [MCP](#mcp-model-context-protocol)를 사용하고, 그렇지 않으면 [REST API](#rest-api-레퍼런스)를 사용하세요. 설정은 [빠른 시작](#빠른-시작)을 참고하세요.

## 개요

asiai는 두 가지 메커니즘을 통해 Mac의 LLM 추론 인프라를 AI 에이전트에 공개합니다:

- **MCP 서버** — [Model Context Protocol](https://modelcontextprotocol.io)을 통한 네이티브 도구 통합. MCP를 지원하는 AI 에이전트(Claude Code, Cursor, Cline 및 기타 MCP 호환 클라이언트)에 최적입니다.
- **REST API** — 표준 HTTP/JSON 엔드포인트. 에이전트 프레임워크, 스웜 오케스트레이터 및 HTTP 지원 시스템(CrewAI, AutoGen, LangGraph, 커스텀 에이전트)에 최적입니다.

두 방식 모두 동일한 기능에 접근할 수 있습니다:

- 시스템 상태(CPU, RAM, GPU, 서멀, 스왑) **모니터링**
- 실행 중인 추론 엔진과 로드된 모델 **감지**
- GPU 관측성과 추론 활동 신호를 사용한 성능 문제 **진단**
- 프로그래밍 방식으로 모델 **벤치마크** 실행 및 리그레션 추적
- 하드웨어 기반 최적 모델/엔진 **추천** 받기

로컬 접근에는 인증이 필요 없습니다. 모든 인터페이스는 기본적으로 `127.0.0.1`에 바인딩됩니다.

### 어떤 통합 방식을 사용해야 합니까?

| 기준 | MCP | REST API |
|------|-----|----------|
| 에이전트가 MCP를 지원함 | **MCP 사용** | — |
| 스웜 / 멀티 에이전트 오케스트레이터 | — | **REST API 사용** |
| 폴링 / 예약 모니터링 | — | **REST API 사용** |
| Prometheus / Grafana 통합 | — | **REST API 사용** |
| 인터랙티브 AI 어시스턴트 (Claude Code, Cursor) | **MCP 사용** | — |
| Docker 컨테이너 내 에이전트 | — | **REST API 사용** |
| 커스텀 스크립트 또는 자동화 | — | **REST API 사용** |

## 빠른 시작

### asiai 설치

```bash
# Homebrew (권장)
brew tap druide67/tap && brew install asiai

# pip (MCP 지원 포함)
pip install "asiai[mcp]"

# pip (REST API만)
pip install asiai
```

### 옵션 A: MCP 서버 (MCP 호환 에이전트용)

```bash
# MCP 서버 시작 (stdio 트랜스포트 — Claude Code, Cursor 등에서 사용)
asiai mcp
```

수동으로 서버를 시작할 필요가 없습니다 — MCP 클라이언트가 자동으로 `asiai mcp`를 실행합니다. 아래 [MCP 설정](#mcp-model-context-protocol)을 참고하세요.

### 옵션 B: REST API (HTTP 기반 에이전트용)

```bash
# 포그라운드 (개발용)
asiai web --no-open

# 백그라운드 데몬 (프로덕션)
asiai daemon start web
```

API는 `http://127.0.0.1:8899`에서 사용할 수 있습니다. 포트는 `--port`로 설정 가능합니다:

```bash
asiai daemon start web --port 8642
```

원격 접근(다른 머신의 AI 에이전트 또는 Docker 컨테이너에서):

```bash
asiai daemon start web --host 0.0.0.0
```

> **참고:** 에이전트가 Docker 내부에서 실행되는 경우, `127.0.0.1`에 접근할 수 없습니다. 호스트의 네트워크 IP(예: `192.168.0.16`) 또는 Docker Desktop for Mac의 `host.docker.internal`을 사용하세요.

### 확인

```bash
# REST API
curl http://127.0.0.1:8899/api/status

# MCP (사용 가능한 도구 목록)
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | asiai mcp
```

---

## MCP (Model Context Protocol)

asiai는 추론 모니터링을 네이티브 도구로 공개하는 [MCP 서버](https://modelcontextprotocol.io)를 구현합니다. MCP 호환 클라이언트는 직접 연결하여 이러한 도구를 사용할 수 있습니다 — HTTP 설정이나 URL 관리가 필요 없습니다.

### 설정

#### 로컬 (동일 머신)

MCP 클라이언트 설정(예: Claude Code의 `~/.claude/settings.json`)에 추가하세요:

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

asiai가 가상 환경에 설치된 경우:

```json
{
  "mcpServers": {
    "asiai": {
      "command": "/path/to/.venv/bin/asiai",
      "args": ["mcp"]
    }
  }
}
```

#### 원격 (SSH를 통한 다른 머신)

```json
{
  "mcpServers": {
    "asiai": {
      "command": "ssh",
      "args": [
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        "your-mac-host",
        "cd /path/to/asiai && .venv/bin/asiai mcp"
      ]
    }
  }
}
```

#### SSE 트랜스포트 (네트워크)

HTTP 기반 MCP 트랜스포트를 선호하는 환경의 경우:

```bash
asiai mcp --transport sse --host 127.0.0.1 --port 8900
```

### MCP 도구 레퍼런스

모든 도구는 JSON을 반환합니다. 읽기 전용 도구는 2초 이내에 응답합니다. `run_benchmark`만 활성 작업입니다.

| 도구 | 설명 | 파라미터 |
|------|------|---------|
| `check_inference_health` | 빠른 상태 확인 — 엔진 가동/중단, 메모리 프레셔, 서멀, GPU 사용률 | — |
| `get_inference_snapshot` | 전체 시스템 상태 스냅샷 (SQLite에 이력 저장) | — |
| `list_models` | 모든 엔진에 로드된 전체 모델 (VRAM, 양자화, 컨텍스트 길이) | — |
| `detect_engines` | 3계층 감지: 설정, 포트 스캔, 프로세스 감지. 비표준 포트의 엔진도 자동 감지 | — |
| `run_benchmark` | 모델 벤치마크 또는 교차 모델 비교 실행. 레이트 제한: 60초당 1회 | `model` (선택), `runs` (1-10, 기본 3), `compare` (문자열 목록, 선택, `model`과 배타적, 최대 8) |
| `get_recommendations` | 하드웨어 기반 모델/엔진 추천 | — |
| `diagnose` | 진단 검사 실행 (시스템, 엔진, 데몬 상태) | — |
| `get_metrics_history` | SQLite에서 과거 시스템 메트릭 조회 | `hours` (1-168, 기본 24) |
| `get_benchmark_history` | 과거 벤치마크 결과 조회 | `hours` (1-720, 기본 24), `model` (선택), `engine` (선택) |
| `compare_engines` | 지정 모델에 대한 엔진 비교 순위 및 판정; 이력 기반 멀티 모델 비교 지원 | `model` (필수) |
| `refresh_engines` | MCP 서버 재시작 없이 엔진 재감지 | — |

### MCP 리소스

도구 호출 없이 사용 가능한 정적 데이터 엔드포인트:

| URI | 설명 |
|-----|------|
| `asiai://status` | 현재 상태 (메모리, 서멀, GPU) |
| `asiai://models` | 모든 엔진의 로드된 모델 |
| `asiai://system` | 하드웨어 정보 (칩, RAM, 코어, OS, 가동 시간) |

### MCP 보안

- **sudo 불필요**: MCP 모드에서는 전력 메트릭이 비활성화됩니다 (`power=False` 강제)
- **레이트 제한**: 벤치마크는 60초당 1회로 제한
- **입력 클램핑**: `hours`는 1-168, `runs`는 1-10으로 클램핑
- **기본 로컬**: stdio 트랜스포트는 네트워크 노출 없음; SSE는 `127.0.0.1`에 바인딩

### MCP 제한 사항

- **재연결 없음**: SSH 연결이 끊어지면(네트워크 문제, Mac 슬립) MCP 서버가 종료되며 클라이언트가 수동으로 재연결해야 합니다. 무인 모니터링에는 폴링 방식의 REST API가 더 안정적입니다.
- **단일 클라이언트**: stdio 트랜스포트는 한 번에 하나의 클라이언트만 지원합니다. 여러 클라이언트의 동시 접근이 필요하면 SSE 트랜스포트를 사용하세요.

---

## REST API 레퍼런스

asiai API는 **읽기 전용**입니다 — 모니터링과 보고만 하며 엔진을 제어하지 않습니다. 모델 로드/언로드에는 엔진 고유 명령(`ollama pull`, `lms load` 등)을 사용하세요.

모든 엔드포인트는 HTTP 200으로 JSON을 반환합니다. 엔진에 접근할 수 없는 경우에도 해당 엔진의 `"running": false`를 포함한 HTTP 200 응답이 반환됩니다 — API 자체는 실패하지 않습니다.

| 엔드포인트 | 일반적인 응답 시간 | 권장 타임아웃 |
|-----------|------------------|-------------|
| `GET /api/status` | 500ms 미만 (10초 캐시) | 2초 |
| `GET /api/snapshot` | 1-3초 (실시간 수집) | 10초 |
| `GET /api/metrics` | 500ms 미만 | 2초 |
| `GET /api/history` | 500ms 미만 | 5초 |
| `GET /api/engine-history` | 500ms 미만 | 5초 |

### `GET /api/status`

빠른 상태 확인. 10초 캐시. 응답 시간 500ms 미만.

**응답:**

```json
{
  "hostname": "mac-mini",
  "chip": "Apple M4 Pro",
  "ram_gb": 64.0,
  "cpu_percent": 12.3,
  "memory_pressure": "normal",
  "gpu_utilization_percent": 45.2,
  "engines": {
    "ollama": {
      "running": true,
      "models_loaded": 2,
      "port": 11434
    },
    "lmstudio": {
      "running": true,
      "models_loaded": 1,
      "port": 1234
    }
  },
  "asiai_version": "1.0.1",
  "uptime_seconds": 86400
}
```

### `GET /api/snapshot`

전체 시스템 상태. `/api/status`의 모든 것에 더해 상세 모델 정보, GPU 메트릭, 서멀 데이터를 포함합니다.

**응답:**

```json
{
  "system": {
    "hostname": "mac-mini",
    "chip": "Apple M4 Pro",
    "cores_p": 12,
    "cores_e": 4,
    "gpu_cores": 20,
    "ram_total_gb": 64.0,
    "ram_used_gb": 41.2,
    "ram_percent": 64.4,
    "swap_used_gb": 0.0,
    "memory_pressure": "normal",
    "cpu_percent": 12.3,
    "thermal_state": "nominal",
    "gpu_utilization_percent": 45.2,
    "gpu_renderer_percent": 38.1,
    "gpu_tiler_percent": 12.4,
    "gpu_memory_allocated_bytes": 8589934592
  },
  "engines": [
    {
      "name": "ollama",
      "running": true,
      "port": 11434,
      "models": [
        {
          "name": "qwen3.5:latest",
          "size_params": "35B",
          "size_vram_bytes": 21474836480,
          "quantization": "Q4_K_M",
          "context_length": 32768
        }
      ]
    }
  ],
  "timestamp": "2026-03-09T14:30:00Z"
}
```

### `GET /api/metrics`

Prometheus 호환 메트릭. Prometheus, Datadog 또는 기타 호환 도구로 스크레이프할 수 있습니다.

**응답 (text/plain):**

```
# HELP asiai_cpu_percent CPU usage percentage
# TYPE asiai_cpu_percent gauge
asiai_cpu_percent 12.3

# HELP asiai_ram_used_gb RAM used in GB
# TYPE asiai_ram_used_gb gauge
asiai_ram_used_gb 41.2

# HELP asiai_gpu_utilization_percent GPU utilization percentage
# TYPE asiai_gpu_utilization_percent gauge
asiai_gpu_utilization_percent 45.2

# HELP asiai_engine_up Engine availability (1=up, 0=down)
# TYPE asiai_engine_up gauge
asiai_engine_up{engine="ollama"} 1
asiai_engine_up{engine="lmstudio"} 1

# HELP asiai_models_loaded Number of models loaded per engine
# TYPE asiai_models_loaded gauge
asiai_models_loaded{engine="ollama"} 2
```

### `GET /api/history?hours=N`

SQLite에서 과거 시스템 메트릭. 기본: `hours=24`. 최대: `hours=2160` (90일).

**응답:**

```json
{
  "points": [
    {
      "timestamp": "2026-03-09T14:00:00Z",
      "cpu_percent": 15.2,
      "ram_used_gb": 40.1,
      "ram_percent": 62.7,
      "swap_used_gb": 0.0,
      "memory_pressure": "normal",
      "thermal_state": "nominal",
      "gpu_utilization_percent": 42.0,
      "gpu_renderer_percent": 35.0,
      "gpu_tiler_percent": 10.0,
      "gpu_memory_allocated_bytes": 8589934592
    }
  ],
  "count": 144,
  "hours": 24
}
```

### `GET /api/engine-history?engine=X&hours=N`

엔진별 활동 이력. 추론 패턴 감지에 유용합니다.

**파라미터:**

| 파라미터 | 필수 | 기본값 | 설명 |
|---------|------|-------|------|
| `engine` | 예 | — | 엔진 이름 (ollama, lmstudio 등) |
| `hours` | 아니오 | 24 | 시간 범위 |

**응답:**

```json
{
  "engine": "ollama",
  "points": [
    {
      "timestamp": "2026-03-09T14:00:00Z",
      "running": true,
      "tcp_connections": 3,
      "requests_processing": 1,
      "kv_cache_usage_percent": 45.2
    }
  ],
  "count": 144,
  "hours": 24
}
```

## 메트릭 해석

### 시스템 상태 임계값

| 메트릭 | 정상 | 경고 | 위험 |
|--------|------|------|------|
| `memory_pressure` | `normal` | `warn` | `critical` |
| `ram_percent` | 75% 미만 | 75-90% | 90% 초과 |
| `swap_used_gb` | 0 | 0.1-2.0 | 2.0 초과 |
| `thermal_state` | `nominal` | `fair` | `serious` / `critical` |
| `cpu_percent` | 80% 미만 | 80-95% | 95% 초과 |

### GPU 임계값

| 메트릭 | 유휴 | 추론 활성 | 과부하 |
|--------|------|----------|--------|
| `gpu_utilization_percent` | 0-5% | 20-80% | 90% 초과 (지속) |
| `gpu_renderer_percent` | 0-5% | 15-70% | 85% 초과 (지속) |
| `gpu_memory_allocated_bytes` | 1 GB 미만 | 2-48 GB | RAM의 90% 초과 |

> **중요:** `gpu_utilization_percent = 0`은 GPU가 유휴 상태라는 의미이지, 고장이 아닙니다. `-1.0`은 메트릭을 사용할 수 없음(예: 미지원 하드웨어 또는 수집 실패)을 의미합니다 — "GPU 사망"으로 취급하지 마세요.

### 추론 성능

| 메트릭 | 우수 | 양호 | 저하 |
|--------|------|------|------|
| `tok/s` (7B 모델) | 80 초과 | 40-80 | 40 미만 |
| `tok/s` (35B 모델) | 40 초과 | 20-40 | 20 미만 |
| `tok/s` (70B 모델) | 15 초과 | 8-15 | 8 미만 |
| `TTFT` | 100ms 미만 | 100-500ms | 500ms 초과 |

## 진단 의사결정 트리

### 느린 생성 (낮은 tok/s)

``` mermaid
graph TD
    A["tok/s below expected?"] --> B["Check memory_pressure"]
    A --> C["Check thermal_state"]
    A --> D["Check gpu_utilization_percent"]
    A --> E["Check swap_used_gb"]

    B -->|critical| B1["Models swapping to disk.<br/>Unload models or add RAM."]
    B -->|normal| B2["Continue"]

    C -->|"serious / critical"| C1["Thermal throttling.<br/>Cool down, check airflow."]
    C -->|nominal| C2["Continue"]

    D -->|"< 10%"| D1["GPU not being used.<br/>Check engine config (num_gpu layers)."]
    D -->|"> 90%"| D2["GPU saturated.<br/>Reduce concurrent requests."]
    D -->|"20-80%"| D3["Normal. Check model<br/>quantization and context size."]

    E -->|"> 0"| E1["Model too large for RAM.<br/>Use smaller quantization."]
    E -->|"0"| E2["Check engine version,<br/>try different engine."]
```

### 엔진 무응답

``` mermaid
graph TD
    A["engine.running == false?"] --> B["Check process: lsof -i :port"]
    A --> C["Check memory_pressure"]
    A --> D["Try: asiai doctor"]

    B -->|No process| B1["Engine crashed. Restart it."]
    B -->|Process exists| B2["Engine hung."]

    C -->|critical| C1["OOM killed.<br/>Unload other models first."]
    C -->|normal| C2["Check engine logs."]

    D --> D1["Comprehensive diagnostics"]
```

### 높은 메모리 프레셔 / VRAM 오버플로

``` mermaid
graph TD
    A["memory_pressure == warn/critical?"] --> B["Check swap_used_gb"]
    A --> C["Check models loaded"]
    A --> D["Check gpu_memory_allocated_bytes"]

    B -->|"> 2 GB"| B1["VRAM overflow.<br/>Latency 5-50x worse (disk swap).<br/>Unload models or use Q3_K_S."]
    B -->|"< 2 GB"| B2["Manageable.<br/>Monitor closely."]

    C -->|"Multiple large models"| C1["Unload unused models.<br/>ollama rm / lms unload"]
    C -->|"Single model > 80% RAM"| C2["Use smaller quantization."]

    D --> D1["If > 80% of RAM,<br/>next model load triggers swap."]
```

## 추론 활동 신호

asiai는 여러 신호를 통해 활성 추론을 감지합니다:

### GPU 사용률

```
GET /api/snapshot → system.gpu_utilization_percent
```

- **5% 미만**: 추론이 실행되지 않음
- **20-80%**: 활성 추론 (Apple Silicon 유니파이드 메모리의 일반적 범위)
- **90% 초과**: 대량 추론 또는 다수의 동시 요청

### TCP 연결

```
GET /api/engine-history?engine=ollama&hours=1
```

활성 추론 요청은 각각 TCP 연결을 유지합니다. `tcp_connections`의 스파이크는 활성 생성을 나타냅니다.

### 엔진별 메트릭

`/metrics`를 노출하는 엔진(llama.cpp, vllm-mlx)의 경우:

- `requests_processing > 0`: 활성 추론
- `kv_cache_usage_percent > 0`: 모델에 활성 컨텍스트가 있음

### 상관 패턴

가장 신뢰할 수 있는 추론 감지는 여러 신호를 결합합니다:

```python
snapshot = get_snapshot()
gpu_active = snapshot["system"]["gpu_utilization_percent"] > 15
engine_busy = any(
    e.get("tcp_connections", 0) > 0
    for e in snapshot.get("engine_status", [])
)
inference_running = gpu_active and engine_busy
```

## 코드 예제

### 상태 확인 (Python, 표준 라이브러리만)

```python
import json
import urllib.request

ASIAI_URL = "http://127.0.0.1:8899"  # Docker: 호스트 IP 또는 host.docker.internal 사용

def check_health():
    """빠른 상태 확인. 상태 dict를 반환합니다."""
    req = urllib.request.Request(f"{ASIAI_URL}/api/status")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())

def is_healthy(status):
    """상태를 해석합니다."""
    issues = []
    if status.get("memory_pressure") != "normal":
        issues.append(f"memory_pressure: {status['memory_pressure']}")
    gpu = status.get("gpu_utilization_percent", 0)
    if gpu > 90:
        issues.append(f"gpu_utilization: {gpu}%")
    engines = status.get("engines", {})
    for name, info in engines.items():
        if not info.get("running"):
            issues.append(f"engine_down: {name}")
    return {"healthy": len(issues) == 0, "issues": issues}

# 사용 예
status = check_health()
health = is_healthy(status)
if not health["healthy"]:
    print(f"Issues detected: {health['issues']}")
```

### 전체 시스템 상태

```python
def get_full_state():
    """전체 시스템 스냅샷을 가져옵니다."""
    req = urllib.request.Request(f"{ASIAI_URL}/api/snapshot")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

def get_history(hours=24):
    """과거 메트릭을 가져옵니다."""
    req = urllib.request.Request(f"{ASIAI_URL}/api/history?hours={hours}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

# 성능 트렌드 감지
history = get_history(hours=6)
points = history["points"]
if len(points) >= 2:
    recent_gpu = points[-1].get("gpu_utilization_percent", 0)
    earlier_gpu = points[0].get("gpu_utilization_percent", 0)
    if recent_gpu > earlier_gpu * 1.5:
        print("GPU utilization trending up significantly")
```

## 벤치마크 카드 (공유 가능한 이미지)

CLI로 공유 가능한 벤치마크 카드 이미지를 생성할 수 있습니다:

```bash
asiai bench --card                    # SVG를 로컬에 저장 (의존성 제로)
asiai bench --card --share            # SVG + PNG (커뮤니티 API 경유)
asiai bench --quick --card --share    # 빠른 벤치 + 카드 + 공유 (~15초)
```

모델, 칩, 엔진 비교 막대 차트, 승자 하이라이트, 메트릭 칩을 포함한 **1200x630 다크 테마 카드**입니다. Reddit, X, Discord, GitHub README에 최적화되어 있습니다.

카드는 SVG로 `~/.local/share/asiai/cards/`에 저장됩니다. `--share`를 추가하면 PNG 다운로드와 공유 가능한 URL을 얻을 수 있습니다 — PNG는 Reddit, X, Discord 게시에 필요합니다.

### MCP를 통해

`run_benchmark` MCP 도구는 `card` 파라미터로 카드 생성을 지원합니다:

```json
{"tool": "run_benchmark", "arguments": {"model": "qwen3.5", "card": true}}
```

응답에는 `card_path`가 포함됩니다 — MCP 서버 파일시스템의 SVG 파일 절대 경로입니다.

## 웹훅 알림 (푸시 알림)

폴링 대신 상태 변화가 발생할 때 asiai가 푸시 알림을 보내도록 설정할 수 있습니다:

```bash
# 웹훅 추가 (Slack, Discord 또는 임의의 URL)
asiai alert add https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# 알림 트리거:
# - 엔진 중단 / 복구
# - 메모리 프레셔 전환 (normal → warn → critical)
# - 서멀 쓰로틀링 감지
```

알림은 **전환 시에만** 발생하며(매 확인이 아님), 플러딩 방지를 위해 5분 쿨다운이 있습니다. 지속적 폴링 없이 인프라 변화에 대응해야 하는 스웜 오케스트레이터에 이상적입니다.

알림 목록 및 삭제: `asiai alert list`, `asiai alert remove <id>`.

## 에이전트 식별

REST API 요청에 에이전트를 식별하는 `User-Agent` 헤더를 포함하는 것을 **권장**합니다:

```
User-Agent: asiai-agent/<framework>/<version>
```

예시:

- `User-Agent: asiai-agent/openclaw/1.2.0`
- `User-Agent: asiai-agent/crewai/0.5`
- `User-Agent: asiai-agent/custom-orchestrator/1.0`

이것은 **필수가 아닙니다** — User-Agent 헤더 없는 요청도 정상 작동합니다. 하지만 다음에 도움이 됩니다:

- **디버깅** — 로그에서 에이전트 요청과 브라우저 접근 구분
- **에이전트별 분석** — 어떤 에이전트가 API에 접근하는지, 빈도와 엔드포인트 파악
- **멀티 에이전트 환경** — 여러 에이전트가 동일한 asiai 인스턴스를 공유할 때 식별

MCP 클라이언트의 경우, 식별은 자동입니다 (MCP 프로토콜에 클라이언트 메타데이터 포함).

---

## 에이전트 등록 (선택 사항)

등록은 **완전히 선택 사항**입니다 — asiai는 등록 없이도 완전하게 작동합니다. 기본적으로 텔레메트리나 폰홈이 없습니다.

등록을 선택하면 asiai 에이전트 네트워크에 참여합니다: API 한 번 호출, 이메일 불필요, 개인 데이터 불필요 — 하드웨어 정보만 필요합니다.

```bash
curl -X POST https://api.asiai.dev/api/v1/agent-register \
  -H "Content-Type: application/json" \
  -d '{
    "chip": "Apple M4 Pro",
    "ram_gb": 64,
    "engines": ["ollama", "lmstudio"],
    "framework": "my-agent",
    "asiai_version": "1.0.1"
  }'
```

**응답:**

```json
{
  "status": "registered",
  "agent_id": "a1b2c3d4e5f6",
  "agent_token": "secret_...",
  "total_agents": 42
}
```

`agent_id`와 `agent_token`을 `~/.local/share/asiai/agent.json`에 안전하게 저장하세요. 커뮤니티 API 호출과 벤치마크 제출에 필요합니다.

### 등록으로 해제되는 기능

| 기능 | agent_id 없이 | agent_id 있으면 |
|------|-------------|---------------|
| 로컬 bench/monitor/web | 예 | 예 |
| `/api/status`, `/api/snapshot` | 예 | 예 |
| `--share` 벤치마크 | 아니오 | **예** |
| `asiai compare` (커뮤니티) | 아니오 | **예** |
| `asiai recommend --community` | 아니오 | **예** |
| 백분위 통계 | 아니오 | **예** |
| 에이전트 디렉토리 (동일 칩 피어 검색) | 아니오 | **예** |
| 성능 알림 (새 엔진이 당신을 앞지름) | 아니오 | **출시 예정** |

### 하트비트

주기적 하트비트로 등록을 활성 상태로 유지합니다:

```bash
curl -X POST https://api.asiai.dev/api/v1/agent-heartbeat \
  -H "Content-Type: application/json" \
  -H "X-Agent-Id: a1b2c3d4e5f6" \
  -H "X-Agent-Token: secret_..." \
  -d '{
    "engines": ["ollama", "lmstudio"],
    "version": "1.0.1",
    "models_loaded": 3,
    "uptime_hours": 72
  }'
```

### 프라이버시

- **IP 주소 저장 안 함** — IP는 레이트 제한에만 사용되며 에이전트 레지스트리에 저장되지 않습니다
- **개인 데이터 없음** — 하드웨어 정보(칩, RAM), 엔진 이름, 프레임워크 이름만
- **옵트인 전용** — 명시적으로 등록하지 않는 한 asiai는 폰홈하지 않습니다
- **토큰 보안** — `agent_token`은 저장 전에 해시됩니다(SHA-256); 평문은 등록 시 한 번만 반환됩니다
- **레이트 제한 데이터** — 레이트 제한 테이블의 IP 해시(일일 솔트 SHA-256)는 30일 후 자동 삭제됩니다

## FAQ

**Q: asiai에 root/sudo 권한이 필요합니까?**
A: 아닙니다. GPU 관측성은 `ioreg`(권한 불필요)를 사용합니다. 전력 메트릭(벤치마크의 `--power` 플래그)은 `sudo powermetrics`가 필요하지만 선택 사항입니다.

**Q: API 응답 시간은 어떻게 됩니까?**
A: `/api/status`는 500ms 이내에 응답합니다(10초 캐시). `/api/snapshot`은 1-3초 소요됩니다(모든 엔진에서 실시간 데이터 수집).

**Q: asiai를 Linux에서 실행할 수 있습니까?**
A: 아닙니다. asiai는 macOS Apple Silicon 전용입니다. `sysctl`, `vm_stat`, `ioreg`, `launchd` 등 모두 macOS 전용 API를 사용합니다.

**Q: 여러 Mac을 모니터링하려면 어떻게 합니까?**
A: 각 Mac에서 `asiai daemon start web --host 0.0.0.0`을 실행하세요. Prometheus로 `/api/metrics`를 스크레이프하고 Grafana에서 시각화합니다.

**Q: 엔진이 크래시되면 어떻게 합니까?**
A: asiai는 엔진 장애를 자동으로 감지합니다. 진단에는 `asiai doctor`를 사용하세요. 자동 알림을 위해 `asiai alert add`로 웹훅 알림을 설정할 수 있습니다.
