---
description: Echtzeit-LLM-Monitoring-Dashboard im Browser. GPU-Metriken, Engine-Gesundheit, Leistungsverlauf. Keine Einrichtung erforderlich.
---

# asiai web

Web-Dashboard für visuelles Monitoring und Benchmarking starten.

## Verwendung

```bash
asiai web
asiai web --port 9000
asiai web --host 0.0.0.0
asiai web --no-open
```

## Optionen

| Option | Standard | Beschreibung |
|--------|---------|-------------|
| `--port` | `8899` | HTTP-Port |
| `--host` | `127.0.0.1` | Bind-Adresse |
| `--no-open` | | Browser nicht automatisch öffnen |
| `--db` | `~/.local/share/asiai/asiai.db` | Pfad zur SQLite-Datenbank |

## Voraussetzungen

Das Web-Dashboard benötigt zusätzliche Abhängigkeiten:

```bash
pip install asiai[web]
# oder alles installieren:
pip install asiai[all]
```

## Seiten

### Dashboard (`/`)

Systemübersicht mit Engine-Status, geladenen Modellen, Speichernutzung und letzten Benchmark-Ergebnissen.

### Benchmark (`/bench`)

Engine-übergreifende Benchmarks direkt aus dem Browser starten:

- **Quick Bench**-Button — 1 Prompt, 1 Durchlauf, ~15 Sekunden
- Erweiterte Optionen: Engines, Prompts, Durchläufe, Kontextgröße (4K/16K/32K/64K), Leistung
- Live-Fortschritt über SSE
- Ergebnistabelle mit Gewinner-Hervorhebung
- Durchsatz- und TTFT-Diagramme
- **Teilbare Karte** — automatisch nach Benchmark generiert (PNG über API, SVG-Fallback)
- **Teilen-Bereich** — Link kopieren, PNG/SVG herunterladen, auf X/Reddit teilen, JSON exportieren

### Verlauf (`/history`)

Benchmark- und Systemmetriken über die Zeit visualisieren:

- Systemdiagramme: CPU-Last, Speicher %, GPU-Auslastung (mit Renderer/Tiler-Aufschlüsselung)
- Engine-Aktivität: TCP-Verbindungen, verarbeitete Anfragen, KV-Cache-Nutzung %
- Benchmark-Diagramme: Durchsatz (tok/s) und TTFT pro Engine
- Prozessmetriken: Engine-CPU % und RSS-Speicher während Benchmark-Durchläufen
- Nach Zeitbereich filtern (1h / 24h / 7d / 30d / 90d) oder benutzerdefinierter Datumsbereich
- Datentabelle mit Kontextgrößenangabe (z.B. „code (64K ctx)")

### Monitor (`/monitor`)

Echtzeit-Systemüberwachung mit 5-Sekunden-Aktualisierung:

- CPU-Last-Sparkline
- Speicheranzeige
- Thermischer Zustand
- Liste geladener Modelle

### Doctor (`/doctor`)

Interaktiver Gesundheitscheck für System, Engines und Datenbank. Dieselben Prüfungen wie `asiai doctor` mit visueller Oberfläche.

## API-Endpunkte

Das Web-Dashboard bietet REST-API-Endpunkte für programmatischen Zugriff.

### `GET /api/status`

Leichtgewichtiger Gesundheitscheck. 10s gecacht, antwortet in < 500ms.

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

Statuswerte: `ok` (alle Engines erreichbar), `degraded` (einige nicht erreichbar), `error` (alle nicht erreichbar).

### `GET /api/snapshot`

Vollständiger System- + Engine-Snapshot. 5s gecacht. Enthält CPU-Last, Speicher, thermischen Zustand und Engine-Status mit geladenen Modellen.

### `GET /api/benchmarks`

Benchmark-Ergebnisse mit Filtern. Gibt Daten pro Durchlauf zurück, einschließlich tok/s, TTFT, Leistung, context_size, engine_version.

| Parameter | Standard | Beschreibung |
|-----------|---------|-------------|
| `hours` | `168` | Zeitbereich in Stunden (0 = alle) |
| `model` | | Nach Modellname filtern |
| `engine` | | Nach Engine-Name filtern |
| `since` / `until` | | Unix-Zeitstempel-Bereich (überschreibt hours) |

### `GET /api/engine-history`

Engine-Statusverlauf (Erreichbarkeit, TCP-Verbindungen, KV Cache, vorhergesagte Tokens).

| Parameter | Standard | Beschreibung |
|-----------|---------|-------------|
| `hours` | `168` | Zeitbereich in Stunden |
| `engine` | | Nach Engine-Name filtern |

### `GET /api/benchmark-process`

CPU- und Speichermetriken auf Prozessebene von Benchmark-Durchläufen (7-Tage-Aufbewahrung).

| Parameter | Standard | Beschreibung |
|-----------|---------|-------------|
| `hours` | `168` | Zeitbereich in Stunden |
| `engine` | | Nach Engine-Name filtern |

### `GET /api/metrics`

Prometheus-Expositionsformat. Gauges für System-, Engine-, Modell- und Benchmark-Metriken.

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'asiai'
    static_configs:
      - targets: ['localhost:8899']
    metrics_path: '/api/metrics'
    scrape_interval: 30s
```

Metriken umfassen:

| Metrik | Typ | Beschreibung |
|--------|-----|-------------|
| `asiai_cpu_load_1m` | gauge | CPU-Lastdurchschnitt (1 Min.) |
| `asiai_memory_used_bytes` | gauge | Genutzter Speicher |
| `asiai_thermal_speed_limit_pct` | gauge | CPU-Geschwindigkeitslimit % |
| `asiai_engine_reachable{engine}` | gauge | Engine-Erreichbarkeit (0/1) |
| `asiai_engine_models_loaded{engine}` | gauge | Anzahl geladener Modelle |
| `asiai_engine_tcp_connections{engine}` | gauge | Hergestellte TCP-Verbindungen |
| `asiai_engine_requests_processing{engine}` | gauge | Aktuell verarbeitete Anfragen |
| `asiai_engine_kv_cache_usage_ratio{engine}` | gauge | KV-Cache-Füllungsrate (0-1) |
| `asiai_engine_tokens_predicted_total{engine}` | counter | Kumulative vorhergesagte Tokens |
| `asiai_model_vram_bytes{engine,model}` | gauge | VRAM pro Modell |
| `asiai_bench_tok_per_sec{engine,model}` | gauge | Letzter Benchmark tok/s |

## Hinweise

- Das Dashboard bindet standardmäßig an `127.0.0.1` (nur localhost)
- Verwenden Sie `--host 0.0.0.0` zur Freigabe im Netzwerk (z.B. für Remote-Monitoring)
- Port `8899` wurde gewählt, um Konflikte mit Inferenz-Engine-Ports zu vermeiden
