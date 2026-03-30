---
description: Automatische Erkennung laufender LLM-Inferenz-Engines auf Ihrem Mac. 3-Schichten-Kaskade — Konfiguration, Port-Scan, Prozesserkennung.
---

# asiai detect

Automatische Erkennung von Inferenz-Engines über eine 3-Schichten-Kaskade.

## Verwendung

```bash
asiai detect                      # Auto-Erkennung (3-Schichten-Kaskade)
asiai detect --url http://host:port  # Nur bestimmte URL(s) scannen
```

## Ausgabe

```
Detected engines:

  ● ollama 0.17.4
    URL: http://localhost:11434

  ● lmstudio 0.4.5
    URL: http://localhost:1234
    Running: 1 model(s)
      - qwen3.5-35b-a3b  MLX

  ● omlx 0.9.2
    URL: http://localhost:8800
```

## Funktionsweise: 3-Schichten-Erkennung

asiai verwendet eine Kaskade von drei Erkennungsschichten, von der schnellsten zur gründlichsten:

### Schicht 1: Konfiguration (schnellste, ~100ms)

Liest `~/.config/asiai/engines.json` — bei vorherigen Durchläufen entdeckte Engines. Dies findet Engines auf nicht standardmäßigen Ports (z.B. oMLX auf 8800) ohne erneutes Scannen.

### Schicht 2: Port-Scan (~200ms)

Scannt Standardports plus einen erweiterten Bereich:

| Port | Engine |
|------|--------|
| 11434 | Ollama |
| 1234 | LM Studio |
| 8080 | mlx-lm oder llama.cpp |
| 8000-8009 | oMLX oder vllm-mlx |
| 52415 | Exo |

### Schicht 3: Prozesserkennung (Fallback)

Verwendet `ps` und `lsof`, um Engine-Prozesse auf beliebigen Ports zu finden. Findet Engines auf völlig unerwarteten Ports.

### Automatische Persistierung

Jede in Schicht 2 oder 3 entdeckte Engine wird automatisch in der Konfigurationsdatei (Schicht 1) für schnellere Erkennung beim nächsten Mal gespeichert. Auto-entdeckte Einträge werden nach 7 Tagen Inaktivität bereinigt.

Wenn mehrere Engines einen Port teilen (z.B. mlx-lm und llama.cpp auf 8080), verwendet asiai API-Endpoint-Probing, um die richtige Engine zu identifizieren.

## Explizite URLs

Bei `--url` werden nur die angegebenen URLs gescannt. Es wird keine Konfiguration gelesen oder geschrieben — nützlich für einmalige Prüfungen.

```bash
asiai detect --url http://192.168.0.16:11434,http://localhost:8800
```

## Siehe auch

- [config](config.md) — Persistente Engine-Konfiguration verwalten
