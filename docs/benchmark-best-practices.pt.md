---
description: "Como obter resultados precisos de benchmark LLM no Mac: gerenciamento térmico, apps em segundo plano, número de execuções e dicas de reprodutibilidade."
---

# Boas Práticas de Benchmark

> **Versão**: 0.3.2
> **Status**: Documento vivo — atualizado conforme a metodologia evolui
> **Referências**: MLPerf Inference, SPEC CPU 2017, NVIDIA GenAI-Perf

## Visão Geral

`asiai bench` segue padrões de benchmarking estabelecidos para produzir resultados **confiáveis, reprodutíveis e comparáveis** entre engines de inferência no Apple Silicon. Este documento acompanha quais boas práticas estão implementadas, planejadas ou intencionalmente excluídas.

## Resumo de Conformidade

| Categoria | Prática | Status | Desde |
|-----------|---------|--------|-------|
| **Métricas** | TTFT separado de tok/s | Implementado | v0.3.1 |
| | Amostragem determinística (temperature=0) | Implementado | v0.3.2 |
| | Contagem de tokens via API do servidor (não chunks SSE) | Implementado | v0.3.1 |
| | Monitoramento de potência por engine | Implementado | v0.3.1 |
| | Campo explícito generation_duration_ms | Implementado | v0.3.1 |
| **Aquecimento** | 1 geração de aquecimento por engine (não cronometrada) | Implementado | v0.3.2 |
| **Execuções** | Padrão 3 execuções (mínimo SPEC) | Implementado | v0.3.2 |
| | Mediana como métrica primária (padrão SPEC) | Implementado | v0.3.2 |
| | Média + desvio padrão como secundários | Implementado | v0.3.0 |
| **Variância** | Desvio padrão agrupado intra-prompt | Implementado | v0.3.1 |
| | Classificação de estabilidade baseada em CV | Implementado | v0.3.0 |
| **Ambiente** | Execução sequencial de engines (isolamento de memória) | Implementado | v0.1 |
| | Detecção de throttling térmico + aviso | Implementado | v0.3.2 |
| | Nível térmico + speed_limit registrados | Implementado | v0.1 |
| **Reprodutibilidade** | Versão da engine armazenada por benchmark | Implementado | v0.3.2 |
| | Formato + quantização do modelo armazenados | Implementado | v0.3.2 |
| | Chip de hardware + versão do macOS armazenados | Implementado | v0.3.2 |
| | Código de benchmark open-source | Implementado | v0.1 |
| **Regressão** | Comparação com baseline histórico (SQLite) | Implementado | v0.3.0 |
| | Comparação por (engine, model, prompt_type) | Implementado | v0.3.1 |
| | Filtragem por metrics_version | Implementado | v0.3.1 |
| **Prompts** | 4 tipos de prompts diversos + preenchimento de contexto | Implementado | v0.1 |
| | max_tokens fixo por prompt | Implementado | v0.1 |

## Melhorias Planejadas

### P1 — Rigor Estatístico

| Prática | Descrição | Padrão |
|---------|-----------|--------|
| **Intervalos de confiança 95%** | IC = média +/- 2*EP. Mais informativo que +/- desvio. | Acadêmico |
| **Percentis (P50/P90/P99)** | Para TTFT especialmente — latência de cauda importa. | NVIDIA GenAI-Perf |
| **Detecção de outliers (IQR)** | Sinalizar execuções fora de [Q1 - 1.5*IQR, Q3 + 1.5*IQR]. | Padrão estatístico |
| **Detecção de tendência** | Detectar degradação monotônica de desempenho entre execuções (drift térmico). | Acadêmico |

### P2 — Reprodutibilidade

| Prática | Descrição | Padrão |
|---------|-----------|--------|
| **Cooldown entre engines** | Pausa de 3-5s entre engines para estabilizar temperatura. | Benchmark GPU |
| **Verificação de taxa de tokens** | Avisar se tokens_generated < 90% de max_tokens. | MLPerf |
| **Formato de exportação** | `asiai bench --export` JSON para submissões comunitárias. | Submissões MLPerf |

### P3 — Avançado

| Prática | Descrição | Padrão |
|---------|-----------|--------|
| **Opção `ignore_eos`** | Forçar geração até max_tokens para benchmarks de throughput. | NVIDIA |
| **Teste de requisições concorrentes** | Testar throughput de batching (relevante para vllm-mlx). | NVIDIA |
| **Auditoria de processos em segundo plano** | Avisar se processos pesados estão rodando durante o benchmark. | SPEC |

## Desvios Intencionais

| Prática | Razão do desvio |
|---------|-----------------|
| **Duração mínima de 600s do MLPerf** | Projetado para GPUs de datacenter. Inferência local no Apple Silicon com 3 execuções + 4 prompts já leva ~2-5 minutos. Suficiente para resultados estáveis. |
| **2 workloads de aquecimento não-cronometrados do SPEC** | Usamos 1 geração de aquecimento (não 2 workloads completos). Um único aquecimento é suficiente para engines de inferência local onde o aquecimento JIT é mínimo. |
| **Desvio padrão populacional vs amostral** | Usamos desvio padrão populacional (divisor N) em vez de amostral (divisor N-1). Com N pequeno (3-5 execuções), a diferença é mínima e o populacional é mais conservador. |
| **Controle de escalonamento de frequência** | O Apple Silicon não expõe controles de governador de CPU. Registramos thermal_speed_limit em vez disso para detectar throttling. |

## Considerações Específicas do Apple Silicon

### Arquitetura de Memória Unificada

O Apple Silicon compartilha memória entre CPU e GPU. Duas implicações importantes:

1. **Nunca faça benchmark de duas engines simultaneamente** — elas competem pelo mesmo pool de memória.
   `asiai bench` executa engines sequencialmente por design.
2. **Relatório de VRAM** — Ollama e LM Studio reportam `size_vram` nativamente. Para outras engines
   (llama.cpp, mlx-lm, oMLX, vLLM-MLX, Exo), o asiai usa `ri_phys_footprint` via libproc como
   estimativa de fallback. Isso é o que o Monitor de Atividade exibe e inclui alocações Metal/GPU.
   Valores estimados são rotulados como "(est.)" na UI.

### Throttling Térmico

- **MacBook Air** (sem ventilador): throttling severo sob carga sustentada. Resultados degradam após 5-10 min.
- **MacBook Pro** (com ventilador): throttling é leve e geralmente controlado pelo ventilador acelerando.
- **Mac Mini/Studio/Pro**: resfriamento ativo, throttling mínimo.

`asiai bench` registra `thermal_speed_limit` por resultado e avisa se throttling é detectado
(speed_limit < 100%) durante qualquer execução.

### Cache KV e Tamanho de Contexto

Tamanhos de contexto grandes (32k+) podem causar instabilidade de desempenho em engines que pré-alocam
cache KV no carregamento do modelo. Exemplo: LM Studio tem padrão `loaded_context_length: 262144`
(256k), que aloca ~15-25 GB de cache KV para um modelo 35B, potencialmente saturando
64 GB de memória unificada.

**Recomendações**:
- Ao fazer benchmark de contextos grandes, defina o tamanho de contexto da engine para corresponder ao tamanho real do teste
  (ex.: `lms load model --context-length 65536` para testes de 64k).
- Compare engines com configurações equivalentes de tamanho de contexto para resultados justos.

## Metadados Armazenados Por Benchmark

Cada resultado de benchmark no SQLite inclui:

| Campo | Exemplo | Propósito |
|-------|---------|-----------|
| `engine` | "ollama" | Identificação da engine |
| `engine_version` | "0.17.4" | Detectar mudanças de desempenho entre atualizações |
| `model` | "qwen3.5:35b-a3b" | Identificação do modelo |
| `model_format` | "gguf" | Diferenciar variantes de formato |
| `model_quantization` | "Q4_K_M" | Diferenciar níveis de quantização |
| `hw_chip` | "Apple M4 Pro" | Identificação de hardware |
| `os_version` | "15.3" | Rastreamento da versão do macOS |
| `thermal_level` | "nominal" | Condição do ambiente |
| `thermal_speed_limit` | 100 | Detecção de throttling |
| `metrics_version` | 2 | Versão da fórmula (previne regressão entre versões) |

Esses metadados permitem:
- **Comparação justa de regressão**: comparar apenas resultados com metadados correspondentes
- **Benchmarks entre máquinas**: identificar diferenças de hardware
- **Compartilhamento de dados comunitários**: resultados autodescritos (planejado para v1.x)
