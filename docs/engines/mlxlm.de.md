---
description: "mlx-lm Server Benchmark auf dem Mac: optimal für MoE-Modelle, Port 8080 Konfiguration und Apple Silicon Leistungsdaten."
---

# mlx-lm

mlx-lm ist Apples Referenz-MLX-Inferenzserver, der Modelle nativ auf der Metal-GPU über Port 8080 ausführt. Es ist besonders effizient für MoE-Modelle (Mixture of Experts) auf Apple Silicon und nutzt Unified Memory für das Laden von Modellen ohne Kopiervorgang.

[mlx-lm](https://github.com/ml-explore/mlx-examples) führt Modelle nativ auf Apple MLX aus und bietet effiziente Unified-Memory-Nutzung.

## Installation

```bash
brew install mlx-lm
mlx_lm.server --model mlx-community/gemma-2-9b-it-4bit
```

## Details

| Eigenschaft | Wert |
|------------|------|
| Standardport | 8080 |
| API-Typ | OpenAI-kompatibel |
| VRAM-Berichterstattung | Nein |
| Modellformat | MLX (safetensors) |
| Erkennung | `/version`-Endpunkt oder `lsof`-Prozesserkennung |

## Hinweise

- mlx-lm teilt Port 8080 mit llama.cpp. asiai verwendet API-Probing und Prozesserkennung, um sie zu unterscheiden.
- Modelle verwenden das HuggingFace/MLX-Community-Format (z.B. `mlx-community/gemma-2-9b-it-4bit`).
- Native MLX-Ausführung bietet typischerweise hervorragende Leistung auf Apple Silicon.

## Siehe auch

Vergleichen Sie Engines mit `asiai bench --engines mlxlm` --- [mehr erfahren](../benchmark-llm-mac.md)
