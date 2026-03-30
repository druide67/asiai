---
description: "asiai als Hintergrunddienst auf dem Mac ausführen: automatisches Monitoring, Web-Dashboard und Prometheus-Metriken beim Systemstart."
---

# asiai daemon

Hintergrunddienste über macOS launchd LaunchAgents verwalten.

## Dienste

| Dienst | Beschreibung | Modell |
|--------|-------------|--------|
| `monitor` | Erfasst System- + Inferenzmetriken in regelmäßigen Abständen | Periodisch (`StartInterval`) |
| `web` | Führt das Web-Dashboard als persistenten Dienst aus | Dauerhaft (`KeepAlive`) |

## Verwendung

```bash
# Monitor-Daemon (Standard)
asiai daemon start                     # Monitoring starten (alle 60s)
asiai daemon start --interval 30       # Benutzerdefiniertes Intervall
asiai daemon start --alert-webhook URL # Webhook-Alerts aktivieren

# Web-Dashboard-Dienst
asiai daemon start web                 # Web starten auf 127.0.0.1:8899
asiai daemon start web --port 9000     # Benutzerdefinierter Port
asiai daemon start web --host 0.0.0.0  # Im Netzwerk freigeben (keine Auth!)

# Status (zeigt alle Dienste)
asiai daemon status

# Stoppen
asiai daemon stop                      # Monitor stoppen
asiai daemon stop web                  # Web stoppen
asiai daemon stop --all                # Alle Dienste stoppen

# Logs
asiai daemon logs                      # Monitor-Logs
asiai daemon logs web                  # Web-Logs
asiai daemon logs web -n 100           # Letzte 100 Zeilen
```

## Funktionsweise

Jeder Dienst installiert eine separate launchd-LaunchAgent-Plist in `~/Library/LaunchAgents/`:

- **Monitor**: Führt `asiai monitor --quiet` im konfigurierten Intervall aus (Standard: 60s). Daten werden in SQLite gespeichert. Bei `--alert-webhook` werden Alerts bei Zustandsübergängen per POST gesendet (Speicherdruck, Thermal, Engine nicht erreichbar).
- **Web**: Führt `asiai web --no-open` als persistenten Prozess aus. Startet bei Absturz automatisch neu (`KeepAlive: true`, `ThrottleInterval: 10s`).

Beide Dienste starten automatisch bei der Anmeldung (`RunAtLoad: true`).

## Sicherheit

- Dienste laufen auf **Benutzerebene** (kein Root erforderlich)
- Das Web-Dashboard bindet standardmäßig an `127.0.0.1` (nur localhost)
- Eine Warnung wird bei Verwendung von `--host 0.0.0.0` angezeigt — keine Authentifizierung konfiguriert
- Logs werden in `~/.local/share/asiai/` gespeichert
