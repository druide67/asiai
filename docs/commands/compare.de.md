---
description: Modell- und Engine-übergreifende Benchmark-Matrix. Vergleichen Sie bis zu 8 model@engine-Kombinationen in einem Durchlauf.
---

# asiai compare

Vergleichen Sie Ihre lokalen Benchmarks mit Community-Daten.

## Verwendung

```bash
asiai compare [options]
```

## Optionen

| Option | Beschreibung |
|--------|-------------|
| `--chip CHIP` | Apple-Silicon-Chip zum Vergleich (Standard: Auto-Erkennung) |
| `--model MODEL` | Nach Modellname filtern |
| `--db PATH` | Pfad zur lokalen Benchmark-Datenbank |

## Beispiel

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

## Hinweise

- Wenn `--chip` nicht angegeben wird, erkennt asiai Ihren Apple-Silicon-Chip automatisch.
- Das Delta zeigt den prozentualen Unterschied zwischen Ihrem lokalen Median und dem Community-Median.
- Positive Deltas bedeuten, dass Ihr Setup schneller als der Community-Durchschnitt ist.
- Lokale Ergebnisse stammen aus Ihrer Benchmark-Verlaufsdatenbank (`~/.local/share/asiai/benchmarks.db` standardmäßig).
