---
description: "Explora y consulta la tabla de clasificación comunitaria de asiai: compara resultados de benchmarks entre chips Apple Silicon y motores de inferencia."
---

# asiai leaderboard

Explora los datos de benchmarks comunitarios de la red asiai.

## Uso

```bash
asiai leaderboard [options]
```

## Opciones

| Opción | Descripción |
|--------|-------------|
| `--chip CHIP` | Filtrar por chip Apple Silicon (ej. `M4 Pro`, `M2 Ultra`) |
| `--model MODEL` | Filtrar por nombre de modelo |

## Ejemplo

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

## Notas

- Requiere la API comunitaria en `api.asiai.dev`.
- Los resultados son anónimos. No se comparten datos personales ni identificativos de la máquina.
- Contribuye con tus propios resultados con `asiai bench --share`.
