# Agent Integration Guide

> **If you are an AI agent**, skip to [API Reference](#api-reference). For setup, see [Quick Start](#quick-start).

## Overview

asiai exposes your Mac's LLM inference infrastructure through a REST API. An AI agent can:

- **Monitor** system health (CPU, RAM, GPU, thermal, swap)
- **Detect** which inference engines are running and what models are loaded
- **Diagnose** performance issues using GPU observability and inference activity signals
- **Benchmark** models programmatically and track regressions
- **Alert** on memory pressure, thermal throttling, or engine failures

All endpoints return JSON. No authentication required for local access. The API binds to `127.0.0.1` by default.

## Quick Start

### Install asiai

```bash
# Homebrew (recommended)
brew tap druide67/tap && brew install asiai

# pip
pip install asiai
```

### Start the API server

```bash
# Foreground (development)
asiai web --no-open

# Background daemon (production)
asiai daemon start web
```

The API is available at `http://127.0.0.1:7654`.

For remote access (e.g., AI agent on a different machine):

```bash
asiai daemon start web --host 0.0.0.0
```

### Verify

```bash
curl http://127.0.0.1:7654/api/status
```

## API Reference

### `GET /api/status`

Quick health check. Cached 10 seconds. Response time < 500ms.

**Response:**

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
  "asiai_version": "1.0.0",
  "uptime_seconds": 86400
}
```

### `GET /api/snapshot`

Full system state. Includes everything from `/api/status` plus detailed model information, GPU metrics, and thermal data.

**Response:**

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

Prometheus-compatible metrics. Scrape with Prometheus, Datadog, or any compatible tool.

**Response (text/plain):**

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

Historical system metrics from SQLite. Default: `hours=24`. Max: `hours=2160` (90 days).

**Response:**

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

Engine-specific activity history. Useful for detecting inference patterns.

**Parameters:**

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `engine`  | Yes      | —       | Engine name (ollama, lmstudio, etc.) |
| `hours`   | No       | 24      | Time range |

**Response:**

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

## Interpreting Metrics

### System Health Thresholds

| Metric | Normal | Warning | Critical |
|--------|--------|---------|----------|
| `memory_pressure` | `normal` | `warn` | `critical` |
| `ram_percent` | < 75% | 75–90% | > 90% |
| `swap_used_gb` | 0 | 0.1–2.0 | > 2.0 |
| `thermal_state` | `nominal` | `fair` | `serious` / `critical` |
| `cpu_percent` | < 80% | 80–95% | > 95% |

### GPU Thresholds

| Metric | Idle | Active Inference | Overloaded |
|--------|------|------------------|------------|
| `gpu_utilization_percent` | < 5% | 20–80% | > 90% sustained |
| `gpu_renderer_percent` | < 5% | 15–70% | > 85% sustained |
| `gpu_memory_allocated_bytes` | < 1 GB | 2–48 GB | > 90% of RAM |

### Inference Performance

| Metric | Excellent | Good | Degraded |
|--------|-----------|------|----------|
| `tok/s` (7B model) | > 80 | 40–80 | < 40 |
| `tok/s` (35B model) | > 40 | 20–40 | < 20 |
| `tok/s` (70B model) | > 15 | 8–15 | < 8 |
| `TTFT` | < 100ms | 100–500ms | > 500ms |

## Diagnostic Decision Trees

### Slow Generation (low tok/s)

```
tok/s below expected?
├── Check memory_pressure
│   ├── "critical" → Models swapping to disk. Unload models or add RAM.
│   └── "normal" → Continue
├── Check thermal_state
│   ├── "serious"/"critical" → Thermal throttling. Cool down, check airflow.
│   └── "nominal" → Continue
├── Check gpu_utilization_percent
│   ├── < 10% → GPU not being used. Check engine config (num_gpu layers).
│   ├── > 90% → GPU saturated. Reduce concurrent requests.
│   └── 20-80% → Normal. Check model quantization and context size.
└── Check swap_used_gb
    ├── > 0 → Model too large for RAM. Use smaller quantization.
    └── 0 → Check engine version, try different engine.
```

### Engine Not Responding

```
engine.running == false?
├── Check if process exists: lsof -i :<port>
│   ├── No process → Engine crashed. Restart it.
│   └── Process exists but not responding → Engine hung.
├── Check memory_pressure
│   ├── "critical" → OOM killed. Unload other models first.
│   └── "normal" → Check engine logs.
└── Try: asiai doctor (comprehensive diagnostics)
```

### High Memory Pressure

```
memory_pressure == "warn" or "critical"?
├── Check models loaded across all engines
│   ├── Multiple large models → Unload unused models
│   │   ├── Ollama: ollama rm <model> or wait for auto-unload
│   │   └── LM Studio: unload via UI or lms unload
│   └── Single model > 80% RAM → Use smaller quantization
├── Check swap_used_gb
│   ├── > 2 GB → Critical. Performance severely degraded.
│   └── < 2 GB → Manageable but monitor closely.
└── Check gpu_memory_allocated_bytes
    └── Compare to ram_total_gb. If > 80%, model barely fits.
```

## Inference Activity Signals

asiai detects active inference through multiple signals:

### GPU Utilization

```
GET /api/snapshot → system.gpu_utilization_percent
```

- **< 5%**: No inference running
- **20–80%**: Active inference (normal range for Apple Silicon unified memory)
- **> 90%**: Heavy inference or multiple concurrent requests

### TCP Connections

```
GET /api/engine-history?engine=ollama&hours=1
```

Each active inference request maintains a TCP connection. A spike in `tcp_connections` indicates active generation.

### Engine-Specific Metrics

For engines that expose `/metrics` (llama.cpp, vllm-mlx):

- `requests_processing > 0`: Active inference
- `kv_cache_usage_percent > 0`: Model has active context

### Correlation Pattern

The most reliable inference detection combines multiple signals:

```python
snapshot = get_snapshot()
gpu_active = snapshot["system"]["gpu_utilization_percent"] > 15
engine_busy = any(
    e.get("tcp_connections", 0) > 0
    for e in snapshot.get("engine_status", [])
)
inference_running = gpu_active and engine_busy
```

## Example Code

### Health Check (Python, stdlib only)

```python
import json
import urllib.request

ASIAI_URL = "http://127.0.0.1:7654"

def check_health():
    """Quick health check. Returns dict with status."""
    req = urllib.request.Request(f"{ASIAI_URL}/api/status")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())

def is_healthy(status):
    """Interpret health status."""
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

# Usage
status = check_health()
health = is_healthy(status)
if not health["healthy"]:
    print(f"Issues detected: {health['issues']}")
```

### Full System State

```python
def get_full_state():
    """Get complete system snapshot."""
    req = urllib.request.Request(f"{ASIAI_URL}/api/snapshot")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

def get_history(hours=24):
    """Get historical metrics."""
    req = urllib.request.Request(f"{ASIAI_URL}/api/history?hours={hours}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

# Detect performance trend
history = get_history(hours=6)
points = history["points"]
if len(points) >= 2:
    recent_gpu = points[-1].get("gpu_utilization_percent", 0)
    earlier_gpu = points[0].get("gpu_utilization_percent", 0)
    if recent_gpu > earlier_gpu * 1.5:
        print("GPU utilization trending up significantly")
```

## User-Agent Convention

When making requests to asiai's API, set a descriptive User-Agent header:

```
User-Agent: asiai-agent/my-framework-name
```

This helps with debugging and monitoring. Examples:

- `User-Agent: asiai-agent/openclaw`
- `User-Agent: asiai-agent/langchain`
- `User-Agent: asiai-agent/custom-orchestrator`

## Register Your Agent

To access community features (benchmarks, compare, recommendations), register your agent with a single API call. No email, no personal data — just your hardware info.

```bash
curl -X POST https://api.asiai.dev/api/v1/agent-register \
  -H "Content-Type: application/json" \
  -d '{
    "chip": "Apple M4 Pro",
    "ram_gb": 64,
    "engines": ["ollama", "lmstudio"],
    "framework": "my-agent",
    "asiai_version": "1.0.0"
  }'
```

**Response:**

```json
{
  "status": "registered",
  "agent_id": "a1b2c3d4e5f6",
  "agent_token": "secret_...",
  "total_agents": 42
}
```

Store `agent_id` and `agent_token` securely in `~/.local/share/asiai/agent.json`. You'll need both for community API calls and benchmark submissions.

### What registration unlocks

| Feature | Without agent_id | With agent_id |
|---------|-----------------|---------------|
| Local bench/monitor/web | Yes | Yes |
| `/api/status`, `/api/snapshot` | Yes | Yes |
| `--share` benchmarks | No | Yes |
| `asiai compare` (community) | No | Yes |
| `asiai recommend --community` | No | Yes |
| Percentile stats | No | Yes |

### Heartbeat

Keep your registration active with periodic heartbeats:

```bash
curl -X POST https://api.asiai.dev/api/v1/agent-heartbeat \
  -H "Content-Type: application/json" \
  -H "X-Agent-Id: a1b2c3d4e5f6" \
  -H "X-Agent-Token: secret_..." \
  -d '{
    "engines": ["ollama", "lmstudio"],
    "version": "1.0.0",
    "models_loaded": 3,
    "uptime_hours": 72
  }'
```

## FAQ

**Q: Does asiai require root/sudo?**
A: No. GPU observability uses `ioreg` (no privileges). Power metrics (`--power` flag in benchmarks) require `sudo powermetrics`, but this is optional.

**Q: What's the API response time?**
A: `/api/status` responds in < 500ms (cached 10s). `/api/snapshot` takes 1–3s (collects live data from all engines).

**Q: Can I run asiai on Linux?**
A: No. asiai is macOS Apple Silicon only. It uses `sysctl`, `vm_stat`, `ioreg`, and `IOReport` — all macOS-specific APIs.

**Q: How do I monitor multiple Macs?**
A: Run `asiai daemon start web --host 0.0.0.0` on each Mac. Scrape `/api/metrics` with Prometheus. Visualize in Grafana.

**Q: What if an engine crashes?**
A: asiai detects engine failures automatically. Use `asiai doctor` for diagnostics. Set up webhook alerts with `asiai alert add` for automated notifications.
