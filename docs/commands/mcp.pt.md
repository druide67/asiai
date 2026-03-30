---
description: Servidor MCP com 11 ferramentas para agentes de IA monitorarem motores de inferência, executarem benchmarks e obterem recomendações baseadas em hardware.
---

# asiai mcp

Inicia o servidor MCP (Model Context Protocol), permitindo que agentes de IA monitorem e façam benchmark da sua infraestrutura de inferência.

## Uso

```bash
asiai mcp                          # Transporte stdio (Claude Code)
asiai mcp --transport sse          # Transporte SSE (agentes em rede)
asiai mcp --transport sse --port 9000
```

## Opções

| Opção | Descrição |
|-------|-----------|
| `--transport` | Protocolo de transporte: `stdio` (padrão), `sse`, `streamable-http` |
| `--host` | Endereço de bind (padrão: `127.0.0.1`) |
| `--port` | Porta para transporte SSE/HTTP (padrão: `8900`) |
| `--register` | Registro opt-in na rede de agentes asiai (anônimo) |

## Ferramentas (11)

| Ferramenta | Descrição | Somente leitura |
|------------|-----------|-----------------|
| `check_inference_health` | Verificação rápida de saúde: motores up/down, pressão de memória, térmico, GPU | Sim |
| `get_inference_snapshot` | Snapshot completo do sistema com todas as métricas | Sim |
| `list_models` | Listar todos os modelos carregados em todos os motores | Sim |
| `detect_engines` | Re-escanear motores de inferência | Sim |
| `run_benchmark` | Executar benchmark ou comparação cross-model (limitado a 1/min) | Não |
| `get_recommendations` | Recomendações de motor/modelo baseadas em hardware | Sim |
| `diagnose` | Executar verificações de diagnóstico (como `asiai doctor`) | Sim |
| `get_metrics_history` | Consultar métricas históricas (1-168 horas) | Sim |
| `get_benchmark_history` | Consultar resultados de benchmark anteriores com filtros | Sim |
| `compare_engines` | Comparar performance de motores para um modelo com veredito; suporta comparação multi-model do histórico | Sim |
| `refresh_engines` | Re-detectar motores sem reiniciar o servidor | Sim |

## Recursos (3)

| Recurso | URI | Descrição |
|---------|-----|-----------|
| Status do Sistema | `asiai://status` | Saúde atual do sistema (memória, térmico, GPU) |
| Modelos | `asiai://models` | Todos os modelos carregados em todos os motores |
| Info do Sistema | `asiai://system` | Informações de hardware (chip, RAM, cores, SO, uptime) |

## Integração com Claude Code

Adicione à configuração MCP do seu Claude Code (`~/.claude/claude_desktop_config.json`):

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

Depois pergunte ao Claude: *"Verifique minha saúde de inferência"* ou *"Compare Ollama vs LM Studio para qwen3.5"*.

## Benchmark cards

A ferramenta `run_benchmark` suporta geração de cards via parâmetro `card`. Quando `card=true`, um benchmark card SVG de 1200x630 é gerado e `card_path` é retornado na resposta.

```json
{"tool": "run_benchmark", "arguments": {"model": "qwen3.5", "card": true}}
```

Comparação cross-model (mutuamente exclusivo com `model`, máx 8 slots):

```json
{"tool": "run_benchmark", "arguments": {"compare": ["qwen3.5:4b", "deepseek-r1:7b"], "card": true}}
```

Equivalente CLI para PNG + compartilhamento:

```bash
asiai bench --quick --card --share    # Benchmark rápido + card + compartilhamento (~15s)
```

Veja a página [Benchmark Card](../benchmark-card.md) para detalhes.

## Registro de agente

Junte-se à rede de agentes asiai para obter recursos da comunidade (leaderboard, comparação, estatísticas percentis):

```bash
asiai mcp --register                  # Registrar na primeira execução, heartbeat nas seguintes
asiai unregister                      # Remover credenciais locais
```

O registro é **opt-in e anônimo** — apenas informações de hardware (chip, RAM) e nomes de motores são enviados. Nenhum IP, hostname ou dado pessoal é armazenado. As credenciais são salvas em `~/.local/share/asiai/agent.json` (chmod 600).

Em chamadas `asiai mcp --register` subsequentes, um heartbeat é enviado em vez de re-registrar. Se a API estiver inacessível, o servidor MCP inicia normalmente sem registro.

Verifique o status do seu registro com `asiai version`.

## Agentes em rede

Para agentes em outras máquinas (ex: monitorando um Mac Mini headless):

```bash
asiai mcp --transport sse --host 0.0.0.0 --port 8900
```

Veja o [guia de Integração com Agentes](../agent.md) para instruções detalhadas de configuração.
