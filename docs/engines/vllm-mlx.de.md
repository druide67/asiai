---
description: "vLLM-MLX auf Apple Silicon: vLLM-kompatible API auf MLX, Port 8000, Prometheus-Metriken und Benchmark-Daten."
---

# vllm-mlx

vLLM-MLX bringt das vLLM-Serving-Framework über MLX auf Apple Silicon und bietet Continuous Batching und eine OpenAI-kompatible API auf Port 8000. Es kann 400+ tok/s bei optimierten Modellen erreichen und ist damit eine der schnellsten Optionen für gleichzeitige Inferenz auf dem Mac.

[vllm-mlx](https://github.com/vllm-project/vllm) bringt Continuous Batching über MLX auf Apple Silicon.

## Installation

```bash
pip install vllm-mlx
vllm serve mlx-community/gemma-2-9b-it-4bit
```

## Details

| Eigenschaft | Wert |
|------------|------|
| Standardport | 8000 |
| API-Typ | OpenAI-kompatibel |
| VRAM-Berichterstattung | Nein |
| Modellformat | MLX (safetensors) |
| Erkennung | `/version`-Endpunkt oder `lsof`-Prozesserkennung |

## Hinweise

- vllm-mlx unterstützt Continuous Batching und eignet sich für die Verarbeitung gleichzeitiger Anfragen.
- Kann 400+ tok/s auf Apple Silicon mit optimierten Modellen erreichen.
- Verwendet die standardmäßige vLLM-OpenAI-kompatible API.

## Siehe auch

Vergleichen Sie Engines mit `asiai bench --engines vllm-mlx` --- [mehr erfahren](../benchmark-llm-mac.md)
