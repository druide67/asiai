# Primeiros passos

**Apple Silicon AI** — CLI multi-motor de benchmark e monitoramento LLM.

asiai compara motores de inferência lado a lado no seu Mac. Carregue o mesmo modelo no Ollama e LM Studio, execute `asiai bench` e obtenha os números. Sem suposições, sem achismos — apenas tok/s, TTFT, eficiência energética e estabilidade por motor.

## Início rápido

```bash
brew tap druide67/tap
brew install asiai
```

Ou com pip:

```bash
pip install asiai
```

Depois detecte seus motores:

```bash
asiai detect
```

E execute um benchmark:

```bash
asiai bench -m qwen3.5 --runs 3 --power
```

## O que medimos

| Métrica | Descrição |
|---------|-----------|
| **tok/s** | Velocidade de geração (tokens/seg), excluindo processamento de prompt |
| **TTFT** | Time to first token — latência de processamento do prompt |
| **Power** | Consumo de GPU em watts (`sudo powermetrics`) |
| **tok/s/W** | Eficiência energética — tokens por segundo por watt |
| **Stability** | Variância entre execuções: estável (<5%), variável (<10%), instável (>10%) |
| **VRAM** | Footprint de memória — nativo (Ollama, LM Studio) ou estimado via `ri_phys_footprint` (todos os motores) |
| **Thermal** | Estado de throttling da CPU e percentual de limitação |

## Motores suportados

| Motor | Porta | API |
|-------|-------|-----|
| [Ollama](https://ollama.com) | 11434 | Nativa |
| [LM Studio](https://lmstudio.ai) | 1234 | Compatível com OpenAI |
| [mlx-lm](https://github.com/ml-explore/mlx-examples) | 8080 | Compatível com OpenAI |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | 8080 | Compatível com OpenAI |
| [oMLX](https://github.com/jundot/omlx) | 8000 | Compatível com OpenAI |
| [vllm-mlx](https://github.com/vllm-project/vllm) | 8000 | Compatível com OpenAI |

## Requisitos

- macOS em Apple Silicon (M1 / M2 / M3 / M4)
- Python 3.11+
- Pelo menos um motor de inferência rodando localmente

## Zero dependências

O core usa apenas a biblioteca padrão do Python — `urllib`, `sqlite3`, `subprocess`, `argparse`. Sem `requests`, sem `psutil`, sem `rich`.

Extras opcionais:

- `asiai[tui]` — Dashboard de terminal Textual
- `asiai[dev]` — pytest, ruff, pytest-cov
