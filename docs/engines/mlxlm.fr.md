---
description: "Benchmark serveur mlx-lm sur Mac : optimal pour les modèles MoE, configuration port 8080 et données de performance Apple Silicon."
---

# mlx-lm

mlx-lm est le serveur d'inférence MLX de référence d'Apple, exécutant les modèles nativement sur le GPU Metal via le port 8080. Il est particulièrement efficace pour les modèles MoE (Mixture of Experts) sur Apple Silicon, tirant parti de la mémoire unifiée pour un chargement de modèle en zéro-copie.

[mlx-lm](https://github.com/ml-explore/mlx-examples) exécute les modèles nativement sur Apple MLX, offrant une utilisation efficace de la mémoire unifiée.

## Installation

```bash
brew install mlx-lm
mlx_lm.server --model mlx-community/gemma-2-9b-it-4bit
```

## Détails

| Propriété | Valeur |
|-----------|--------|
| Port par défaut | 8080 |
| Type d'API | Compatible OpenAI |
| Rapport VRAM | Non |
| Format de modèle | MLX (safetensors) |
| Détection | Endpoint `/version` ou détection de processus `lsof` |

## Notes

- mlx-lm partage le port 8080 avec llama.cpp. asiai utilise le sondage API et la détection de processus pour les distinguer.
- Les modèles utilisent le format HuggingFace/MLX community (ex. `mlx-community/gemma-2-9b-it-4bit`).
- L'exécution native MLX offre généralement d'excellentes performances sur Apple Silicon.

## Voir aussi

Comparez les moteurs avec `asiai bench --engines mlxlm` --- [en savoir plus](../benchmark-llm-mac.md)
