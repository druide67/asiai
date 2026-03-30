---
description: "Quelle est la vitesse d'Ollama sur Apple Silicon ? Configuration de benchmark, port par défaut (11434), conseils de performance et comparaison avec d'autres moteurs."
---

# Ollama

Ollama est le moteur d'inférence LLM le plus populaire pour Mac, utilisant un backend llama.cpp avec des modèles GGUF sur le port 11434. Dans nos benchmarks sur M4 Pro 64 Go, il atteint 70 tok/s sur Qwen3-Coder-30B mais est 46% plus lent que LM Studio (MLX) en débit.

[Ollama](https://ollama.com) est le runner LLM local le plus populaire. asiai utilise son API native.

## Installation

```bash
brew install ollama
ollama serve
ollama pull gemma2:9b
```

## Détails

| Propriété | Valeur |
|-----------|--------|
| Port par défaut | 11434 |
| Type d'API | Native (non-OpenAI) |
| Rapport VRAM | Oui |
| Format de modèle | GGUF |
| Mesure du temps de chargement | Oui (via démarrage à froid `/api/generate`) |

## Notes

- Ollama rapporte l'utilisation VRAM par modèle, qu'asiai affiche dans les sorties benchmark et monitor.
- Les noms de modèles utilisent le format `nom:tag` (ex. `gemma2:9b`, `qwen3.5:35b-a3b`).
- asiai envoie `temperature: 0` pour des résultats de benchmark déterministes.

## Voir aussi

Voyez comment Ollama se compare : [Benchmark Ollama vs LM Studio](../ollama-vs-lmstudio.md)
