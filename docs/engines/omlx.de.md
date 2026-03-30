---
description: "oMLX Benchmark auf Apple Silicon: SSD-KV-Caching, Continuous Batching, Port 8000 und Leistungsvergleich."
---

# oMLX

oMLX ist ein nativer macOS-Inferenzserver, der paginiertes SSD-KV-Caching nutzt, um größere Kontextfenster zu handhaben als der Speicher allein erlauben würde, mit Continuous Batching für gleichzeitige Anfragen auf Port 8000. Es unterstützt sowohl OpenAI- als auch Anthropic-kompatible APIs auf Apple Silicon.

[oMLX](https://omlx.ai/) ist ein nativer macOS-LLM-Inferenzserver mit paginiertem SSD-KV-Caching und Continuous Batching, verwaltet über die Menüleiste. Gebaut auf MLX für Apple Silicon.

## Installation

```bash
brew tap jundot/omlx https://github.com/jundot/omlx
brew install omlx
```

Oder laden Sie die `.dmg` von den [GitHub Releases](https://github.com/jundot/omlx/releases) herunter.

## Details

| Eigenschaft | Wert |
|------------|------|
| Standardport | 8000 |
| API-Typ | OpenAI-kompatibel + Anthropic-kompatibel |
| VRAM-Berichterstattung | Nein |
| Modellformat | MLX (safetensors) |
| Erkennung | `/admin/info`-JSON-Endpunkt oder `/admin`-HTML-Seite |
| Voraussetzungen | macOS 15+, Apple Silicon (M1+), mind. 16 GB RAM |

## Hinweise

- oMLX teilt Port 8000 mit vllm-mlx. asiai verwendet `/admin/info`-Probing, um sie zu unterscheiden.
- SSD-KV-Caching ermöglicht größere Kontextfenster bei geringerem Speicherdruck.
- Continuous Batching verbessert den Durchsatz bei gleichzeitigen Anfragen.
- Unterstützt Text-LLMs, Vision-Language-Modelle, OCR-Modelle, Embeddings und Reranker.
- Das Admin-Dashboard unter `/admin` bietet Echtzeit-Servermetriken.
- Integriertes Auto-Update bei Installation über `.dmg`.

## Siehe auch

Vergleichen Sie Engines mit `asiai bench --engines omlx` --- [mehr erfahren](../benchmark-llm-mac.md)
