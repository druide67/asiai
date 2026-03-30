---
description: Matriz de benchmark entre modelos y motores. Compara hasta 8 combinaciones modelo@motor en una sola ejecución.
---

# asiai compare

Compara tus benchmarks locales con los datos comunitarios.

## Uso

```bash
asiai compare [options]
```

## Opciones

| Opción | Descripción |
|--------|-------------|
| `--chip CHIP` | Chip Apple Silicon contra el cual comparar (por defecto: detección automática) |
| `--model MODEL` | Filtrar por nombre de modelo |
| `--db PATH` | Ruta a la base de datos de benchmarks local |

## Ejemplo

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

## Notas

- Si no se especifica `--chip`, asiai detecta automáticamente tu chip Apple Silicon.
- El delta muestra la diferencia porcentual entre tu mediana local y la mediana comunitaria.
- Los deltas positivos significan que tu configuración es más rápida que el promedio comunitario.
- Los resultados locales provienen de tu base de datos de historial de benchmarks (`~/.local/share/asiai/benchmarks.db` por defecto).
