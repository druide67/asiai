---
description: "Alle geladenen LLM-Modelle über Engines auflisten: VRAM-Nutzung, Quantisierung, Kontextlänge und Format für jedes Modell anzeigen."
---

# asiai models

Geladene Modelle über alle erkannten Engines auflisten.

## Verwendung

```bash
asiai models
```

## Ausgabe

```
ollama  v0.17.5  http://localhost:11434
  ● qwen3.5:35b-a3b                             26.0 GB Q4_K_M

lmstudio  v0.4.6  http://localhost:1234
  ● qwen3.5-35b-a3b                              9.2 GB    MLX
```

Zeigt Engine-Version, Modellname, VRAM-Nutzung (wenn verfügbar), Format und Quantisierungsstufe für jede Engine.

VRAM wird von Ollama und LM Studio nativ gemeldet. Für andere Engines schätzt asiai die Speichernutzung über `ri_phys_footprint` (die macOS-Physical-Footprint-Metrik, identisch mit der Aktivitätsanzeige). Geschätzte Werte sind mit „(est.)" gekennzeichnet.
