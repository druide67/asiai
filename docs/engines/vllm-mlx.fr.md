---
description: "vLLM-MLX sur Apple Silicon : API compatible vLLM sur MLX, port 8000, métriques Prometheus et données de benchmark."
---

# vllm-mlx

vLLM-MLX apporte le framework de serving vLLM sur Apple Silicon via MLX, offrant du batching continu et une API compatible OpenAI sur le port 8000. Il peut atteindre 400+ tok/s sur les modèles optimisés, en faisant l'une des options les plus rapides pour l'inférence concurrente sur Mac.

[vllm-mlx](https://github.com/vllm-project/vllm) apporte le batching continu sur Apple Silicon via MLX.

## Installation

```bash
pip install vllm-mlx
vllm serve mlx-community/gemma-2-9b-it-4bit
```

## Détails

| Propriété | Valeur |
|-----------|--------|
| Port par défaut | 8000 |
| Type d'API | Compatible OpenAI |
| Rapport VRAM | Non |
| Format de modèle | MLX (safetensors) |
| Détection | Endpoint `/version` ou détection de processus `lsof` |

## Notes

- vllm-mlx supporte le batching continu, le rendant adapté au traitement de requêtes concurrentes.
- Peut atteindre 400+ tok/s sur Apple Silicon avec les modèles optimisés.
- Utilise l'API standard compatible OpenAI de vLLM.

## Voir aussi

Comparez les moteurs avec `asiai bench --engines vllm-mlx` --- [en savoir plus](../benchmark-llm-mac.md)
