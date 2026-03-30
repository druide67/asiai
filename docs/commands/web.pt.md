---
description: Dashboard de monitoramento LLM em tempo real no navegador. Métricas de GPU, saúde dos motores, histórico de performance. Sem configuração necessária.
---

# asiai web

Inicia o dashboard web para monitoramento visual e benchmarking.

## Uso

```bash
asiai web
asiai web --port 9000
asiai web --host 0.0.0.0
asiai web --no-open
```

## Opções

| Opção | Padrão | Descrição |
|-------|--------|-----------|
| `--port` | `8899` | Porta HTTP para escutar |
| `--host` | `127.0.0.1` | Host para fazer bind |
| `--no-open` | | Não abrir o navegador automaticamente |
| `--db` | `~/.local/share/asiai/asiai.db` | Caminho para o banco de dados SQLite |

## Requisitos

O dashboard web requer dependências adicionais:

```bash
pip install asiai[web]
# ou instale tudo:
pip install asiai[all]
```

## Páginas

### Dashboard (`/`)

Visão geral do sistema com status dos motores, modelos carregados, uso de memória e últimos resultados de benchmark.

### Benchmark (`/bench`)

Execute benchmarks cross-engine diretamente do navegador:

- Botão **Quick Bench** — 1 prompt, 1 execução, ~15 segundos
- Opções avançadas: motores, prompts, execuções, context-size (4K/16K/32K/64K), potência
- Progresso ao vivo via SSE
- Tabela de resultados com destaque do vencedor
- Gráficos de throughput e TTFT
- **Card compartilhável** — gerado automaticamente após benchmark (PNG via API, fallback SVG)
- **Seção de compartilhamento** — copiar link, baixar PNG/SVG, compartilhar no X/Reddit, exportar JSON

### Histórico (`/history`)

Visualize métricas de benchmark e sistema ao longo do tempo:

- Gráficos de sistema: carga de CPU, % de memória, utilização de GPU (com breakdown renderer/tiler)
- Atividade dos motores: conexões TCP, requisições processando, uso de cache KV %
- Gráficos de benchmark: throughput (tok/s) e TTFT por motor
- Métricas de processo: CPU % e memória RSS dos motores durante execuções de benchmark
- Filtrar por período (1h / 24h / 7d / 30d / 90d) ou período customizado
- Tabela de dados com indicação de context-size (ex: "code (64K ctx)")

### Monitor (`/monitor`)

Monitoramento de sistema em tempo real com atualização a cada 5 segundos:

- Sparkline de carga de CPU
- Gauge de memória
- Estado térmico
- Lista de modelos carregados

### Doctor (`/doctor`)

Verificação de saúde interativa para sistema, motores e banco de dados. Mesmas verificações do `asiai doctor` com interface visual.

## Endpoints da API

O dashboard web expõe endpoints de API REST para acesso programático.

### `GET /api/status`

Verificação de saúde leve. Cache de 10s, responde em < 500ms.

```json
{
  "status": "ok",
  "ts": 1709700000,
  "uptime": 86400,
  "engines": {"ollama": true, "lmstudio": false},
  "memory_pressure": "normal",
  "thermal_level": "nominal"
}
```

Valores de status: `ok` (todos os motores acessíveis), `degraded` (alguns down), `error` (todos down).

### `GET /api/snapshot`

Snapshot completo de sistema + motores. Cache de 5s. Inclui carga de CPU, memória, estado térmico e status por motor com modelos carregados.

### `GET /api/benchmarks`

Resultados de benchmark com filtros. Retorna dados por execução incluindo tok/s, TTFT, potência, context_size, engine_version.

| Parâmetro | Padrão | Descrição |
|-----------|--------|-----------|
| `hours` | `168` | Período em horas (0 = todos) |
| `model` | | Filtrar por nome do modelo |
| `engine` | | Filtrar por nome do motor |
| `since` / `until` | | Período em Unix timestamp (sobrescreve hours) |

### `GET /api/engine-history`

Histórico de status dos motores (acessibilidade, conexões TCP, cache KV, tokens previstos).

| Parâmetro | Padrão | Descrição |
|-----------|--------|-----------|
| `hours` | `168` | Período em horas |
| `engine` | | Filtrar por nome do motor |

### `GET /api/benchmark-process`

Métricas de CPU e memória no nível de processo das execuções de benchmark (retenção de 7 dias).

| Parâmetro | Padrão | Descrição |
|-----------|--------|-----------|
| `hours` | `168` | Período em horas |
| `engine` | | Filtrar por nome do motor |

### `GET /api/metrics`

Formato Prometheus exposition. Gauges cobrindo métricas de sistema, motor, modelo e benchmark.

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'asiai'
    static_configs:
      - targets: ['localhost:8899']
    metrics_path: '/api/metrics'
    scrape_interval: 30s
```

Métricas incluem:

| Métrica | Tipo | Descrição |
|---------|------|-----------|
| `asiai_cpu_load_1m` | gauge | Média de carga de CPU (1 min) |
| `asiai_memory_used_bytes` | gauge | Memória usada |
| `asiai_thermal_speed_limit_pct` | gauge | % de limite de velocidade da CPU |
| `asiai_engine_reachable{engine}` | gauge | Acessibilidade do motor (0/1) |
| `asiai_engine_models_loaded{engine}` | gauge | Contagem de modelos carregados |
| `asiai_engine_tcp_connections{engine}` | gauge | Conexões TCP estabelecidas |
| `asiai_engine_requests_processing{engine}` | gauge | Requisições sendo processadas |
| `asiai_engine_kv_cache_usage_ratio{engine}` | gauge | Taxa de preenchimento do cache KV (0-1) |
| `asiai_engine_tokens_predicted_total{engine}` | counter | Total acumulado de tokens previstos |
| `asiai_model_vram_bytes{engine,model}` | gauge | VRAM por modelo |
| `asiai_bench_tok_per_sec{engine,model}` | gauge | tok/s do último benchmark |

## Notas

- O dashboard faz bind em `127.0.0.1` por padrão (apenas localhost)
- Use `--host 0.0.0.0` para expor na rede (ex: para monitoramento remoto)
- A porta `8899` é escolhida para evitar conflitos com portas de motores de inferência
