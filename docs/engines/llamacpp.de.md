---
description: "llama.cpp-Server auf dem Mac: Low-Level-Kontrolle, Port 8080, KV-Cache-Metriken und Benchmark-Ergebnisse auf Apple Silicon."
---

# llama.cpp

llama.cpp ist die grundlegende C++-Inferenz-Engine für GGUF-Modelle, die maximale Low-Level-Kontrolle über KV Cache, Thread-Anzahl und Kontextgröße auf Port 8080 bietet. Es betreibt Ollamas Backend, kann aber eigenständig für Feinabstimmung auf Apple Silicon ausgeführt werden.

[llama.cpp](https://github.com/ggml-org/llama.cpp) ist eine leistungsstarke C++-Inferenz-Engine mit GGUF-Modellunterstützung.

## Installation

```bash
brew install llama.cpp
llama-server -m model.gguf
```

## Details

| Eigenschaft | Wert |
|------------|------|
| Standardport | 8080 |
| API-Typ | OpenAI-kompatibel |
| VRAM-Berichterstattung | Nein |
| Modellformat | GGUF |
| Erkennung | `/health` + `/props`-Endpunkte oder `lsof`-Prozesserkennung |

## Hinweise

- llama.cpp teilt Port 8080 mit mlx-lm. asiai erkennt es über die `/health`- und `/props`-Endpunkte.
- Der Server kann mit benutzerdefinierten Kontextgrößen und Thread-Zahlen für Optimierung gestartet werden.

## Siehe auch

Vergleichen Sie Engines mit `asiai bench --engines llamacpp` --- [mehr erfahren](../benchmark-llm-mac.md)
