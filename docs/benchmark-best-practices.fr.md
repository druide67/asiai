---
description: "Comment obtenir des résultats de benchmark LLM fiables sur Mac : gestion thermique, applications en arrière-plan, nombre d'exécutions et conseils de reproductibilité."
---

# Bonnes pratiques de benchmark

> **Version** : 0.3.2
> **Statut** : Document évolutif — mis à jour avec l'évolution de la méthodologie
> **Références** : MLPerf Inference, SPEC CPU 2017, NVIDIA GenAI-Perf

## Vue d'ensemble

`asiai bench` suit les standards de benchmarking établis pour produire des résultats **fiables, reproductibles et comparables** entre les moteurs d'inférence sur Apple Silicon. Ce document recense les bonnes pratiques implémentées, prévues ou intentionnellement exclues.

## Résumé de conformité

| Catégorie | Pratique | Statut | Depuis |
|-----------|----------|--------|--------|
| **Métriques** | TTFT séparé du tok/s | Implémenté | v0.3.1 |
| | Échantillonnage déterministe (temperature=0) | Implémenté | v0.3.2 |
| | Comptage de tokens via l'API serveur (pas les chunks SSE) | Implémenté | v0.3.1 |
| | Monitoring de puissance par moteur | Implémenté | v0.3.1 |
| | Champ explicite generation_duration_ms | Implémenté | v0.3.1 |
| **Warmup** | 1 génération de warmup par moteur (non chronométrée) | Implémenté | v0.3.2 |
| **Exécutions** | 3 exécutions par défaut (minimum SPEC) | Implémenté | v0.3.2 |
| | Médiane comme métrique principale (standard SPEC) | Implémenté | v0.3.2 |
| | Moyenne + stddev en secondaire | Implémenté | v0.3.0 |
| **Variance** | Stddev intra-prompt poolée | Implémenté | v0.3.1 |
| | Classification de stabilité basée sur le CV | Implémenté | v0.3.0 |
| **Environnement** | Exécution séquentielle des moteurs (isolation mémoire) | Implémenté | v0.1 |
| | Détection du throttling thermique + avertissement | Implémenté | v0.3.2 |
| | Niveau thermique + speed_limit enregistrés | Implémenté | v0.1 |
| **Reproductibilité** | Version du moteur stockée par benchmark | Implémenté | v0.3.2 |
| | Format du modèle + quantification stockés | Implémenté | v0.3.2 |
| | Puce matérielle + version macOS stockées | Implémenté | v0.3.2 |
| | Code de benchmark open-source | Implémenté | v0.1 |
| **Régression** | Comparaison avec la baseline historique (SQLite) | Implémenté | v0.3.0 |
| | Comparaison par (moteur, modèle, type_prompt) | Implémenté | v0.3.1 |
| | Filtrage par metrics_version | Implémenté | v0.3.1 |
| **Prompts** | 4 types de prompts diversifiés + remplissage de contexte | Implémenté | v0.1 |
| | max_tokens fixe par prompt | Implémenté | v0.1 |

## Améliorations prévues

### P1 — Rigueur statistique

| Pratique | Description | Standard |
|----------|-------------|----------|
| **Intervalles de confiance à 95%** | CI = moyenne +/- 2*SE. Plus informatif que +/- stddev. | Académique |
| **Percentiles (P50/P90/P99)** | Pour le TTFT en particulier — la latence de queue compte. | NVIDIA GenAI-Perf |
| **Détection des valeurs aberrantes (IQR)** | Signaler les exécutions hors de [Q1 - 1.5*IQR, Q3 + 1.5*IQR]. | Standard statistique |
| **Détection de tendance** | Détecter la dégradation monotone des performances entre les exécutions (dérive thermique). | Académique |

### P2 — Reproductibilité

| Pratique | Description | Standard |
|----------|-------------|----------|
| **Refroidissement entre moteurs** | Pause de 3-5s entre les moteurs pour stabiliser la température. | Benchmark GPU |
| **Vérification du ratio de tokens** | Avertir si tokens_generated < 90% de max_tokens. | MLPerf |
| **Format d'export** | `asiai bench --export` JSON pour les soumissions communautaires. | Soumissions MLPerf |

### P3 — Avancé

| Pratique | Description | Standard |
|----------|-------------|----------|
| **Option `ignore_eos`** | Forcer la génération jusqu'à max_tokens pour les benchmarks de débit. | NVIDIA |
| **Test de requêtes concurrentes** | Tester le débit en batch (pertinent pour vllm-mlx). | NVIDIA |
| **Audit des processus en arrière-plan** | Avertir si des processus lourds tournent pendant le benchmark. | SPEC |

## Déviations intentionnelles

| Pratique | Raison de la déviation |
|----------|----------------------|
| **Durée minimale MLPerf de 600s** | Conçu pour les GPU de datacenter. L'inférence locale sur Apple Silicon avec 3 exécutions + 4 prompts prend déjà ~2-5 minutes. Suffisant pour des résultats stables. |
| **2 charges de warmup non chronométrées SPEC** | Nous utilisons 1 génération de warmup (pas 2 charges complètes). Un seul warmup suffit pour les moteurs d'inférence locaux où le warmup JIT est minimal. |
| **Stddev population vs échantillon** | Nous utilisons la stddev de population (diviseur N) au lieu de la stddev d'échantillon (diviseur N-1). Avec un petit N (3-5 exécutions), la différence est minimale et la population est plus conservative. |
| **Contrôle de la mise à l'échelle de fréquence** | Apple Silicon n'expose pas de contrôles de gouverneur CPU. Nous enregistrons thermal_speed_limit à la place pour détecter le throttling. |

## Considérations spécifiques à Apple Silicon

### Architecture mémoire unifiée

Apple Silicon partage la mémoire entre CPU et GPU. Deux implications clés :

1. **Ne jamais benchmarker deux moteurs simultanément** — ils se disputent le même pool mémoire.
   `asiai bench` exécute les moteurs séquentiellement par conception.
2. **Rapport VRAM** — Ollama et LM Studio rapportent `size_vram` nativement. Pour les autres moteurs
   (llama.cpp, mlx-lm, oMLX, vLLM-MLX, Exo), asiai utilise `ri_phys_footprint` via libproc comme
   estimation de secours. C'est ce qu'affiche le Moniteur d'activité et cela inclut les allocations Metal/GPU.
   Les valeurs estimées sont étiquetées « (est.) » dans l'interface.

### Throttling thermique

- **MacBook Air** (sans ventilateur) : throttling sévère sous charge soutenue. Les résultats se dégradent après 5-10 min.
- **MacBook Pro** (ventilateur) : throttling léger, généralement géré par la montée en vitesse du ventilateur.
- **Mac Mini/Studio/Pro** : refroidissement actif, throttling minimal.

`asiai bench` enregistre `thermal_speed_limit` par résultat et avertit si un throttling est détecté
(speed_limit < 100%) pendant une exécution.

### KV Cache et longueur de contexte

Les grandes tailles de contexte (32k+) peuvent causer une instabilité de performance sur les moteurs qui pré-allouent
le KV cache au chargement du modèle. Exemple : LM Studio utilise par défaut `loaded_context_length: 262144`
(256k), ce qui alloue ~15-25 Go de KV cache pour un modèle 35B, saturant potentiellement
64 Go de mémoire unifiée.

**Recommandations** :
- Pour benchmarker de grands contextes, réglez la longueur de contexte du moteur pour correspondre à la taille réelle du test
  (ex. `lms load model --context-length 65536` pour les tests 64k).
- Comparez les moteurs avec des paramètres de longueur de contexte équivalents pour des résultats équitables.

## Métadonnées stockées par benchmark

Chaque résultat de benchmark dans SQLite inclut :

| Champ | Exemple | Objectif |
|-------|---------|----------|
| `engine` | "ollama" | Identification du moteur |
| `engine_version` | "0.17.4" | Détecter les changements de performance entre les mises à jour |
| `model` | "qwen3.5:35b-a3b" | Identification du modèle |
| `model_format` | "gguf" | Différencier les variantes de format |
| `model_quantization` | "Q4_K_M" | Différencier les niveaux de quantification |
| `hw_chip` | "Apple M4 Pro" | Identification du matériel |
| `os_version` | "15.3" | Suivi de la version macOS |
| `thermal_level` | "nominal" | Condition environnementale |
| `thermal_speed_limit` | 100 | Détection du throttling |
| `metrics_version` | 2 | Version de la formule (empêche la régression inter-versions) |

Ces métadonnées permettent :
- **Comparaison de régression équitable** : ne comparer que les résultats avec des métadonnées identiques
- **Benchmarks inter-machines** : identifier les différences matérielles
- **Partage de données communautaire** : résultats auto-descriptifs (prévu pour v1.x)
