---
description: Continuous GPU utilization, thermal state and memory pressure monitoring for Apple Silicon. No sudo required.
---

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
| `--alert-webhook URL` | POST alerts to webhook URL on state transitions |

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

## Alert webhooks

When `--alert-webhook URL` is provided, asiai will POST a JSON alert to the webhook URL whenever a **state transition** is detected:

| Alert type | Trigger | Severity |
|------------|---------|----------|
| `mem_pressure_warn` | Memory pressure: normal → warn | warning |
| `mem_pressure_critical` | Memory pressure: normal/warn → critical | critical |
| `thermal_degraded` | Thermal level: nominal → fair/serious/critical | warning/critical |
| `engine_down` | Engine was reachable, now unreachable | critical |

Alerts use a **5-minute cooldown** per type to prevent spam. Each alert is stored in SQLite for history.

### Webhook payload

```json
{
    "alert": "mem_pressure_warn",
    "severity": "warning",
    "ts": 1741350000,
    "host": "macmini.local",
    "message": "Memory pressure changed: normal → warn",
    "details": {
        "mem_pressure": "warn",
        "mem_used": 54000000000,
        "mem_total": 68719476736
    },
    "source": "asiai/0.7.0"
}
```

### Usage with daemon

```bash
asiai daemon start monitor --alert-webhook https://hooks.slack.com/services/...
```

## Data storage

All snapshots are stored in SQLite (`~/.local/share/asiai/metrics.db`) with 90-day automatic retention.
