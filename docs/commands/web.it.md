---
description: Dashboard di monitoraggio LLM in tempo reale nel browser. Metriche GPU, stato motori, storico prestazioni. Nessuna configurazione necessaria.
---

# asiai web

Avvia la dashboard web per monitoraggio visuale e benchmarking.

## Uso

```bash
asiai web
asiai web --port 9000
asiai web --host 0.0.0.0
asiai web --no-open
```

## Opzioni

| Opzione | Default | Descrizione |
|--------|---------|-------------|
| `--port` | `8899` | Porta HTTP di ascolto |
| `--host` | `127.0.0.1` | Host di bind |
| `--no-open` | | Non aprire il browser automaticamente |
| `--db` | `~/.local/share/asiai/asiai.db` | Percorso al database SQLite |

## Requisiti

La dashboard web richiede dipendenze aggiuntive:

```bash
pip install asiai[web]
# oppure installa tutto:
pip install asiai[all]
```

## Pagine

### Dashboard (`/`)

Panoramica del sistema con stato motori, modelli caricati, utilizzo memoria e ultimi risultati benchmark.

### Benchmark (`/bench`)

Esegui benchmark cross-engine direttamente dal browser:

- Pulsante **Quick Bench** — 1 prompt, 1 esecuzione, ~15 secondi
- Opzioni avanzate: motori, prompt, esecuzioni, dimensione contesto (4K/16K/32K/64K), potenza
- Progresso in tempo reale via SSE
- Tabella risultati con evidenziazione del vincitore
- Grafici throughput e TTFT
- **Scheda condivisibile** — generata automaticamente dopo il benchmark (PNG via API, SVG come fallback)
- **Sezione condivisione** — copia link, scarica PNG/SVG, condividi su X/Reddit, esporta JSON

### Storico (`/history`)

Visualizza benchmark e metriche di sistema nel tempo:

- Grafici sistema: carico CPU, % memoria, utilizzo GPU (con dettaglio renderer/tiler)
- Attività motori: connessioni TCP, richieste in elaborazione, % utilizzo cache KV
- Grafici benchmark: throughput (tok/s) e TTFT per motore
- Metriche processo: CPU % del motore e memoria RSS durante le esecuzioni benchmark
- Filtra per intervallo temporale (1h / 24h / 7d / 30d / 90d) o intervallo date personalizzato
- Tabella dati con indicazione dimensione contesto (es. "code (64K ctx)")

### Monitor (`/monitor`)

Monitoraggio sistema in tempo reale con aggiornamento ogni 5 secondi:

- Sparkline carico CPU
- Indicatore memoria
- Stato termico
- Lista modelli caricati

### Doctor (`/doctor`)

Controllo di stato interattivo per sistema, motori e database. Stessi controlli di `asiai doctor` con interfaccia visuale.

## Endpoint API

La dashboard web espone endpoint API REST per accesso programmatico.

### `GET /api/status`

Controllo rapido dello stato. Cache 10s, risponde in < 500ms.

```json
{
  "status": "ok",
  "ts": 1709700000,
  "uptime": 86400,
  "engines": {"ollama": true, "lmstudio": false},
  "memory_pressure": "normal",
  "thermal_level": "nominal"
}
```

Valori stato: `ok` (tutti i motori raggiungibili), `degraded` (alcuni inattivi), `error` (tutti inattivi).

### `GET /api/snapshot`

Snapshot completo sistema + motori. Cache 5s. Include carico CPU, memoria, stato termico e stato per motore con modelli caricati.

### `GET /api/benchmarks`

Risultati benchmark con filtri. Restituisce dati per esecuzione inclusi tok/s, TTFT, potenza, context_size, engine_version.

| Parametro | Default | Descrizione |
|-----------|---------|-------------|
| `hours` | `168` | Intervallo temporale in ore (0 = tutto) |
| `model` | | Filtra per nome modello |
| `engine` | | Filtra per nome motore |
| `since` / `until` | | Intervallo timestamp Unix (sovrascrive hours) |

### `GET /api/engine-history`

Storico stato motori (raggiungibilità, connessioni TCP, cache KV, token predetti).

| Parametro | Default | Descrizione |
|-----------|---------|-------------|
| `hours` | `168` | Intervallo temporale in ore |
| `engine` | | Filtra per nome motore |

### `GET /api/benchmark-process`

Metriche CPU e memoria a livello processo dalle esecuzioni benchmark (conservazione 7 giorni).

| Parametro | Default | Descrizione |
|-----------|---------|-------------|
| `hours` | `168` | Intervallo temporale in ore |
| `engine` | | Filtra per nome motore |

### `GET /api/metrics`

Formato di esposizione Prometheus. Gauge che coprono metriche di sistema, motore, modello e benchmark.

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'asiai'
    static_configs:
      - targets: ['localhost:8899']
    metrics_path: '/api/metrics'
    scrape_interval: 30s
```

Le metriche includono:

| Metrica | Tipo | Descrizione |
|--------|------|-------------|
| `asiai_cpu_load_1m` | gauge | Media carico CPU (1 min) |
| `asiai_memory_used_bytes` | gauge | Memoria utilizzata |
| `asiai_thermal_speed_limit_pct` | gauge | Limite velocità CPU % |
| `asiai_engine_reachable{engine}` | gauge | Raggiungibilità motore (0/1) |
| `asiai_engine_models_loaded{engine}` | gauge | Conteggio modelli caricati |
| `asiai_engine_tcp_connections{engine}` | gauge | Connessioni TCP stabilite |
| `asiai_engine_requests_processing{engine}` | gauge | Richieste in elaborazione |
| `asiai_engine_kv_cache_usage_ratio{engine}` | gauge | Rapporto riempimento cache KV (0-1) |
| `asiai_engine_tokens_predicted_total{engine}` | counter | Totale cumulativo token predetti |
| `asiai_model_vram_bytes{engine,model}` | gauge | VRAM per modello |
| `asiai_bench_tok_per_sec{engine,model}` | gauge | Ultimo benchmark tok/s |

## Note

- La dashboard si collega a `127.0.0.1` di default (solo localhost)
- Usa `--host 0.0.0.0` per esporre in rete (es. per monitoraggio remoto)
- La porta `8899` è scelta per evitare conflitti con le porte dei motori di inferenza
