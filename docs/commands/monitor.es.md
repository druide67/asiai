---
description: Monitoreo continuo de utilización de GPU, estado térmico y presión de memoria para Apple Silicon. Sin necesidad de sudo.
---

# asiai monitor

Snapshot de métricas del sistema e inferencia, almacenado en SQLite.

## Uso

```bash
asiai monitor [options]
```

## Opciones

| Opción | Descripción |
|--------|-------------|
| `-w, --watch SEC` | Actualizar cada SEC segundos |
| `-q, --quiet` | Recopilar y almacenar sin salida (para uso con daemon) |
| `-H, --history PERIOD` | Mostrar historial (ej. `24h`, `1h`) |
| `-a, --analyze HOURS` | Análisis completo con tendencias |
| `-c, --compare TS TS` | Comparar dos marcas de tiempo |
| `--alert-webhook URL` | Enviar alertas por POST a URL del webhook en transiciones de estado |

## Salida

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

El monitoreo de energía usa el Apple IOReport Energy Model para leer el consumo de energía de GPU, CPU, ANE y DRAM — sin necesidad de sudo. Consulta [Metodología](../methodology.md#power-measurement) para detalles de validación.

## Alertas por webhook

Cuando se proporciona `--alert-webhook URL`, asiai enviará una alerta JSON por POST a la URL del webhook cada vez que se detecte una **transición de estado**:

| Tipo de alerta | Disparador | Severidad |
|------------|---------|----------|
| `mem_pressure_warn` | Presión de memoria: normal → warn | warning |
| `mem_pressure_critical` | Presión de memoria: normal/warn → critical | critical |
| `thermal_degraded` | Nivel térmico: nominal → fair/serious/critical | warning/critical |
| `engine_down` | Motor accesible, ahora inaccesible | critical |

Las alertas usan un **enfriamiento de 5 minutos** por tipo para prevenir spam. Cada alerta se almacena en SQLite para historial.

### Payload del webhook

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

### Uso con daemon

```bash
asiai daemon start monitor --alert-webhook https://hooks.slack.com/services/...
```

## Almacenamiento de datos

Todos los snapshots se almacenan en SQLite (`~/.local/share/asiai/metrics.db`) con retención automática de 90 días.
