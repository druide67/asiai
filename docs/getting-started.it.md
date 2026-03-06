# Per iniziare

**Apple Silicon AI** — CLI multi-motore per benchmark e monitoraggio LLM.

asiai confronta i motori di inferenza fianco a fianco sul tuo Mac. Carica lo stesso modello su Ollama e LM Studio, esegui `asiai bench` e ottieni i numeri. Niente supposizioni, niente sensazioni — solo tok/s, TTFT, efficienza energetica e stabilità per motore.

## Avvio rapido

```bash
brew tap druide67/tap
brew install asiai
```

O con pip:

```bash
pip install asiai
```

Poi rileva i tuoi motori:

```bash
asiai detect
```

E esegui un benchmark:

```bash
asiai bench -m qwen3.5 --runs 3 --power
```

## Cosa misuriamo

| Metrica | Descrizione |
|---------|-------------|
| **tok/s** | Velocità di generazione (token/sec), esclusa l'elaborazione del prompt |
| **TTFT** | Time to first token — latenza di elaborazione del prompt |
| **Power** | Consumo GPU in watt (`sudo powermetrics`) |
| **tok/s/W** | Efficienza energetica — token al secondo per watt |
| **Stability** | Varianza tra esecuzioni: stabile (<5%), variabile (<10%), instabile (>10%) |
| **VRAM** | Footprint memoria GPU (solo Ollama) |
| **Thermal** | Stato di throttling CPU e percentuale di limitazione |

## Motori supportati

| Motore | Porta | API |
|--------|-------|-----|
| [Ollama](https://ollama.com) | 11434 | Nativa |
| [LM Studio](https://lmstudio.ai) | 1234 | Compatibile OpenAI |
| [mlx-lm](https://github.com/ml-explore/mlx-examples) | 8080 | Compatibile OpenAI |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | 8080 | Compatibile OpenAI |
| [vllm-mlx](https://github.com/vllm-project/vllm) | 8000 | Compatibile OpenAI |

## Requisiti

- macOS su Apple Silicon (M1 / M2 / M3 / M4)
- Python 3.11+
- Almeno un motore di inferenza in esecuzione locale

## Zero dipendenze

Il core usa solo la libreria standard Python — `urllib`, `sqlite3`, `subprocess`, `argparse`. Nessun `requests`, nessun `psutil`, nessun `rich`.

Extra opzionali:

- `asiai[tui]` — Dashboard terminale Textual
- `asiai[dev]` — pytest, ruff, pytest-cov
