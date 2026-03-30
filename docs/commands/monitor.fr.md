---
description: Monitoring continu de l'utilisation GPU, de l'état thermique et de la pression mémoire pour Apple Silicon. Sans sudo.
---

# asiai monitor

Snapshot des métriques système et d'inférence, stocké dans SQLite.

## Utilisation

```bash
asiai monitor [options]
```

## Options

| Option | Description |
|--------|-------------|
| `-w, --watch SEC` | Rafraîchir toutes les SEC secondes |
| `-q, --quiet` | Collecter et stocker sans sortie (pour le daemon) |
| `-H, --history PERIOD` | Afficher l'historique (ex. `24h`, `1h`) |
| `-a, --analyze HOURS` | Analyse complète avec tendances |
| `-c, --compare TS TS` | Comparer deux horodatages |
| `--alert-webhook URL` | Envoyer les alertes par POST à l'URL webhook lors des transitions d'état |

## Sortie

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

Le monitoring de puissance utilise le framework Energy Model IOReport d'Apple pour lire la consommation GPU, CPU, ANE et DRAM — sans sudo requis. Voir [Méthodologie](../methodology.md#mesure-de-puissance) pour les détails de validation.

## Webhooks d'alerte

Quand `--alert-webhook URL` est fourni, asiai envoie une alerte JSON par POST à l'URL webhook à chaque **transition d'état** détectée :

| Type d'alerte | Déclencheur | Sévérité |
|---------------|-------------|----------|
| `mem_pressure_warn` | Pression mémoire : normal → warn | warning |
| `mem_pressure_critical` | Pression mémoire : normal/warn → critical | critical |
| `thermal_degraded` | Niveau thermique : nominal → fair/serious/critical | warning/critical |
| `engine_down` | Le moteur était accessible, maintenant inaccessible | critical |

Les alertes ont un **délai de 5 minutes** par type pour éviter le spam. Chaque alerte est stockée dans SQLite pour l'historique.

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

### Utilisation avec le daemon

```bash
asiai daemon start monitor --alert-webhook https://hooks.slack.com/services/...
```

## Stockage des données

Tous les snapshots sont stockés dans SQLite (`~/.local/share/asiai/metrics.db`) avec une rétention automatique de 90 jours.
