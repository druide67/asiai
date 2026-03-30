---
title: "Ollama vs LM Studio: Benchmark Apple Silicon"
description: "Benchmark Ollama vs LM Studio no Apple Silicon: tok/s, TTFT, energia e VRAM comparados lado a lado no M4 Pro com medições reais."
type: article
date: 2026-03-28
updated: 2026-03-29
dataset:
  name: "Benchmark Ollama vs LM Studio no Apple Silicon M4 Pro"
  description: "Benchmark head-to-head comparando Ollama (llama.cpp) e LM Studio (MLX) no Mac Mini M4 Pro 64GB com Qwen3-Coder-30B. Métricas: tok/s, TTFT, potência da GPU, eficiência, VRAM."
  date: "2026-03"
---

# Ollama vs LM Studio: Benchmark Apple Silicon

Qual motor de inferência é mais rápido no seu Mac? Fizemos benchmark do Ollama (backend llama.cpp) e LM Studio (backend MLX) head-to-head no mesmo modelo e hardware usando asiai 1.4.0 em março de 2026.

## Configuração do Teste

| | |
|---|---|
| **Hardware** | Mac Mini M4 Pro, 64 GB de memória unificada |
| **Modelo** | Qwen3-Coder-30B (arquitetura MoE, Q4_K_M / MLX 4-bit) |
| **Versão asiai** | 1.4.0 |
| **Metodologia** | 1 aquecimento + 1 execução medida por motor, temperature=0, modelo descarregado entre motores ([metodologia completa](methodology.md)) |

## Resultados

| Métrica | LM Studio (MLX) | Ollama (llama.cpp) | Diferença |
|---------|-----------------|-------------------|-----------|
| **Throughput** | 102,2 tok/s | 69,8 tok/s | **+46%** |
| **TTFT** | 291 ms | 175 ms | Ollama mais rápido |
| **Potência GPU** | 12,4 W | 15,4 W | **-20%** |
| **Eficiência** | 8,2 tok/s/W | 4,5 tok/s/W | **+82%** |
| **Memória do Processo** | 21,4 GB (RSS) | 41,6 GB (RSS) | -49% |

!!! note "Sobre os números de memória"
    O Ollama pré-aloca cache KV para toda a janela de contexto (262K tokens), o que infla seu footprint de memória. O LM Studio aloca cache KV sob demanda. O RSS do processo reflete a memória total usada pelo processo do motor, não apenas os pesos do modelo.

## Principais Descobertas

### LM Studio vence em throughput (+46%)

A otimização nativa Metal do MLX extrai mais largura de banda da memória unificada do Apple Silicon. Em arquiteturas MoE, a vantagem é significativa. Na variante maior Qwen3.5-35B-A3B, medimos uma diferença ainda maior: **71,2 vs 30,3 tok/s (2,3x)**.

### Ollama vence em TTFT

O backend llama.cpp do Ollama processa o prompt inicial mais rápido (175ms vs 291ms). Para uso interativo com prompts curtos, isso faz o Ollama parecer mais ágil. Para tarefas de geração mais longas, a vantagem de throughput do LM Studio domina o tempo total.

### LM Studio é mais eficiente energeticamente (+82%)

Com 8,2 tok/s por watt vs 4,5, o LM Studio gera quase o dobro de tokens por joule. Isso importa para laptops na bateria e para cargas de trabalho sustentadas em servidores sempre ligados.

### Uso de memória: contexto importa

A grande diferença na memória do processo (21,4 vs 41,6 GB) se deve em parte ao Ollama pré-alocar cache KV para sua janela de contexto máxima. Para uma comparação justa, considere o contexto real usado durante sua carga de trabalho, não o RSS de pico.

## Quando Usar Cada Um

| Caso de Uso | Recomendado | Por quê |
|-------------|-------------|---------|
| **Throughput máximo** | LM Studio (MLX) | +46% de geração mais rápida |
| **Chat interativo (baixa latência)** | Ollama | TTFT menor (175 vs 291 ms) |
| **Bateria / eficiência** | LM Studio | 82% mais tok/s por watt |
| **Docker / compatibilidade de API** | Ollama | Ecossistema mais amplo, API compatível com OpenAI |
| **Memória limitada (Mac 16GB)** | LM Studio | RSS menor, cache KV sob demanda |
| **Servir múltiplos modelos** | Ollama | Gerenciamento de modelos integrado, keep_alive |

## Outros Modelos

A diferença de throughput varia por arquitetura de modelo:

| Modelo | LM Studio (MLX) | Ollama (llama.cpp) | Diferença |
|--------|-----------------|-------------------|-----------|
| Qwen3-Coder-30B (MoE) | 102,2 tok/s | 69,8 tok/s | +46% |
| Qwen3.5-35B-A3B (MoE) | 71,2 tok/s | 30,3 tok/s | +135% |

Modelos MoE mostram as maiores diferenças porque o MLX lida com roteamento esparso de experts mais eficientemente no Metal.

## Execute Seu Próprio Benchmark

```bash
pip install asiai
asiai bench --engines ollama,lmstudio --prompts code --runs 3 --card
```

O asiai compara motores lado a lado com o mesmo modelo, mesmos prompts e mesmo hardware. Os modelos são automaticamente descarregados entre motores para evitar contenção de memória.

[Veja a metodologia completa](methodology.md) · [Veja o leaderboard da comunidade](leaderboard.md) · [Como fazer benchmark de LLMs no Mac](benchmark-llm-mac.md)
