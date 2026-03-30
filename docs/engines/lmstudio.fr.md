---
description: "Benchmark LM Studio sur Apple Silicon : moteur MLX le plus rapide, configuration port 1234, utilisation VRAM et comparaison avec Ollama."
---

# LM Studio

LM Studio est le moteur d'inférence MLX le plus rapide sur Apple Silicon, servant les modèles sur le port 1234 avec une API compatible OpenAI. Sur M4 Pro 64 Go, il atteint 130 tok/s sur Qwen3-Coder-30B (MLX), près de 2x plus rapide que le backend llama.cpp d'Ollama pour les modèles MoE.

[LM Studio](https://lmstudio.ai) fournit une API compatible OpenAI avec une interface graphique pour la gestion des modèles.

## Installation

```bash
brew install --cask lm-studio
```

Démarrez le serveur local depuis l'application LM Studio, puis chargez un modèle.

## Détails

| Propriété | Valeur |
|-----------|--------|
| Port par défaut | 1234 |
| Type d'API | Compatible OpenAI |
| Rapport VRAM | Oui (via le CLI `lms ps --json`) |
| Format de modèle | GGUF, MLX |
| Détection | Endpoint `/lms/version` ou plist du bundle applicatif |

## Rapport VRAM

Depuis la v0.7.0, asiai récupère l'utilisation VRAM depuis le CLI LM Studio (`~/.lmstudio/bin/lms ps --json`). Cela fournit des données précises de taille de modèle que l'API compatible OpenAI n'expose pas.

Si le CLI `lms` n'est pas installé ou indisponible, asiai se rabat gracieusement sur un rapport VRAM à 0 (même comportement qu'avant la v0.7.0).

## Notes

- LM Studio supporte les formats de modèle GGUF et MLX.
- La détection de version utilise l'endpoint API `/lms/version`, avec un repli sur le plist du bundle applicatif sur disque.
- Les noms de modèles utilisent généralement le format HuggingFace (ex. `gemma-2-9b-it`).

## Voir aussi

Voyez comment LM Studio se compare : [Benchmark Ollama vs LM Studio](../ollama-vs-lmstudio.md)
