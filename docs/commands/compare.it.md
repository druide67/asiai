---
description: Matrice di benchmark cross-model e cross-engine. Confronta fino a 8 combinazioni modello@motore in una singola esecuzione.
---

# asiai compare

Confronta i tuoi benchmark locali con i dati della community.

## Uso

```bash
asiai compare [options]
```

## Opzioni

| Opzione | Descrizione |
|--------|-------------|
| `--chip CHIP` | Chip Apple Silicon contro cui confrontare (default: rilevamento automatico) |
| `--model MODEL` | Filtra per nome modello |
| `--db PATH` | Percorso al database benchmark locale |

## Esempio

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

## Note

- Se `--chip` non è specificato, asiai rileva automaticamente il tuo chip Apple Silicon.
- Il delta mostra la differenza percentuale tra la tua mediana locale e la mediana della community.
- Delta positivi significano che la tua configurazione è più veloce della media comunitaria.
- I risultati locali provengono dal tuo database storico di benchmark (`~/.local/share/asiai/benchmarks.db` di default).
