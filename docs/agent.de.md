---
description: Geben Sie Ihren KI-Agenten Echtzeit-Einblick in die LLM-Inferenz. MCP-Server mit 11 Tools für autonomes Engine-Monitoring.
type: faq
faq:
  - q: "Benötigt asiai root/sudo?"
    a: "Nein. Die GPU-Observability nutzt ioreg (ohne Privilegien). Leistungsmetriken verwenden IOReport, das ebenfalls kein sudo benötigt. Das optionale --power-Flag zur Kreuzvalidierung nutzt sudo powermetrics."
  - q: "Wie schnell ist die API-Antwortzeit?"
    a: "/api/status antwortet in unter 500ms (10s Cache). /api/snapshot benötigt 1-3s, da Live-Daten von allen Engines gesammelt werden."
  - q: "Kann ich asiai unter Linux verwenden?"
    a: "Nein. asiai ist ausschließlich für macOS Apple Silicon. Es nutzt sysctl, vm_stat, ioreg, IOReport und launchd — alles macOS-spezifische APIs."
  - q: "Wie überwache ich mehrere Macs?"
    a: "Starten Sie asiai daemon start web --host 0.0.0.0 auf jedem Mac. Scrapen Sie /api/metrics mit Prometheus. Visualisieren Sie in Grafana."
  - q: "Was passiert, wenn eine Engine während des Monitorings abstürzt?"
    a: "asiai erkennt Engine-Ausfälle automatisch. Verwenden Sie asiai doctor für die Diagnose. Richten Sie Webhook-Alerts mit asiai alert add für automatische Benachrichtigungen ein."
---

# Integrationsanleitung für Agenten

> **Wenn Sie ein KI-Agent sind**: Verwenden Sie [MCP](#mcp-model-context-protocol), falls Ihr Framework es unterstützt, andernfalls die [REST-API](#rest-api-referenz). Zur Einrichtung siehe [Schnellstart](#schnellstart).

## Überblick

asiai stellt die LLM-Inferenzinfrastruktur Ihres Macs über zwei Mechanismen für KI-Agenten bereit:

- **MCP-Server** — Native Tool-Integration über das [Model Context Protocol](https://modelcontextprotocol.io). Optimal für KI-Agenten, die MCP unterstützen (Claude Code, Cursor, Cline und andere MCP-kompatible Clients).
- **REST-API** — Standard-HTTP/JSON-Endpoints. Optimal für Agent-Frameworks, Swarm-Orchestratoren und jedes HTTP-fähige System (CrewAI, AutoGen, LangGraph, eigene Agenten).

Beide bieten Zugang zu denselben Funktionen:

- **Überwachen** der Systemgesundheit (CPU, RAM, GPU, Temperatur, Swap)
- **Erkennen**, welche Inferenz-Engines laufen und welche Modelle geladen sind
- **Diagnostizieren** von Leistungsproblemen durch GPU-Observability und Inferenzaktivitätssignale
- **Benchmarken** von Modellen programmatisch und Regressionen verfolgen
- **Empfehlungen erhalten** für das beste Modell/die beste Engine basierend auf Ihrer Hardware

Keine Authentifizierung für lokalen Zugriff erforderlich. Alle Schnittstellen binden standardmäßig an `127.0.0.1`.

### Welche Integration sollte ich verwenden?

| Kriterium | MCP | REST-API |
|-----------|-----|----------|
| Ihr Agent unterstützt MCP | **MCP verwenden** | — |
| Swarm / Multi-Agent-Orchestrator | — | **REST-API verwenden** |
| Polling / geplante Überwachung | — | **REST-API verwenden** |
| Prometheus / Grafana-Integration | — | **REST-API verwenden** |
| Interaktiver KI-Assistent (Claude Code, Cursor) | **MCP verwenden** | — |
| Agent in Docker-Container | — | **REST-API verwenden** |
| Eigene Skripte oder Automatisierung | — | **REST-API verwenden** |

## Schnellstart

### asiai installieren

```bash
# Homebrew (empfohlen)
brew tap druide67/tap && brew install asiai

# pip (mit MCP-Unterstützung)
pip install "asiai[mcp]"

# pip (nur REST-API)
pip install asiai
```

### Option A: MCP-Server (für MCP-kompatible Agenten)

```bash
# MCP-Server starten (stdio-Transport — verwendet von Claude Code, Cursor, etc.)
asiai mcp
```

Kein manueller Serverstart nötig — der MCP-Client startet `asiai mcp` automatisch. Siehe [MCP-Einrichtung](#mcp-model-context-protocol) weiter unten.

### Option B: REST-API (für HTTP-basierte Agenten)

```bash
# Vordergrund (Entwicklung)
asiai web --no-open

# Hintergrund-Daemon (Produktion)
asiai daemon start web
```

Die API ist unter `http://127.0.0.1:8899` verfügbar. Der Port ist mit `--port` konfigurierbar:

```bash
asiai daemon start web --port 8642
```

Für Fernzugriff (z.B. KI-Agent auf einem anderen Rechner oder aus einem Docker-Container):

```bash
asiai daemon start web --host 0.0.0.0
```

> **Hinweis:** Wenn Ihr Agent in Docker läuft, ist `127.0.0.1` nicht erreichbar. Verwenden Sie die Netzwerk-IP des Hosts (z.B. `192.168.0.16`) oder `host.docker.internal` bei Docker Desktop für Mac.

### Überprüfung

```bash
# REST-API
curl http://127.0.0.1:8899/api/status

# MCP (verfügbare Tools auflisten)
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | asiai mcp
```

---

## MCP (Model Context Protocol)

asiai implementiert einen [MCP-Server](https://modelcontextprotocol.io), der Inferenz-Monitoring als native Tools bereitstellt. Jeder MCP-kompatible Client kann sich verbinden und diese Tools direkt nutzen — kein HTTP-Setup, keine URL-Verwaltung.

### Einrichtung

#### Lokal (gleicher Rechner)

Fügen Sie Folgendes zur MCP-Client-Konfiguration hinzu (z.B. `~/.claude/settings.json` für Claude Code):

```json
{
  "mcpServers": {
    "asiai": {
      "command": "asiai",
      "args": ["mcp"]
    }
  }
}
```

Falls asiai in einer virtuellen Umgebung installiert ist:

```json
{
  "mcpServers": {
    "asiai": {
      "command": "/path/to/.venv/bin/asiai",
      "args": ["mcp"]
    }
  }
}
```

#### Remote (anderer Rechner via SSH)

```json
{
  "mcpServers": {
    "asiai": {
      "command": "ssh",
      "args": [
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        "your-mac-host",
        "cd /path/to/asiai && .venv/bin/asiai mcp"
      ]
    }
  }
}
```

#### SSE-Transport (Netzwerk)

Für Umgebungen, die HTTP-basierten MCP-Transport bevorzugen:

```bash
asiai mcp --transport sse --host 127.0.0.1 --port 8900
```

### MCP-Tools-Referenz

Alle Tools geben JSON zurück. Nur-Lese-Tools antworten in < 2 Sekunden. `run_benchmark` ist die einzige aktive Operation.

| Tool | Beschreibung | Parameter |
|------|-------------|-----------|
| `check_inference_health` | Schneller Gesundheitscheck — Engines online/offline, Speicherdruck, Temperatur, GPU-Auslastung | — |
| `get_inference_snapshot` | Vollständiger Systemzustands-Snapshot (in SQLite für Verlauf gespeichert) | — |
| `list_models` | Alle geladenen Modelle über alle Engines mit VRAM, Quantisierung, Kontextlänge | — |
| `detect_engines` | 3-Schichten-Erkennung: Konfiguration, Port-Scan, Prozesserkennung. Findet Engines auf nicht-standardmäßigen Ports automatisch. | — |
| `run_benchmark` | Benchmark auf einem Modell oder Modellvergleich ausführen. Ratenlimitiert: 1 pro 60 Sekunden | `model` (optional), `runs` (1–10, Standard 3), `compare` (String-Liste, optional, gegenseitig exklusiv mit `model`, max 8) |
| `get_recommendations` | Hardware-spezifische Modell-/Engine-Empfehlungen basierend auf Ihrem Chip und RAM | — |
| `diagnose` | Diagnosetests ausführen (System, Engines, Daemon-Gesundheit) | — |
| `get_metrics_history` | Historische Systemmetriken aus SQLite | `hours` (1–168, Standard 24) |
| `get_benchmark_history` | Historische Benchmark-Ergebnisse | `hours` (1–720, Standard 24), `model` (optional), `engine` (optional) |
| `compare_engines` | Rangbasierter Engine-Vergleich mit Urteil für ein bestimmtes Modell; unterstützt Multi-Modell-Vergleich aus dem Verlauf | `model` (erforderlich) |
| `refresh_engines` | Engines neu erkennen ohne den MCP-Server neu zu starten | — |

### MCP-Ressourcen

Statische Daten-Endpoints, verfügbar ohne Tool-Aufruf:

| URI | Beschreibung |
|-----|-------------|
| `asiai://status` | Aktueller Gesundheitszustand (Speicher, Temperatur, GPU) |
| `asiai://models` | Alle geladenen Modelle über alle Engines |
| `asiai://system` | Hardware-Informationen (Chip, RAM, Kerne, OS, Betriebszeit) |

### MCP-Sicherheit

- **Kein sudo**: Leistungsmetriken sind im MCP-Modus deaktiviert (`power=False` erzwungen)
- **Ratenlimitierung**: Benchmarks sind auf 1 pro 60 Sekunden limitiert
- **Eingabebegrenzung**: `hours` begrenzt auf 1–168, `runs` begrenzt auf 1–10
- **Standardmäßig lokal**: stdio-Transport hat keine Netzwerkexposition; SSE bindet an `127.0.0.1`

### MCP-Einschränkungen

- **Keine Wiederverbindung**: Wenn die SSH-Verbindung abbricht (Netzwerkproblem, Mac-Ruhezustand), stirbt der MCP-Server und der Client muss sich manuell neu verbinden. Für unbeaufsichtigtes Monitoring ist die REST-API mit Polling belastbarer.
- **Einzelner Client**: Der stdio-Transport bedient jeweils nur einen Client. Verwenden Sie SSE-Transport, wenn mehrere Clients gleichzeitigen Zugriff benötigen.

---

## REST-API-Referenz

Die API von asiai ist **schreibgeschützt** — sie überwacht und berichtet, steuert aber keine Engines. Zum Laden/Entladen von Modellen verwenden Sie die nativen Engine-Befehle (`ollama pull`, `lms load`, etc.).

Alle Endpoints geben JSON mit HTTP 200 zurück. Wenn eine Engine nicht erreichbar ist, gibt die Antwort trotzdem 200 mit `"running": false` für diese Engine zurück — die API selbst schlägt nicht fehl.

| Endpoint | Typische Antwortzeit | Empfohlener Timeout |
|----------|---------------------|---------------------|
| `GET /api/status` | < 500ms (10s Cache) | 2s |
| `GET /api/snapshot` | 1–3s (Live-Erfassung) | 10s |
| `GET /api/metrics` | < 500ms | 2s |
| `GET /api/history` | < 500ms | 5s |
| `GET /api/engine-history` | < 500ms | 5s |

### `GET /api/status`

Schneller Gesundheitscheck. 10 Sekunden Cache. Antwortzeit < 500ms.

**Antwort:**

```json
{
  "hostname": "mac-mini",
  "chip": "Apple M4 Pro",
  "ram_gb": 64.0,
  "cpu_percent": 12.3,
  "memory_pressure": "normal",
  "gpu_utilization_percent": 45.2,
  "engines": {
    "ollama": {
      "running": true,
      "models_loaded": 2,
      "port": 11434
    },
    "lmstudio": {
      "running": true,
      "models_loaded": 1,
      "port": 1234
    }
  },
  "asiai_version": "1.0.1",
  "uptime_seconds": 86400
}
```

### `GET /api/snapshot`

Vollständiger Systemzustand. Enthält alles aus `/api/status` plus detaillierte Modellinformationen, GPU-Metriken und Temperaturdaten.

**Antwort:**

```json
{
  "system": {
    "hostname": "mac-mini",
    "chip": "Apple M4 Pro",
    "cores_p": 12,
    "cores_e": 4,
    "gpu_cores": 20,
    "ram_total_gb": 64.0,
    "ram_used_gb": 41.2,
    "ram_percent": 64.4,
    "swap_used_gb": 0.0,
    "memory_pressure": "normal",
    "cpu_percent": 12.3,
    "thermal_state": "nominal",
    "gpu_utilization_percent": 45.2,
    "gpu_renderer_percent": 38.1,
    "gpu_tiler_percent": 12.4,
    "gpu_memory_allocated_bytes": 8589934592
  },
  "engines": [
    {
      "name": "ollama",
      "running": true,
      "port": 11434,
      "models": [
        {
          "name": "qwen3.5:latest",
          "size_params": "35B",
          "size_vram_bytes": 21474836480,
          "quantization": "Q4_K_M",
          "context_length": 32768
        }
      ]
    }
  ],
  "timestamp": "2026-03-09T14:30:00Z"
}
```

### `GET /api/metrics`

Prometheus-kompatible Metriken. Scrapen Sie mit Prometheus, Datadog oder jedem kompatiblen Tool.

**Antwort (text/plain):**

```
# HELP asiai_cpu_percent CPU usage percentage
# TYPE asiai_cpu_percent gauge
asiai_cpu_percent 12.3

# HELP asiai_ram_used_gb RAM used in GB
# TYPE asiai_ram_used_gb gauge
asiai_ram_used_gb 41.2

# HELP asiai_gpu_utilization_percent GPU utilization percentage
# TYPE asiai_gpu_utilization_percent gauge
asiai_gpu_utilization_percent 45.2

# HELP asiai_engine_up Engine availability (1=up, 0=down)
# TYPE asiai_engine_up gauge
asiai_engine_up{engine="ollama"} 1
asiai_engine_up{engine="lmstudio"} 1

# HELP asiai_models_loaded Number of models loaded per engine
# TYPE asiai_models_loaded gauge
asiai_models_loaded{engine="ollama"} 2
```

### `GET /api/history?hours=N`

Historische Systemmetriken aus SQLite. Standard: `hours=24`. Maximum: `hours=2160` (90 Tage).

**Antwort:**

```json
{
  "points": [
    {
      "timestamp": "2026-03-09T14:00:00Z",
      "cpu_percent": 15.2,
      "ram_used_gb": 40.1,
      "ram_percent": 62.7,
      "swap_used_gb": 0.0,
      "memory_pressure": "normal",
      "thermal_state": "nominal",
      "gpu_utilization_percent": 42.0,
      "gpu_renderer_percent": 35.0,
      "gpu_tiler_percent": 10.0,
      "gpu_memory_allocated_bytes": 8589934592
    }
  ],
  "count": 144,
  "hours": 24
}
```

### `GET /api/engine-history?engine=X&hours=N`

Engine-spezifischer Aktivitätsverlauf. Nützlich zur Erkennung von Inferenzmustern.

**Parameter:**

| Parameter | Erforderlich | Standard | Beschreibung |
|-----------|-------------|----------|-------------|
| `engine`  | Ja          | —        | Engine-Name (ollama, lmstudio, etc.) |
| `hours`   | Nein        | 24       | Zeitbereich |

**Antwort:**

```json
{
  "engine": "ollama",
  "points": [
    {
      "timestamp": "2026-03-09T14:00:00Z",
      "running": true,
      "tcp_connections": 3,
      "requests_processing": 1,
      "kv_cache_usage_percent": 45.2
    }
  ],
  "count": 144,
  "hours": 24
}
```

## Metriken interpretieren

### Schwellenwerte für die Systemgesundheit

| Metrik | Normal | Warnung | Kritisch |
|--------|--------|---------|----------|
| `memory_pressure` | `normal` | `warn` | `critical` |
| `ram_percent` | < 75% | 75–90% | > 90% |
| `swap_used_gb` | 0 | 0,1–2,0 | > 2,0 |
| `thermal_state` | `nominal` | `fair` | `serious` / `critical` |
| `cpu_percent` | < 80% | 80–95% | > 95% |

### GPU-Schwellenwerte

| Metrik | Leerlauf | Aktive Inferenz | Überlastet |
|--------|----------|-----------------|------------|
| `gpu_utilization_percent` | 0–5% | 20–80% | > 90% dauerhaft |
| `gpu_renderer_percent` | 0–5% | 15–70% | > 85% dauerhaft |
| `gpu_memory_allocated_bytes` | < 1 GB | 2–48 GB | > 90% des RAM |

> **Wichtig:** `gpu_utilization_percent = 0` bedeutet, dass die GPU im Leerlauf ist, nicht defekt. Ein Wert von `-1.0` bedeutet, dass die Metrik nicht verfügbar ist (z.B. nicht unterstützte Hardware oder Erfassungsfehler) — interpretieren Sie dies nicht als „GPU tot".

### Inferenzleistung

| Metrik | Ausgezeichnet | Gut | Verschlechtert |
|--------|--------------|-----|----------------|
| `tok/s` (7B-Modell) | > 80 | 40–80 | < 40 |
| `tok/s` (35B-Modell) | > 40 | 20–40 | < 20 |
| `tok/s` (70B-Modell) | > 15 | 8–15 | < 8 |
| `TTFT` | < 100ms | 100–500ms | > 500ms |

## Diagnostische Entscheidungsbäume

### Langsame Generierung (niedriger tok/s)

```
tok/s unter Erwartung?
├── memory_pressure prüfen
│   ├── "critical" → Modelle swappen auf Festplatte. Modelle entladen oder RAM hinzufügen.
│   └── "normal" → Weiter
├── thermal_state prüfen
│   ├── "serious"/"critical" → Thermisches Throttling. Abkühlen, Belüftung prüfen.
│   └── "nominal" → Weiter
├── gpu_utilization_percent prüfen
│   ├── < 10% → GPU wird nicht genutzt. Engine-Konfiguration prüfen (num_gpu-Schichten).
│   ├── > 90% → GPU gesättigt. Gleichzeitige Anfragen reduzieren.
│   └── 20-80% → Normal. Quantisierung und Kontextgröße prüfen.
└── swap_used_gb prüfen
    ├── > 0 → Modell zu groß für RAM. Kleinere Quantisierung verwenden.
    └── 0 → Engine-Version prüfen, andere Engine versuchen.
```

### Engine antwortet nicht

```
engine.running == false?
├── Prüfen ob Prozess existiert: lsof -i :<port>
│   ├── Kein Prozess → Engine abgestürzt. Neu starten.
│   └── Prozess existiert aber antwortet nicht → Engine hängt.
├── memory_pressure prüfen
│   ├── "critical" → OOM-Kill. Erst andere Modelle entladen.
│   └── "normal" → Engine-Logs prüfen.
└── Versuchen: asiai doctor (umfassende Diagnose)
```

### Hoher Speicherdruck / VRAM-Überlauf

```
memory_pressure == "warn" oder "critical"?
├── swap_used_gb prüfen
│   ├── > 2 GB → VRAM-Überlauf. Modelle passen nicht in Unified Memory.
│   │   ├── Latenz wird 5–50× schlechter (Festplatten-Swap).
│   │   ├── Modelle entladen: ollama rm <model>, lms unload
│   │   └── Oder kleinere Quantisierung verwenden (Q4_K_M → Q3_K_S).
│   └── < 2 GB → Handhabbar, aber genau beobachten.
├── Geladene Modelle über alle Engines prüfen
│   ├── Mehrere große Modelle → Unbenutzte Modelle entladen
│   │   ├── Ollama: ollama rm <model> oder auf Auto-Entladung warten
│   │   └── LM Studio: über UI entladen oder lms unload
│   └── Einzelnes Modell > 80% RAM → Kleinere Quantisierung verwenden
└── gpu_memory_allocated_bytes prüfen
    └── Mit ram_total_gb vergleichen. Wenn > 80%, wird das nächste Modell-Laden Swap auslösen.
```

## Inferenzaktivitätssignale

asiai erkennt aktive Inferenz durch mehrere Signale:

### GPU-Auslastung

```
GET /api/snapshot → system.gpu_utilization_percent
```

- **< 5%**: Keine Inferenz aktiv
- **20–80%**: Aktive Inferenz (normaler Bereich für Apple Silicon Unified Memory)
- **> 90%**: Intensive Inferenz oder mehrere gleichzeitige Anfragen

### TCP-Verbindungen

```
GET /api/engine-history?engine=ollama&hours=1
```

Jede aktive Inferenzanfrage hält eine TCP-Verbindung aufrecht. Ein Anstieg der `tcp_connections` zeigt aktive Generierung an.

### Engine-spezifische Metriken

Für Engines, die `/metrics` bereitstellen (llama.cpp, vllm-mlx):

- `requests_processing > 0`: Aktive Inferenz
- `kv_cache_usage_percent > 0`: Modell hat aktiven Kontext

### Korrelationsmuster

Die zuverlässigste Inferenzerkennung kombiniert mehrere Signale:

```python
snapshot = get_snapshot()
gpu_active = snapshot["system"]["gpu_utilization_percent"] > 15
engine_busy = any(
    e.get("tcp_connections", 0) > 0
    for e in snapshot.get("engine_status", [])
)
inference_running = gpu_active and engine_busy
```

## Codebeispiele

### Gesundheitscheck (Python, nur Standardbibliothek)

```python
import json
import urllib.request

ASIAI_URL = "http://127.0.0.1:8899"  # Docker: Host-IP oder host.docker.internal verwenden

def check_health():
    """Schneller Gesundheitscheck. Gibt Dict mit Status zurück."""
    req = urllib.request.Request(f"{ASIAI_URL}/api/status")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())

def is_healthy(status):
    """Gesundheitszustand interpretieren."""
    issues = []
    if status.get("memory_pressure") != "normal":
        issues.append(f"memory_pressure: {status['memory_pressure']}")
    gpu = status.get("gpu_utilization_percent", 0)
    if gpu > 90:
        issues.append(f"gpu_utilization: {gpu}%")
    engines = status.get("engines", {})
    for name, info in engines.items():
        if not info.get("running"):
            issues.append(f"engine_down: {name}")
    return {"healthy": len(issues) == 0, "issues": issues}

# Verwendung
status = check_health()
health = is_healthy(status)
if not health["healthy"]:
    print(f"Probleme erkannt: {health['issues']}")
```

### Vollständiger Systemzustand

```python
def get_full_state():
    """Vollständigen System-Snapshot abrufen."""
    req = urllib.request.Request(f"{ASIAI_URL}/api/snapshot")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

def get_history(hours=24):
    """Historische Metriken abrufen."""
    req = urllib.request.Request(f"{ASIAI_URL}/api/history?hours={hours}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

# Leistungstrend erkennen
history = get_history(hours=6)
points = history["points"]
if len(points) >= 2:
    recent_gpu = points[-1].get("gpu_utilization_percent", 0)
    earlier_gpu = points[0].get("gpu_utilization_percent", 0)
    if recent_gpu > earlier_gpu * 1.5:
        print("GPU-Auslastung steigt signifikant an")
```

## Benchmark-Karten (teilbare Bilder)

Erstellen Sie eine teilbare Benchmark-Karte per CLI:

```bash
asiai bench --card                    # SVG lokal gespeichert (keine Abhängigkeiten)
asiai bench --card --share            # SVG + PNG über Community-API
asiai bench --quick --card --share    # Schnellbenchmark + Karte + Teilen (~15s)
```

Eine **1200x630 Karte im dunklen Design** mit Modell, Chip, Engine-Vergleichs-Balkendiagramm, Gewinner-Hervorhebung und Metrik-Chips. Optimiert für Reddit, X, Discord und GitHub-READMEs.

Karten werden in `~/.local/share/asiai/cards/` als SVG gespeichert. Fügen Sie `--share` hinzu, um einen PNG-Download und eine teilbare URL zu erhalten — PNG wird für die Veröffentlichung auf Reddit, X und Discord benötigt.

### Via MCP

Das MCP-Tool `run_benchmark` unterstützt Kartengenerierung mit dem Parameter `card`:

```json
{"tool": "run_benchmark", "arguments": {"model": "qwen3.5", "card": true}}
```

Die Antwort enthält `card_path` — den absoluten Pfad zur SVG-Datei im Dateisystem des MCP-Servers.

## Webhook-Alerts (Push-Benachrichtigungen)

Anstatt zu pollen, konfigurieren Sie asiai für Push-Benachrichtigungen bei Zustandsänderungen:

```bash
# Webhook hinzufügen (Slack, Discord oder beliebige URL)
asiai alert add https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Alerts werden ausgelöst bei:
# - Engine fällt aus / kommt zurück
# - Speicherdruck-Übergänge (normal → warn → critical)
# - Thermisches Throttling erkannt
```

Alerts werden nur bei **Übergängen** ausgelöst (nicht bei jeder Prüfung) mit einem 5-Minuten-Cooldown zur Vermeidung von Flooding. Ideal für Swarm-Orchestratoren, die auf Infrastrukturänderungen reagieren müssen, ohne kontinuierlich zu pollen.

Zum Auflisten oder Entfernen von Alerts: `asiai alert list`, `asiai alert remove <id>`.

## Identifizieren Sie Ihren Agenten

Wir **empfehlen**, einen `User-Agent`-Header zur Identifizierung Ihres Agenten bei REST-API-Anfragen mitzusenden:

```
User-Agent: asiai-agent/<framework>/<version>
```

Beispiele:

- `User-Agent: asiai-agent/openclaw/1.2.0`
- `User-Agent: asiai-agent/crewai/0.5`
- `User-Agent: asiai-agent/custom-orchestrator/1.0`

Dies ist **nicht erforderlich** — Anfragen ohne User-Agent-Header funktionieren einwandfrei. Aber es hilft bei:

- **Debugging** — Agent-Anfragen von menschlichen Browser-Zugriffen in den Logs unterscheiden
- **Pro-Agent-Analytik** — sehen, welche Agenten die API nutzen, wie oft und welche Endpoints
- **Multi-Agent-Umgebungen** — wenn mehrere Agenten die gleiche asiai-Instanz nutzen, wer ist wer

Für MCP-Clients ist die Identifikation automatisch (das MCP-Protokoll enthält Client-Metadaten).

---

## Agenten registrieren (optional)

Die Registrierung ist **vollständig optional** — asiai funktioniert komplett ohne sie. Kein Phone-Home, keine Telemetrie standardmäßig.

Wenn Sie sich registrieren, treten Sie dem asiai-Agenten-Netzwerk bei: ein API-Aufruf, keine E-Mail, keine persönlichen Daten — nur Ihre Hardware-Informationen.

```bash
curl -X POST https://api.asiai.dev/api/v1/agent-register \
  -H "Content-Type: application/json" \
  -d '{
    "chip": "Apple M4 Pro",
    "ram_gb": 64,
    "engines": ["ollama", "lmstudio"],
    "framework": "my-agent",
    "asiai_version": "1.0.1"
  }'
```

**Antwort:**

```json
{
  "status": "registered",
  "agent_id": "a1b2c3d4e5f6",
  "agent_token": "secret_...",
  "total_agents": 42
}
```

Speichern Sie `agent_id` und `agent_token` sicher in `~/.local/share/asiai/agent.json`. Sie benötigen beides für Community-API-Aufrufe und Benchmark-Einreichungen.

### Was die Registrierung freischaltet

| Funktion | Ohne agent_id | Mit agent_id |
|----------|--------------|-------------|
| Lokales bench/monitor/web | Ja | Ja |
| `/api/status`, `/api/snapshot` | Ja | Ja |
| `--share` Benchmarks | Nein | **Ja** |
| `asiai compare` (Community) | Nein | **Ja** |
| `asiai recommend --community` | Nein | **Ja** |
| Perzentilstatistiken | Nein | **Ja** |
| Agentenverzeichnis (Peers auf gleichem Chip finden) | Nein | **Ja** |
| Leistungsalerts (neue Engine schlägt Ihre) | Nein | **Demnächst** |

### Heartbeat

Halten Sie Ihre Registrierung mit periodischen Heartbeats aktiv:

```bash
curl -X POST https://api.asiai.dev/api/v1/agent-heartbeat \
  -H "Content-Type: application/json" \
  -H "X-Agent-Id: a1b2c3d4e5f6" \
  -H "X-Agent-Token: secret_..." \
  -d '{
    "engines": ["ollama", "lmstudio"],
    "version": "1.0.1",
    "models_loaded": 3,
    "uptime_hours": 72
  }'
```

### Datenschutz

- **Keine IP-Adresse gespeichert** — Ihre IP wird nur für die Ratenlimitierung verwendet und nie im Agentenregister gespeichert
- **Keine persönlichen Daten** — nur Hardware-Informationen (Chip, RAM), Engine-Namen und Framework-Name
- **Nur Opt-in** — asiai kontaktiert nie einen Server, es sei denn, Sie registrieren sich ausdrücklich
- **Token-Sicherheit** — Ihr `agent_token` wird vor der Speicherung gehasht (SHA-256); der Klartext wird nur einmal bei der Registrierung zurückgegeben
- **Ratenlimitierungsdaten** — IP-Hashes (täglich gesalzener SHA-256) in der Ratenlimitierungstabelle werden nach 30 Tagen automatisch gelöscht

## FAQ

**F: Benötigt asiai root/sudo?**
A: Nein. Die GPU-Observability nutzt `ioreg` (ohne Privilegien). Leistungsmetriken (`--power`-Flag bei Benchmarks) benötigen `sudo powermetrics`, aber das ist optional.

**F: Wie schnell ist die API-Antwortzeit?**
A: `/api/status` antwortet in < 500ms (10s Cache). `/api/snapshot` benötigt 1–3s (sammelt Live-Daten von allen Engines).

**F: Kann ich asiai unter Linux verwenden?**
A: Nein. asiai ist ausschließlich für macOS Apple Silicon. Es nutzt `sysctl`, `vm_stat`, `ioreg` und `launchd` — alles macOS-spezifische APIs.

**F: Wie überwache ich mehrere Macs?**
A: Starten Sie `asiai daemon start web --host 0.0.0.0` auf jedem Mac. Scrapen Sie `/api/metrics` mit Prometheus. Visualisieren Sie in Grafana.

**F: Was passiert, wenn eine Engine abstürzt?**
A: asiai erkennt Engine-Ausfälle automatisch. Verwenden Sie `asiai doctor` für die Diagnose. Richten Sie Webhook-Alerts mit `asiai alert add` für automatische Benachrichtigungen ein.
