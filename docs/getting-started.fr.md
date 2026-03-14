# Premiers pas

**Apple Silicon AI** — CLI multi-moteur de benchmark et monitoring LLM.

asiai compare les moteurs d'inférence côte à côte sur votre Mac. Chargez le même modèle sur Ollama et LM Studio, lancez `asiai bench`, obtenez les chiffres. Pas de suppositions, pas de feeling — juste tok/s, TTFT, efficacité énergétique et stabilité par moteur.

## Démarrage rapide

```bash
brew tap druide67/tap
brew install asiai
```

Ou avec pip :

```bash
pip install asiai
```

Puis détectez vos moteurs :

```bash
asiai detect
```

Et lancez un benchmark :

```bash
asiai bench -m qwen3.5 --runs 3 --power
```

## Ce qu'on mesure

| Métrique | Description |
|----------|-------------|
| **tok/s** | Vitesse de génération (tokens/sec), hors traitement du prompt |
| **TTFT** | Time to first token — latence de traitement du prompt |
| **Power** | Consommation GPU en watts (`sudo powermetrics`) |
| **tok/s/W** | Efficacité énergétique — tokens par seconde par watt |
| **Stability** | Variance inter-runs : stable (<5%), variable (<10%), instable (>10%) |
| **VRAM** | Empreinte mémoire GPU (Ollama, LM Studio) |
| **Thermal** | État de throttling CPU et pourcentage de limitation |

## Moteurs supportés

| Moteur | Port | API |
|--------|------|-----|
| [Ollama](https://ollama.com) | 11434 | Native |
| [LM Studio](https://lmstudio.ai) | 1234 | Compatible OpenAI |
| [mlx-lm](https://github.com/ml-explore/mlx-examples) | 8080 | Compatible OpenAI |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | 8080 | Compatible OpenAI |
| [oMLX](https://github.com/jundot/omlx) | 8000 | Compatible OpenAI |
| [vllm-mlx](https://github.com/vllm-project/vllm) | 8000 | Compatible OpenAI |

## Prérequis

- macOS sur Apple Silicon (M1 / M2 / M3 / M4)
- Python 3.11+
- Au moins un moteur d'inférence en local

## Zéro dépendance

Le cœur utilise uniquement la bibliothèque standard Python — `urllib`, `sqlite3`, `subprocess`, `argparse`. Pas de `requests`, pas de `psutil`, pas de `rich`.

Extras optionnels :

- `asiai[tui]` — Dashboard terminal Textual
- `asiai[dev]` — pytest, ruff, pytest-cov
