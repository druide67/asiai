---
description: Recomendaciones de modelos basadas en hardware según la RAM, núcleos GPU y margen térmico de tu Mac.
---

# asiai recommend

Obtén recomendaciones de motores para tu hardware y caso de uso.

## Uso

```bash
asiai recommend [options]
```

## Opciones

| Opción | Descripción |
|--------|-------------|
| `--model MODEL` | Modelo para el cual obtener recomendaciones |
| `--use-case USE_CASE` | Optimizar para: `throughput`, `latency` o `efficiency` |
| `--community` | Incluir datos de benchmarks comunitarios en las recomendaciones |
| `--db PATH` | Ruta a la base de datos de benchmarks local |

## Fuentes de datos

Las recomendaciones se construyen a partir de los mejores datos disponibles, en orden de prioridad:

1. **Benchmarks locales** — tus propias ejecuciones en tu hardware
2. **Datos comunitarios** — resultados agregados de chips similares (con `--community`)
3. **Heurísticas** — reglas integradas cuando no hay datos de benchmark disponibles

## Niveles de confianza

| Nivel | Criterio |
|-------|----------|
| Alto | 5 o más ejecuciones de benchmark locales |
| Medio | 1 a 4 ejecuciones locales, o datos comunitarios disponibles |
| Bajo | Basado en heurísticas, sin datos de benchmark |

## Ejemplo

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

## Notas

- Ejecuta `asiai bench` primero para obtener las recomendaciones más precisas.
- Usa `--community` para llenar vacíos cuando no hayas evaluado un motor específico localmente.
- El caso de uso `efficiency` tiene en cuenta el consumo de energía (requiere datos de `--power` de benchmarks anteriores).
