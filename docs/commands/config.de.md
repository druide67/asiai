---
description: "Wie Sie asiai konfigurieren: Engine-URLs, Ports und persistente Einstellungen für Ihr LLM-Benchmark-Setup auf dem Mac verwalten."
---

# asiai config

Persistente Engine-Konfiguration verwalten. Von `asiai detect` entdeckte Engines werden automatisch in `~/.config/asiai/engines.json` gespeichert, um nachfolgende Erkennung zu beschleunigen.

## Verwendung

```bash
asiai config show              # Bekannte Engines anzeigen
asiai config add <engine> <url> [--label NAME]  # Engine manuell hinzufügen
asiai config remove <url>      # Eine Engine entfernen
asiai config reset             # Gesamte Konfiguration löschen
```

## Unterbefehle

### show

Zeigt alle bekannten Engines mit URL, Version, Quelle (auto/manual) und letztem Erkennungszeitpunkt.

```
$ asiai config show
Known engines (3):
  ollama v0.17.7 at http://localhost:11434  (auto)  last seen 2m ago
  lmstudio v0.4.6 at http://localhost:1234  (auto)  last seen 2m ago
  omlx v0.9.2 at http://localhost:8800 [mac-mini]  (manual)  last seen 5m ago
```

### add

Engine manuell auf einem nicht standardmäßigen Port registrieren. Manuelle Engines werden nie automatisch entfernt.

```bash
asiai config add omlx http://localhost:8800 --label mac-mini
asiai config add ollama http://192.168.0.16:11434 --label mini
```

### remove

Einen Engine-Eintrag nach URL entfernen.

```bash
asiai config remove http://localhost:8800
```

### reset

Die gesamte Konfigurationsdatei löschen. Der nächste `asiai detect` wird Engines von Grund auf neu erkennen.

## Funktionsweise

Die Konfigurationsdatei speichert während der Erkennung entdeckte Engines:

- **Auto-Einträge** (`source: auto`): Werden automatisch erstellt, wenn `asiai detect` eine neue Engine findet. Nach 7 Tagen Inaktivität bereinigt.
- **Manuelle Einträge** (`source: manual`): Über `asiai config add` erstellt. Werden nie automatisch bereinigt.

Die 3-Schichten-Erkennungskaskade in `asiai detect` nutzt diese Konfiguration als Schicht 1 (schnellste), gefolgt von Port-Scan (Schicht 2) und Prozesserkennung (Schicht 3). Siehe [detect](detect.md) für Details.

## Speicherort der Konfigurationsdatei

```
~/.config/asiai/engines.json
```
