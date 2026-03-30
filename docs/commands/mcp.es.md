---
description: Servidor MCP que expone 11 herramientas para que agentes de IA monitoreen motores de inferencia, ejecuten benchmarks y obtengan recomendaciones basadas en hardware.
---

# asiai mcp

Inicia el servidor MCP (Model Context Protocol), permitiendo que los agentes de IA monitoreen y evalúen tu infraestructura de inferencia.

## Uso

```bash
asiai mcp                          # transporte stdio (Claude Code)
asiai mcp --transport sse          # transporte SSE (agentes en red)
asiai mcp --transport sse --port 9000
```

## Opciones

| Opción | Descripción |
|--------|-------------|
| `--transport` | Protocolo de transporte: `stdio` (por defecto), `sse`, `streamable-http` |
| `--host` | Dirección de enlace (por defecto: `127.0.0.1`) |
| `--port` | Puerto para transporte SSE/HTTP (por defecto: `8900`) |
| `--register` | Registro voluntario en la red de agentes asiai (anónimo) |

## Herramientas (11)

| Herramienta | Descripción | Solo lectura |
|------|-------------|-----------|
| `check_inference_health` | Verificación rápida: motores activos/caídos, presión de memoria, térmica, GPU | Sí |
| `get_inference_snapshot` | Snapshot completo del sistema con todas las métricas | Sí |
| `list_models` | Lista todos los modelos cargados en todos los motores | Sí |
| `detect_engines` | Re-escanear motores de inferencia | Sí |
| `run_benchmark` | Ejecutar un benchmark o comparación entre modelos (limitado a 1/min) | No |
| `get_recommendations` | Recomendaciones de motor/modelo según tu hardware | Sí |
| `diagnose` | Ejecutar verificaciones de diagnóstico (como `asiai doctor`) | Sí |
| `get_metrics_history` | Consultar historial de métricas (1-168 horas) | Sí |
| `get_benchmark_history` | Consultar resultados de benchmarks anteriores con filtros | Sí |
| `compare_engines` | Comparar rendimiento de motores para un modelo con veredicto; soporta comparación multi-modelo desde historial | Sí |
| `refresh_engines` | Re-detectar motores sin reiniciar el servidor | Sí |

## Recursos (3)

| Recurso | URI | Descripción |
|----------|-----|-------------|
| Estado del sistema | `asiai://status` | Estado actual del sistema (memoria, térmica, GPU) |
| Modelos | `asiai://models` | Todos los modelos cargados en todos los motores |
| Info del sistema | `asiai://system` | Info de hardware (chip, RAM, núcleos, SO, tiempo activo) |

## Integración con Claude Code

Añade a tu configuración MCP de Claude Code (`~/.claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "asiai": {
      "command": "asiai",
      "args": ["mcp"]
    }
  }
}
```

Luego pregunta a Claude: *"Verifica el estado de mi inferencia"* o *"Compara Ollama vs LM Studio para qwen3.5"*.

## Tarjetas de benchmark

La herramienta `run_benchmark` soporta generación de tarjetas mediante el parámetro `card`. Cuando `card=true`, se genera una tarjeta SVG de 1200x630 y se devuelve `card_path` en la respuesta.

```json
{"tool": "run_benchmark", "arguments": {"model": "qwen3.5", "card": true}}
```

Comparación entre modelos (mutuamente excluyente con `model`, máximo 8 slots):

```json
{"tool": "run_benchmark", "arguments": {"compare": ["qwen3.5:4b", "deepseek-r1:7b"], "card": true}}
```

Equivalente en CLI para PNG + compartir:

```bash
asiai bench --quick --card --share    # Benchmark rápido + tarjeta + compartir (~15s)
```

Consulta la página de [Tarjeta de benchmark](../benchmark-card.md) para más detalles.

## Registro de agente

Únete a la red de agentes asiai para obtener funciones comunitarias (tabla de clasificación, comparación, percentiles):

```bash
asiai mcp --register                  # Registrar en primera ejecución, heartbeat en las siguientes
asiai unregister                      # Eliminar credenciales locales
```

El registro es **voluntario y anónimo** — solo se envía información de hardware (chip, RAM) y nombres de motores. No se almacenan IP, hostname ni datos personales. Las credenciales se guardan en `~/.local/share/asiai/agent.json` (chmod 600).

En llamadas posteriores a `asiai mcp --register`, se envía un heartbeat en lugar de volver a registrarse. Si la API no es accesible, el servidor MCP se inicia normalmente sin registro.

Verifica tu estado de registro con `asiai version`.

## Agentes en red

Para agentes en otras máquinas (ej. monitoreando un Mac Mini sin pantalla):

```bash
asiai mcp --transport sse --host 0.0.0.0 --port 8900
```

Consulta la [Guía de integración con agentes](../agent.md) para instrucciones detalladas de configuración.
