---
description: Monitoraggio continuo di utilizzo GPU, stato termico e pressione memoria per Apple Silicon. Nessun sudo necessario.
---

# asiai monitor

Snapshot di metriche di sistema e inferenza, salvato in SQLite.

## Uso

```bash
asiai monitor [options]
```

## Opzioni

| Opzione | Descrizione |
|--------|-------------|
| `-w, --watch SEC` | Aggiorna ogni SEC secondi |
| `-q, --quiet` | Raccolta e salvataggio senza output (per uso daemon) |
| `-H, --history PERIOD` | Mostra storico (es. `24h`, `1h`) |
| `-a, --analyze HOURS` | Analisi completa con tendenze |
| `-c, --compare TS TS` | Confronta due timestamp |
| `--alert-webhook URL` | Invia avvisi POST all'URL webhook sulle transizioni di stato |

## Output

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

Il monitoraggio della potenza usa Apple IOReport Energy Model per leggere il consumo energetico di GPU, CPU, ANE e DRAM — nessun sudo necessario. Vedi [Metodologia](../methodology.md#power-measurement) per i dettagli di validazione.

## Avvisi webhook

Quando viene fornito `--alert-webhook URL`, asiai invierà un avviso JSON via POST all'URL webhook ogni volta che viene rilevata una **transizione di stato**:

| Tipo di avviso | Trigger | Severità |
|------------|---------|----------|
| `mem_pressure_warn` | Pressione memoria: normal → warn | warning |
| `mem_pressure_critical` | Pressione memoria: normal/warn → critical | critical |
| `thermal_degraded` | Livello termico: nominal → fair/serious/critical | warning/critical |
| `engine_down` | Motore raggiungibile, ora non raggiungibile | critical |

Gli avvisi usano un **raffreddamento di 5 minuti** per tipo per prevenire lo spam. Ogni avviso viene salvato in SQLite per lo storico.

### Payload webhook

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

## Archiviazione dati

Tutti gli snapshot sono salvati in SQLite (`~/.local/share/asiai/metrics.db`) con conservazione automatica di 90 giorni.
