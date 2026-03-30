---
description: Execute benchmarks LLM lado a lado no Apple Silicon. Compare motores, meça tok/s, TTFT e eficiência energética. Compartilhe resultados.
---

# asiai bench

Benchmark cross-engine com prompts padronizados.

## Uso

```bash
asiai bench [options]
```

## Opções

| Opção | Descrição |
|-------|-----------|
| `-m, --model MODEL` | Modelo para benchmark (padrão: auto-detecção) |
| `-e, --engines LIST` | Filtrar motores (ex: `ollama,lmstudio,mlxlm`) |
| `-p, --prompts LIST` | Tipos de prompt: `code`, `tool_call`, `reasoning`, `long_gen` |
| `-r, --runs N` | Execuções por prompt (padrão: 3, para mediana + desvio padrão) |
| `--power` | Validação cruzada de energia com sudo powermetrics (IOReport sempre ativo) |
| `--context-size SIZE` | Prompt de preenchimento de contexto: `4k`, `16k`, `32k`, `64k` |
| `--export FILE` | Exportar resultados para arquivo JSON |
| `-H, --history PERIOD` | Mostrar benchmarks anteriores (ex: `7d`, `24h`) |
| `-Q, --quick` | Benchmark rápido: 1 prompt (code), 1 execução (~15 segundos) |
| `--compare MODEL [MODEL...]` | Comparação cross-model (2-8 modelos, mutuamente exclusivo com `-m`) |
| `--card` | Gerar benchmark card compartilhável (SVG local, PNG com `--share`) |
| `--share` | Compartilhar resultados no banco de dados de benchmark da comunidade |

## Exemplo

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

Quatro prompts padronizados testam diferentes padrões de geração:

| Nome | Tokens | Testa |
|------|--------|-------|
| `code` | 512 | Geração de código estruturado (BST em Python) |
| `tool_call` | 256 | Chamada de função JSON / seguimento de instruções |
| `reasoning` | 384 | Problema matemático de múltiplas etapas |
| `long_gen` | 1024 | Throughput sustentado (script bash) |

Use `--context-size` para testar com prompts de preenchimento de contexto grande.

## Correspondência cross-engine de modelos

O runner resolve nomes de modelos entre motores automaticamente — `gemma2:9b` (Ollama) e `gemma-2-9b` (LM Studio) são reconhecidos como o mesmo modelo.

## Exportação JSON

Exporte resultados para compartilhamento ou análise:

```bash
asiai bench -m qwen3.5 --export bench.json
```

O JSON inclui metadados da máquina, estatísticas por motor (mediana, IC 95%, P50/P90/P99), dados brutos por execução e uma versão de schema para compatibilidade futura.

## Detecção de regressão

Após cada benchmark, o asiai compara resultados contra os últimos 7 dias de histórico e alerta sobre regressões de performance (ex: após atualização de motor ou upgrade do macOS).

## Benchmark rápido

Execute um benchmark rápido com um único prompt e uma execução (~15 segundos):

```bash
asiai bench --quick
asiai bench -Q -m qwen3.5
```

Ideal para demos, GIFs e verificações rápidas. O prompt `code` é usado por padrão. Você pode substituir com `--prompts` se necessário.

## Comparação cross-model

Compare múltiplos modelos em uma única sessão com `--compare`:

```bash
# Auto-expandir em todos os motores disponíveis
asiai bench --compare qwen3.5:4b deepseek-r1:7b

# Filtrar para um motor específico
asiai bench --compare qwen3.5:4b deepseek-r1:7b -e ollama

# Fixar cada modelo em um motor com @
asiai bench --compare qwen3.5:4b@lmstudio deepseek-r1:7b@ollama
```

A notação `@` faz split no **último** `@` da string, então nomes de modelos contendo `@` são tratados corretamente.

### Regras

- `--compare` e `--model` são **mutuamente exclusivos** — use um ou outro.
- Aceita 2 a 8 slots de modelo.
- Sem `@`, cada modelo é expandido para cada motor onde está disponível.

### Tipos de sessão

O tipo de sessão é detectado automaticamente baseado na lista de slots:

| Tipo | Condição | Exemplo |
|------|----------|---------|
| **engine** | Mesmo modelo, motores diferentes | `--compare qwen3.5:4b@lmstudio qwen3.5:4b@ollama` |
| **model** | Modelos diferentes, mesmo motor | `--compare qwen3.5:4b deepseek-r1:7b -e ollama` |
| **matrix** | Mix de modelos e motores | `--compare qwen3.5:4b@lmstudio deepseek-r1:7b@ollama` |

### Combinado com outras flags

`--compare` funciona com todas as flags de saída e execução:

```bash
asiai bench --compare qwen3.5:4b deepseek-r1:7b --quick
asiai bench --compare qwen3.5:4b deepseek-r1:7b --card --share
asiai bench --compare qwen3.5:4b deepseek-r1:7b --runs 5 --power
```

## Benchmark card

Gere um benchmark card compartilhável:

```bash
asiai bench --card                    # SVG salvo localmente
asiai bench --card --share            # SVG + PNG (via API da comunidade)
asiai bench --quick --card --share    # Benchmark rápido + card + compartilhamento
```

O card é uma imagem 1200x630 com tema escuro contendo:
- Nome do modelo e badge do chip de hardware
- Banner de specs: quantização, RAM, GPU cores, tamanho de contexto
- Gráfico de barras estilo terminal de tok/s por motor
- Destaque do vencedor com delta (ex: "2.4x")
- Chips de métricas: tok/s, TTFT, estabilidade, VRAM, potência (W + tok/s/W), versão do motor
- Branding asiai

O SVG é salvo em `~/.local/share/asiai/cards/`. Com `--share`, um PNG também é baixado da API.

## Compartilhamento na comunidade

Compartilhe seus resultados anonimamente:

```bash
asiai bench --share
```

Veja o leaderboard da comunidade com `asiai leaderboard`.

## Detecção de deriva térmica

Ao executar 3+ execuções, o asiai detecta degradação monótona de tok/s entre execuções consecutivas. Se o tok/s cair consistentemente (>5%), um alerta é emitido indicando possível acúmulo de throttling térmico.
