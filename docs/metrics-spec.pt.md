---
description: "Definições detalhadas de todas as métricas de benchmark do asiai: tok/s, TTFT, potência em watts, eficiência, VRAM, estabilidade, estado térmico."
---

# Especificação de Métricas de Benchmark

> **Versão**: 0.4.0
> **Status**: Implementado
> **Escopo**: `asiai bench` — todos os motores

## Motivação

Os resultados de benchmark devem ser **comparáveis entre motores**. Cada métrica tem uma única definição que todas as implementações de motor devem respeitar. A implementação pode variar (API server-side vs medição client-side), mas a semântica deve ser idêntica.

## Métricas

### M1. `tok_per_sec` — Velocidade de Geração

**Definição**: Tokens produzidos por segundo considerando **apenas o tempo de geração**, excluindo processamento de prompt (TTFT).

```
generation_s = total_duration_s - ttft_s
tok_per_sec  = tokens_generated / generation_s    (if generation_s >= 0.01)
             = 0.0                                 (otherwise)
```

| Motor | Fonte de `generation_s` |
|-------|------------------------|
| Ollama | `eval_duration / 1e9` (API do servidor — direto) |
| OpenAI-compat | `elapsed_s - (ttft_ms / 1000)` (client-side) |

**Justificativa**: Em tamanhos de contexto grandes (ex: 64k tokens), o TTFT pode dominar a duração total. Incluí-lo no tok/s faz geradores rápidos parecerem lentos (ex: 3,2 tok/s em vez de 42 tok/s).

### M2. `ttft_ms` — Time to First Token

**Definição**: Tempo entre o envio da requisição e o recebimento do primeiro token de saída, em ms.

| Motor | Fonte |
|-------|-------|
| Ollama | `prompt_eval_duration / 1e6` (API do servidor) |
| OpenAI-compat | `(time.monotonic() no 1o chunk de conteúdo - t0) * 1000` (cliente) |

Nota: As semânticas diferem levemente (medição servidor vs cliente), mas em localhost a diferença é ~1ms — aceitável.

### M3. `total_duration_ms` — Duração Total

**Definição**: Tempo total wall-clock da requisição (processamento de prompt + geração), em ms.

**Invariante**: `total_duration_ms >= ttft_ms` — sempre.

| Motor | Fonte |
|-------|-------|
| Ollama | `total_duration / 1e6` (API do servidor) |
| OpenAI-compat | `elapsed_s * 1000` (wall-clock do cliente) |

### M4. `tokens_generated` — Contagem de Tokens

**Definição**: Número de tokens de saída produzidos pelo modelo.

**Fonte (por prioridade)**:
1. Contador do servidor: Ollama `eval_count`, OpenAI-compat `usage.completion_tokens`
2. Estimativa por comprimento de texto: `max(1, len(text) // 4)` (heurística: ~4 chars/token)
3. **Nunca** `len(text_parts)` (chunks SSE != tokens)

### M5. `generation_duration_ms` — Duração da Geração

**Definição**: Tempo de geração apenas (excluindo TTFT), em ms.
Torna a decomposição `total = ttft + geração` explícita e auditável.

| Motor | Fonte |
|-------|-------|
| Ollama | `eval_duration / 1e6` (API do servidor — direto) |
| OpenAI-compat | `max(0, elapsed_s - ttft_s) * 1000` (computado) |

### M6. `power_watts` — Potência da GPU

**Definição**: Potência média da GPU durante a execução **deste motor específico**, em watts.

**Escopo**: Um `PowerMonitor` por motor. Iniciado antes do primeiro prompt, parado após a última execução. Cada motor tem sua própria medição — sem média da sessão inteira.

Fonte: `sudo powermetrics` (macOS).

### M7. `tok_per_sec_per_watt` — Eficiência Energética

```
tok_per_sec_per_watt = tok_per_sec / power_watts
```

Usa o tok/s corrigido (M1) e a potência por motor (M6).

### M8. `std_dev_tok_s` — Variância (Pooled)

**Definição**: Desvio padrão pooled intra-prompt — captura o ruído entre execuções **sem** misturar a variância inter-prompt.

```
For each prompt_type p with runs [v1, v2, ..., vn]:
    var_p = sum((vi - mean_p)^2) / n    (population variance)

pooled_variance = mean(var_p for all p with n >= 2)
std_dev_tok_s   = sqrt(pooled_variance)
```

**Classificação de estabilidade** (inalterada):
- CV < 5% → `stable`
- CV < 10% → `variable`
- CV >= 10% → `unstable`

Onde CV = `(std_dev_tok_s / avg_tok_s) * 100`.

## Mapa de Implementação

| Métrica | `base.py` | `ollama.py` | `openai_compat.py` | `runner.py` | `reporter.py` |
|---------|-----------|-------------|--------------------|-----------  |----------------|
| M1 tok/s | field | server API | client (excl. TTFT) | passthrough | avg |
| M2 ttft_ms | field | server API | client streaming | passthrough | avg |
| M3 total_duration_ms | field | server API | client wall-clock | passthrough | avg |
| M4 tokens_generated | field | server API | server or `len//4` | passthrough | avg |
| M5 generation_duration_ms | field | server API | computed | stored in dict | — |
| M6 power_watts | — | — | — | per-engine monitor | passthrough |
| M7 tok/s/W | — | — | — | computed | passthrough |
| M8 std_dev | — | — | — | — | pooled intra-prompt |

## Protocolo de Benchmark

1. **Aquecimento**: 1 geração não cronometrada por motor (`"Hello"`, max_tokens=1) para aquecer caches.
2. **Execuções medidas**: 3 execuções por padrão por prompt por motor (configurável via `--runs`).
3. **Amostragem**: `temperature=0` (greedy) em todos os motores para saída determinística.
4. **Relatório**: Mediana de tok/s como métrica primária (padrão SPEC), média +/- desvio padrão como secundária.
5. **Throttling**: Alerta emitido se `thermal_speed_limit < 100%` durante qualquer execução.
6. **Metadados**: engine_version, model_format, model_quantization, hw_chip, os_version armazenados por resultado para reprodutibilidade.

Veja [benchmark-best-practices.md](benchmark-best-practices.md) para a auditoria completa da metodologia.
