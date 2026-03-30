---
description: Monitoramento contínuo de utilização de GPU, estado térmico e pressão de memória para Apple Silicon. Sem sudo necessário.
---

# asiai monitor

Snapshot de métricas de sistema e inferência, armazenado em SQLite.

## Uso

```bash
asiai monitor [options]
```

## Opções

| Opção | Descrição |
|-------|-----------|
| `-w, --watch SEC` | Atualizar a cada SEC segundos |
| `-q, --quiet` | Coletar e armazenar sem saída (para uso como daemon) |
| `-H, --history PERIOD` | Mostrar histórico (ex: `24h`, `1h`) |
| `-a, --analyze HOURS` | Análise abrangente com tendências |
| `-c, --compare TS TS` | Comparar dois timestamps |
| `--alert-webhook URL` | Enviar alertas via POST para URL de webhook em transições de estado |

## Saída

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

O monitoramento de energia usa o framework Apple IOReport Energy Model para ler o consumo de energia da GPU, CPU, ANE e DRAM — sem sudo necessário. Veja [Metodologia](../methodology.md#power-measurement) para detalhes de validação.

## Webhooks de alerta

Quando `--alert-webhook URL` é fornecido, o asiai envia alertas JSON via POST para a URL do webhook sempre que uma **transição de estado** é detectada:

| Tipo de alerta | Gatilho | Severidade |
|----------------|---------|------------|
| `mem_pressure_warn` | Pressão de memória: normal → warn | warning |
| `mem_pressure_critical` | Pressão de memória: normal/warn → critical | critical |
| `thermal_degraded` | Nível térmico: nominal → fair/serious/critical | warning/critical |
| `engine_down` | Motor estava acessível, agora inacessível | critical |

Os alertas usam um **cooldown de 5 minutos** por tipo para evitar spam. Cada alerta é armazenado em SQLite para histórico.

### Payload do webhook

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

### Uso com daemon

```bash
asiai daemon start monitor --alert-webhook https://hooks.slack.com/services/...
```

## Armazenamento de dados

Todos os snapshots são armazenados em SQLite (`~/.local/share/asiai/metrics.db`) com retenção automática de 90 dias.
