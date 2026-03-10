# Agent Integration Guide

> **If you are an AI agent**: use [MCP](#mcp-model-context-protocol) if your framework supports it, otherwise use the [REST API](#rest-api-reference). For setup, see [Quick Start](#quick-start).

## Overview

asiai exposes your Mac's LLM inference infrastructure to AI agents through two mechanisms:

- **MCP Server** — Native tool integration via the [Model Context Protocol](https://modelcontextprotocol.io). Best for AI agents that support MCP (Claude Code, Cursor, Cline, and other MCP-compatible clients).
- **REST API** — Standard HTTP/JSON endpoints. Best for agent frameworks, swarm orchestrators, and any HTTP-capable system (CrewAI, AutoGen, LangGraph, custom agents).

Both give access to the same capabilities:

- **Monitor** system health (CPU, RAM, GPU, thermal, swap)
- **Detect** which inference engines are running and what models are loaded
- **Diagnose** performance issues using GPU observability and inference activity signals
- **Benchmark** models programmatically and track regressions
- **Get recommendations** for the best model/engine based on your hardware

No authentication required for local access. All interfaces bind to `127.0.0.1` by default.

### Which integration should I use?

| Criteria | MCP | REST API |
|----------|-----|----------|
| Your agent supports MCP | **Use MCP** | — |
| Swarm / multi-agent orchestrator | — | **Use REST API** |
| Polling / scheduled monitoring | — | **Use REST API** |
| Prometheus / Grafana integration | — | **Use REST API** |
| Interactive AI assistant (Claude Code, Cursor) | **Use MCP** | — |
| Agent inside Docker container | — | **Use REST API** |
| Custom scripts or automation | — | **Use REST API** |

## Quick Start

### Install asiai

```bash
# Homebrew (recommended)
brew tap druide67/tap && brew install asiai

# pip (with MCP support)
pip install "asiai[mcp]"

# pip (REST API only)
pip install asiai
```

### Option A: MCP Server (for MCP-compatible agents)

```bash
# Start MCP server (stdio transport — used by Claude Code, Cursor, etc.)
asiai mcp
```

No manual server start needed — the MCP client launches `asiai mcp` automatically. See [MCP setup](#mcp-model-context-protocol) below.

### Option B: REST API (for HTTP-based agents)

```bash
# Foreground (development)
asiai web --no-open

# Background daemon (production)
asiai daemon start web
```

The API is available at `http://127.0.0.1:7654`. The port is configurable with `--port`:

```bash
asiai daemon start web --port 8642
```

For remote access (e.g., AI agent on a different machine or from a Docker container):

```bash
asiai daemon start web --host 0.0.0.0
```

> **Note:** If your agent runs inside Docker, `127.0.0.1` is unreachable. Use the host's network IP (e.g., `192.168.0.16`) or `host.docker.internal` on Docker Desktop for Mac.

### Verify

```bash
# REST API
curl http://127.0.0.1:7654/api/status

# MCP (list available tools)
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | asiai mcp
```

---

## MCP (Model Context Protocol)

asiai implements an [MCP server](https://modelcontextprotocol.io) that exposes inference monitoring as native tools. Any MCP-compatible client can connect and use these tools directly — no HTTP setup, no URL management.

### Setup

#### Local (same machine)

Add to your MCP client configuration (e.g., `~/.claude/settings.json` for Claude Code):

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

If asiai is installed in a virtualenv:

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

#### Remote (different machine via SSH)

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

#### SSE transport (network)

For environments that prefer HTTP-based MCP transport:

```bash
asiai mcp --transport sse --host 127.0.0.1 --port 8900
```

### MCP Tools Reference

All tools return JSON. Read-only tools respond in < 2 seconds. `run_benchmark` is the only active operation.

| Tool | Description | Parameters |
|------|-------------|------------|
| `check_inference_health` | Quick health check — engines up/down, memory pressure, thermal, GPU utilization | — |
| `get_inference_snapshot` | Full system state snapshot (stored in SQLite for history) | — |
| `list_models` | All models loaded across all engines with VRAM, quantization, context length | — |
| `detect_engines` | Re-scan all 6 engine ports and return what's running | — |
| `run_benchmark` | Run benchmark on a model. Rate limited: 1 per 60 seconds | `model` (optional), `runs` (1–10, default 3) |
| `get_recommendations` | Hardware-aware model/engine recommendations for your chip and RAM | — |
| `diagnose` | Run diagnostic checks (system, engines, daemon health) | — |
| `get_metrics_history` | Historical system metrics from SQLite | `hours` (1–168, default 24) |
| `get_benchmark_history` | Historical benchmark results | `hours` (1–720, default 24), `model` (optional), `engine` (optional) |

### MCP Resources

Static data endpoints, available without calling a tool:

| URI | Description |
|-----|-------------|
| `asiai://status` | Current health status (memory, thermal, GPU) |
| `asiai://models` | All loaded models across engines |
| `asiai://system` | Hardware info (chip, RAM, cores, OS, uptime) |

### MCP Security

- **No sudo**: Power metrics are disabled in MCP mode (`power=False` forced)
- **Rate limiting**: Benchmarks are limited to 1 per 60 seconds
- **Input clamping**: `hours` clamped to 1–168, `runs` clamped to 1–10
- **Local by default**: stdio transport has no network exposure; SSE binds to `127.0.0.1`

### MCP Limitations

- **No reconnection**: If the SSH connection drops (network issue, Mac sleep), the MCP server dies and the client must reconnect manually. For unattended monitoring, the REST API with polling is more resilient.
- **Single client**: stdio transport serves one client at a time. Use SSE transport if multiple clients need concurrent access.

---

## REST API Reference

asiai's API is **read-only** — it monitors and reports, but does not control engines. To load/unload models, use engine-native commands (`ollama pull`, `lms load`, etc.).

All endpoints return JSON with HTTP 200. If an engine is unreachable, the response still returns 200 with `"running": false` for that engine — the API itself does not fail.

| Endpoint | Typical response time | Recommended timeout |
|----------|----------------------|---------------------|
| `GET /api/status` | < 500ms (cached 10s) | 2s |
| `GET /api/snapshot` | 1–3s (live collection) | 10s |
| `GET /api/metrics` | < 500ms | 2s |
| `GET /api/history` | < 500ms | 5s |
| `GET /api/engine-history` | < 500ms | 5s |

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
| `gpu_utilization_percent` | 0–5% | 20–80% | > 90% sustained |
| `gpu_renderer_percent` | 0–5% | 15–70% | > 85% sustained |
| `gpu_memory_allocated_bytes` | < 1 GB | 2–48 GB | > 90% of RAM |

> **Important:** `gpu_utilization_percent = 0` means the GPU is idle, not broken. A value of `-1.0` means the metric is unavailable (e.g., unsupported hardware or collection failure) — do not treat it as "GPU dead".

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

### High Memory Pressure / VRAM Overflow

```
memory_pressure == "warn" or "critical"?
├── Check swap_used_gb
│   ├── > 2 GB → VRAM overflow. Models don't fit in unified memory.
│   │   ├── Latency will be 5–50× worse (disk swap).
│   │   ├── Unload models: ollama rm <model>, lms unload
│   │   └── Or use smaller quantization (Q4_K_M → Q3_K_S).
│   └── < 2 GB → Manageable but monitor closely.
├── Check models loaded across all engines
│   ├── Multiple large models → Unload unused models
│   │   ├── Ollama: ollama rm <model> or wait for auto-unload
│   │   └── LM Studio: unload via UI or lms unload
│   └── Single model > 80% RAM → Use smaller quantization
└── Check gpu_memory_allocated_bytes
    └── Compare to ram_total_gb. If > 80%, next model load will trigger swap.
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

ASIAI_URL = "http://127.0.0.1:7654"  # Docker: use host IP or host.docker.internal

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

## Webhook Alerts (Push Notifications)

Instead of polling, configure asiai to push notifications when state changes occur:

```bash
# Add a webhook (Slack, Discord, or any URL)
asiai alert add https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Alerts trigger on:
# - Engine goes down / comes back up
# - Memory pressure transitions (normal → warn → critical)
# - Thermal throttling detected
```

Alerts fire on **transitions only** (not on every check) with a 5-minute cooldown to prevent flooding. This is ideal for swarm orchestrators that need to react to infrastructure changes without continuous polling.

To list or remove alerts: `asiai alert list`, `asiai alert remove <id>`.

## Identify Your Agent

We **recommend** including a `User-Agent` header identifying your agent on REST API requests:

```
User-Agent: asiai-agent/<framework>/<version>
```

Examples:

- `User-Agent: asiai-agent/openclaw/1.2.0`
- `User-Agent: asiai-agent/crewai/0.5`
- `User-Agent: asiai-agent/custom-orchestrator/1.0`

This is **not required** — requests without a User-Agent header work fine. But it helps with:

- **Debugging** — distinguish agent requests from human browser access in logs
- **Per-agent analytics** — see which agents hit the API, how often, and which endpoints
- **Multi-agent environments** — when multiple agents share the same asiai instance, identify who's who

For MCP clients, identification is automatic (the MCP protocol includes client metadata).

---

## Register Your Agent (Optional)

Registration is **entirely optional** — asiai works fully without it. No phone home, no telemetry by default.

If you choose to register, you join the asiai agent network: one API call, no email, no personal data — just your hardware info.

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
| `--share` benchmarks | No | **Yes** |
| `asiai compare` (community) | No | **Yes** |
| `asiai recommend --community` | No | **Yes** |
| Percentile stats | No | **Yes** |
| Agent directory (find peers on same chip) | No | **Yes** |
| Performance alerts (new engine beats yours) | No | **Coming soon** |

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

### Privacy

- **No IP address stored** — your IP is used only for rate limiting and never persisted in the agent registry
- **No personal data** — only hardware info (chip, RAM), engine names, and framework name
- **Opt-in only** — asiai never phones home unless you explicitly register
- **Token security** — your `agent_token` is hashed (SHA-256) before storage; the plaintext is returned only once at registration
- **Rate limit data** — IP hashes (daily-salted SHA-256) in the rate limit table are automatically purged after 30 days

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
