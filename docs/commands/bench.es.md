---
description: Ejecuta benchmarks comparativos de LLMs en Apple Silicon. Compara motores, mide tok/s, TTFT, eficiencia energética. Comparte resultados.
---

# asiai bench

Benchmark entre motores con prompts estandarizados.

## Uso

```bash
asiai bench [options]
```

## Opciones

| Opción | Descripción |
|--------|-------------|
| `-m, --model MODEL` | Modelo a evaluar (por defecto: detección automática) |
| `-e, --engines LIST` | Filtrar motores (ej. `ollama,lmstudio,mlxlm`) |
| `-p, --prompts LIST` | Tipos de prompt: `code`, `tool_call`, `reasoning`, `long_gen` |
| `-r, --runs N` | Ejecuciones por prompt (por defecto: 3, para mediana + desviación estándar) |
| `--power` | Validación cruzada de potencia con sudo powermetrics (IOReport siempre activo) |
| `--context-size SIZE` | Prompt de llenado de contexto: `4k`, `16k`, `32k`, `64k` |
| `--export FILE` | Exportar resultados a archivo JSON |
| `-H, --history PERIOD` | Mostrar benchmarks anteriores (ej. `7d`, `24h`) |
| `-Q, --quick` | Benchmark rápido: 1 prompt (code), 1 ejecución (~15 segundos) |
| `--compare MODEL [MODEL...]` | Comparación entre modelos (2-8 modelos, mutuamente excluyente con `-m`) |
| `--card` | Generar una tarjeta de benchmark compartible (SVG local, PNG con `--share`) |
| `--share` | Compartir resultados en la base de datos comunitaria |

## Ejemplo

```bash
asiai bench -m qwen3.5 --runs 3 --power
```

```
  Mac Mini M4 Pro — Apple M4 Pro  RAM: 64.0 GB (42% used)  Pressure: normal

Benchmark: qwen3.5

  Engine       tok/s (±stddev)    Tokens   Duration     TTFT       VRAM    Thermal
  ────────── ───────────────── ───────── ────────── ──────── ────────── ──────────
  lmstudio    72.6 ± 0.0 (stable)   435    6.20s    0.28s        —    nominal
  ollama      30.4 ± 0.1 (stable)   448   15.28s    0.25s   26.0 GB   nominal

  Winner: lmstudio (2.4x faster)
  Power: lmstudio 13.2W (5.52 tok/s/W) — ollama 16.0W (1.89 tok/s/W)
```

## Prompts

Cuatro prompts estandarizados prueban diferentes patrones de generación:

| Nombre | Tokens | Evalúa |
|------|--------|-------|
| `code` | 512 | Generación de código estructurado (BST en Python) |
| `tool_call` | 256 | Llamadas a funciones JSON / seguimiento de instrucciones |
| `reasoning` | 384 | Problema matemático de múltiples pasos |
| `long_gen` | 1024 | Rendimiento sostenido (script bash) |

Usa `--context-size` para probar con prompts de llenado de contexto grande.

## Coincidencia de modelos entre motores

El runner resuelve nombres de modelos entre motores automáticamente — `gemma2:9b` (Ollama) y `gemma-2-9b` (LM Studio) se reconocen como el mismo modelo.

## Exportación JSON

Exporta resultados para compartir o analizar:

```bash
asiai bench -m qwen3.5 --export bench.json
```

El JSON incluye metadatos de la máquina, estadísticas por motor (mediana, IC 95%, P50/P90/P99), datos por ejecución y una versión de esquema para compatibilidad futura.

## Detección de regresión

Después de cada benchmark, asiai compara los resultados con el historial de los últimos 7 días y advierte sobre regresiones de rendimiento (ej. después de una actualización del motor o de macOS).

## Benchmark rápido

Ejecuta un benchmark rápido con un solo prompt y una ejecución (~15 segundos):

```bash
asiai bench --quick
asiai bench -Q -m qwen3.5
```

Ideal para demos, GIFs y verificaciones rápidas. El prompt `code` se usa por defecto. Puedes anularlo con `--prompts` si es necesario.

## Comparación entre modelos

Compara múltiples modelos en una sola sesión con `--compare`:

```bash
# Expandir automáticamente a todos los motores disponibles
asiai bench --compare qwen3.5:4b deepseek-r1:7b

# Filtrar a un motor específico
asiai bench --compare qwen3.5:4b deepseek-r1:7b -e ollama

# Fijar cada modelo a un motor con @
asiai bench --compare qwen3.5:4b@lmstudio deepseek-r1:7b@ollama
```

La notación `@` divide en el **último** `@` de la cadena, por lo que los nombres de modelos que contienen `@` se manejan correctamente.

### Reglas

- `--compare` y `--model` son **mutuamente excluyentes** — usa uno u otro.
- Acepta de 2 a 8 slots de modelo.
- Sin `@`, cada modelo se expande a todos los motores donde está disponible.

### Tipos de sesión

El tipo de sesión se detecta automáticamente según la lista de slots:

| Tipo | Condición | Ejemplo |
|------|-----------|---------|
| **engine** | Mismo modelo, diferentes motores | `--compare qwen3.5:4b@lmstudio qwen3.5:4b@ollama` |
| **model** | Diferentes modelos, mismo motor | `--compare qwen3.5:4b deepseek-r1:7b -e ollama` |
| **matrix** | Mezcla de modelos y motores | `--compare qwen3.5:4b@lmstudio deepseek-r1:7b@ollama` |

### Combinado con otras opciones

`--compare` funciona con todas las opciones de salida y ejecución:

```bash
asiai bench --compare qwen3.5:4b deepseek-r1:7b --quick
asiai bench --compare qwen3.5:4b deepseek-r1:7b --card --share
asiai bench --compare qwen3.5:4b deepseek-r1:7b --runs 5 --power
```

## Tarjeta de benchmark

Genera una tarjeta de benchmark compartible:

```bash
asiai bench --card                    # SVG guardado localmente
asiai bench --card --share            # SVG + PNG (vía API comunitaria)
asiai bench --quick --card --share    # Benchmark rápido + tarjeta + compartir
```

La tarjeta es una imagen de 1200x630 con tema oscuro que incluye:
- Nombre del modelo e insignia del chip de hardware
- Banner de especificaciones: cuantización, RAM, núcleos GPU, tamaño de contexto
- Gráfico de barras estilo terminal de tok/s por motor
- Resaltado del ganador con delta (ej. "2.4x")
- Chips de métricas: tok/s, TTFT, estabilidad, VRAM, potencia (W + tok/s/W), versión del motor
- Marca asiai

El SVG se guarda en `~/.local/share/asiai/cards/`. Con `--share`, también se descarga un PNG desde la API.

## Compartir con la comunidad

Comparte tus resultados de forma anónima:

```bash
asiai bench --share
```

Consulta la tabla de clasificación comunitaria con `asiai leaderboard`.

## Detección de degradación térmica

Al ejecutar 3+ ejecuciones, asiai detecta la degradación monótona de tok/s entre ejecuciones consecutivas. Si tok/s cae consistentemente (>5%), se emite una advertencia indicando posible acumulación de throttling térmico.
