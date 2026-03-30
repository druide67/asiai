---
description: Recommandations de modèles adaptées au matériel basées sur la RAM, les cœurs GPU et la marge thermique de votre Mac.
---

# asiai recommend

Obtenez des recommandations de moteur pour votre matériel et votre cas d'usage.

## Utilisation

```bash
asiai recommend [options]
```

## Options

| Option | Description |
|--------|-------------|
| `--model MODEL` | Modèle pour lequel obtenir des recommandations |
| `--use-case USE_CASE` | Optimiser pour : `throughput`, `latency` ou `efficiency` |
| `--community` | Inclure les données de benchmark communautaires dans les recommandations |
| `--db PATH` | Chemin vers la base de données de benchmarks locale |

## Sources de données

Les recommandations sont construites à partir des meilleures données disponibles, par ordre de priorité :

1. **Benchmarks locaux** — vos propres exécutions sur votre matériel
2. **Données communautaires** — résultats agrégés de puces similaires (avec `--community`)
3. **Heuristiques** — règles intégrées quand aucune donnée de benchmark n'est disponible

## Niveaux de confiance

| Niveau | Critères |
|--------|----------|
| Élevé | 5 exécutions de benchmark locales ou plus |
| Moyen | 1 à 4 exécutions locales, ou données communautaires disponibles |
| Faible | Basé sur les heuristiques, aucune donnée de benchmark |

## Exemple

```bash
asiai recommend --model qwen3.5 --use-case throughput
```

```
  Recommendation: qwen3.5 — M4 Pro — throughput

  #   Engine       tok/s    Confidence   Source
  ── ────────── ──────── ──────────── ──────────
  1   lmstudio    72.6     high         local (5 runs)
  2   ollama      30.4     high         local (5 runs)
  3   exo         18.2     medium       community

  Tip: lmstudio is 2.4x faster than ollama for this model.
```

## Notes

- Lancez d'abord `asiai bench` pour les recommandations les plus précises.
- Utilisez `--community` pour combler les lacunes quand vous n'avez pas benchmarké un moteur spécifique localement.
- Le cas d'usage `efficiency` prend en compte la consommation électrique (nécessite des données `--power` de benchmarks précédents).
