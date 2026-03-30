---
title: "Comment benchmarker les LLM sur Mac"
description: "Comment benchmarker l'inférence LLM sur Mac : guide étape par étape pour mesurer tok/s, TTFT, puissance et VRAM sur Apple Silicon avec plusieurs moteurs."
type: howto
date: 2026-03-28
updated: 2026-03-29
duration: PT5M
steps:
  - name: "Installer asiai"
    text: "Installez asiai via pip (pip install asiai) ou Homebrew (brew tap druide67/tap && brew install asiai)."
  - name: "Détecter vos moteurs"
    text: "Exécutez 'asiai detect' pour trouver automatiquement les moteurs d'inférence en cours (Ollama, LM Studio, llama.cpp, mlx-lm, oMLX, vLLM-MLX, Exo) sur votre Mac."
  - name: "Lancer un benchmark"
    text: "Exécutez 'asiai bench' pour détecter automatiquement le meilleur modèle et lancer une comparaison inter-moteurs mesurant tok/s, TTFT, puissance et VRAM."
---

# Comment benchmarker les LLM sur Mac

Vous faites tourner un LLM local sur votre Mac ? Voici comment mesurer les performances réelles — pas des impressions, pas du « ça a l'air rapide », mais de vrais tok/s, TTFT, consommation électrique et utilisation mémoire.

## Pourquoi benchmarker ?

Le même modèle tourne à des vitesses très différentes selon le moteur d'inférence. Sur Apple Silicon, les moteurs basés MLX (LM Studio, mlx-lm, oMLX) peuvent être **2x plus rapides** que les moteurs basés llama.cpp (Ollama) pour le même modèle. Sans mesure, vous laissez de la performance sur la table.

## Démarrage rapide (2 minutes)

### 1. Installer asiai

```bash
pip install asiai
```

Ou via Homebrew :

```bash
brew tap druide67/tap
brew install asiai
```

### 2. Détecter vos moteurs

```bash
asiai detect
```

asiai trouve automatiquement les moteurs en cours d'exécution (Ollama, LM Studio, llama.cpp, mlx-lm, oMLX, vLLM-MLX, Exo) sur votre Mac.

### 3. Lancer un benchmark

```bash
asiai bench
```

C'est tout. asiai détecte automatiquement le meilleur modèle parmi vos moteurs et lance une comparaison inter-moteurs.

## Ce qui est mesuré

| Métrique | Signification |
|----------|--------------|
| **tok/s** | Tokens générés par seconde (génération uniquement, hors traitement du prompt) |
| **TTFT** | Time to First Token — latence avant le début de la génération |
| **Puissance** | Watts GPU + CPU pendant l'inférence (via IOReport, sans sudo) |
| **tok/s/W** | Efficacité énergétique — tokens par seconde par watt |
| **VRAM** | Mémoire utilisée par le modèle (API native ou estimée via `ri_phys_footprint`) |
| **Stabilité** | Variance inter-exécutions : stable (<5% CV), variable (<10%), instable (>10%) |
| **Thermique** | Si votre Mac a été throttlé pendant le benchmark |

## Exemple de sortie

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

*Exemple de sortie d'un vrai benchmark sur M4 Pro 64 Go. Vos chiffres varieront selon le matériel et le modèle. [Voir plus de résultats →](ollama-vs-lmstudio.md)*

## Options avancées

### Comparer des moteurs spécifiques

```bash
asiai bench --engines ollama,lmstudio,omlx
```

### Plusieurs prompts et exécutions

```bash
asiai bench --prompts code,reasoning,tool_call --runs 3
```

### Benchmark à grand contexte

```bash
asiai bench --context-size 64K
```

### Générer une carte partageable

```bash
asiai bench --card --share
```

Crée une image de carte de benchmark et partage les résultats avec le [classement communautaire](leaderboard.md).

## Conseils Apple Silicon

### La mémoire compte

Sur un Mac 16 Go, limitez-vous aux modèles de moins de 14 Go (chargés). Les modèles MoE (Qwen3.5-35B-A3B, 3B actifs) sont idéaux — ils offrent une qualité de classe 35B pour une utilisation mémoire de classe 7B.

### Le choix du moteur compte plus qu'on ne le pense

Les moteurs MLX sont significativement plus rapides que llama.cpp sur Apple Silicon pour la plupart des modèles. [Voir notre comparaison Ollama vs LM Studio](ollama-vs-lmstudio.md) pour des chiffres réels.

### Throttling thermique

Le MacBook Air (sans ventilateur) throttle après 5-10 minutes d'inférence soutenue. Le Mac Mini/Studio/Pro gère les charges soutenues sans throttling. asiai détecte et signale le throttling thermique automatiquement.

## Comparez-vous à la communauté

Voyez comment votre Mac se positionne par rapport aux autres machines Apple Silicon :

```bash
asiai compare
```

Ou visitez le [classement en ligne](leaderboard.md).

## FAQ

**Q : Quel est le moteur d'inférence LLM le plus rapide sur Apple Silicon ?**
R : Dans nos benchmarks sur M4 Pro 64 Go, LM Studio (backend MLX) est le plus rapide en génération de tokens — 46% plus rapide qu'Ollama (llama.cpp). Cependant, Ollama a un TTFT (time to first token) plus bas. Voir notre [comparaison détaillée](ollama-vs-lmstudio.md).

**Q : De combien de RAM ai-je besoin pour faire tourner un modèle 30B sur Mac ?**
R : Un modèle 30B quantifié Q4_K_M utilise 24-32 Go de mémoire unifiée selon le moteur. Il faut au moins 32 Go de RAM, idéalement 64 Go pour éviter la pression mémoire. Les modèles MoE comme Qwen3.5-35B-A3B n'utilisent que ~7 Go de paramètres actifs.

**Q : Est-ce que asiai fonctionne sur les Mac Intel ?**
R : Non. asiai nécessite Apple Silicon (M1/M2/M3/M4). Il utilise des API spécifiques à macOS pour les métriques GPU, le monitoring de puissance et la détection matérielle qui ne sont disponibles que sur Apple Silicon.

**Q : Ollama ou LM Studio est plus rapide sur M4 ?**
R : LM Studio est plus rapide en débit (102 tok/s vs 70 tok/s sur Qwen3-Coder-30B). Ollama est plus rapide pour la latence du premier token (0.18s vs 0.29s) et pour les grandes fenêtres de contexte (>32K tokens) où le prefill llama.cpp est jusqu'à 3x plus rapide.

**Q : Combien de temps dure un benchmark ?**
R : Un benchmark rapide prend environ 2 minutes. Une comparaison complète inter-moteurs avec plusieurs prompts et exécutions prend 10-15 minutes. Utilisez `asiai bench --quick` pour un test rapide en une seule exécution.

**Q : Puis-je comparer mes résultats avec d'autres utilisateurs Mac ?**
R : Oui. Exécutez `asiai bench --share` pour soumettre anonymement vos résultats au [classement communautaire](leaderboard.md). Utilisez `asiai compare` pour voir comment votre Mac se compare aux autres machines Apple Silicon.

## Pour aller plus loin

- [Méthodologie de benchmark](methodology.md) — comment asiai assure des mesures fiables
- [Bonnes pratiques de benchmark](benchmark-best-practices.md) — conseils pour des résultats précis
- [Comparaison des moteurs](ollama-vs-lmstudio.md) — Ollama vs LM Studio face à face
