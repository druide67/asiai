---
description: Apple Silicon 持续 GPU 利用率、温控状态和内存压力监控。无需 sudo。
---

# asiai monitor

系统和推理指标快照，存储在 SQLite 中。

## 用法

```bash
asiai monitor [options]
```

## 选项

| 选项 | 描述 |
|------|------|
| `-w, --watch SEC` | 每 SEC 秒刷新 |
| `-q, --quiet` | 仅采集存储，不输出（用于守护进程） |
| `-H, --history PERIOD` | 显示历史（如 `24h`、`1h`） |
| `-a, --analyze HOURS` | 含趋势的综合分析 |
| `-c, --compare TS TS` | 比较两个时间戳 |
| `--alert-webhook URL` | 状态转换时向 webhook URL 发送 POST 告警 |

## 输出

```
System
  Uptime:    3d 12h
  CPU Load:  2.45 / 3.12 / 2.89  (1m / 5m / 15m)
  Memory:    45.2 GB / 64.0 GB  71%
  Pressure:  normal
  Thermal:   nominal  (100%)

GPU
  Utilization: 45%  (renderer 44%, tiler 45%)
  Memory:      24.2 GB in use / 48.0 GB allocated

Power
  GPU: 12.6W  CPU: 4.4W  ANE: 0.0W  DRAM: 5.2W
  Total: 22.2W  (IOReport, no sudo)

Inference  ollama 0.17.4
  Models loaded: 1  VRAM total: 26.0 GB

  Model                                        VRAM   Format  Quant
  ──────────────────────────────────────── ────────── ──────── ──────
  qwen3.5:35b-a3b                            26.0 GB     gguf Q4_K_M
```

功耗监控使用 Apple IOReport Energy Model 读取 GPU、CPU、ANE 和 DRAM 功耗——无需 sudo。详见[方法论](../methodology.md#power-measurement)的验证细节。

## 告警 Webhook

提供 `--alert-webhook URL` 时，asiai 在检测到**状态转换**时向 webhook URL 发送 JSON 告警：

| 告警类型 | 触发条件 | 严重级别 |
|---------|---------|---------|
| `mem_pressure_warn` | 内存压力：normal → warn | warning |
| `mem_pressure_critical` | 内存压力：normal/warn → critical | critical |
| `thermal_degraded` | 温控级别：nominal → fair/serious/critical | warning/critical |
| `engine_down` | 引擎之前可达，现在不可达 | critical |

告警使用每类型 **5 分钟冷却期**防止洪泛。每个告警存储在 SQLite 中用于历史记录。

### Webhook 载荷

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

### 配合守护进程使用

```bash
asiai daemon start monitor --alert-webhook https://hooks.slack.com/services/...
```

## 数据存储

所有快照存储在 SQLite（`~/.local/share/asiai/metrics.db`），自动保留 90 天。
