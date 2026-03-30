---
description: MCP-Server mit 11 Tools für KI-Agenten zur Überwachung von Inferenz-Engines, zum Ausführen von Benchmarks und für hardwareangepasste Empfehlungen.
---

# asiai mcp

MCP-Server (Model Context Protocol) starten, der KI-Agenten die Überwachung und das Benchmarking Ihrer Inferenzinfrastruktur ermöglicht.

## Verwendung

```bash
asiai mcp                          # stdio-Transport (Claude Code)
asiai mcp --transport sse          # SSE-Transport (Netzwerk-Agenten)
asiai mcp --transport sse --port 9000
```

## Optionen

| Option | Beschreibung |
|--------|-------------|
| `--transport` | Transportprotokoll: `stdio` (Standard), `sse`, `streamable-http` |
| `--host` | Bind-Adresse (Standard: `127.0.0.1`) |
| `--port` | Port für SSE/HTTP-Transport (Standard: `8900`) |
| `--register` | Opt-in-Registrierung beim asiai-Agentennetzwerk (anonym) |

## Tools (11)

| Tool | Beschreibung | Nur-Lesen |
|------|-------------|-----------|
| `check_inference_health` | Schneller Gesundheitscheck: Engines up/down, Speicherdruck, Thermal, GPU | Ja |
| `get_inference_snapshot` | Vollständiger System-Snapshot mit allen Metriken | Ja |
| `list_models` | Alle geladenen Modelle über alle Engines auflisten | Ja |
| `detect_engines` | Inferenz-Engines erneut scannen | Ja |
| `run_benchmark` | Benchmark oder modellübergreifenden Vergleich ausführen (auf 1/min begrenzt) | Nein |
| `get_recommendations` | Hardwareangepasste Engine-/Modellempfehlungen | Ja |
| `diagnose` | Diagnosechecks ausführen (wie `asiai doctor`) | Ja |
| `get_metrics_history` | Historische Metriken abfragen (1-168 Stunden) | Ja |
| `get_benchmark_history` | Vergangene Benchmark-Ergebnisse mit Filtern abfragen | Ja |
| `compare_engines` | Engine-Leistung für ein Modell mit Urteil vergleichen; unterstützt Multi-Modell-Vergleich aus dem Verlauf | Ja |
| `refresh_engines` | Engines ohne Serverneustart erneut erkennen | Ja |

## Ressourcen (3)

| Ressource | URI | Beschreibung |
|-----------|-----|-------------|
| Systemstatus | `asiai://status` | Aktuelle Systemgesundheit (Speicher, Thermal, GPU) |
| Modelle | `asiai://models` | Alle geladenen Modelle über alle Engines |
| Systeminfo | `asiai://system` | Hardware-Info (Chip, RAM, Kerne, OS, Uptime) |

## Claude Code Integration

Fügen Sie zu Ihrer Claude Code MCP-Konfiguration hinzu (`~/.claude/claude_desktop_config.json`):

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

Dann fragen Sie Claude: *„Prüfe meine Inferenzgesundheit"* oder *„Vergleiche Ollama vs LM Studio für qwen3.5"*.

## Benchmark-Karten

Das `run_benchmark`-Tool unterstützt Kartengenerierung über den `card`-Parameter. Bei `card=true` wird eine 1200x630 SVG-Benchmark-Karte generiert und `card_path` in der Antwort zurückgegeben.

```json
{"tool": "run_benchmark", "arguments": {"model": "qwen3.5", "card": true}}
```

Modellübergreifender Vergleich (gegenseitig exklusiv mit `model`, max 8 Slots):

```json
{"tool": "run_benchmark", "arguments": {"compare": ["qwen3.5:4b", "deepseek-r1:7b"], "card": true}}
```

CLI-Äquivalent für PNG + Sharing:

```bash
asiai bench --quick --card --share    # Schnellbench + Karte + Teilen (~15s)
```

Siehe die Seite [Benchmark-Karte](../benchmark-card.md) für Details.

## Agentenregistrierung

Treten Sie dem asiai-Agentennetzwerk bei für Community-Funktionen (Leaderboard, Vergleich, Perzentil-Statistiken):

```bash
asiai mcp --register                  # Beim ersten Start registrieren, danach Heartbeat
asiai unregister                      # Lokale Zugangsdaten entfernen
```

Die Registrierung ist **optional und anonym** — nur Hardware-Infos (Chip, RAM) und Engine-Namen werden gesendet. Keine IP, kein Hostname, keine persönlichen Daten werden gespeichert. Zugangsdaten werden in `~/.local/share/asiai/agent.json` gespeichert (chmod 600).

Bei nachfolgenden `asiai mcp --register`-Aufrufen wird ein Heartbeat statt einer Neuregistrierung gesendet. Wenn die API nicht erreichbar ist, startet der MCP-Server normal ohne Registrierung.

Prüfen Sie Ihren Registrierungsstatus mit `asiai version`.

## Netzwerk-Agenten

Für Agenten auf anderen Maschinen (z.B. Überwachung eines Headless Mac Mini):

```bash
asiai mcp --transport sse --host 0.0.0.0 --port 8900
```

Siehe die [Anleitung zur Agentenintegration](../agent.md) für detaillierte Setup-Anweisungen.
