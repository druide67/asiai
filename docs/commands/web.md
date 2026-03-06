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

## Notes

- The dashboard binds to `127.0.0.1` by default (localhost only)
- Use `--host 0.0.0.0` to expose on the network (e.g., for remote monitoring)
- Port `8899` is chosen to avoid conflicts with inference engine ports
