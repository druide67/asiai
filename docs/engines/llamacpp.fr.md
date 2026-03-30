---
description: "Serveur llama.cpp sur Mac : contrôle bas niveau, port 8080, métriques KV cache et résultats de benchmark sur Apple Silicon."
---

# llama.cpp

llama.cpp est le moteur d'inférence C++ fondamental pour les modèles GGUF, offrant un contrôle bas niveau maximal sur le KV cache, le nombre de threads et la taille de contexte sur le port 8080. Il alimente le backend d'Ollama mais peut être exécuté de manière autonome pour un réglage fin sur Apple Silicon.

[llama.cpp](https://github.com/ggml-org/llama.cpp) est un moteur d'inférence C++ haute performance supportant les modèles GGUF.

## Installation

```bash
brew install llama.cpp
llama-server -m model.gguf
```

## Détails

| Propriété | Valeur |
|-----------|--------|
| Port par défaut | 8080 |
| Type d'API | Compatible OpenAI |
| Rapport VRAM | Non |
| Format de modèle | GGUF |
| Détection | Endpoints `/health` + `/props` ou détection de processus `lsof` |

## Notes

- llama.cpp partage le port 8080 avec mlx-lm. asiai le détecte via les endpoints `/health` et `/props`.
- Le serveur peut être démarré avec des tailles de contexte et des nombres de threads personnalisés pour le réglage.

## Voir aussi

Comparez les moteurs avec `asiai bench --engines llamacpp` --- [en savoir plus](../benchmark-llm-mac.md)
