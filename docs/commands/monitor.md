# asiai monitor

System and inference metrics snapshot, stored in SQLite.

## Usage

```bash
asiai monitor [options]
```

## Options

| Option | Description |
|--------|-------------|
| `-w, --watch SEC` | Refresh every SEC seconds |
| `-q, --quiet` | Collect and store without output (for daemon use) |
| `-H, --history PERIOD` | Show history (e.g., `24h`, `1h`) |
| `-a, --analyze HOURS` | Comprehensive analysis with trends |
| `-c, --compare TS TS` | Compare two timestamps |

## Output

```
System
  Uptime:    3d 12h
  CPU Load:  2.45 / 3.12 / 2.89  (1m / 5m / 15m)
  Memory:    45.2 GB / 64.0 GB  71%
  Pressure:  normal
  Thermal:   nominal  (100%)

Inference  ollama 0.17.4
  Models loaded: 1  VRAM total: 26.0 GB

  Model                                        VRAM   Format  Quant
  ──────────────────────────────────────── ────────── ──────── ──────
  qwen3.5:35b-a3b                            26.0 GB     gguf Q4_K_M
```

## Data storage

All snapshots are stored in SQLite (`~/.local/share/asiai/metrics.db`) with 90-day automatic retention.
