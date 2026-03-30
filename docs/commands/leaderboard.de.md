---
description: "Das asiai-Community-Leaderboard durchsuchen und abfragen: Benchmark-Ergebnisse über Apple-Silicon-Chips und Inferenz-Engines vergleichen."
---

# asiai leaderboard

Community-Benchmark-Daten aus dem asiai-Netzwerk durchsuchen.

## Verwendung

```bash
asiai leaderboard [options]
```

## Optionen

| Option | Beschreibung |
|--------|-------------|
| `--chip CHIP` | Nach Apple-Silicon-Chip filtern (z.B. `M4 Pro`, `M2 Ultra`) |
| `--model MODEL` | Nach Modellname filtern |

## Beispiel

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

## Hinweise

- Erfordert die Community-API unter `api.asiai.dev`.
- Ergebnisse sind anonymisiert. Keine persönlichen oder maschinenidentifizierenden Daten werden geteilt.
- Tragen Sie Ihre eigenen Ergebnisse mit `asiai bench --share` bei.
