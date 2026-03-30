---
description: "Esegui asiai come daemon in background su Mac: monitoraggio automatico, dashboard web e metriche Prometheus all'avvio."
---

# asiai daemon

Gestisci servizi in background tramite LaunchAgent di macOS launchd.

## Servizi

| Servizio | Descrizione | Modello |
|---------|-------------|-------|
| `monitor` | Raccoglie metriche di sistema e inferenza a intervalli regolari | Periodico (`StartInterval`) |
| `web` | Esegue la dashboard web come servizio persistente | A lunga esecuzione (`KeepAlive`) |

## Uso

```bash
# Daemon di monitoraggio (default)
asiai daemon start                     # Avvia monitoraggio (ogni 60s)
asiai daemon start --interval 30       # Intervallo personalizzato
asiai daemon start --alert-webhook URL # Abilita avvisi webhook

# Servizio dashboard web
asiai daemon start web                 # Avvia web su 127.0.0.1:8899
asiai daemon start web --port 9000     # Porta personalizzata
asiai daemon start web --host 0.0.0.0  # Esponi in rete (nessuna autenticazione!)

# Stato (mostra tutti i servizi)
asiai daemon status

# Ferma
asiai daemon stop                      # Ferma monitor
asiai daemon stop web                  # Ferma web
asiai daemon stop --all                # Ferma tutti i servizi

# Log
asiai daemon logs                      # Log del monitor
asiai daemon logs web                  # Log del web
asiai daemon logs web -n 100           # Ultime 100 righe
```

## Come funziona

Ogni servizio installa un plist LaunchAgent launchd separato in `~/Library/LaunchAgents/`:

- **Monitor**: esegue `asiai monitor --quiet` all'intervallo configurato (default: 60s). I dati sono salvati in SQLite. Se viene fornito `--alert-webhook`, gli avvisi vengono inviati via POST alle transizioni di stato (pressione memoria, termica, motore giù).
- **Web**: esegue `asiai web --no-open` come processo persistente. Si riavvia automaticamente in caso di crash (`KeepAlive: true`, `ThrottleInterval: 10s`).

Entrambi i servizi si avviano automaticamente al login (`RunAtLoad: true`).

## Sicurezza

- I servizi girano a **livello utente** (nessun root necessario)
- La dashboard web si collega a `127.0.0.1` di default (solo localhost)
- Viene mostrato un avviso quando si usa `--host 0.0.0.0` — nessuna autenticazione configurata
- I log sono salvati in `~/.local/share/asiai/`
