# asiai web

Launch the web dashboard for visual monitoring and benchmarking.

## Usage

```bash
asiai web
asiai web --port 9000
asiai web --host 0.0.0.0
asiai web --no-open
```

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--port` | `8899` | HTTP port to listen on |
| `--host` | `127.0.0.1` | Host to bind to |
| `--no-open` | | Don't open the browser automatically |
| `--db` | `~/.local/share/asiai/asiai.db` | Path to the SQLite database |

## Requirements

The web dashboard requires additional dependencies:

```bash
pip install asiai[web]
# or install everything:
pip install asiai[all]
```

## Pages

### Dashboard (`/`)

System overview with engine status, loaded models, memory usage, and last benchmark results.

### Benchmark (`/bench`)

Run cross-engine benchmarks directly from the browser:

- **Quick Bench** button — 1 prompt, 1 run, ~15 seconds
- Advanced options: engines, prompts, runs, context-size (4K/16K/32K/64K), power
- Live progress via SSE
- Results table with winner highlighting
- Throughput and TTFT charts
- **Shareable card** — auto-generated after benchmark (PNG via API, SVG fallback)
- **Share section** — copy link, download PNG/SVG, share on X/Reddit, export JSON

### History (`/history`)

Visualize benchmark and system metrics over time:

- System charts: CPU load, Memory %, GPU utilization (with renderer/tiler breakdown)
- Engine activity: TCP connections, requests processing, KV cache usage %
- Benchmark charts: throughput (tok/s) and TTFT per engine
- Process metrics: engine CPU % and RSS memory during benchmark runs
- Filter by time range (1h / 24h / 7d / 30d / 90d) or custom date range
- Data table with context-size indication (e.g., "code (64K ctx)")

### Monitor (`/monitor`)

Real-time system monitoring with 5-second refresh:

- CPU load sparkline
- Memory gauge
- Thermal state
- Loaded models list

### Doctor (`/doctor`)

Interactive health check for system, engines, and database. Same checks as `asiai doctor` with a visual interface.

## API Endpoints

The web dashboard exposes REST API endpoints for programmatic access.

### `GET /api/status`

Lightweight health check. Cached 10s, responds in < 500ms.

```json
{
  "status": "ok",
  "ts": 1709700000,
  "uptime": 86400,
  "engines": {"ollama": true, "lmstudio": false},
  "memory_pressure": "normal",
  "thermal_level": "nominal"
}
```

Status values: `ok` (all engines reachable), `degraded` (some down), `error` (all down).

### `GET /api/snapshot`

Full system + engine snapshot. Cached 5s. Includes CPU load, memory, thermal state, and per-engine status with loaded models.

### `GET /api/benchmarks`

Benchmark results with filters. Returns per-run data including tok/s, TTFT, power, context_size, engine_version.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `hours` | `168` | Time range in hours (0 = all) |
| `model` | | Filter by model name |
| `engine` | | Filter by engine name |
| `since` / `until` | | Unix timestamp range (overrides hours) |

### `GET /api/engine-history`

Engine status history (reachability, TCP connections, KV cache, tokens predicted).

| Parameter | Default | Description |
|-----------|---------|-------------|
| `hours` | `168` | Time range in hours |
| `engine` | | Filter by engine name |

### `GET /api/benchmark-process`

Process-level CPU and memory metrics from benchmark runs (7-day retention).

| Parameter | Default | Description |
|-----------|---------|-------------|
| `hours` | `168` | Time range in hours |
| `engine` | | Filter by engine name |

### `GET /api/metrics`

Prometheus exposition format. Gauges covering system, engine, model, and benchmark metrics.

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'asiai'
    static_configs:
      - targets: ['localhost:8899']
    metrics_path: '/api/metrics'
    scrape_interval: 30s
```

Metrics include:

| Metric | Type | Description |
|--------|------|-------------|
| `asiai_cpu_load_1m` | gauge | CPU load average (1 min) |
| `asiai_memory_used_bytes` | gauge | Memory used |
| `asiai_thermal_speed_limit_pct` | gauge | CPU speed limit % |
| `asiai_engine_reachable{engine}` | gauge | Engine reachability (0/1) |
| `asiai_engine_models_loaded{engine}` | gauge | Models loaded count |
| `asiai_engine_tcp_connections{engine}` | gauge | Established TCP connections |
| `asiai_engine_requests_processing{engine}` | gauge | Requests currently processing |
| `asiai_engine_kv_cache_usage_ratio{engine}` | gauge | KV cache fill ratio (0-1) |
| `asiai_engine_tokens_predicted_total{engine}` | counter | Cumulative tokens predicted |
| `asiai_model_vram_bytes{engine,model}` | gauge | VRAM per model |
| `asiai_bench_tok_per_sec{engine,model}` | gauge | Last benchmark tok/s |

## Notes

- The dashboard binds to `127.0.0.1` by default (localhost only)
- Use `--host 0.0.0.0` to expose on the network (e.g., for remote monitoring)
- Port `8899` is chosen to avoid conflicts with inference engine ports
