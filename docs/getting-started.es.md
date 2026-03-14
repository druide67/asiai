# Primeros pasos

**Apple Silicon AI** — CLI multi-motor de benchmark y monitoreo LLM.

asiai compara motores de inferencia lado a lado en tu Mac. Carga el mismo modelo en Ollama y LM Studio, ejecuta `asiai bench` y obtén los números. Sin suposiciones, sin vibraciones — solo tok/s, TTFT, eficiencia energética y estabilidad por motor.

## Inicio rápido

```bash
brew tap druide67/tap
brew install asiai
```

O con pip:

```bash
pip install asiai
```

Luego detecta tus motores:

```bash
asiai detect
```

Y ejecuta un benchmark:

```bash
asiai bench -m qwen3.5 --runs 3 --power
```

## Qué medimos

| Métrica | Descripción |
|---------|-------------|
| **tok/s** | Velocidad de generación (tokens/seg), excluyendo procesamiento de prompt |
| **TTFT** | Time to first token — latencia de procesamiento del prompt |
| **Power** | Consumo de GPU en vatios (`sudo powermetrics`) |
| **tok/s/W** | Eficiencia energética — tokens por segundo por vatio |
| **Stability** | Varianza entre ejecuciones: estable (<5%), variable (<10%), inestable (>10%) |
| **VRAM** | Huella de memoria GPU (Ollama, LM Studio) |
| **Thermal** | Estado de throttling de CPU y porcentaje de limitación |

## Motores soportados

| Motor | Puerto | API |
|-------|--------|-----|
| [Ollama](https://ollama.com) | 11434 | Nativa |
| [LM Studio](https://lmstudio.ai) | 1234 | Compatible con OpenAI |
| [mlx-lm](https://github.com/ml-explore/mlx-examples) | 8080 | Compatible con OpenAI |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | 8080 | Compatible con OpenAI |
| [oMLX](https://github.com/jundot/omlx) | 8000 | Compatible con OpenAI |
| [vllm-mlx](https://github.com/vllm-project/vllm) | 8000 | Compatible con OpenAI |

## Requisitos

- macOS en Apple Silicon (M1 / M2 / M3 / M4)
- Python 3.11+
- Al menos un motor de inferencia ejecutándose localmente

## Sin dependencias

El núcleo usa solo la biblioteca estándar de Python — `urllib`, `sqlite3`, `subprocess`, `argparse`. Sin `requests`, sin `psutil`, sin `rich`.

Extras opcionales:

- `asiai[tui]` — Dashboard de terminal Textual
- `asiai[dev]` — pytest, ruff, pytest-cov
