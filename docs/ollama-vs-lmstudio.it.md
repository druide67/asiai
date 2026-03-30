---
title: "Ollama vs LM Studio: Benchmark su Apple Silicon"
description: "Benchmark Ollama vs LM Studio su Apple Silicon: tok/s, TTFT, potenza, VRAM confrontati fianco a fianco su M4 Pro con misurazioni reali."
type: article
date: 2026-03-28
updated: 2026-03-29
dataset:
  name: "Benchmark Ollama vs LM Studio su Apple Silicon M4 Pro"
  description: "Benchmark diretto tra Ollama (llama.cpp) e LM Studio (MLX) su Mac Mini M4 Pro 64GB con Qwen3-Coder-30B. Metriche: tok/s, TTFT, potenza GPU, efficienza, VRAM."
  date: "2026-03"
---

# Ollama vs LM Studio: Benchmark su Apple Silicon

Quale motore di inferenza è più veloce sul tuo Mac? Abbiamo confrontato Ollama (backend llama.cpp) e LM Studio (backend MLX) testa a testa con lo stesso modello e hardware usando asiai 1.4.0 a marzo 2026.

## Configurazione del test

| | |
|---|---|
| **Hardware** | Mac Mini M4 Pro, 64 GB di memoria unificata |
| **Modello** | Qwen3-Coder-30B (architettura MoE, Q4_K_M / MLX 4-bit) |
| **Versione asiai** | 1.4.0 |
| **Metodologia** | 1 warmup + 1 esecuzione misurata per motore, temperature=0, modello scaricato tra motori ([metodologia completa](methodology.md)) |

## Risultati

| Metrica | LM Studio (MLX) | Ollama (llama.cpp) | Differenza |
|--------|-----------------|-------------------|------------|
| **Throughput** | 102,2 tok/s | 69,8 tok/s | **+46%** |
| **TTFT** | 291 ms | 175 ms | Ollama più veloce |
| **Potenza GPU** | 12,4 W | 15,4 W | **-20%** |
| **Efficienza** | 8,2 tok/s/W | 4,5 tok/s/W | **+82%** |
| **Memoria processo** | 21,4 GB (RSS) | 41,6 GB (RSS) | -49% |

!!! note "Sui numeri di memoria"
    Ollama pre-alloca la cache KV per l'intera finestra di contesto (262K token), il che gonfia l'impronta di memoria. LM Studio alloca la cache KV su richiesta. L'RSS del processo riflette la memoria totale usata dal processo del motore, non solo i pesi del modello.

## Risultati chiave

### LM Studio vince nel throughput (+46%)

L'ottimizzazione nativa Metal di MLX estrae più banda dalla memoria unificata di Apple Silicon. Sulle architetture MoE, il vantaggio è significativo. Sulla variante più grande Qwen3.5-35B-A3B, abbiamo misurato un gap ancora più ampio: **71,2 vs 30,3 tok/s (2,3x)**.

### Ollama vince nel TTFT

Il backend llama.cpp di Ollama elabora il prompt iniziale più velocemente (175ms vs 291ms). Per l'uso interattivo con prompt brevi, questo rende Ollama più reattivo. Per compiti di generazione più lunghi, il vantaggio di throughput di LM Studio domina il tempo totale.

### LM Studio è più efficiente energeticamente (+82%)

Con 8,2 tok/s per watt contro 4,5, LM Studio genera quasi il doppio dei token per joule. Questo conta per i portatili a batteria e per carichi di lavoro sostenuti su server sempre accesi.

### Utilizzo memoria: il contesto conta

Il grande gap nella memoria del processo (21,4 vs 41,6 GB) è in parte dovuto alla pre-allocazione della cache KV di Ollama per la finestra di contesto massima. Per un confronto equo, considera il contesto effettivamente usato durante il tuo carico di lavoro, non l'RSS di picco.

## Quando usare ciascuno

| Caso d'uso | Consigliato | Perché |
|----------|------------|-----|
| **Massimo throughput** | LM Studio (MLX) | +46% generazione più veloce |
| **Chat interattiva (bassa latenza)** | Ollama | TTFT inferiore (175 vs 291 ms) |
| **Autonomia batteria / efficienza** | LM Studio | 82% in più di tok/s per watt |
| **Docker / compatibilità API** | Ollama | Ecosistema più ampio, API compatibile OpenAI |
| **Memoria limitata (Mac 16GB)** | LM Studio | RSS inferiore, cache KV su richiesta |
| **Servire più modelli** | Ollama | Gestione modelli integrata, keep_alive |

## Altri modelli

Il gap di throughput varia per architettura del modello:

| Modello | LM Studio (MLX) | Ollama (llama.cpp) | Gap |
|-------|-----------------|-------------------|-----|
| Qwen3-Coder-30B (MoE) | 102,2 tok/s | 69,8 tok/s | +46% |
| Qwen3.5-35B-A3B (MoE) | 71,2 tok/s | 30,3 tok/s | +135% |

I modelli MoE mostrano le differenze maggiori perché MLX gestisce il routing sparse degli esperti in modo più efficiente su Metal.

## Esegui il tuo benchmark

```bash
pip install asiai
asiai bench --engines ollama,lmstudio --prompts code --runs 3 --card
```

asiai confronta i motori fianco a fianco con lo stesso modello, gli stessi prompt e lo stesso hardware. I modelli vengono automaticamente scaricati tra motori per prevenire contesa di memoria.

[Vedi la metodologia completa](methodology.md) · [Vedi la classifica comunitaria](leaderboard.md) · [Come fare benchmark di LLM su Mac](benchmark-llm-mac.md)
