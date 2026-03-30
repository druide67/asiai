---
description: "Benchmark oMLX sur Apple Silicon : KV caching SSD, batching continu, port 8000 et comparaison de performances."
---

# oMLX

oMLX est un serveur d'inférence natif macOS qui utilise le KV caching SSD paginé pour gérer des fenêtres de contexte plus grandes que ce que la mémoire seule permettrait, avec du batching continu pour les requêtes concurrentes sur le port 8000. Il supporte les API compatibles OpenAI et Anthropic sur Apple Silicon.

[oMLX](https://omlx.ai/) est un serveur d'inférence LLM natif macOS avec KV caching SSD paginé et batching continu, géré depuis la barre de menus. Construit sur MLX pour Apple Silicon.

## Installation

```bash
brew tap jundot/omlx https://github.com/jundot/omlx
brew install omlx
```

Ou téléchargez le `.dmg` depuis les [releases GitHub](https://github.com/jundot/omlx/releases).

## Détails

| Propriété | Valeur |
|-----------|--------|
| Port par défaut | 8000 |
| Type d'API | Compatible OpenAI + compatible Anthropic |
| Rapport VRAM | Non |
| Format de modèle | MLX (safetensors) |
| Détection | Endpoint JSON `/admin/info` ou page HTML `/admin` |
| Prérequis | macOS 15+, Apple Silicon (M1+), 16 Go RAM min |

## Notes

- oMLX partage le port 8000 avec vllm-mlx. asiai utilise le sondage `/admin/info` pour les distinguer.
- Le KV caching SSD permet des fenêtres de contexte plus grandes avec moins de pression mémoire.
- Le batching continu améliore le débit sous requêtes concurrentes.
- Supporte les LLM texte, modèles vision-langage, modèles OCR, embeddings et rerankers.
- Le dashboard admin sur `/admin` fournit des métriques serveur en temps réel.
- Mise à jour automatique intégrée quand installé via `.dmg`.

## Voir aussi

Comparez les moteurs avec `asiai bench --engines omlx` --- [en savoir plus](../benchmark-llm-mac.md)
