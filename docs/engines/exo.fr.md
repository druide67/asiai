---
description: "Inférence LLM distribuée Exo : benchmarkez plusieurs Mac ensemble, port 52415, configuration de cluster et performances."
---

# Exo

Exo permet l'inférence LLM distribuée en mutualisant la VRAM de plusieurs Mac Apple Silicon sur votre réseau local, sur le port 52415. Il permet d'exécuter des modèles 70B+ paramètres qui ne tiendraient pas sur une seule machine, avec découverte automatique des pairs et une API compatible OpenAI.

[Exo](https://github.com/exo-explore/exo) permet l'inférence distribuée sur plusieurs appareils Apple Silicon. Exécutez de grands modèles (70B+) en mutualisant la VRAM de plusieurs Mac.

## Installation

```bash
pip install exo-inference
exo
```

Ou installer depuis les sources :

```bash
git clone https://github.com/exo-explore/exo.git
cd exo && pip install -e .
exo
```

## Détails

| Propriété | Valeur |
|-----------|--------|
| Port par défaut | 52415 |
| Type d'API | Compatible OpenAI |
| Rapport VRAM | Oui (agrégé sur les nœuds du cluster) |
| Format de modèle | GGUF / MLX |
| Détection | Auto via DEFAULT_URLS |

## Benchmarking

```bash
asiai bench --engines exo -m llama3.3:70b
```

Exo est benchmarké comme tout autre moteur. asiai le détecte automatiquement sur le port 52415.

## Notes

- Exo découvre automatiquement les nœuds pairs sur le réseau local.
- La VRAM affichée dans asiai reflète la mémoire totale agrégée sur tous les nœuds du cluster.
- Les grands modèles qui ne tiennent pas sur un seul Mac peuvent tourner de manière transparente sur le cluster.
- Démarrez `exo` sur chaque Mac du cluster avant de lancer les benchmarks.

## Voir aussi

Comparez les moteurs avec `asiai bench --engines exo` --- [en savoir plus](../benchmark-llm-mac.md)
