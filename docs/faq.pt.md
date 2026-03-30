---
title: "Perguntas Frequentes"
description: "Perguntas comuns sobre o asiai: motores suportados, requisitos Apple Silicon, benchmark de LLMs no Mac, requisitos de RAM e mais."
type: faq
faq:
  - q: "O que é o asiai?"
    a: "asiai é uma ferramenta CLI open-source que faz benchmark e monitora motores de inferência LLM em Macs com Apple Silicon. Suporta 7 motores (Ollama, LM Studio, mlx-lm, llama.cpp, oMLX, vllm-mlx, Exo) e mede tok/s, TTFT, consumo de energia e uso de VRAM."
  - q: "Qual é o motor de inferência LLM mais rápido no Apple Silicon?"
    a: "Em benchmarks no M4 Pro 64GB com Qwen3-Coder-30B, o LM Studio (backend MLX) atinge 102 tok/s vs 70 tok/s do Ollama — 46% mais rápido para geração de tokens. No entanto, o Ollama tem menor latência de time-to-first-token."
  - q: "O asiai funciona em Macs Intel?"
    a: "Não. O asiai requer Apple Silicon (M1, M2, M3 ou M4). Ele usa APIs específicas do macOS para métricas de GPU, monitoramento de energia via IOReport e detecção de hardware que só estão disponíveis em chips Apple Silicon."
  - q: "Quanta RAM preciso para rodar LLMs localmente?"
    a: "Para um modelo 7B quantizado em Q4: 8 GB mínimo. Para 13B: 16 GB. Para 30B: 32-64 GB. Modelos MoE como Qwen3.5-35B-A3B usam apenas cerca de 7 GB de parâmetros ativos, ideais para Macs com 16 GB."
  - q: "Ollama ou LM Studio é melhor para Mac?"
    a: "Depende do seu caso de uso. O LM Studio (MLX) é mais rápido para throughput e mais eficiente energeticamente. O Ollama (llama.cpp) tem menor latência de primeiro token e lida melhor com janelas de contexto grandes (>32K). Veja a comparação detalhada em asiai.dev/ollama-vs-lmstudio."
  - q: "O asiai requer sudo ou acesso root?"
    a: "Não. Todas as funcionalidades, incluindo observabilidade de GPU (ioreg) e monitoramento de energia (IOReport), funcionam sem sudo. A flag opcional --power para validação cruzada com powermetrics é a única funcionalidade que usa sudo."
  - q: "Como instalo o asiai?"
    a: "Instale via pip (pip install asiai) ou Homebrew (brew tap druide67/tap && brew install asiai). Requer Python 3.11+."
  - q: "Agentes de IA podem usar o asiai?"
    a: "Sim. O asiai inclui um servidor MCP com 11 ferramentas e 3 recursos. Instale com pip install asiai[mcp] e configure como asiai mcp no seu cliente MCP (Claude Code, Cursor, etc.)."
  - q: "Quão precisas são as medições de energia?"
    a: "As leituras de energia do IOReport têm menos de 1,5% de diferença comparado ao sudo powermetrics, validado em 20 amostras tanto no LM Studio (MLX) quanto no Ollama (llama.cpp)."
  - q: "Posso fazer benchmark de vários modelos de uma vez?"
    a: "Sim. Use asiai bench --compare para executar benchmarks cross-model. Suporta sintaxe model@engine para controle preciso, com até 8 slots de comparação."
  - q: "Como compartilho meus resultados de benchmark?"
    a: "Execute asiai bench --share para enviar resultados anonimamente para o leaderboard da comunidade. Adicione --card para gerar uma imagem de benchmark card compartilhável de 1200x630."
  - q: "Quais métricas o asiai mede?"
    a: "Sete métricas principais: tok/s (velocidade de geração), TTFT (tempo até o primeiro token), potência (GPU+CPU watts), tok/s/W (eficiência energética), uso de VRAM, estabilidade entre execuções e estado de throttling térmico."
---

# Perguntas Frequentes

## Geral

**O que é o asiai?**

asiai é uma ferramenta CLI open-source que faz benchmark e monitora motores de inferência LLM em Macs com Apple Silicon. Suporta 7 motores (Ollama, LM Studio, mlx-lm, llama.cpp, oMLX, vllm-mlx, Exo) e mede tok/s, TTFT, consumo de energia e uso de VRAM com zero dependências.

**O asiai funciona em Macs Intel ou Linux?**

Não. O asiai requer Apple Silicon (M1, M2, M3 ou M4). Ele usa APIs específicas do macOS (`sysctl`, `vm_stat`, `ioreg`, `IOReport`, `launchd`) que só estão disponíveis em Macs com Apple Silicon.

**O asiai requer sudo ou acesso root?**

Não. Todas as funcionalidades, incluindo observabilidade de GPU (`ioreg`) e monitoramento de energia (`IOReport`), funcionam sem sudo. A flag opcional `--power` para validação cruzada com `powermetrics` é a única funcionalidade que usa sudo.

## Motores e Performance

**Qual é o motor de inferência LLM mais rápido no Apple Silicon?**

Em nossos benchmarks no M4 Pro 64GB com Qwen3-Coder-30B (Q4_K_M), o LM Studio (backend MLX) atinge **102 tok/s** vs **70 tok/s** do Ollama — 46% mais rápido para geração de tokens. O LM Studio também é 82% mais eficiente energeticamente (8,23 vs 4,53 tok/s/W). Veja nossa [comparação detalhada](ollama-vs-lmstudio.md).

**Ollama ou LM Studio é melhor para Mac?**

Depende do seu caso de uso:

- **LM Studio (MLX)**: Melhor para throughput (geração de código, respostas longas). Mais rápido, mais eficiente, menor uso de VRAM.
- **Ollama (llama.cpp)**: Melhor para latência (chatbots, uso interativo). TTFT mais rápido. Melhor para janelas de contexto grandes (>32K tokens).

**Quanta RAM preciso para rodar LLMs localmente?**

| Tamanho do Modelo | Quantização | RAM Necessária |
|-------------------|-------------|----------------|
| 7B | Q4_K_M | 8 GB mínimo |
| 13B | Q4_K_M | 16 GB mínimo |
| 30B | Q4_K_M | 32-64 GB |
| 35B MoE (3B ativos) | Q4_K_M | 16 GB (apenas parâmetros ativos carregados) |

## Benchmarking

**Como executo meu primeiro benchmark?**

Três comandos:

```bash
pip install asiai     # Instalar
asiai detect          # Encontrar motores
asiai bench           # Executar benchmark
```

**Quanto tempo leva um benchmark?**

Um benchmark rápido (`asiai bench --quick`) leva cerca de 2 minutos. Uma comparação cross-engine completa com múltiplos prompts e 3 execuções leva 10-15 minutos.

**Quão precisas são as medições de energia?**

As leituras de energia do IOReport têm menos de 1,5% de diferença comparado ao `sudo powermetrics`, validado em 20 amostras tanto no LM Studio (MLX) quanto no Ollama (llama.cpp).

**Posso comparar meus resultados com outros usuários de Mac?**

Sim. Execute `asiai bench --share` para enviar resultados anonimamente para o [leaderboard da comunidade](leaderboard.md). Use `asiai compare` para ver como seu Mac se compara.

## Integração com Agentes de IA

**Agentes de IA podem usar o asiai?**

Sim. O asiai inclui um servidor MCP com 11 ferramentas e 3 recursos. Instale com `pip install "asiai[mcp]"` e configure como `asiai mcp` no seu cliente MCP (Claude Code, Cursor, Windsurf). Veja o [Guia de Integração com Agentes](agent.md).

**Quais ferramentas MCP estão disponíveis?**

11 ferramentas: `check_inference_health`, `get_inference_snapshot`, `list_models`, `detect_engines`, `run_benchmark`, `get_recommendations`, `diagnose`, `get_metrics_history`, `get_benchmark_history`, `refresh_engines`, `compare_engines`.

3 recursos: `asiai://status`, `asiai://models`, `asiai://system`.
