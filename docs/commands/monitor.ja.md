---
description: Apple SiliconのGPU使用率、サーマル状態、メモリプレッシャーの継続的監視。sudo不要。
---

# asiai monitor

システムと推論メトリクスのスナップショット。SQLiteに保存されます。

## 使用方法

```bash
asiai monitor [options]
```

## オプション

| オプション | 説明 |
|-----------|------|
| `-w, --watch SEC` | SEC秒ごとにリフレッシュ |
| `-q, --quiet` | 出力なしで収集・保存（デーモン用） |
| `-H, --history PERIOD` | 履歴を表示（例：`24h`、`1h`） |
| `-a, --analyze HOURS` | トレンドを含む包括的分析 |
| `-c, --compare TS TS` | 2つのタイムスタンプを比較 |
| `--alert-webhook URL` | 状態遷移時にWebhook URLへアラートをPOST |

## 出力

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

電力監視はAppleのIOReport Energy Modelを使用してGPU、CPU、ANE、DRAMの消費電力を読み取ります — sudo不要。バリデーションの詳細は[手法](../methodology.md#電力測定)を参照。

## アラートWebhook

`--alert-webhook URL` が指定された場合、asiai は**状態遷移**が検出されるたびにWebhook URLへJSON アラートをPOSTします：

| アラートタイプ | トリガー | 重大度 |
|-------------|---------|--------|
| `mem_pressure_warn` | メモリプレッシャー：normal → warn | warning |
| `mem_pressure_critical` | メモリプレッシャー：normal/warn → critical | critical |
| `thermal_degraded` | サーマルレベル：nominal → fair/serious/critical | warning/critical |
| `engine_down` | エンジンが到達可能だったが到達不能に | critical |

アラートはスパム防止のためタイプごとに**5分間のクールダウン**があります。各アラートは履歴用にSQLiteに保存されます。

### Webhookペイロード

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

### デーモンとの使用

```bash
asiai daemon start monitor --alert-webhook https://hooks.slack.com/services/...
```

## データ保存

すべてのスナップショットはSQLite（`~/.local/share/asiai/metrics.db`）に保存され、90日間の自動保持期間があります。
