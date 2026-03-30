---
description: "asiai-Version, Python-Umgebung und Agentenregistrierungsstatus mit einem einzigen Befehl prüfen."
---

# asiai version

Version und Systeminformationen anzeigen.

## Verwendung

```bash
asiai version
asiai --version
```

## Ausgabe

Der `version`-Unterbefehl zeigt erweiterten Systemkontext:

```
asiai 1.0.1
  Apple M4 Pro, 64 GB RAM
  Engines: ollama, lmstudio
  Daemon: monitor, web
```

Das `--version`-Flag zeigt nur den Versionsstring:

```
asiai 1.0.1
```

## Anwendungsfälle

- Schnelle Systemprüfung in Issues und Fehlermeldungen
- Kontexterfassung für Agenten (Chip, RAM, verfügbare Engines)
- Scripting: `VERSION=$(asiai version | head -1)`
