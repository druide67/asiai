---
description: "Sfoglia e interroga la classifica comunitaria di asiai: confronta i risultati benchmark tra chip Apple Silicon e motori di inferenza."
---

# asiai leaderboard

Sfoglia i dati benchmark della community dalla rete asiai.

## Uso

```bash
asiai leaderboard [options]
```

## Opzioni

| Opzione | Descrizione |
|--------|-------------|
| `--chip CHIP` | Filtra per chip Apple Silicon (es. `M4 Pro`, `M2 Ultra`) |
| `--model MODEL` | Filtra per nome modello |

## Esempio

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

## Note

- Richiede l'API comunitaria su `api.asiai.dev`.
- I risultati sono anonimi. Nessun dato personale o identificativo della macchina viene condiviso.
- Contribuisci con i tuoi risultati con `asiai bench --share`.
