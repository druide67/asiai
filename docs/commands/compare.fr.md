---
description: Matrice de benchmark inter-modèles et inter-moteurs. Comparez jusqu'à 8 combinaisons model@engine en une seule exécution.
---

# asiai compare

Comparez vos benchmarks locaux avec les données communautaires.

## Utilisation

```bash
asiai compare [options]
```

## Options

| Option | Description |
|--------|-------------|
| `--chip CHIP` | Puce Apple Silicon pour la comparaison (par défaut : auto-détection) |
| `--model MODEL` | Filtrer par nom de modèle |
| `--db PATH` | Chemin vers la base de données de benchmarks locale |

## Exemple

```bash
asiai compare --model qwen3.5
```

```
  Compare: qwen3.5 — M4 Pro

  Engine       Your tok/s   Community median   Delta
  ────────── ──────────── ────────────────── ────────
  lmstudio        72.6           70.1          +3.6%
  ollama          30.4           31.0          -1.9%

  Chip: Apple M4 Pro (auto-detected)
```

## Notes

- Si `--chip` n'est pas spécifié, asiai détecte automatiquement votre puce Apple Silicon.
- Le delta montre le pourcentage de différence entre votre médiane locale et la médiane communautaire.
- Les deltas positifs signifient que votre configuration est plus rapide que la moyenne communautaire.
- Les résultats locaux proviennent de votre base de données d'historique de benchmarks (`~/.local/share/asiai/benchmarks.db` par défaut).
