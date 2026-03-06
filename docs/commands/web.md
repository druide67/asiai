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

- Select engines and prompts
- Configure number of runs (1-10)
- Optional power measurement (requires `sudo NOPASSWD` for `powermetrics`)
- Live progress via SSE
- Results table with winner highlighting
- Throughput and TTFT charts

### History (`/history`)

Visualize benchmark results over time:

- Throughput (tok/s) and TTFT line charts
- Filter by time range (24h / 7d / 30d / 90d)
- Sortable data table

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

### `GET /api/metrics`

Prometheus exposition format. 15 gauges covering system, engine, model, and benchmark metrics.

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
| `asiai_model_vram_bytes{engine,model}` | gauge | VRAM per model |
| `asiai_bench_tok_per_sec{engine,model}` | gauge | Last benchmark tok/s |

## Notes

- The dashboard binds to `127.0.0.1` by default (localhost only)
- Use `--host 0.0.0.0` to expose on the network (e.g., for remote monitoring)
- Port `8899` is chosen to avoid conflicts with inference engine ports
