---
description: Server MCP che espone 11 strumenti per agenti IA per monitorare motori di inferenza, eseguire benchmark e ottenere raccomandazioni basate sull'hardware.
---

# asiai mcp

Avvia il server MCP (Model Context Protocol), consentendo agli agenti IA di monitorare e valutare la tua infrastruttura di inferenza.

## Uso

```bash
asiai mcp                          # trasporto stdio (Claude Code)
asiai mcp --transport sse          # trasporto SSE (agenti in rete)
asiai mcp --transport sse --port 9000
```

## Opzioni

| Opzione | Descrizione |
|--------|-------------|
| `--transport` | Protocollo di trasporto: `stdio` (default), `sse`, `streamable-http` |
| `--host` | Indirizzo di bind (default: `127.0.0.1`) |
| `--port` | Porta per trasporto SSE/HTTP (default: `8900`) |
| `--register` | Registrazione volontaria nella rete agenti asiai (anonima) |

## Strumenti (11)

| Strumento | Descrizione | Sola lettura |
|------|-------------|-----------|
| `check_inference_health` | Controllo rapido: motori attivi/inattivi, pressione memoria, termica, GPU | Sì |
| `get_inference_snapshot` | Snapshot completo del sistema con tutte le metriche | Sì |
| `list_models` | Elenca tutti i modelli caricati su tutti i motori | Sì |
| `detect_engines` | Ri-scansiona i motori di inferenza | Sì |
| `run_benchmark` | Esegui un benchmark o confronto tra modelli (limitato a 1/min) | No |
| `get_recommendations` | Raccomandazioni motore/modello in base all'hardware | Sì |
| `diagnose` | Esegui controlli diagnostici (come `asiai doctor`) | Sì |
| `get_metrics_history` | Interroga lo storico metriche (1-168 ore) | Sì |
| `get_benchmark_history` | Interroga risultati benchmark passati con filtri | Sì |
| `compare_engines` | Confronto motori classificato con verdetto; supporta confronto multi-modello dallo storico | Sì |
| `refresh_engines` | Ri-rileva motori senza riavviare il server | Sì |

## Risorse (3)

| Risorsa | URI | Descrizione |
|----------|-----|-------------|
| Stato sistema | `asiai://status` | Stato attuale del sistema (memoria, termica, GPU) |
| Modelli | `asiai://models` | Tutti i modelli caricati su tutti i motori |
| Info sistema | `asiai://system` | Info hardware (chip, RAM, core, SO, uptime) |

## Integrazione Claude Code

Aggiungi alla configurazione MCP di Claude Code (`~/.claude/claude_desktop_config.json`):

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

Poi chiedi a Claude: *"Controlla lo stato della mia inferenza"* o *"Confronta Ollama vs LM Studio per qwen3.5"*.

## Schede benchmark

Lo strumento `run_benchmark` supporta la generazione di schede tramite il parametro `card`. Quando `card=true`, viene generata una scheda SVG 1200x630 e `card_path` viene restituito nella risposta.

```json
{"tool": "run_benchmark", "arguments": {"model": "qwen3.5", "card": true}}
```

Confronto tra modelli (mutuamente esclusivo con `model`, max 8 slot):

```json
{"tool": "run_benchmark", "arguments": {"compare": ["qwen3.5:4b", "deepseek-r1:7b"], "card": true}}
```

Equivalente CLI per PNG + condivisione:

```bash
asiai bench --quick --card --share    # Benchmark rapido + scheda + condivisione (~15s)
```

Vedi la pagina [Scheda benchmark](../benchmark-card.md) per i dettagli.

## Registrazione agente

Entra nella rete agenti asiai per funzionalità comunitarie (classifica, confronto, percentili):

```bash
asiai mcp --register                  # Registra alla prima esecuzione, heartbeat alle successive
asiai unregister                      # Rimuovi credenziali locali
```

La registrazione è **volontaria e anonima** — vengono inviati solo info hardware (chip, RAM) e nomi dei motori. Nessun IP, hostname o dato personale viene salvato. Le credenziali sono in `~/.local/share/asiai/agent.json` (chmod 600).

Alle chiamate successive di `asiai mcp --register`, viene inviato un heartbeat invece di registrarsi nuovamente. Se l'API non è raggiungibile, il server MCP si avvia normalmente senza registrazione.

Verifica lo stato della registrazione con `asiai version`.

## Agenti in rete

Per agenti su altre macchine (es. monitoraggio di un Mac Mini headless):

```bash
asiai mcp --transport sse --host 0.0.0.0 --port 8900
```

Vedi la [Guida all'integrazione agenti](../agent.md) per istruzioni dettagliate.
