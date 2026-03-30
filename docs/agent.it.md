---
description: Offri ai tuoi agenti IA visibilità in tempo reale sull'inferenza LLM. Server MCP con 11 strumenti per il monitoraggio autonomo dei motori.
type: faq
faq:
  - q: "asiai richiede root/sudo?"
    a: "No. L'osservabilità della GPU usa ioreg (nessun privilegio). Le metriche di potenza usano IOReport che non richiede sudo. Il flag opzionale --power per la validazione incrociata usa sudo powermetrics."
  - q: "Qual è il tempo di risposta dell'API?"
    a: "/api/status risponde in meno di 500ms (cache 10s). /api/snapshot richiede 1-3s poiché raccoglie dati in tempo reale da tutti i motori."
  - q: "Posso eseguire asiai su Linux?"
    a: "No. asiai è solo per macOS Apple Silicon. Usa sysctl, vm_stat, ioreg, IOReport e launchd — tutte API specifiche di macOS."
  - q: "Come monitoro più Mac?"
    a: "Esegui asiai daemon start web --host 0.0.0.0 su ogni Mac. Raccogli /api/metrics con Prometheus. Visualizza in Grafana."
  - q: "Cosa succede se un motore si blocca durante il monitoraggio?"
    a: "asiai rileva automaticamente i guasti dei motori. Usa asiai doctor per la diagnostica. Configura le notifiche webhook con asiai alert add per le notifiche automatiche."
---

# Guida all'integrazione con agenti

> **Se sei un agente IA**: usa [MCP](#mcp-model-context-protocol) se il tuo framework lo supporta, altrimenti usa l'[API REST](#riferimento-api-rest). Per la configurazione, vedi [Avvio rapido](#avvio-rapido).

## Panoramica

asiai espone l'infrastruttura di inferenza LLM del tuo Mac agli agenti IA attraverso due meccanismi:

- **Server MCP** — Integrazione nativa degli strumenti tramite il [Model Context Protocol](https://modelcontextprotocol.io). Ideale per agenti IA che supportano MCP (Claude Code, Cursor, Cline e altri client compatibili con MCP).
- **API REST** — Endpoint HTTP/JSON standard. Ideale per framework di agenti, orchestratori di swarm e qualsiasi sistema con capacità HTTP (CrewAI, AutoGen, LangGraph, agenti personalizzati).

Entrambi danno accesso alle stesse funzionalità:

- **Monitorare** lo stato del sistema (CPU, RAM, GPU, termica, swap)
- **Rilevare** quali motori di inferenza sono in esecuzione e quali modelli sono caricati
- **Diagnosticare** problemi di prestazioni usando l'osservabilità della GPU e i segnali di attività di inferenza
- **Valutare** modelli in modo programmatico e tracciare le regressioni
- **Ottenere raccomandazioni** per il miglior modello/motore basandosi sul tuo hardware

Nessuna autenticazione richiesta per l'accesso locale. Tutte le interfacce si collegano a `127.0.0.1` per impostazione predefinita.

### Quale integrazione dovrei usare?

| Criterio | MCP | API REST |
|----------|-----|----------|
| Il tuo agente supporta MCP | **Usa MCP** | — |
| Swarm / orchestratore multi-agente | — | **Usa API REST** |
| Polling / monitoraggio programmato | — | **Usa API REST** |
| Integrazione Prometheus / Grafana | — | **Usa API REST** |
| Assistente IA interattivo (Claude Code, Cursor) | **Usa MCP** | — |
| Agente in container Docker | — | **Usa API REST** |
| Script personalizzati o automazione | — | **Usa API REST** |

## Avvio rapido

### Installa asiai

```bash
# Homebrew (raccomandato)
brew tap druide67/tap && brew install asiai

# pip (con supporto MCP)
pip install "asiai[mcp]"

# pip (solo API REST)
pip install asiai
```

### Opzione A: Server MCP (per agenti compatibili con MCP)

```bash
# Avvia il server MCP (trasporto stdio — usato da Claude Code, Cursor, ecc.)
asiai mcp
```

Non è necessario avviare manualmente il server — il client MCP lancia `asiai mcp` automaticamente. Vedi la [configurazione MCP](#mcp-model-context-protocol) qui sotto.

### Opzione B: API REST (per agenti basati su HTTP)

```bash
# In primo piano (sviluppo)
asiai web --no-open

# Daemon in background (produzione)
asiai daemon start web
```

L'API è disponibile su `http://127.0.0.1:8899`. La porta è configurabile con `--port`:

```bash
asiai daemon start web --port 8642
```

Per l'accesso remoto (es. agente IA su un'altra macchina o da un container Docker):

```bash
asiai daemon start web --host 0.0.0.0
```

> **Nota:** Se il tuo agente gira all'interno di Docker, `127.0.0.1` non è raggiungibile. Usa l'IP di rete dell'host (es. `192.168.0.16`) o `host.docker.internal` su Docker Desktop per Mac.

### Verifica

```bash
# API REST
curl http://127.0.0.1:8899/api/status

# MCP (elenco strumenti disponibili)
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | asiai mcp
```

---

## MCP (Model Context Protocol)

asiai implementa un [server MCP](https://modelcontextprotocol.io) che espone il monitoraggio dell'inferenza come strumenti nativi. Qualsiasi client compatibile con MCP può connettersi e utilizzare questi strumenti direttamente — nessuna configurazione HTTP, nessuna gestione di URL.

### Configurazione

#### Locale (stessa macchina)

Aggiungi alla configurazione del tuo client MCP (es. `~/.claude/settings.json` per Claude Code):

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

Se asiai è installato in un virtualenv:

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

#### Remoto (macchina diversa via SSH)

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

#### Trasporto SSE (rete)

Per ambienti che preferiscono il trasporto MCP basato su HTTP:

```bash
asiai mcp --transport sse --host 127.0.0.1 --port 8900
```

### Riferimento strumenti MCP

Tutti gli strumenti restituiscono JSON. Gli strumenti in sola lettura rispondono in < 2 secondi. `run_benchmark` è l'unica operazione attiva.

| Strumento | Descrizione | Parametri |
|------|-------------|------------|
| `check_inference_health` | Controllo rapido — motori attivi/inattivi, pressione di memoria, termica, utilizzo GPU | — |
| `get_inference_snapshot` | Snapshot completo dello stato del sistema (salvato in SQLite per lo storico) | — |
| `list_models` | Tutti i modelli caricati su tutti i motori con VRAM, quantizzazione, lunghezza contesto | — |
| `detect_engines` | Rilevamento a 3 livelli: config, scansione porte, rilevamento processi. Trova motori su porte non standard automaticamente. | — |
| `run_benchmark` | Esegui benchmark su un modello o confronto tra modelli. Limitato: 1 per 60 secondi | `model` (opzionale), `runs` (1–10, default 3), `compare` (lista stringhe, opzionale, mutuamente esclusivo con `model`, max 8) |
| `get_recommendations` | Raccomandazioni modello/motore consapevoli dell'hardware per il tuo chip e RAM | — |
| `diagnose` | Esegui controlli diagnostici (sistema, motori, stato daemon) | — |
| `get_metrics_history` | Metriche di sistema storiche da SQLite | `hours` (1–168, default 24) |
| `get_benchmark_history` | Risultati benchmark storici | `hours` (1–720, default 24), `model` (opzionale), `engine` (opzionale) |
| `compare_engines` | Confronto motori classificato con verdetto per un modello; supporta confronto multi-modello dallo storico | `model` (obbligatorio) |
| `refresh_engines` | Ri-rileva i motori senza riavviare il server MCP | — |

### Risorse MCP

Endpoint di dati statici, disponibili senza chiamare uno strumento:

| URI | Descrizione |
|-----|-------------|
| `asiai://status` | Stato attuale (memoria, termica, GPU) |
| `asiai://models` | Tutti i modelli caricati su tutti i motori |
| `asiai://system` | Info hardware (chip, RAM, core, SO, uptime) |

### Sicurezza MCP

- **Nessun sudo**: Le metriche di potenza sono disabilitate in modalità MCP (`power=False` forzato)
- **Limitazione di frequenza**: I benchmark sono limitati a 1 per 60 secondi
- **Clamping degli input**: `hours` limitato a 1–168, `runs` limitato a 1–10
- **Locale per default**: il trasporto stdio non ha esposizione di rete; SSE si collega a `127.0.0.1`

### Limitazioni MCP

- **Nessuna riconnessione**: Se la connessione SSH cade (problema di rete, sleep del Mac), il server MCP muore e il client deve riconnettersi manualmente. Per monitoraggio non presidiato, l'API REST con polling è più resiliente.
- **Client singolo**: il trasporto stdio serve un client alla volta. Usa il trasporto SSE se più client necessitano accesso concorrente.

---

## Riferimento API REST

L'API di asiai è **in sola lettura** — monitora e riporta, ma non controlla i motori. Per caricare/scaricare modelli, usa i comandi nativi del motore (`ollama pull`, `lms load`, ecc.).

Tutti gli endpoint restituiscono JSON con HTTP 200. Se un motore non è raggiungibile, la risposta restituisce comunque 200 con `"running": false` per quel motore — l'API stessa non fallisce.

| Endpoint | Tempo di risposta tipico | Timeout consigliato |
|----------|----------------------|---------------------|
| `GET /api/status` | < 500ms (cache 10s) | 2s |
| `GET /api/snapshot` | 1–3s (raccolta live) | 10s |
| `GET /api/metrics` | < 500ms | 2s |
| `GET /api/history` | < 500ms | 5s |
| `GET /api/engine-history` | < 500ms | 5s |

### `GET /api/status`

Controllo rapido dello stato. Cache di 10 secondi. Tempo di risposta < 500ms.

**Risposta:**

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

Stato completo del sistema. Include tutto da `/api/status` più informazioni dettagliate sui modelli, metriche GPU e dati termici.

**Risposta:**

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

Metriche in formato Prometheus. Raccogli con Prometheus, Datadog o qualsiasi strumento compatibile.

**Risposta (text/plain):**

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

Metriche di sistema storiche da SQLite. Default: `hours=24`. Max: `hours=2160` (90 giorni).

**Risposta:**

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

Storico dello stato dei motori. Utile per rilevare pattern di inferenza.

**Parametri:**

| Parametro | Obbligatorio | Default | Descrizione |
|-----------|----------|---------|-------------|
| `engine`  | Sì       | —       | Nome del motore (ollama, lmstudio, ecc.) |
| `hours`   | No       | 24      | Intervallo di tempo |

**Risposta:**

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

## Interpretare le metriche

### Soglie di stato del sistema

| Metrica | Normale | Attenzione | Critico |
|--------|--------|---------|----------|
| `memory_pressure` | `normal` | `warn` | `critical` |
| `ram_percent` | < 75% | 75–90% | > 90% |
| `swap_used_gb` | 0 | 0.1–2.0 | > 2.0 |
| `thermal_state` | `nominal` | `fair` | `serious` / `critical` |
| `cpu_percent` | < 80% | 80–95% | > 95% |

### Soglie GPU

| Metrica | Inattivo | Inferenza attiva | Sovraccarico |
|--------|------|------------------|------------|
| `gpu_utilization_percent` | 0–5% | 20–80% | > 90% sostenuto |
| `gpu_renderer_percent` | 0–5% | 15–70% | > 85% sostenuto |
| `gpu_memory_allocated_bytes` | < 1 GB | 2–48 GB | > 90% della RAM |

> **Importante:** `gpu_utilization_percent = 0` significa che la GPU è inattiva, non guasta. Un valore di `-1.0` significa che la metrica non è disponibile (es. hardware non supportato o errore nella raccolta) — non trattarlo come "GPU morta".

### Prestazioni di inferenza

| Metrica | Eccellente | Buono | Degradato |
|--------|-----------|------|----------|
| `tok/s` (modello 7B) | > 80 | 40–80 | < 40 |
| `tok/s` (modello 35B) | > 40 | 20–40 | < 20 |
| `tok/s` (modello 70B) | > 15 | 8–15 | < 8 |
| `TTFT` | < 100ms | 100–500ms | > 500ms |

## Alberi decisionali diagnostici

### Generazione lenta (tok/s basso)

```
tok/s sotto le aspettative?
├── Controlla memory_pressure
│   ├── "critical" → I modelli stanno facendo swap su disco. Scarica modelli o aggiungi RAM.
│   └── "normal" → Continua
├── Controlla thermal_state
│   ├── "serious"/"critical" → Throttling termico. Raffredda, controlla il flusso d'aria.
│   └── "nominal" → Continua
├── Controlla gpu_utilization_percent
│   ├── < 10% → GPU non utilizzata. Controlla la config del motore (num_gpu layers).
│   ├── > 90% → GPU satura. Riduci le richieste concorrenti.
│   └── 20-80% → Normale. Controlla quantizzazione e dimensione contesto.
└── Controlla swap_used_gb
    ├── > 0 → Modello troppo grande per la RAM. Usa quantizzazione inferiore.
    └── 0 → Controlla versione motore, prova un motore diverso.
```

### Motore non risponde

```
engine.running == false?
├── Controlla se il processo esiste: lsof -i :<port>
│   ├── Nessun processo → Il motore è crashato. Riavvialo.
│   └── Processo esiste ma non risponde → Il motore è bloccato.
├── Controlla memory_pressure
│   ├── "critical" → Terminato per OOM. Prima scarica gli altri modelli.
│   └── "normal" → Controlla i log del motore.
└── Prova: asiai doctor (diagnostica completa)
```

### Pressione di memoria elevata / Overflow VRAM

```
memory_pressure == "warn" o "critical"?
├── Controlla swap_used_gb
│   ├── > 2 GB → Overflow VRAM. I modelli non entrano nella memoria unificata.
│   │   ├── La latenza sarà 5–50x peggiore (swap su disco).
│   │   ├── Scarica modelli: ollama rm <model>, lms unload
│   │   └── Oppure usa quantizzazione inferiore (Q4_K_M → Q3_K_S).
│   └── < 2 GB → Gestibile ma monitora attentamente.
├── Controlla modelli caricati su tutti i motori
│   ├── Più modelli grandi → Scarica i modelli non utilizzati
│   │   ├── Ollama: ollama rm <model> o attendi lo scaricamento automatico
│   │   └── LM Studio: scarica tramite UI o lms unload
│   └── Singolo modello > 80% RAM → Usa quantizzazione inferiore
└── Controlla gpu_memory_allocated_bytes
    └── Confronta con ram_total_gb. Se > 80%, il prossimo caricamento causerà swap.
```

## Segnali di attività di inferenza

asiai rileva l'inferenza attiva attraverso più segnali:

### Utilizzo GPU

```
GET /api/snapshot → system.gpu_utilization_percent
```

- **< 5%**: Nessuna inferenza in corso
- **20–80%**: Inferenza attiva (range normale per memoria unificata Apple Silicon)
- **> 90%**: Inferenza pesante o richieste concorrenti multiple

### Connessioni TCP

```
GET /api/engine-history?engine=ollama&hours=1
```

Ogni richiesta di inferenza attiva mantiene una connessione TCP. Un picco in `tcp_connections` indica generazione attiva.

### Metriche specifiche del motore

Per i motori che espongono `/metrics` (llama.cpp, vllm-mlx):

- `requests_processing > 0`: Inferenza attiva
- `kv_cache_usage_percent > 0`: Il modello ha un contesto attivo

### Pattern di correlazione

Il rilevamento dell'inferenza più affidabile combina più segnali:

```python
snapshot = get_snapshot()
gpu_active = snapshot["system"]["gpu_utilization_percent"] > 15
engine_busy = any(
    e.get("tcp_connections", 0) > 0
    for e in snapshot.get("engine_status", [])
)
inference_running = gpu_active and engine_busy
```

## Codice di esempio

### Controllo stato (Python, solo stdlib)

```python
import json
import urllib.request

ASIAI_URL = "http://127.0.0.1:8899"  # Docker: usa IP host o host.docker.internal

def check_health():
    """Controllo rapido dello stato. Restituisce dict con lo stato."""
    req = urllib.request.Request(f"{ASIAI_URL}/api/status")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())

def is_healthy(status):
    """Interpreta lo stato."""
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

# Utilizzo
status = check_health()
health = is_healthy(status)
if not health["healthy"]:
    print(f"Issues detected: {health['issues']}")
```

### Stato completo del sistema

```python
def get_full_state():
    """Ottieni lo snapshot completo del sistema."""
    req = urllib.request.Request(f"{ASIAI_URL}/api/snapshot")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

def get_history(hours=24):
    """Ottieni le metriche storiche."""
    req = urllib.request.Request(f"{ASIAI_URL}/api/history?hours={hours}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

# Rileva tendenza nelle prestazioni
history = get_history(hours=6)
points = history["points"]
if len(points) >= 2:
    recent_gpu = points[-1].get("gpu_utilization_percent", 0)
    earlier_gpu = points[0].get("gpu_utilization_percent", 0)
    if recent_gpu > earlier_gpu * 1.5:
        print("GPU utilization trending up significantly")
```

## Schede benchmark (immagini condivisibili)

Genera un'immagine di scheda benchmark condivisibile con CLI:

```bash
asiai bench --card                    # SVG salvato localmente (zero dipendenze)
asiai bench --card --share            # SVG + PNG via API comunitaria
asiai bench --quick --card --share    # Bench rapido + scheda + condivisione (~15s)
```

Una **scheda 1200x630 a tema scuro** con modello, chip, grafico a barre del confronto tra motori, evidenziazione del vincitore e chip di metriche. Ottimizzata per Reddit, X, Discord e README di GitHub.

Le schede sono salvate in `~/.local/share/asiai/cards/` come SVG. Aggiungi `--share` per ottenere un download PNG e un URL condivisibile — il PNG è necessario per postare su Reddit, X e Discord.

### Via MCP

Lo strumento MCP `run_benchmark` supporta la generazione di schede con il parametro `card`:

```json
{"tool": "run_benchmark", "arguments": {"model": "qwen3.5", "card": true}}
```

La risposta include `card_path` — il percorso assoluto del file SVG sul filesystem del server MCP.

## Avvisi webhook (notifiche push)

Invece di fare polling, configura asiai per inviare notifiche quando si verificano cambiamenti di stato:

```bash
# Aggiungi un webhook (Slack, Discord o qualsiasi URL)
asiai alert add https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Gli avvisi si attivano su:
# - Motore va giù / torna su
# - Transizioni di pressione di memoria (normal → warn → critical)
# - Throttling termico rilevato
```

Gli avvisi scattano solo sulle **transizioni** (non ad ogni controllo) con un raffreddamento di 5 minuti per prevenire lo spam. Ideale per orchestratori di swarm che devono reagire ai cambiamenti dell'infrastruttura senza polling continuo.

Per elencare o rimuovere avvisi: `asiai alert list`, `asiai alert remove <id>`.

## Identifica il tuo agente

**Raccomandiamo** di includere un header `User-Agent` che identifichi il tuo agente nelle richieste API REST:

```
User-Agent: asiai-agent/<framework>/<version>
```

Esempi:

- `User-Agent: asiai-agent/openclaw/1.2.0`
- `User-Agent: asiai-agent/crewai/0.5`
- `User-Agent: asiai-agent/custom-orchestrator/1.0`

Questo **non è obbligatorio** — le richieste senza header User-Agent funzionano normalmente. Ma aiuta con:

- **Debug** — distinguere le richieste degli agenti dall'accesso browser umano nei log
- **Analytics per agente** — vedere quali agenti accedono all'API, con quale frequenza e quali endpoint
- **Ambienti multi-agente** — quando più agenti condividono la stessa istanza asiai, identificare chi è chi

Per i client MCP, l'identificazione è automatica (il protocollo MCP include i metadati del client).

---

## Registra il tuo agente (opzionale)

La registrazione è **completamente opzionale** — asiai funziona pienamente senza di essa. Nessun "phone home", nessuna telemetria per impostazione predefinita.

Se scegli di registrarti, entri nella rete di agenti asiai: una chiamata API, nessuna email, nessun dato personale — solo le info del tuo hardware.

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

**Risposta:**

```json
{
  "status": "registered",
  "agent_id": "a1b2c3d4e5f6",
  "agent_token": "secret_...",
  "total_agents": 42
}
```

Salva `agent_id` e `agent_token` in modo sicuro in `~/.local/share/asiai/agent.json`. Ti serviranno entrambi per le chiamate API comunitarie e l'invio di benchmark.

### Cosa sblocca la registrazione

| Funzionalità | Senza agent_id | Con agent_id |
|---------|-----------------|---------------|
| Bench/monitor/web locale | Sì | Sì |
| `/api/status`, `/api/snapshot` | Sì | Sì |
| `--share` benchmark | No | **Sì** |
| `asiai compare` (community) | No | **Sì** |
| `asiai recommend --community` | No | **Sì** |
| Statistiche percentile | No | **Sì** |
| Directory agenti (trova peer sullo stesso chip) | No | **Sì** |
| Avvisi prestazioni (nuovo motore batte il tuo) | No | **In arrivo** |

### Heartbeat

Mantieni attiva la registrazione con heartbeat periodici:

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

### Privacy

- **Nessun indirizzo IP salvato** — il tuo IP è usato solo per il rate limiting e non viene mai persistito nel registro agenti
- **Nessun dato personale** — solo info hardware (chip, RAM), nomi dei motori e nome del framework
- **Solo su adesione** — asiai non comunica mai con l'esterno se non registri esplicitamente
- **Sicurezza token** — il tuo `agent_token` viene hashato (SHA-256) prima del salvataggio; il testo in chiaro viene restituito solo una volta alla registrazione
- **Dati rate limit** — gli hash IP (SHA-256 con salt giornaliero) nella tabella rate limit vengono eliminati automaticamente dopo 30 giorni

## FAQ

**D: asiai richiede root/sudo?**
R: No. L'osservabilità GPU usa `ioreg` (nessun privilegio). Le metriche di potenza (flag `--power` nei benchmark) richiedono `sudo powermetrics`, ma è opzionale.

**D: Qual è il tempo di risposta dell'API?**
R: `/api/status` risponde in < 500ms (cache 10s). `/api/snapshot` richiede 1–3s (raccoglie dati in tempo reale da tutti i motori).

**D: Posso eseguire asiai su Linux?**
R: No. asiai è solo per macOS Apple Silicon. Usa `sysctl`, `vm_stat`, `ioreg` e `launchd` — tutte API specifiche di macOS.

**D: Come monitoro più Mac?**
R: Esegui `asiai daemon start web --host 0.0.0.0` su ogni Mac. Raccogli `/api/metrics` con Prometheus. Visualizza in Grafana.

**D: Cosa succede se un motore si blocca?**
R: asiai rileva automaticamente i guasti dei motori. Usa `asiai doctor` per la diagnostica. Configura le notifiche webhook con `asiai alert add` per le notifiche automatiche.
