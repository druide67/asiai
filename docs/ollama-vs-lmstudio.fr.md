---
title: "Ollama vs LM Studio : Benchmark Apple Silicon"
description: "Benchmark Ollama vs LM Studio sur Apple Silicon : tok/s, TTFT, puissance, VRAM comparés côte à côte sur M4 Pro avec des mesures réelles."
type: article
date: 2026-03-28
updated: 2026-03-29
dataset:
  name: "Benchmark Ollama vs LM Studio sur Apple Silicon M4 Pro"
  description: "Benchmark face à face comparant Ollama (llama.cpp) et LM Studio (MLX) sur Mac Mini M4 Pro 64 Go avec Qwen3-Coder-30B. Métriques : tok/s, TTFT, puissance GPU, efficacité, VRAM."
  date: "2026-03"
---

# Ollama vs LM Studio : Benchmark Apple Silicon

Quel moteur d'inférence est le plus rapide sur votre Mac ? Nous avons benchmarké Ollama (backend llama.cpp) et LM Studio (backend MLX) face à face sur le même modèle et le même matériel avec asiai 1.4.0 en mars 2026.

## Configuration du test

| | |
|---|---|
| **Matériel** | Mac Mini M4 Pro, 64 Go de mémoire unifiée |
| **Modèle** | Qwen3-Coder-30B (architecture MoE, Q4_K_M / MLX 4-bit) |
| **Version asiai** | 1.4.0 |
| **Méthodologie** | 1 warmup + 1 exécution mesurée par moteur, temperature=0, modèle déchargé entre les moteurs ([méthodologie complète](methodology.md)) |

## Résultats

| Métrique | LM Studio (MLX) | Ollama (llama.cpp) | Différence |
|----------|-----------------|-------------------|------------|
| **Débit** | 102.2 tok/s | 69.8 tok/s | **+46%** |
| **TTFT** | 291 ms | 175 ms | Ollama plus rapide |
| **Puissance GPU** | 12.4 W | 15.4 W | **-20%** |
| **Efficacité** | 8.2 tok/s/W | 4.5 tok/s/W | **+82%** |
| **Mémoire processus** | 21.4 Go (RSS) | 41.6 Go (RSS) | -49% |

!!! note "À propos des chiffres mémoire"
    Ollama pré-alloue le KV cache pour la fenêtre de contexte complète (262K tokens), ce qui gonfle son empreinte mémoire. LM Studio alloue le KV cache à la demande. Le RSS du processus reflète la mémoire totale utilisée par le processus du moteur, pas seulement les poids du modèle.

## Conclusions clés

### LM Studio gagne en débit (+46%)

L'optimisation Metal native de MLX extrait plus de bande passante de la mémoire unifiée d'Apple Silicon. Sur les architectures MoE, l'avantage est significatif. Sur la variante plus grande Qwen3.5-35B-A3B, nous avons mesuré un écart encore plus large : **71.2 vs 30.3 tok/s (2.3x)**.

### Ollama gagne en TTFT

Le backend llama.cpp d'Ollama traite le prompt initial plus rapidement (175ms vs 291ms). Pour un usage interactif avec des prompts courts, cela rend Ollama plus réactif. Pour les tâches de génération longue, l'avantage en débit de LM Studio domine le temps total.

### LM Studio est plus économe en énergie (+82%)

À 8.2 tok/s par watt contre 4.5, LM Studio génère près de deux fois plus de tokens par joule. C'est important pour les portables sur batterie et pour les charges de travail soutenues sur les serveurs toujours allumés.

### Utilisation mémoire : le contexte compte

Le grand écart de mémoire processus (21.4 vs 41.6 Go) est en partie dû à la pré-allocation du KV cache par Ollama pour sa fenêtre de contexte maximale. Pour une comparaison équitable, considérez le contexte réellement utilisé pendant votre charge de travail, pas le RSS maximum.

## Quand utiliser chacun

| Cas d'usage | Recommandé | Pourquoi |
|-------------|-----------|---------|
| **Débit maximum** | LM Studio (MLX) | +46% de génération plus rapide |
| **Chat interactif (faible latence)** | Ollama | TTFT plus bas (175 vs 291 ms) |
| **Autonomie batterie / efficacité** | LM Studio | 82% plus de tok/s par watt |
| **Docker / compatibilité API** | Ollama | Écosystème plus large, API compatible OpenAI |
| **Mémoire limitée (Mac 16 Go)** | LM Studio | RSS plus bas, KV cache à la demande |
| **Service multi-modèles** | Ollama | Gestion de modèles intégrée, keep_alive |

## Autres modèles

L'écart de débit varie selon l'architecture du modèle :

| Modèle | LM Studio (MLX) | Ollama (llama.cpp) | Écart |
|--------|-----------------|-------------------|-------|
| Qwen3-Coder-30B (MoE) | 102.2 tok/s | 69.8 tok/s | +46% |
| Qwen3.5-35B-A3B (MoE) | 71.2 tok/s | 30.3 tok/s | +135% |

Les modèles MoE montrent les plus grandes différences car MLX gère le routage des experts épars plus efficacement sur Metal.

## Lancez votre propre benchmark

```bash
pip install asiai
asiai bench --engines ollama,lmstudio --prompts code --runs 3 --card
```

asiai compare les moteurs côte à côte avec le même modèle, les mêmes prompts et le même matériel. Les modèles sont automatiquement déchargés entre les moteurs pour éviter la contention mémoire.

[Voir la méthodologie complète](methodology.md) · [Voir le classement communautaire](leaderboard.md) · [Comment benchmarker les LLM sur Mac](benchmark-llm-mac.md)
