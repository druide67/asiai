---
description: "Verteilte LLM-Inferenz mit Exo: mehrere Macs gemeinsam benchmarken, Port 52415, Cluster-Setup und Leistung."
---

# Exo

Exo ermöglicht verteilte LLM-Inferenz, indem es VRAM über mehrere Apple-Silicon-Macs in Ihrem lokalen Netzwerk auf Port 52415 bündelt. Es ermöglicht die Ausführung von 70B+-Parametermodellen, die nicht auf eine einzelne Maschine passen würden, mit automatischer Peer-Erkennung und einer OpenAI-kompatiblen API.

[Exo](https://github.com/exo-explore/exo) ermöglicht verteilte Inferenz über mehrere Apple-Silicon-Geräte. Führen Sie große Modelle (70B+) aus, indem Sie VRAM von mehreren Macs bündeln.

## Installation

```bash
pip install exo-inference
exo
```

Oder aus dem Quellcode installieren:

```bash
git clone https://github.com/exo-explore/exo.git
cd exo && pip install -e .
exo
```

## Details

| Eigenschaft | Wert |
|------------|------|
| Standardport | 52415 |
| API-Typ | OpenAI-kompatibel |
| VRAM-Berichterstattung | Ja (aggregiert über Cluster-Knoten) |
| Modellformat | GGUF / MLX |
| Erkennung | Auto über DEFAULT_URLS |

## Benchmarking

```bash
asiai bench --engines exo -m llama3.3:70b
```

Exo wird wie jede andere Engine benchmarkt. asiai erkennt es automatisch auf Port 52415.

## Hinweise

- Exo entdeckt Peer-Knoten automatisch im lokalen Netzwerk.
- Die in asiai angezeigte VRAM spiegelt den gesamten über alle Cluster-Knoten aggregierten Speicher wider.
- Große Modelle, die nicht auf einen einzelnen Mac passen, können nahtlos über den Cluster laufen.
- Starten Sie `exo` auf jedem Mac im Cluster, bevor Sie Benchmarks ausführen.

## Siehe auch

Vergleichen Sie Engines mit `asiai bench --engines exo` --- [mehr erfahren](../benchmark-llm-mac.md)
