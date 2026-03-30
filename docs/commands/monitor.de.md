---
description: Kontinuierliche Überwachung von GPU-Auslastung, thermischem Zustand und Speicherdruck für Apple Silicon. Kein sudo erforderlich.
---

# asiai monitor

System- und Inferenzmetriken-Snapshot, in SQLite gespeichert.

## Verwendung

```bash
asiai monitor [options]
```

## Optionen

| Option | Beschreibung |
|--------|-------------|
| `-w, --watch SEC` | Alle SEC Sekunden aktualisieren |
| `-q, --quiet` | Erfassen und speichern ohne Ausgabe (für Daemon-Nutzung) |
| `-H, --history PERIOD` | Verlauf anzeigen (z.B. `24h`, `1h`) |
| `-a, --analyze HOURS` | Umfassende Analyse mit Trends |
| `-c, --compare TS TS` | Zwei Zeitstempel vergleichen |
| `--alert-webhook URL` | Alerts bei Zustandsübergängen per POST an Webhook-URL senden |

## Ausgabe

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

Die Leistungsüberwachung nutzt Apples IOReport Energy Model Framework, um den Stromverbrauch von GPU, CPU, ANE und DRAM zu lesen — kein sudo erforderlich. Siehe [Methodik](../methodology.md#leistungsmessung) für Validierungsdetails.

## Alert-Webhooks

Wenn `--alert-webhook URL` angegeben wird, sendet asiai einen JSON-Alert per POST an die Webhook-URL bei jedem erkannten **Zustandsübergang**:

| Alert-Typ | Auslöser | Schweregrad |
|-----------|---------|------------|
| `mem_pressure_warn` | Speicherdruck: normal → warn | warning |
| `mem_pressure_critical` | Speicherdruck: normal/warn → critical | critical |
| `thermal_degraded` | Thermisches Niveau: nominal → fair/serious/critical | warning/critical |
| `engine_down` | Engine war erreichbar, jetzt nicht mehr | critical |

Alerts haben eine **5-Minuten-Abklingzeit** pro Typ, um Spam zu vermeiden. Jeder Alert wird für den Verlauf in SQLite gespeichert.

### Webhook-Payload

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

### Verwendung mit dem Daemon

```bash
asiai daemon start monitor --alert-webhook https://hooks.slack.com/services/...
```

## Datenspeicherung

Alle Snapshots werden in SQLite gespeichert (`~/.local/share/asiai/metrics.db`) mit automatischer 90-Tage-Aufbewahrung.
