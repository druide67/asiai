---
description: "Parcourir et interroger le classement communautaire asiai : comparez les résultats de benchmark sur les puces Apple Silicon et les moteurs d'inférence."
---

# asiai leaderboard

Parcourir les données de benchmark communautaires du réseau asiai.

## Utilisation

```bash
asiai leaderboard [options]
```

## Options

| Option | Description |
|--------|-------------|
| `--chip CHIP` | Filtrer par puce Apple Silicon (ex. `M4 Pro`, `M2 Ultra`) |
| `--model MODEL` | Filtrer par nom de modèle |

## Exemple

```bash
asiai leaderboard --chip "M4 Pro"
```

```
  Community Leaderboard — M4 Pro

  Model                  Engine      tok/s (median)   Runs   Contributors
  ──────────────────── ────────── ──────────────── ────── ──────────────
  qwen3.5:35b-a3b       ollama          30.4          42         12
  qwen3.5:35b-a3b       lmstudio        72.6          38         11
  llama3.3:70b           exo            18.2          15          4
  gemma2:9b              mlx-lm        105.3          27          9

  Source: api.asiai.dev — 122 results
```

## Notes

- Nécessite l'API communautaire sur `api.asiai.dev`.
- Les résultats sont anonymisés. Aucune donnée personnelle ou identifiant de machine n'est partagée.
- Contribuez vos propres résultats avec `asiai bench --share`.
