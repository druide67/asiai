---
title: "Como Fazer Benchmark de LLMs no Mac"
description: "Como fazer benchmark de inferência LLM no Mac: guia passo a passo para medir tok/s, TTFT, potência e VRAM no Apple Silicon com múltiplas engines."
type: howto
date: 2026-03-28
updated: 2026-03-29
duration: PT5M
steps:
  - name: "Instalar o asiai"
    text: "Instale o asiai via pip (pip install asiai) ou Homebrew (brew tap druide67/tap && brew install asiai)."
  - name: "Detectar suas engines"
    text: "Execute 'asiai detect' para encontrar automaticamente engines de inferência em execução (Ollama, LM Studio, llama.cpp, mlx-lm, oMLX, vLLM-MLX, Exo) no seu Mac."
  - name: "Executar um benchmark"
    text: "Execute 'asiai bench' para auto-detectar o melhor modelo entre as engines e executar uma comparação cross-engine medindo tok/s, TTFT, potência e VRAM."
---

# Como Fazer Benchmark de LLMs no Mac

Rodando um LLM local no seu Mac? Veja como medir o desempenho real — não impressões, não "parece rápido", mas tok/s, TTFT, consumo de potência e uso de memória reais.

## Por Que Fazer Benchmark?

O mesmo modelo roda em velocidades muito diferentes dependendo da engine de inferência. No Apple Silicon, engines baseadas em MLX (LM Studio, mlx-lm, oMLX) podem ser **2x mais rápidas** que engines baseadas em llama.cpp (Ollama) para o mesmo modelo. Sem medir, você está deixando desempenho na mesa.

## Início Rápido (2 minutos)

### 1. Instalar o asiai

```bash
pip install asiai
```

Ou via Homebrew:

```bash
brew tap druide67/tap
brew install asiai
```

### 2. Detectar suas engines

```bash
asiai detect
```

O asiai encontra automaticamente engines em execução (Ollama, LM Studio, llama.cpp, mlx-lm, oMLX, vLLM-MLX, Exo) no seu Mac.

### 3. Executar um benchmark

```bash
asiai bench
```

É isso. O asiai auto-detecta o melhor modelo entre suas engines e executa uma comparação cross-engine.

## O Que É Medido

| Métrica | O Que Significa |
|---------|----------------|
| **tok/s** | Tokens gerados por segundo (apenas geração, exclui processamento de prompt) |
| **TTFT** | Time to First Token — latência antes do início da geração |
| **Potência** | Watts de GPU + CPU durante inferência (via IOReport, sem necessidade de sudo) |
| **tok/s/W** | Eficiência energética — tokens por segundo por watt |
| **VRAM** | Memória usada pelo modelo (API nativa ou estimada via `ri_phys_footprint`) |
| **Estabilidade** | Variância entre execuções: estável (<5% CV), variável (<10%), instável (>10%) |
| **Térmico** | Se o Mac sofreu throttling durante o benchmark |

## Exemplo de Saída

```
Mac16,11 — Apple M4 Pro  RAM: 64.0 GB  Pressure: normal

Benchmark: qwen3-coder-30b

  Engine        tok/s   Tokens Duration     TTFT       VRAM    Thermal
  lmstudio      102.2      537    7.00s    0.29s    24.2 GB    nominal
  ollama         69.8      512   17.33s    0.18s    32.0 GB    nominal

  Winner: lmstudio (+46% tok/s)

  Power Efficiency
    lmstudio     102.2 tok/s @ 12.4W = 8.23 tok/s/W
    ollama        69.8 tok/s @ 15.4W = 4.53 tok/s/W
```

*Exemplo de saída de um benchmark real no M4 Pro 64GB. Seus números vão variar conforme hardware e modelo. [Veja mais resultados →](ollama-vs-lmstudio.md)*

## Opções Avançadas

### Comparar engines específicas

```bash
asiai bench --engines ollama,lmstudio,omlx
```

### Múltiplos prompts e execuções

```bash
asiai bench --prompts code,reasoning,tool_call --runs 3
```

### Benchmark de contexto grande

```bash
asiai bench --context-size 64K
```

### Gerar um card compartilhável

```bash
asiai bench --card --share
```

Cria uma imagem de benchmark card e compartilha os resultados com o [leaderboard comunitário](leaderboard.md).

## Dicas para Apple Silicon

### Memória importa

Em um Mac com 16GB, fique com modelos abaixo de 14GB (carregados). Modelos MoE (Qwen3.5-35B-A3B, 3B ativos) são ideais — entregam qualidade de classe 35B com uso de memória de classe 7B.

### A escolha da engine importa mais do que você imagina

Engines MLX são significativamente mais rápidas que llama.cpp no Apple Silicon para a maioria dos modelos. [Veja nossa comparação Ollama vs LM Studio](ollama-vs-lmstudio.md) com números reais.

### Throttling térmico

MacBook Air (sem ventilador) sofre throttling após 5-10 minutos de inferência sustentada. Mac Mini/Studio/Pro lidam com cargas sustentadas sem throttling. O asiai detecta e reporta throttling térmico automaticamente.

## Compare com a Comunidade

Veja como seu Mac se sai contra outras máquinas Apple Silicon:

```bash
asiai compare
```

Ou visite o [leaderboard online](leaderboard.md).

## FAQ

**P: Qual é a engine de inferência LLM mais rápida no Apple Silicon?**
R: Em nossos benchmarks no M4 Pro 64GB, LM Studio (backend MLX) é a mais rápida para geração de tokens — 46% mais rápida que o Ollama (llama.cpp). No entanto, o Ollama tem TTFT (time to first token) menor. Veja nossa [comparação detalhada](ollama-vs-lmstudio.md).

**P: Quanta RAM preciso para rodar um modelo de 30B no Mac?**
R: Um modelo 30B quantizado em Q4_K_M usa 24-32 GB de memória unificada dependendo da engine. Você precisa de pelo menos 32 GB de RAM, idealmente 64 GB para evitar pressão de memória. Modelos MoE como Qwen3.5-35B-A3B usam apenas ~7 GB de parâmetros ativos.

**P: O asiai funciona em Macs Intel?**
R: Não. O asiai requer Apple Silicon (M1/M2/M3/M4). Ele usa APIs específicas do macOS para métricas de GPU, monitoramento de potência e detecção de hardware que estão disponíveis apenas no Apple Silicon.

**P: Ollama ou LM Studio é mais rápido no M4?**
R: LM Studio é mais rápido para throughput (102 tok/s vs 70 tok/s no Qwen3-Coder-30B). Ollama é mais rápido para latência do primeiro token (0.18s vs 0.29s) e para janelas de contexto grandes (>32K tokens) onde o prefill do llama.cpp é até 3x mais rápido.

**P: Quanto tempo leva um benchmark?**
R: Um benchmark rápido leva cerca de 2 minutos. Uma comparação cross-engine completa com múltiplos prompts e execuções leva 10-15 minutos. Use `asiai bench --quick` para um teste rápido de uma única execução.

**P: Posso comparar meus resultados com outros usuários de Mac?**
R: Sim. Execute `asiai bench --share` para enviar resultados anonimamente ao [leaderboard comunitário](leaderboard.md). Use `asiai compare` para ver como seu Mac se compara a outras máquinas Apple Silicon.

## Leitura Adicional

- [Metodologia de Benchmark](methodology.md) — como o asiai garante medições confiáveis
- [Boas Práticas de Benchmark](benchmark-best-practices.md) — dicas para resultados precisos
- [Comparação de Engines](ollama-vs-lmstudio.md) — Ollama vs LM Studio frente a frente
