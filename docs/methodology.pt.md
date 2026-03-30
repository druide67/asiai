---
description: Como o asiai mede tok/s, TTFT e energia. Aquecimento, metodologia estatística e por que os resultados são reprodutíveis.
---

# Metodologia de Benchmark

O asiai segue padrões estabelecidos de benchmarking ([MLPerf](https://mlcommons.org/benchmarks/inference-server/), [SPEC CPU 2017](https://www.spec.org/cpu2017/), [NVIDIA GenAI-Perf](https://docs.nvidia.com/deeplearning/nemo/user-guide/docs/en/stable/benchmarking/genai_perf.html)) para produzir resultados confiáveis, reprodutíveis e comparáveis.

## Protocolo

1. **Verificação pré-execução**: Recusa iniciar se a pressão de memória estiver crítica ou se o sistema estiver com throttling severo (<80%)
2. **Aquecimento**: 1 geração não cronometrada por motor para aquecer compiladores JIT e caches
3. **Execuções medidas**: 3 execuções por padrão por prompt por motor (configurável via `--runs`)
4. **Amostragem**: `temperature=0` (greedy) para saída determinística
5. **Descarregamento de modelo**: Após o benchmark de cada motor, o modelo é descarregado para liberar memória unificada antes do próximo motor iniciar. Isso previne acúmulo de memória e swap ao comparar múltiplos motores com modelos grandes
6. **Cooldown adaptativo**: Após descarregar, o asiai aguarda a pressão de memória do macOS retornar ao "normal" (máx 30s), depois adiciona um cooldown térmico mínimo de 5s
7. **Verificações de sanidade**: Resultados com tok/s <= 0 são descartados. TTFT > 60s ou tok/s > 500 geram alertas (provável swap ou erros de medição)
8. **Relatório**: Mediana de tok/s como métrica primária (padrão SPEC), média +/- desvio padrão como secundária
9. **Throttling**: Alerta emitido se `thermal_speed_limit < 100%` durante qualquer execução. Deriva térmica (queda monótona de tok/s entre execuções, >= 5% de queda) é detectada e reportada
10. **Metadados**: Versão do motor, formato do modelo, quantização, chip de hardware, versão do macOS armazenados por resultado

## Métricas

### tok/s — Velocidade de Geração

Tokens por segundo considerando **apenas o tempo de geração**, excluindo processamento de prompt (TTFT).

```
generation_s = total_duration_s - ttft_s
tok_per_sec  = tokens_generated / generation_s
```

Em tamanhos de contexto grandes (ex: 64k tokens), o TTFT pode dominar a duração total. Excluí-lo do tok/s evita que geradores rápidos pareçam lentos.

### TTFT — Time to First Token

Tempo entre o envio da requisição e o recebimento do primeiro token de saída, em milissegundos. Medido no lado do servidor (Ollama) ou no lado do cliente no primeiro chunk SSE com conteúdo (motores compatíveis com OpenAI).

### Power — Watts da GPU

Potência média da GPU durante a execução de cada motor específico, medida via `sudo powermetrics`. Um `PowerMonitor` por motor — sem média da sessão inteira.

### tok/s/W — Eficiência Energética

```
tok_per_sec_per_watt = tok_per_sec / power_watts
```

### Variância — Desvio Padrão Pooled

O desvio padrão pooled intra-prompt captura o ruído entre execuções **sem** misturar a variância inter-prompt.

Classificação de estabilidade:

- CV < 5% → `stable`
- CV < 10% → `variable`
- CV >= 10% → `unstable`

Onde CV = `(std_dev / mean) * 100`.

## Conformidade

| Prática | Status |
|---------|--------|
| Verificação pré-execução (pressão de memória + térmico) | Implementado |
| TTFT separado do tok/s | Implementado |
| Amostragem determinística (temperature=0) | Implementado |
| Contagem de tokens via API do servidor (não chunks SSE) | Implementado |
| Monitoramento de energia por motor (IOReport, sem sudo) | Implementado |
| 1 geração de aquecimento por motor | Implementado |
| 3 execuções por padrão (mínimo SPEC) | Implementado |
| Mediana como métrica primária (padrão SPEC) | Implementado |
| Desvio padrão pooled intra-prompt | Implementado |
| Descarregamento de modelo entre motores | Implementado |
| Cooldown adaptativo (sensível à pressão de memória) | Implementado |
| Verificações de sanidade (tok/s, limites TTFT) | Implementado |
| Detecção de throttling térmico + alerta | Implementado |
| Detecção de deriva térmica (queda monótona) | Implementado |
| Versão do motor + metadados do modelo armazenados | Implementado |
| VRAM universal via ri_phys_footprint | Implementado |
| Detecção de regressão histórica | Implementado |

## Considerações para Apple Silicon

### Memória Unificada

O Apple Silicon compartilha memória entre CPU e GPU. O asiai executa motores **sequencialmente** e **descarrega modelos entre motores** para evitar contenção de memória e swap. A VRAM é reportada nativamente pelo Ollama e LM Studio; para outros motores, o asiai estima o uso de memória via `ri_phys_footprint` (a métrica de footprint físico do macOS, igual ao Monitor de Atividade). Valores estimados são rotulados "(est.)" na interface.

### Throttling Térmico

- **MacBook Air** (sem ventilador): throttling severo sob carga sustentada
- **MacBook Pro** (com ventilador): throttling leve
- **Mac Mini/Studio/Pro**: refrigeração ativa, throttling mínimo

O asiai registra `thermal_speed_limit` por resultado e alerta se throttling for detectado.

### Cache KV

Tamanhos de contexto grandes (32k+) podem causar instabilidade em motores que pré-alocam cache KV. Configure o comprimento de contexto do motor para corresponder ao tamanho real do teste para resultados justos.

## Medição de Energia

O asiai mede o consumo de energia da GPU, CPU, ANE e DRAM via framework Apple IOReport Energy Model — **sem necessidade de sudo**. A energia é medida automaticamente em cada benchmark e cada snapshot de monitoramento.

O IOReport lê os mesmos contadores de energia do hardware que o `sudo powermetrics`, mas através de uma API em user-space (`libIOReport.dylib` via ctypes). Isso elimina a necessidade de configuração de sudo sem senha.

### Validação

Fizemos validação cruzada do IOReport contra `sudo powermetrics` sob carga de inferência LLM no M4 Pro 64GB, usando 10 amostras pareadas por motor em intervalos de 2 segundos:

| Motor | IOReport média | powermetrics média | Delta médio | Delta máximo |
|-------|---------------|-------------------|-------------|--------------|
| LM Studio (MLX) | 12,6 W | 12,6 W | 0,9% | 2,1% |
| Ollama (llama.cpp) | 15,6 W | 15,4 W | 1,3% | 4,1% |

Ambos os motores confirmaram delta médio <1,5% com 10/10 amostras pareadas. A potência ANE foi 0,000W em todas as 20 amostras, confirmando que nenhum motor de LLM usa atualmente o Neural Engine.

A flag `--power` habilita validação cruzada adicional executando IOReport e `sudo powermetrics` simultaneamente, armazenando ambas as leituras para comparação.

### Eficiência Energética

A eficiência energética (tok/s por watt) é calculada como `tok_per_sec / gpu_watts` para cada resultado de benchmark. Esta métrica permite a comparação do custo de inferência entre motores e hardware.

## Metadados

Cada resultado de benchmark armazena: engine, engine_version, model, model_format, model_quantization, hw_chip, os_version, thermal_level, thermal_speed_limit, power_watts, power_source, metrics_version. Isso permite comparação justa de regressão e benchmarks cross-machine.
