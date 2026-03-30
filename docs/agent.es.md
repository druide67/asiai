---
description: Ofrece a tus agentes IA visibilidad en tiempo real sobre la inferencia LLM. Servidor MCP con 11 herramientas para monitorización autónoma de motores.
type: faq
faq:
  - q: "¿asiai necesita root/sudo?"
    a: "No. La observabilidad GPU usa ioreg (sin privilegios). Las métricas de potencia usan IOReport que tampoco requiere sudo. El flag --power opcional para validación cruzada usa sudo powermetrics."
  - q: "¿Cuál es el tiempo de respuesta de la API?"
    a: "/api/status responde en menos de 500ms (caché 10s). /api/snapshot tarda 1-3s ya que recopila datos en vivo de todos los motores."
  - q: "¿Puedo ejecutar asiai en Linux?"
    a: "No. asiai es exclusivo para macOS Apple Silicon. Usa sysctl, vm_stat, ioreg, IOReport y launchd — todas APIs específicas de macOS."
  - q: "¿Cómo monitorizo varios Macs?"
    a: "Ejecuta asiai daemon start web --host 0.0.0.0 en cada Mac. Recopila /api/metrics con Prometheus. Visualiza en Grafana."
  - q: "¿Qué pasa si un motor falla durante la monitorización?"
    a: "asiai detecta fallos de motores automáticamente. Usa asiai doctor para diagnósticos. Configura alertas webhook con asiai alert add para notificaciones automáticas."
---

# Guía de integración para agentes

> **Si eres un agente IA**: usa [MCP](#mcp-model-context-protocol) si tu framework lo soporta, de lo contrario usa la [API REST](#referencia-de-la-api-rest). Para la configuración, consulta [Inicio rápido](#inicio-rápido).

## Descripción general

asiai expone la infraestructura de inferencia LLM de tu Mac a agentes IA mediante dos mecanismos:

- **Servidor MCP** — Integración nativa de herramientas vía [Model Context Protocol](https://modelcontextprotocol.io). Ideal para agentes IA que soportan MCP (Claude Code, Cursor, Cline y otros clientes compatibles con MCP).
- **API REST** — Endpoints HTTP/JSON estándar. Ideal para frameworks de agentes, orquestadores swarm y cualquier sistema capaz de HTTP (CrewAI, AutoGen, LangGraph, agentes personalizados).

Ambos dan acceso a las mismas capacidades:

- **Monitorizar** el estado del sistema (CPU, RAM, GPU, temperatura, swap)
- **Detectar** qué motores de inferencia están en ejecución y qué modelos están cargados
- **Diagnosticar** problemas de rendimiento usando observabilidad GPU y señales de actividad de inferencia
- **Benchmarkear** modelos programáticamente y seguir regresiones
- **Obtener recomendaciones** del mejor modelo/motor según tu hardware

No requiere autenticación para acceso local. Todas las interfaces escuchan en `127.0.0.1` por defecto.

### ¿Qué integración debo usar?

| Criterio | MCP | API REST |
|----------|-----|----------|
| Tu agente soporta MCP | **Usa MCP** | — |
| Orquestador swarm / multi-agente | — | **Usa API REST** |
| Polling / monitorización programada | — | **Usa API REST** |
| Integración Prometheus / Grafana | — | **Usa API REST** |
| Asistente IA interactivo (Claude Code, Cursor) | **Usa MCP** | — |
| Agente dentro de contenedor Docker | — | **Usa API REST** |
| Scripts personalizados o automatización | — | **Usa API REST** |

## Inicio rápido

### Instalar asiai

```bash
# Homebrew (recomendado)
brew tap druide67/tap && brew install asiai

# pip (con soporte MCP)
pip install "asiai[mcp]"

# pip (solo API REST)
pip install asiai
```

### Opción A: Servidor MCP (para agentes compatibles con MCP)

```bash
# Iniciar servidor MCP (transporte stdio — usado por Claude Code, Cursor, etc.)
asiai mcp
```

No es necesario iniciar el servidor manualmente — el cliente MCP lanza `asiai mcp` automáticamente. Consulta la [configuración MCP](#mcp-model-context-protocol) a continuación.

### Opción B: API REST (para agentes basados en HTTP)

```bash
# Primer plano (desarrollo)
asiai web --no-open

# Daemon en segundo plano (producción)
asiai daemon start web
```

La API está disponible en `http://127.0.0.1:8899`. El puerto es configurable con `--port`:

```bash
asiai daemon start web --port 8642
```

Para acceso remoto (por ejemplo, agente IA en otra máquina o desde un contenedor Docker):

```bash
asiai daemon start web --host 0.0.0.0
```

> **Nota:** Si tu agente se ejecuta dentro de Docker, `127.0.0.1` no es accesible. Usa la IP de red del host (por ejemplo, `192.168.0.16`) o `host.docker.internal` en Docker Desktop para Mac.

### Verificar

```bash
# API REST
curl http://127.0.0.1:8899/api/status

# MCP (listar herramientas disponibles)
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | asiai mcp
```

---

## MCP (Model Context Protocol)

asiai implementa un [servidor MCP](https://modelcontextprotocol.io) que expone la monitorización de inferencia como herramientas nativas. Cualquier cliente compatible con MCP puede conectarse y usar estas herramientas directamente — sin configuración HTTP, sin gestión de URLs.

### Configuración

#### Local (misma máquina)

Añade a la configuración de tu cliente MCP (por ejemplo, `~/.claude/settings.json` para Claude Code):

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

Si asiai está instalado en un virtualenv:

```json
{
  "mcpServers": {
    "asiai": {
      "command": "/path/to/.venv/bin/asiai",
      "args": ["mcp"]
    }
  }
}
```

#### Remoto (otra máquina vía SSH)

```json
{
  "mcpServers": {
    "asiai": {
      "command": "ssh",
      "args": [
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        "your-mac-host",
        "cd /path/to/asiai && .venv/bin/asiai mcp"
      ]
    }
  }
}
```

#### Transporte SSE (red)

Para entornos que prefieren transporte MCP basado en HTTP:

```bash
asiai mcp --transport sse --host 127.0.0.1 --port 8900
```

### Referencia de herramientas MCP

Todas las herramientas devuelven JSON. Las herramientas de solo lectura responden en < 2 segundos. `run_benchmark` es la única operación activa.

| Herramienta | Descripción | Parámetros |
|-------------|-------------|------------|
| `check_inference_health` | Verificación rápida — motores activos/inactivos, presión de memoria, temperatura, utilización GPU | — |
| `get_inference_snapshot` | Instantánea completa del estado del sistema (almacenada en SQLite para historial) | — |
| `list_models` | Todos los modelos cargados en todos los motores con VRAM, cuantización, longitud de contexto | — |
| `detect_engines` | Detección en 3 capas: config, escaneo de puertos, detección de procesos. Encuentra motores en puertos no estándar automáticamente. | — |
| `run_benchmark` | Ejecutar benchmark en un modelo o comparación entre modelos. Limitado: 1 por 60 segundos | `model` (opcional), `runs` (1–10, por defecto 3), `compare` (lista de cadenas, opcional, mutuamente excluyente con `model`, máx 8) |
| `get_recommendations` | Recomendaciones de modelo/motor según tu chip y RAM | — |
| `diagnose` | Ejecutar verificaciones diagnósticas (sistema, motores, estado del daemon) | — |
| `get_metrics_history` | Métricas históricas del sistema desde SQLite | `hours` (1–168, por defecto 24) |
| `get_benchmark_history` | Resultados históricos de benchmarks | `hours` (1–720, por defecto 24), `model` (opcional), `engine` (opcional) |
| `compare_engines` | Comparación ordenada de motores con veredicto para un modelo dado; soporta comparación multi-modelo desde el historial | `model` (requerido) |
| `refresh_engines` | Re-detectar motores sin reiniciar el servidor MCP | — |

### Recursos MCP

Endpoints de datos estáticos, disponibles sin llamar a una herramienta:

| URI | Descripción |
|-----|-------------|
| `asiai://status` | Estado de salud actual (memoria, temperatura, GPU) |
| `asiai://models` | Todos los modelos cargados en todos los motores |
| `asiai://system` | Información de hardware (chip, RAM, núcleos, SO, uptime) |

### Seguridad MCP

- **Sin sudo**: Las métricas de potencia están desactivadas en modo MCP (`power=False` forzado)
- **Limitación de tasa**: Los benchmarks están limitados a 1 por 60 segundos
- **Validación de entrada**: `hours` limitado a 1–168, `runs` limitado a 1–10
- **Local por defecto**: El transporte stdio no tiene exposición de red; SSE escucha en `127.0.0.1`

### Limitaciones MCP

- **Sin reconexión**: Si la conexión SSH se cae (problema de red, Mac en reposo), el servidor MCP muere y el cliente debe reconectarse manualmente. Para monitorización desatendida, la API REST con polling es más resiliente.
- **Cliente único**: El transporte stdio sirve a un cliente a la vez. Usa el transporte SSE si múltiples clientes necesitan acceso concurrente.

---

## Referencia de la API REST

La API de asiai es de **solo lectura** — monitoriza e informa, pero no controla motores. Para cargar/descargar modelos, usa comandos nativos del motor (`ollama pull`, `lms load`, etc.).

Todos los endpoints devuelven JSON con HTTP 200. Si un motor no es accesible, la respuesta aún devuelve 200 con `"running": false` para ese motor — la API en sí no falla.

| Endpoint | Tiempo de respuesta típico | Timeout recomendado |
|----------|---------------------------|---------------------|
| `GET /api/status` | < 500ms (caché 10s) | 2s |
| `GET /api/snapshot` | 1–3s (recopilación en vivo) | 10s |
| `GET /api/metrics` | < 500ms | 2s |
| `GET /api/history` | < 500ms | 5s |
| `GET /api/engine-history` | < 500ms | 5s |

### `GET /api/status`

Verificación rápida de salud. Caché de 10 segundos. Tiempo de respuesta < 500ms.

**Respuesta:**

```json
{
  "hostname": "mac-mini",
  "chip": "Apple M4 Pro",
  "ram_gb": 64.0,
  "cpu_percent": 12.3,
  "memory_pressure": "normal",
  "gpu_utilization_percent": 45.2,
  "engines": {
    "ollama": {
      "running": true,
      "models_loaded": 2,
      "port": 11434
    },
    "lmstudio": {
      "running": true,
      "models_loaded": 1,
      "port": 1234
    }
  },
  "asiai_version": "1.0.1",
  "uptime_seconds": 86400
}
```

### `GET /api/snapshot`

Estado completo del sistema. Incluye todo lo de `/api/status` más información detallada de modelos, métricas GPU y datos de temperatura.

**Respuesta:**

```json
{
  "system": {
    "hostname": "mac-mini",
    "chip": "Apple M4 Pro",
    "cores_p": 12,
    "cores_e": 4,
    "gpu_cores": 20,
    "ram_total_gb": 64.0,
    "ram_used_gb": 41.2,
    "ram_percent": 64.4,
    "swap_used_gb": 0.0,
    "memory_pressure": "normal",
    "cpu_percent": 12.3,
    "thermal_state": "nominal",
    "gpu_utilization_percent": 45.2,
    "gpu_renderer_percent": 38.1,
    "gpu_tiler_percent": 12.4,
    "gpu_memory_allocated_bytes": 8589934592
  },
  "engines": [
    {
      "name": "ollama",
      "running": true,
      "port": 11434,
      "models": [
        {
          "name": "qwen3.5:latest",
          "size_params": "35B",
          "size_vram_bytes": 21474836480,
          "quantization": "Q4_K_M",
          "context_length": 32768
        }
      ]
    }
  ],
  "timestamp": "2026-03-09T14:30:00Z"
}
```

### `GET /api/metrics`

Métricas compatibles con Prometheus. Recopila con Prometheus, Datadog o cualquier herramienta compatible.

**Respuesta (text/plain):**

```
# HELP asiai_cpu_percent CPU usage percentage
# TYPE asiai_cpu_percent gauge
asiai_cpu_percent 12.3

# HELP asiai_ram_used_gb RAM used in GB
# TYPE asiai_ram_used_gb gauge
asiai_ram_used_gb 41.2

# HELP asiai_gpu_utilization_percent GPU utilization percentage
# TYPE asiai_gpu_utilization_percent gauge
asiai_gpu_utilization_percent 45.2

# HELP asiai_engine_up Engine availability (1=up, 0=down)
# TYPE asiai_engine_up gauge
asiai_engine_up{engine="ollama"} 1
asiai_engine_up{engine="lmstudio"} 1

# HELP asiai_models_loaded Number of models loaded per engine
# TYPE asiai_models_loaded gauge
asiai_models_loaded{engine="ollama"} 2
```

### `GET /api/history?hours=N`

Métricas históricas del sistema desde SQLite. Por defecto: `hours=24`. Máximo: `hours=2160` (90 días).

**Respuesta:**

```json
{
  "points": [
    {
      "timestamp": "2026-03-09T14:00:00Z",
      "cpu_percent": 15.2,
      "ram_used_gb": 40.1,
      "ram_percent": 62.7,
      "swap_used_gb": 0.0,
      "memory_pressure": "normal",
      "thermal_state": "nominal",
      "gpu_utilization_percent": 42.0,
      "gpu_renderer_percent": 35.0,
      "gpu_tiler_percent": 10.0,
      "gpu_memory_allocated_bytes": 8589934592
    }
  ],
  "count": 144,
  "hours": 24
}
```

### `GET /api/engine-history?engine=X&hours=N`

Historial de actividad por motor. Útil para detectar patrones de inferencia.

**Parámetros:**

| Parámetro | Requerido | Por defecto | Descripción |
|-----------|-----------|-------------|-------------|
| `engine`  | Sí        | —           | Nombre del motor (ollama, lmstudio, etc.) |
| `hours`   | No        | 24          | Rango de tiempo |

**Respuesta:**

```json
{
  "engine": "ollama",
  "points": [
    {
      "timestamp": "2026-03-09T14:00:00Z",
      "running": true,
      "tcp_connections": 3,
      "requests_processing": 1,
      "kv_cache_usage_percent": 45.2
    }
  ],
  "count": 144,
  "hours": 24
}
```

## Interpretar métricas

### Umbrales de salud del sistema

| Métrica | Normal | Advertencia | Crítico |
|---------|--------|-------------|---------|
| `memory_pressure` | `normal` | `warn` | `critical` |
| `ram_percent` | < 75% | 75–90% | > 90% |
| `swap_used_gb` | 0 | 0.1–2.0 | > 2.0 |
| `thermal_state` | `nominal` | `fair` | `serious` / `critical` |
| `cpu_percent` | < 80% | 80–95% | > 95% |

### Umbrales GPU

| Métrica | Inactivo | Inferencia activa | Sobrecargado |
|---------|----------|-------------------|--------------|
| `gpu_utilization_percent` | 0–5% | 20–80% | > 90% sostenido |
| `gpu_renderer_percent` | 0–5% | 15–70% | > 85% sostenido |
| `gpu_memory_allocated_bytes` | < 1 GB | 2–48 GB | > 90% de la RAM |

> **Importante:** `gpu_utilization_percent = 0` significa que la GPU está inactiva, no averiada. Un valor de `-1.0` significa que la métrica no está disponible (por ejemplo, hardware no soportado o fallo de recopilación) — no lo interpretes como "GPU muerta".

### Rendimiento de inferencia

| Métrica | Excelente | Bueno | Degradado |
|---------|-----------|-------|-----------|
| `tok/s` (modelo 7B) | > 80 | 40–80 | < 40 |
| `tok/s` (modelo 35B) | > 40 | 20–40 | < 20 |
| `tok/s` (modelo 70B) | > 15 | 8–15 | < 8 |
| `TTFT` | < 100ms | 100–500ms | > 500ms |

## Árboles de decisión diagnóstica

### Generación lenta (tok/s bajo)

``` mermaid
graph TD
    A["tok/s below expected?"] --> B["Check memory_pressure"]
    A --> C["Check thermal_state"]
    A --> D["Check gpu_utilization_percent"]
    A --> E["Check swap_used_gb"]

    B -->|critical| B1["Models swapping to disk.<br/>Unload models or add RAM."]
    B -->|normal| B2["Continue"]

    C -->|"serious / critical"| C1["Thermal throttling.<br/>Cool down, check airflow."]
    C -->|nominal| C2["Continue"]

    D -->|"< 10%"| D1["GPU not being used.<br/>Check engine config (num_gpu layers)."]
    D -->|"> 90%"| D2["GPU saturated.<br/>Reduce concurrent requests."]
    D -->|"20-80%"| D3["Normal. Check model<br/>quantization and context size."]

    E -->|"> 0"| E1["Model too large for RAM.<br/>Use smaller quantization."]
    E -->|"0"| E2["Check engine version,<br/>try different engine."]
```

### Motor sin respuesta

``` mermaid
graph TD
    A["engine.running == false?"] --> B["Check process: lsof -i :port"]
    A --> C["Check memory_pressure"]
    A --> D["Try: asiai doctor"]

    B -->|No process| B1["Engine crashed. Restart it."]
    B -->|Process exists| B2["Engine hung."]

    C -->|critical| C1["OOM killed.<br/>Unload other models first."]
    C -->|normal| C2["Check engine logs."]

    D --> D1["Comprehensive diagnostics"]
```

### Alta presión de memoria / Desbordamiento VRAM

``` mermaid
graph TD
    A["memory_pressure == warn/critical?"] --> B["Check swap_used_gb"]
    A --> C["Check models loaded"]
    A --> D["Check gpu_memory_allocated_bytes"]

    B -->|"> 2 GB"| B1["VRAM overflow.<br/>Latency 5-50x worse (disk swap).<br/>Unload models or use Q3_K_S."]
    B -->|"< 2 GB"| B2["Manageable.<br/>Monitor closely."]

    C -->|"Multiple large models"| C1["Unload unused models.<br/>ollama rm / lms unload"]
    C -->|"Single model > 80% RAM"| C2["Use smaller quantization."]

    D --> D1["If > 80% of RAM,<br/>next model load triggers swap."]
```

## Señales de actividad de inferencia

asiai detecta inferencia activa a través de múltiples señales:

### Utilización GPU

```
GET /api/snapshot → system.gpu_utilization_percent
```

- **< 5%**: No hay inferencia en ejecución
- **20–80%**: Inferencia activa (rango normal para memoria unificada Apple Silicon)
- **> 90%**: Inferencia pesada o múltiples peticiones simultáneas

### Conexiones TCP

```
GET /api/engine-history?engine=ollama&hours=1
```

Cada petición de inferencia activa mantiene una conexión TCP. Un pico en `tcp_connections` indica generación activa.

### Métricas específicas del motor

Para motores que exponen `/metrics` (llama.cpp, vllm-mlx):

- `requests_processing > 0`: Inferencia activa
- `kv_cache_usage_percent > 0`: El modelo tiene contexto activo

### Patrón de correlación

La detección de inferencia más fiable combina múltiples señales:

```python
snapshot = get_snapshot()
gpu_active = snapshot["system"]["gpu_utilization_percent"] > 15
engine_busy = any(
    e.get("tcp_connections", 0) > 0
    for e in snapshot.get("engine_status", [])
)
inference_running = gpu_active and engine_busy
```

## Código de ejemplo

### Verificación de salud (Python, solo stdlib)

```python
import json
import urllib.request

ASIAI_URL = "http://127.0.0.1:8899"  # Docker: usa IP del host o host.docker.internal

def check_health():
    """Verificación rápida de salud. Devuelve dict con estado."""
    req = urllib.request.Request(f"{ASIAI_URL}/api/status")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())

def is_healthy(status):
    """Interpreta el estado de salud."""
    issues = []
    if status.get("memory_pressure") != "normal":
        issues.append(f"memory_pressure: {status['memory_pressure']}")
    gpu = status.get("gpu_utilization_percent", 0)
    if gpu > 90:
        issues.append(f"gpu_utilization: {gpu}%")
    engines = status.get("engines", {})
    for name, info in engines.items():
        if not info.get("running"):
            issues.append(f"engine_down: {name}")
    return {"healthy": len(issues) == 0, "issues": issues}

# Uso
status = check_health()
health = is_healthy(status)
if not health["healthy"]:
    print(f"Problemas detectados: {health['issues']}")
```

### Estado completo del sistema

```python
def get_full_state():
    """Obtener instantánea completa del sistema."""
    req = urllib.request.Request(f"{ASIAI_URL}/api/snapshot")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

def get_history(hours=24):
    """Obtener métricas históricas."""
    req = urllib.request.Request(f"{ASIAI_URL}/api/history?hours={hours}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

# Detectar tendencia de rendimiento
history = get_history(hours=6)
points = history["points"]
if len(points) >= 2:
    recent_gpu = points[-1].get("gpu_utilization_percent", 0)
    earlier_gpu = points[0].get("gpu_utilization_percent", 0)
    if recent_gpu > earlier_gpu * 1.5:
        print("La utilización GPU tiene una tendencia ascendente significativa")
```

## Tarjetas de benchmark (imágenes compartibles)

Genera una tarjeta de benchmark compartible con el CLI:

```bash
asiai bench --card                    # SVG guardado localmente (sin dependencias)
asiai bench --card --share            # SVG + PNG vía API comunitaria
asiai bench --quick --card --share    # Bench rápido + tarjeta + compartir (~15s)
```

Una **tarjeta de tema oscuro 1200x630** con modelo, chip, gráfico de barras de comparación de motores, resaltado del ganador y chips de métricas. Optimizada para Reddit, X, Discord y READMEs de GitHub.

Las tarjetas se guardan en `~/.local/share/asiai/cards/` como SVG. Añade `--share` para obtener una descarga PNG y una URL compartible — el PNG es necesario para publicar en Reddit, X y Discord.

### Vía MCP

La herramienta MCP `run_benchmark` soporta generación de tarjetas con el parámetro `card`:

```json
{"tool": "run_benchmark", "arguments": {"model": "qwen3.5", "card": true}}
```

La respuesta incluye `card_path` — la ruta absoluta al archivo SVG en el sistema de archivos del servidor MCP.

## Alertas webhook (notificaciones push)

En lugar de polling, configura asiai para enviar notificaciones push cuando ocurran cambios de estado:

```bash
# Añadir un webhook (Slack, Discord o cualquier URL)
asiai alert add https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Las alertas se activan en:
# - Motor cae / vuelve a estar activo
# - Transiciones de presión de memoria (normal → warn → critical)
# - Throttling térmico detectado
```

Las alertas se disparan solo en **transiciones** (no en cada verificación) con un periodo de enfriamiento de 5 minutos para evitar saturación. Esto es ideal para orquestadores swarm que necesitan reaccionar a cambios de infraestructura sin polling continuo.

Para listar o eliminar alertas: `asiai alert list`, `asiai alert remove <id>`.

## Identifica tu agente

**Recomendamos** incluir un header `User-Agent` que identifique tu agente en las peticiones a la API REST:

```
User-Agent: asiai-agent/<framework>/<version>
```

Ejemplos:

- `User-Agent: asiai-agent/openclaw/1.2.0`
- `User-Agent: asiai-agent/crewai/0.5`
- `User-Agent: asiai-agent/custom-orchestrator/1.0`

Esto **no es obligatorio** — las peticiones sin header User-Agent funcionan correctamente. Pero ayuda con:

- **Depuración** — distinguir peticiones de agentes del acceso humano vía navegador en los logs
- **Analíticas por agente** — ver qué agentes consultan la API, con qué frecuencia y qué endpoints
- **Entornos multi-agente** — cuando múltiples agentes comparten la misma instancia de asiai, identificar quién es quién

Para clientes MCP, la identificación es automática (el protocolo MCP incluye metadatos del cliente).

---

## Registra tu agente (opcional)

El registro es **completamente opcional** — asiai funciona plenamente sin él. Sin phone home, sin telemetría por defecto.

Si eliges registrarte, te unes a la red de agentes asiai: una llamada API, sin email, sin datos personales — solo información de tu hardware.

```bash
curl -X POST https://api.asiai.dev/api/v1/agent-register \
  -H "Content-Type: application/json" \
  -d '{
    "chip": "Apple M4 Pro",
    "ram_gb": 64,
    "engines": ["ollama", "lmstudio"],
    "framework": "my-agent",
    "asiai_version": "1.0.1"
  }'
```

**Respuesta:**

```json
{
  "status": "registered",
  "agent_id": "a1b2c3d4e5f6",
  "agent_token": "secret_...",
  "total_agents": 42
}
```

Almacena `agent_id` y `agent_token` de forma segura en `~/.local/share/asiai/agent.json`. Los necesitarás para llamadas a la API comunitaria y envío de benchmarks.

### Qué desbloquea el registro

| Funcionalidad | Sin agent_id | Con agent_id |
|---------------|-------------|--------------|
| Bench/monitor/web local | Sí | Sí |
| `/api/status`, `/api/snapshot` | Sí | Sí |
| `--share` benchmarks | No | **Sí** |
| `asiai compare` (comunidad) | No | **Sí** |
| `asiai recommend --community` | No | **Sí** |
| Estadísticas percentiles | No | **Sí** |
| Directorio de agentes (encontrar pares en el mismo chip) | No | **Sí** |
| Alertas de rendimiento (un nuevo motor supera al tuyo) | No | **Próximamente** |

### Heartbeat

Mantén tu registro activo con heartbeats periódicos:

```bash
curl -X POST https://api.asiai.dev/api/v1/agent-heartbeat \
  -H "Content-Type: application/json" \
  -H "X-Agent-Id: a1b2c3d4e5f6" \
  -H "X-Agent-Token: secret_..." \
  -d '{
    "engines": ["ollama", "lmstudio"],
    "version": "1.0.1",
    "models_loaded": 3,
    "uptime_hours": 72
  }'
```

### Privacidad

- **Sin dirección IP almacenada** — tu IP se usa solo para limitación de tasa y nunca se persiste en el registro de agentes
- **Sin datos personales** — solo información de hardware (chip, RAM), nombres de motores y nombre del framework
- **Solo opt-in** — asiai nunca contacta servidores externos a menos que te registres explícitamente
- **Seguridad de tokens** — tu `agent_token` se hashea (SHA-256) antes de almacenarse; el texto plano se devuelve solo una vez en el registro
- **Datos de limitación de tasa** — los hashes de IP (SHA-256 con salt diario) en la tabla de limitación de tasa se purgan automáticamente después de 30 días

## FAQ

**P: ¿asiai necesita root/sudo?**
R: No. La observabilidad GPU usa `ioreg` (sin privilegios). Las métricas de potencia (flag `--power` en benchmarks) requieren `sudo powermetrics`, pero es opcional.

**P: ¿Cuál es el tiempo de respuesta de la API?**
R: `/api/status` responde en < 500ms (caché 10s). `/api/snapshot` tarda 1–3s (recopila datos en vivo de todos los motores).

**P: ¿Puedo ejecutar asiai en Linux?**
R: No. asiai es exclusivo para macOS Apple Silicon. Usa `sysctl`, `vm_stat`, `ioreg` y `launchd` — todas APIs específicas de macOS.

**P: ¿Cómo monitorizo varios Macs?**
R: Ejecuta `asiai daemon start web --host 0.0.0.0` en cada Mac. Recopila `/api/metrics` con Prometheus. Visualiza en Grafana.

**P: ¿Qué pasa si un motor falla?**
R: asiai detecta fallos de motores automáticamente. Usa `asiai doctor` para diagnósticos. Configura alertas webhook con `asiai alert add` para notificaciones automáticas.
