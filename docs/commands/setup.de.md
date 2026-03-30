---
description: "Schnelle Einrichtung von asiai: Engines konfigurieren, Verbindungen testen und überprüfen, dass Ihr Apple-Silicon-Mac für LLM-Benchmarking bereit ist."
---

# asiai setup

Interaktiver Einrichtungsassistent für Erstbenutzer. Erkennt Ihre Hardware, prüft auf Inferenz-Engines und schlägt nächste Schritte vor.

## Verwendung

```bash
asiai setup
```

## Was es macht

1. **Hardwareerkennung** — identifiziert Ihren Apple-Silicon-Chip und RAM
2. **Engine-Scan** — prüft auf installierte Inferenz-Engines (Ollama, LM Studio, mlx-lm, llama.cpp, oMLX, vllm-mlx, Exo)
3. **Modellprüfung** — listet geladene Modelle über alle erkannten Engines
4. **Daemon-Status** — zeigt, ob der Monitoring-Daemon läuft
5. **Nächste Schritte** — schlägt Befehle basierend auf Ihrem Setup-Zustand vor

## Beispielausgabe

```
  Setup Wizard

  Hardware:  Apple M4 Pro, 64 GB RAM

  Engines:
    ✓ ollama (v0.17.7) — 3 models loaded
    ✓ lmstudio (v0.4.5) — 1 model loaded

  Daemon: running (monitor + web)

  Suggested next steps:
    • asiai bench              Run your first benchmark
    • asiai monitor --watch    Watch metrics live
    • asiai web                Open the dashboard
```

## Wenn keine Engines gefunden werden

Wenn keine Engines erkannt werden, bietet setup Installationshinweise:

```
  Engines:
    No inference engines detected.

  To get started, install an engine:
    brew install ollama && ollama serve
    # or download LM Studio from https://lmstudio.ai
```
