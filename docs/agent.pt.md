---
description: Dê aos seus agentes de IA visibilidade em tempo real da inferência LLM. Servidor MCP com 11 ferramentas para monitoramento autônomo de engines.
type: faq
faq:
  - q: "O asiai requer root/sudo?"
    a: "Não. A observabilidade da GPU usa ioreg (sem privilégios). As métricas de potência usam IOReport, que também não requer sudo. O flag opcional --power para validação cruzada usa sudo powermetrics."
  - q: "Qual é o tempo de resposta da API?"
    a: "/api/status responde em menos de 500ms (cache de 10s). /api/snapshot leva 1-3s pois coleta dados ao vivo de todas as engines."
  - q: "Posso rodar o asiai no Linux?"
    a: "Não. O asiai é exclusivo para macOS Apple Silicon. Ele usa sysctl, vm_stat, ioreg, IOReport e launchd — todas APIs específicas do macOS."
  - q: "Como monitoro vários Macs?"
    a: "Execute asiai daemon start web --host 0.0.0.0 em cada Mac. Colete /api/metrics com Prometheus. Visualize no Grafana."
  - q: "E se uma engine travar durante o monitoramento?"
    a: "O asiai detecta falhas de engines automaticamente. Use asiai doctor para diagnósticos. Configure alertas via webhook com asiai alert add para notificações automáticas."
---

# Guia de Integração para Agentes

> **Se você é um agente de IA**: use [MCP](#mcp-model-context-protocol) se seu framework suportar, caso contrário use a [API REST](#referência-da-api-rest). Para configuração, veja [Início Rápido](#início-rápido).

## Visão Geral

O asiai expõe a infraestrutura de inferência LLM do seu Mac para agentes de IA através de dois mecanismos:

- **Servidor MCP** — Integração nativa de ferramentas via [Model Context Protocol](https://modelcontextprotocol.io). Ideal para agentes de IA que suportam MCP (Claude Code, Cursor, Cline e outros clientes compatíveis com MCP).
- **API REST** — Endpoints HTTP/JSON padrão. Ideal para frameworks de agentes, orquestradores swarm e qualquer sistema com suporte HTTP (CrewAI, AutoGen, LangGraph, agentes customizados).

Ambos dão acesso às mesmas capacidades:

- **Monitorar** a saúde do sistema (CPU, RAM, GPU, térmica, swap)
- **Detectar** quais engines de inferência estão rodando e quais modelos estão carregados
- **Diagnosticar** problemas de desempenho usando observabilidade da GPU e sinais de atividade de inferência
- **Benchmarkar** modelos programaticamente e rastrear regressões
- **Obter recomendações** do melhor modelo/engine com base no seu hardware

Nenhuma autenticação necessária para acesso local. Todas as interfaces vinculam a `127.0.0.1` por padrão.

### Qual integração devo usar?

| Critério | MCP | API REST |
|----------|-----|----------|
| Seu agente suporta MCP | **Use MCP** | — |
| Orquestrador swarm / multi-agente | — | **Use API REST** |
| Polling / monitoramento agendado | — | **Use API REST** |
| Integração Prometheus / Grafana | — | **Use API REST** |
| Assistente IA interativo (Claude Code, Cursor) | **Use MCP** | — |
| Agente dentro de container Docker | — | **Use API REST** |
| Scripts customizados ou automação | — | **Use API REST** |

## Início Rápido

### Instalar o asiai

```bash
# Homebrew (recomendado)
brew tap druide67/tap && brew install asiai

# pip (com suporte MCP)
pip install "asiai[mcp]"

# pip (apenas API REST)
pip install asiai
```

### Opção A: Servidor MCP (para agentes compatíveis com MCP)

```bash
# Iniciar servidor MCP (transporte stdio — usado por Claude Code, Cursor, etc.)
asiai mcp
```

Não é necessário iniciar o servidor manualmente — o cliente MCP lança `asiai mcp` automaticamente. Veja [configuração MCP](#mcp-model-context-protocol) abaixo.

### Opção B: API REST (para agentes baseados em HTTP)

```bash
# Primeiro plano (desenvolvimento)
asiai web --no-open

# Daemon em segundo plano (produção)
asiai daemon start web
```

A API está disponível em `http://127.0.0.1:8899`. A porta é configurável com `--port`:

```bash
asiai daemon start web --port 8642
```

Para acesso remoto (ex.: agente de IA em outra máquina ou de um container Docker):

```bash
asiai daemon start web --host 0.0.0.0
```

> **Nota:** Se seu agente roda dentro do Docker, `127.0.0.1` é inacessível. Use o IP de rede do host (ex.: `192.168.0.16`) ou `host.docker.internal` no Docker Desktop para Mac.

### Verificar

```bash
# API REST
curl http://127.0.0.1:8899/api/status

# MCP (listar ferramentas disponíveis)
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | asiai mcp
```

---

## MCP (Model Context Protocol)

O asiai implementa um [servidor MCP](https://modelcontextprotocol.io) que expõe o monitoramento de inferência como ferramentas nativas. Qualquer cliente compatível com MCP pode se conectar e usar essas ferramentas diretamente — sem configuração HTTP, sem gerenciamento de URLs.

### Configuração

#### Local (mesma máquina)

Adicione à configuração do seu cliente MCP (ex.: `~/.claude/settings.json` para Claude Code):

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

Se o asiai está instalado em um virtualenv:

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

#### Remoto (máquina diferente via SSH)

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

#### Transporte SSE (rede)

Para ambientes que preferem transporte MCP baseado em HTTP:

```bash
asiai mcp --transport sse --host 127.0.0.1 --port 8900
```

### Referência de Ferramentas MCP

Todas as ferramentas retornam JSON. Ferramentas somente leitura respondem em < 2 segundos. `run_benchmark` é a única operação ativa.

| Ferramenta | Descrição | Parâmetros |
|------------|-----------|------------|
| `check_inference_health` | Verificação rápida de saúde — engines ativas/inativas, pressão de memória, térmica, utilização da GPU | — |
| `get_inference_snapshot` | Snapshot completo do estado do sistema (armazenado em SQLite para histórico) | — |
| `list_models` | Todos os modelos carregados em todas as engines com VRAM, quantização, tamanho de contexto | — |
| `detect_engines` | Detecção em 3 camadas: config, varredura de portas, detecção de processos. Encontra engines em portas não-padrão automaticamente. | — |
| `run_benchmark` | Executar benchmark em um modelo ou comparação entre modelos. Limitado: 1 por 60 segundos | `model` (opcional), `runs` (1–10, padrão 3), `compare` (lista de strings, opcional, mutuamente exclusivo com `model`, máx 8) |
| `get_recommendations` | Recomendações de modelo/engine com base no seu hardware | — |
| `diagnose` | Executar verificações de diagnóstico (sistema, engines, saúde do daemon) | — |
| `get_metrics_history` | Métricas históricas do sistema a partir do SQLite | `hours` (1–168, padrão 24) |
| `get_benchmark_history` | Resultados históricos de benchmark | `hours` (1–720, padrão 24), `model` (opcional), `engine` (opcional) |
| `compare_engines` | Comparação ranqueada de engines com veredito para um modelo dado; suporta comparação multi-modelo a partir do histórico | `model` (obrigatório) |
| `refresh_engines` | Re-detectar engines sem reiniciar o servidor MCP | — |

### Recursos MCP

Endpoints de dados estáticos, disponíveis sem chamar uma ferramenta:

| URI | Descrição |
|-----|-----------|
| `asiai://status` | Estado de saúde atual (memória, térmica, GPU) |
| `asiai://models` | Todos os modelos carregados em todas as engines |
| `asiai://system` | Informações de hardware (chip, RAM, núcleos, SO, uptime) |

### Segurança MCP

- **Sem sudo**: Métricas de potência são desabilitadas no modo MCP (`power=False` forçado)
- **Rate limiting**: Benchmarks limitados a 1 por 60 segundos
- **Clamping de entrada**: `hours` limitado a 1–168, `runs` limitado a 1–10
- **Local por padrão**: transporte stdio não tem exposição de rede; SSE vincula a `127.0.0.1`

### Limitações do MCP

- **Sem reconexão**: Se a conexão SSH cair (problema de rede, Mac em suspensão), o servidor MCP morre e o cliente deve reconectar manualmente. Para monitoramento não-assistido, a API REST com polling é mais resiliente.
- **Cliente único**: transporte stdio atende um cliente por vez. Use transporte SSE se múltiplos clientes precisam de acesso concorrente.

---

## Referência da API REST

A API do asiai é **somente leitura** — ela monitora e reporta, mas não controla engines. Para carregar/descarregar modelos, use comandos nativos da engine (`ollama pull`, `lms load`, etc.).

Todos os endpoints retornam JSON com HTTP 200. Se uma engine está inacessível, a resposta ainda retorna 200 com `"running": false` para essa engine — a API em si não falha.

| Endpoint | Tempo de resposta típico | Timeout recomendado |
|----------|--------------------------|---------------------|
| `GET /api/status` | < 500ms (cache 10s) | 2s |
| `GET /api/snapshot` | 1–3s (coleta ao vivo) | 10s |
| `GET /api/metrics` | < 500ms | 2s |
| `GET /api/history` | < 500ms | 5s |
| `GET /api/engine-history` | < 500ms | 5s |

### `GET /api/status`

Verificação rápida de saúde. Cache de 10 segundos. Tempo de resposta < 500ms.

**Resposta:**

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

Estado completo do sistema. Inclui tudo do `/api/status` mais informações detalhadas de modelos, métricas de GPU e dados térmicos.

**Resposta:**

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

Métricas compatíveis com Prometheus. Colete com Prometheus, Datadog ou qualquer ferramenta compatível.

**Resposta (text/plain):**

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

Métricas históricas do sistema a partir do SQLite. Padrão: `hours=24`. Máximo: `hours=2160` (90 dias).

**Resposta:**

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

Histórico de atividade específico por engine. Útil para detectar padrões de inferência.

**Parâmetros:**

| Parâmetro | Obrigatório | Padrão | Descrição |
|-----------|-------------|--------|-----------|
| `engine`  | Sim         | —      | Nome da engine (ollama, lmstudio, etc.) |
| `hours`   | Não         | 24     | Intervalo de tempo |

**Resposta:**

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

## Interpretando Métricas

### Limites de Saúde do Sistema

| Métrica | Normal | Alerta | Crítico |
|---------|--------|--------|---------|
| `memory_pressure` | `normal` | `warn` | `critical` |
| `ram_percent` | < 75% | 75–90% | > 90% |
| `swap_used_gb` | 0 | 0.1–2.0 | > 2.0 |
| `thermal_state` | `nominal` | `fair` | `serious` / `critical` |
| `cpu_percent` | < 80% | 80–95% | > 95% |

### Limites de GPU

| Métrica | Inativo | Inferência Ativa | Sobrecarregado |
|---------|---------|-------------------|----------------|
| `gpu_utilization_percent` | 0–5% | 20–80% | > 90% sustentado |
| `gpu_renderer_percent` | 0–5% | 15–70% | > 85% sustentado |
| `gpu_memory_allocated_bytes` | < 1 GB | 2–48 GB | > 90% da RAM |

> **Importante:** `gpu_utilization_percent = 0` significa que a GPU está ociosa, não com defeito. Um valor de `-1.0` significa que a métrica está indisponível (ex.: hardware não suportado ou falha na coleta) — não interprete como "GPU morta".

### Desempenho de Inferência

| Métrica | Excelente | Bom | Degradado |
|---------|-----------|-----|-----------|
| `tok/s` (modelo 7B) | > 80 | 40–80 | < 40 |
| `tok/s` (modelo 35B) | > 40 | 20–40 | < 20 |
| `tok/s` (modelo 70B) | > 15 | 8–15 | < 8 |
| `TTFT` | < 100ms | 100–500ms | > 500ms |

## Árvores de Decisão para Diagnóstico

### Geração Lenta (tok/s baixo)

```
tok/s abaixo do esperado?
├── Verificar memory_pressure
│   ├── "critical" → Modelos sendo trocados para disco. Descarregue modelos ou adicione RAM.
│   └── "normal" → Continuar
├── Verificar thermal_state
│   ├── "serious"/"critical" → Throttling térmico. Resfrie, verifique a ventilação.
│   └── "nominal" → Continuar
├── Verificar gpu_utilization_percent
│   ├── < 10% → GPU não está sendo usada. Verifique a config da engine (camadas num_gpu).
│   ├── > 90% → GPU saturada. Reduza requisições concorrentes.
│   └── 20-80% → Normal. Verifique a quantização do modelo e o tamanho do contexto.
└── Verificar swap_used_gb
    ├── > 0 → Modelo grande demais para a RAM. Use quantização menor.
    └── 0 → Verifique a versão da engine, tente uma engine diferente.
```

### Engine Não Responde

```
engine.running == false?
├── Verificar se o processo existe: lsof -i :<port>
│   ├── Sem processo → Engine travou. Reinicie.
│   └── Processo existe mas não responde → Engine travada.
├── Verificar memory_pressure
│   ├── "critical" → Eliminada por OOM. Descarregue outros modelos primeiro.
│   └── "normal" → Verifique os logs da engine.
└── Tente: asiai doctor (diagnóstico completo)
```

### Alta Pressão de Memória / Estouro de VRAM

```
memory_pressure == "warn" ou "critical"?
├── Verificar swap_used_gb
│   ├── > 2 GB → Estouro de VRAM. Modelos não cabem na memória unificada.
│   │   ├── A latência será 5–50× pior (swap em disco).
│   │   ├── Descarregue modelos: ollama rm <model>, lms unload
│   │   └── Ou use quantização menor (Q4_K_M → Q3_K_S).
│   └── < 2 GB → Gerenciável, mas monitore de perto.
├── Verificar modelos carregados em todas as engines
│   ├── Múltiplos modelos grandes → Descarregue modelos não usados
│   │   ├── Ollama: ollama rm <model> ou aguarde o descarregamento automático
│   │   └── LM Studio: descarregue pela UI ou lms unload
│   └── Modelo único > 80% RAM → Use quantização menor
└── Verificar gpu_memory_allocated_bytes
    └── Compare com ram_total_gb. Se > 80%, o próximo modelo carregado ativará swap.
```

## Sinais de Atividade de Inferência

O asiai detecta inferência ativa através de múltiplos sinais:

### Utilização da GPU

```
GET /api/snapshot → system.gpu_utilization_percent
```

- **< 5%**: Nenhuma inferência rodando
- **20–80%**: Inferência ativa (faixa normal para memória unificada Apple Silicon)
- **> 90%**: Inferência pesada ou múltiplas requisições concorrentes

### Conexões TCP

```
GET /api/engine-history?engine=ollama&hours=1
```

Cada requisição de inferência ativa mantém uma conexão TCP. Um pico em `tcp_connections` indica geração ativa.

### Métricas Específicas da Engine

Para engines que expõem `/metrics` (llama.cpp, vllm-mlx):

- `requests_processing > 0`: Inferência ativa
- `kv_cache_usage_percent > 0`: Modelo com contexto ativo

### Padrão de Correlação

A detecção de inferência mais confiável combina múltiplos sinais:

```python
snapshot = get_snapshot()
gpu_active = snapshot["system"]["gpu_utilization_percent"] > 15
engine_busy = any(
    e.get("tcp_connections", 0) > 0
    for e in snapshot.get("engine_status", [])
)
inference_running = gpu_active and engine_busy
```

## Código de Exemplo

### Verificação de Saúde (Python, apenas stdlib)

```python
import json
import urllib.request

ASIAI_URL = "http://127.0.0.1:8899"  # Docker: use o IP do host ou host.docker.internal

def check_health():
    """Verificação rápida de saúde. Retorna dict com status."""
    req = urllib.request.Request(f"{ASIAI_URL}/api/status")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())

def is_healthy(status):
    """Interpreta o estado de saúde."""
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

### Estado Completo do Sistema

```python
def get_full_state():
    """Obtém snapshot completo do sistema."""
    req = urllib.request.Request(f"{ASIAI_URL}/api/snapshot")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

def get_history(hours=24):
    """Obtém métricas históricas."""
    req = urllib.request.Request(f"{ASIAI_URL}/api/history?hours={hours}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

# Detectar tendência de desempenho
history = get_history(hours=6)
points = history["points"]
if len(points) >= 2:
    recent_gpu = points[-1].get("gpu_utilization_percent", 0)
    earlier_gpu = points[0].get("gpu_utilization_percent", 0)
    if recent_gpu > earlier_gpu * 1.5:
        print("Utilização da GPU com tendência de alta significativa")
```

## Benchmark Cards (Imagens Compartilháveis)

Gere uma imagem de benchmark card compartilhável via CLI:

```bash
asiai bench --card                    # SVG salvo localmente (zero dependências)
asiai bench --card --share            # SVG + PNG via API comunitária
asiai bench --quick --card --share    # Bench rápido + card + share (~15s)
```

Um **card de tema escuro 1200x630** com modelo, chip, gráfico de barras de comparação de engines, destaque do vencedor e chips de métricas. Otimizado para Reddit, X, Discord e READMEs do GitHub.

Os cards são salvos em `~/.local/share/asiai/cards/` como SVG. Adicione `--share` para obter um download PNG e uma URL compartilhável — PNG é necessário para postar no Reddit, X e Discord.

### Via MCP

A ferramenta MCP `run_benchmark` suporta geração de cards com o parâmetro `card`:

```json
{"tool": "run_benchmark", "arguments": {"model": "qwen3.5", "card": true}}
```

A resposta inclui `card_path` — o caminho absoluto para o arquivo SVG no sistema de arquivos do servidor MCP.

## Alertas via Webhook (Notificações Push)

Em vez de fazer polling, configure o asiai para enviar notificações quando mudanças de estado ocorrem:

```bash
# Adicionar um webhook (Slack, Discord ou qualquer URL)
asiai alert add https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Alertas são acionados em:
# - Engine cai / volta ao ar
# - Transições de pressão de memória (normal → warn → critical)
# - Throttling térmico detectado
```

Os alertas disparam apenas em **transições** (não em cada verificação) com um cooldown de 5 minutos para evitar inundação. Ideal para orquestradores swarm que precisam reagir a mudanças na infraestrutura sem polling contínuo.

Para listar ou remover alertas: `asiai alert list`, `asiai alert remove <id>`.

## Identifique Seu Agente

**Recomendamos** incluir um header `User-Agent` identificando seu agente nas requisições da API REST:

```
User-Agent: asiai-agent/<framework>/<version>
```

Exemplos:

- `User-Agent: asiai-agent/openclaw/1.2.0`
- `User-Agent: asiai-agent/crewai/0.5`
- `User-Agent: asiai-agent/custom-orchestrator/1.0`

Isso **não é obrigatório** — requisições sem header User-Agent funcionam normalmente. Mas ajuda com:

- **Depuração** — distinguir requisições de agentes de acessos humanos nos logs
- **Analytics por agente** — ver quais agentes acessam a API, com que frequência e quais endpoints
- **Ambientes multi-agente** — quando vários agentes compartilham a mesma instância asiai, identificar quem é quem

Para clientes MCP, a identificação é automática (o protocolo MCP inclui metadados do cliente).

---

## Registrar Seu Agente (Opcional)

O registro é **totalmente opcional** — o asiai funciona completamente sem ele. Sem envio de dados, sem telemetria por padrão.

Se você optar por se registrar, você entra na rede de agentes asiai: uma chamada de API, sem email, sem dados pessoais — apenas informações do seu hardware.

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

**Resposta:**

```json
{
  "status": "registered",
  "agent_id": "a1b2c3d4e5f6",
  "agent_token": "secret_...",
  "total_agents": 42
}
```

Armazene `agent_id` e `agent_token` com segurança em `~/.local/share/asiai/agent.json`. Você precisará de ambos para chamadas à API comunitária e envio de benchmarks.

### O que o registro desbloqueia

| Recurso | Sem agent_id | Com agent_id |
|---------|--------------|--------------|
| Bench/monitor/web local | Sim | Sim |
| `/api/status`, `/api/snapshot` | Sim | Sim |
| `--share` benchmarks | Não | **Sim** |
| `asiai compare` (comunidade) | Não | **Sim** |
| `asiai recommend --community` | Não | **Sim** |
| Estatísticas de percentil | Não | **Sim** |
| Diretório de agentes (encontrar pares no mesmo chip) | Não | **Sim** |
| Alertas de desempenho (nova engine supera a sua) | Não | **Em breve** |

### Heartbeat

Mantenha seu registro ativo com heartbeats periódicos:

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

### Privacidade

- **Sem armazenamento de IP** — seu IP é usado apenas para rate limiting e nunca persiste no registro de agentes
- **Sem dados pessoais** — apenas informações de hardware (chip, RAM), nomes de engines e nome do framework
- **Somente opt-in** — o asiai nunca envia dados a menos que você se registre explicitamente
- **Segurança do token** — seu `agent_token` é hasheado (SHA-256) antes do armazenamento; o texto simples é retornado apenas uma vez no registro
- **Dados de rate limit** — hashes de IP (SHA-256 com salt diário) na tabela de rate limit são automaticamente purgados após 30 dias

## FAQ

**P: O asiai requer root/sudo?**
R: Não. A observabilidade da GPU usa `ioreg` (sem privilégios). Métricas de potência (flag `--power` em benchmarks) requerem `sudo powermetrics`, mas isso é opcional.

**P: Qual é o tempo de resposta da API?**
R: `/api/status` responde em < 500ms (cache 10s). `/api/snapshot` leva 1–3s (coleta dados ao vivo de todas as engines).

**P: Posso rodar o asiai no Linux?**
R: Não. O asiai é exclusivo para macOS Apple Silicon. Ele usa `sysctl`, `vm_stat`, `ioreg` e `launchd` — todas APIs específicas do macOS.

**P: Como monitoro vários Macs?**
R: Execute `asiai daemon start web --host 0.0.0.0` em cada Mac. Colete `/api/metrics` com Prometheus. Visualize no Grafana.

**P: E se uma engine travar?**
R: O asiai detecta falhas de engines automaticamente. Use `asiai doctor` para diagnósticos. Configure alertas via webhook com `asiai alert add` para notificações automáticas.
