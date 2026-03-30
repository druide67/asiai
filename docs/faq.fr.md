---
title: "Questions fréquentes"
description: "Questions courantes sur asiai : moteurs supportés, prérequis Apple Silicon, benchmarking LLM sur Mac, besoins en RAM, et plus."
type: faq
faq:
  - q: "Qu'est-ce qu'asiai ?"
    a: "asiai est un outil CLI open-source qui benchmarke et surveille les moteurs d'inférence LLM sur les Mac Apple Silicon. Il supporte 7 moteurs (Ollama, LM Studio, mlx-lm, llama.cpp, oMLX, vllm-mlx, Exo) et mesure les tok/s, TTFT, la consommation électrique et l'utilisation VRAM."
  - q: "Quel est le moteur LLM le plus rapide sur Apple Silicon ?"
    a: "Dans les benchmarks sur M4 Pro 64 Go avec Qwen3-Coder-30B, LM Studio (backend MLX) atteint 102 tok/s contre 70 tok/s pour Ollama — 46% plus rapide en génération de tokens. Cependant, Ollama a une latence time-to-first-token plus basse."
  - q: "Est-ce qu'asiai fonctionne sur les Mac Intel ?"
    a: "Non. asiai nécessite Apple Silicon (M1, M2, M3 ou M4). Il utilise des API spécifiques à macOS pour les métriques GPU, le monitoring de puissance IOReport et la détection matérielle qui ne sont disponibles que sur les puces Apple Silicon."
  - q: "De combien de RAM ai-je besoin pour faire tourner des LLM en local ?"
    a: "Pour un modèle 7B quantifié Q4 : 8 Go minimum. Pour 13B : 16 Go. Pour 30B : 32-64 Go. Les modèles MoE comme Qwen3.5-35B-A3B n'utilisent qu'environ 7 Go de paramètres actifs, ce qui les rend idéaux pour les Mac 16 Go."
  - q: "Ollama ou LM Studio est meilleur pour Mac ?"
    a: "Cela dépend de votre cas d'usage. LM Studio (MLX) est plus rapide en débit et plus économe en énergie. Ollama (llama.cpp) a une latence first-token plus basse et gère mieux les grandes fenêtres de contexte (>32K). Voir la comparaison détaillée sur asiai.dev/ollama-vs-lmstudio."
  - q: "Est-ce qu'asiai nécessite sudo ou un accès root ?"
    a: "Non. Toutes les fonctionnalités, y compris l'observabilité GPU (ioreg) et le monitoring de puissance (IOReport), fonctionnent sans sudo. Le flag optionnel --power pour la validation croisée avec powermetrics est la seule fonctionnalité qui utilise sudo."
  - q: "Comment installer asiai ?"
    a: "Installez via pip (pip install asiai) ou Homebrew (brew tap druide67/tap && brew install asiai). Python 3.11+ requis."
  - q: "Les agents IA peuvent-ils utiliser asiai ?"
    a: "Oui. asiai inclut un serveur MCP avec 11 outils et 3 ressources. Installez avec pip install asiai[mcp] et configurez comme asiai mcp dans votre client MCP (Claude Code, Cursor, etc.)."
  - q: "Quelle est la précision des mesures de puissance ?"
    a: "Les mesures de puissance IOReport ont moins de 1,5% d'écart par rapport à sudo powermetrics, validé sur 20 échantillons sur LM Studio (MLX) et Ollama (llama.cpp)."
  - q: "Puis-je benchmarker plusieurs modèles à la fois ?"
    a: "Oui. Utilisez asiai bench --compare pour lancer des benchmarks inter-modèles. Supporte la syntaxe model@engine pour un contrôle précis, avec jusqu'à 8 emplacements de comparaison."
  - q: "Comment partager mes résultats de benchmark ?"
    a: "Exécutez asiai bench --share pour soumettre anonymement vos résultats au classement communautaire. Ajoutez --card pour générer une image de carte de benchmark partageable 1200x630."
  - q: "Quelles métriques asiai mesure-t-il ?"
    a: "Sept métriques principales : tok/s (vitesse de génération), TTFT (time to first token), puissance (watts GPU+CPU), tok/s/W (efficacité énergétique), utilisation VRAM, stabilité inter-exécutions et état de throttling thermique."
---

# Questions fréquentes

## Général

**Qu'est-ce qu'asiai ?**

asiai est un outil CLI open-source qui benchmarke et surveille les moteurs d'inférence LLM sur les Mac Apple Silicon. Il supporte 7 moteurs (Ollama, LM Studio, mlx-lm, llama.cpp, oMLX, vllm-mlx, Exo) et mesure les tok/s, TTFT, la consommation électrique et l'utilisation VRAM avec zéro dépendance.

**Est-ce qu'asiai fonctionne sur les Mac Intel ou Linux ?**

Non. asiai nécessite Apple Silicon (M1, M2, M3 ou M4). Il utilise des API spécifiques à macOS (`sysctl`, `vm_stat`, `ioreg`, `IOReport`, `launchd`) qui ne sont disponibles que sur les Mac Apple Silicon.

**Est-ce qu'asiai nécessite sudo ou un accès root ?**

Non. Toutes les fonctionnalités, y compris l'observabilité GPU (`ioreg`) et le monitoring de puissance (`IOReport`), fonctionnent sans sudo. Le flag optionnel `--power` pour la validation croisée avec `powermetrics` est la seule fonctionnalité qui utilise sudo.

## Moteurs et performances

**Quel est le moteur LLM le plus rapide sur Apple Silicon ?**

Dans nos benchmarks sur M4 Pro 64 Go avec Qwen3-Coder-30B (Q4_K_M), LM Studio (backend MLX) atteint **102 tok/s** contre **70 tok/s** pour Ollama — 46% plus rapide en génération de tokens. LM Studio est aussi 82% plus économe en énergie (8.23 vs 4.53 tok/s/W). Voir notre [comparaison détaillée](ollama-vs-lmstudio.md).

**Ollama ou LM Studio est meilleur pour Mac ?**

Cela dépend de votre cas d'usage :

- **LM Studio (MLX)** : Idéal pour le débit (génération de code, longues réponses). Plus rapide, plus efficient, moins de VRAM.
- **Ollama (llama.cpp)** : Idéal pour la latence (chatbots, usage interactif). TTFT plus rapide. Meilleur pour les grandes fenêtres de contexte (>32K tokens).

**De combien de RAM ai-je besoin pour faire tourner des LLM en local ?**

| Taille du modèle | Quantification | RAM nécessaire |
|-------------------|---------------|----------------|
| 7B | Q4_K_M | 8 Go minimum |
| 13B | Q4_K_M | 16 Go minimum |
| 30B | Q4_K_M | 32-64 Go |
| 35B MoE (3B actifs) | Q4_K_M | 16 Go (seuls les paramètres actifs sont chargés) |

## Benchmarking

**Comment lancer mon premier benchmark ?**

Trois commandes :

```bash
pip install asiai     # Installer
asiai detect          # Trouver les moteurs
asiai bench           # Lancer le benchmark
```

**Combien de temps dure un benchmark ?**

Un benchmark rapide (`asiai bench --quick`) prend environ 2 minutes. Une comparaison complète inter-moteurs avec plusieurs prompts et 3 exécutions prend 10-15 minutes.

**Quelle est la précision des mesures de puissance ?**

Les mesures de puissance IOReport ont moins de 1,5% d'écart par rapport à `sudo powermetrics`, validé sur 20 échantillons sur LM Studio (MLX) et Ollama (llama.cpp).

**Puis-je comparer mes résultats avec d'autres utilisateurs Mac ?**

Oui. Exécutez `asiai bench --share` pour soumettre anonymement vos résultats au [classement communautaire](leaderboard.md). Utilisez `asiai compare` pour voir comment votre Mac se positionne.

## Intégration avec les agents IA

**Les agents IA peuvent-ils utiliser asiai ?**

Oui. asiai inclut un serveur MCP avec 11 outils et 3 ressources. Installez avec `pip install "asiai[mcp]"` et configurez comme `asiai mcp` dans votre client MCP (Claude Code, Cursor, Windsurf). Voir le [Guide d'intégration agent](agent.md).

**Quels outils MCP sont disponibles ?**

11 outils : `check_inference_health`, `get_inference_snapshot`, `list_models`, `detect_engines`, `run_benchmark`, `get_recommendations`, `diagnose`, `get_metrics_history`, `get_benchmark_history`, `refresh_engines`, `compare_engines`.

3 ressources : `asiai://status`, `asiai://models`, `asiai://system`.
