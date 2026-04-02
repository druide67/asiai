---
description: Comment asiai mesure les tok/s, TTFT et la puissance. Warmup, méthodologie statistique et pourquoi les résultats sont reproductibles.
---

# Méthodologie de benchmark

asiai suit les standards de benchmarking établis ([MLPerf](https://mlcommons.org/benchmarks/inference-server/), [SPEC CPU 2017](https://www.spec.org/cpu2017/), [NVIDIA GenAI-Perf](https://docs.nvidia.com/deeplearning/nemo/user-guide/docs/en/stable/benchmarking/genai_perf.html)) pour produire des résultats fiables, reproductibles et comparables.

## Protocole

1. **Vérification pré-vol** : Refuser de démarrer si la pression mémoire est critique ou si le système est fortement throttlé (<80%)
2. **Warmup** : 1 génération non chronométrée par moteur pour amorcer les compilateurs JIT et les caches
3. **Exécutions mesurées** : Par défaut 3 exécutions par prompt par moteur (configurable via `--runs`)
4. **Échantillonnage** : `temperature=0` (greedy) pour une sortie déterministe
5. **Déchargement du modèle** : Après le benchmark de chaque moteur, le modèle est déchargé pour libérer la mémoire unifiée avant le prochain moteur. Cela empêche l'accumulation mémoire et le swapping lors de la comparaison de plusieurs moteurs sur de grands modèles
6. **Refroidissement adaptatif** : Après le déchargement, asiai attend que la pression mémoire macOS revienne à « normal » (max 30s), puis ajoute un minimum de 5s de refroidissement thermique
7. **Contrôles de cohérence** : Les résultats avec tok/s ≤ 0 sont rejetés. Un TTFT > 60s ou tok/s > 500 déclenche des avertissements (swapping probable ou erreurs de mesure)
8. **Reporting** : Médiane tok/s comme métrique principale (standard SPEC), moyenne ± stddev en secondaire
9. **Throttling** : Avertissement émis si `thermal_speed_limit < 100%` pendant une exécution. La dérive thermique (diminution monotone des tok/s entre les exécutions, baisse ≥ 5%) est détectée et signalée
10. **Métadonnées** : Version du moteur, format du modèle, quantification, puce matérielle, version macOS stockés par résultat

## Métriques

### tok/s — Vitesse de génération

Tokens par seconde du **temps de génération uniquement**, hors traitement du prompt (TTFT).

**Ollama** (API native, `/api/generate`) :
```
tok_per_sec = eval_count / (eval_duration_ns / 1e9)
```
Source : timing GPU interne rapporté par Ollama. Pas de surcharge réseau. C'est la mesure la plus précise.

**Moteurs compatibles OpenAI** (LM Studio, llama.cpp, mlx-lm, vllm-mlx) :
```
generation_s = wall_clock_s - ttft_s
tok_per_sec  = completion_tokens / generation_s
```
Source : horloge murale côté client via streaming SSE. Inclut la surcharge HTTP par chunk (~1% plus lent que le timing côté serveur, validé par validation croisée).

**Comptage de tokens** : depuis `usage.completion_tokens` dans la réponse du serveur. Si le serveur ne rapporte pas ce champ, asiai revient à `len(text) // 4` et enregistre un avertissement. Ce repli peut être décalé d'environ 25%.

**Validation croisée** (avril 2026, Qwen3.5-35B NVFP4, M4 Pro 64GB) :

| Méthode | tok/s | Écart vs référence |
|---------|-------|--------------------|
| Ollama native (GPU interne) | 66.6 | référence |
| OpenAI streaming (client) | 66.1 | -0.8% |

Pour les grandes tailles de contexte (ex. 64k tokens), le TTFT peut dominer la durée totale. L'exclure du tok/s empêche les générateurs rapides de paraître lents.

### TTFT — Time to First Token

Temps entre l'envoi de la requête et la réception du premier token de sortie, en millisecondes.

Depuis la v1.6.0, asiai mesure **deux valeurs TTFT** pour Ollama, et une seule pour tous les autres moteurs :

**Ollama** (double mesure) :

- **TTFT côté serveur** (`ttft_ms`) : extrait de `prompt_eval_duration` dans la réponse Ollama. C'est le temps pur de traitement GPU du prompt, sans aucune surcharge réseau — la mesure la plus précise possible. Rapporté comme `ttft_source: server`.
- **TTFT côté client** (`ttft_client_ms`) : mesuré à l'arrivée du premier chunk SSE de contenu. Inclut la configuration HTTP, la transmission de la requête et le traitement serveur. C'est la même méthode utilisée pour tous les autres moteurs.

**Moteurs compatibles OpenAI** (LM Studio, llama.cpp, mlx-lm, vllm-mlx) :

- **TTFT côté client** (`ttft_client_ms`) : mesuré au premier chunk SSE de contenu. C'est la seule mesure disponible car ces moteurs n'exposent pas le timing interne de traitement du prompt. `ttft_ms` et `ttft_client_ms` contiennent la même valeur.

**Métrique comparable** : `ttft_client_ms` est la métrique **comparable entre moteurs** — elle utilise la même méthode de mesure quel que soit le moteur. Utilisez-la pour comparer le TTFT entre différents moteurs. Le `ttft_ms` côté serveur d'Ollama est plus précis pour le temps absolu de traitement du prompt, mais n'est pas directement comparable avec les autres moteurs.

**Validation croisée** (avril 2026, Qwen3.5-35B NVFP4, M4 Pro 64GB) :

| Méthode | TTFT | Écart |
|---------|------|-------|
| Ollama côté serveur (`ttft_ms`) | 27 ms | référence |
| Ollama côté client (`ttft_client_ms`) | 51 ms | +24 ms |

L'écart de 24ms représente la surcharge HTTP sur localhost. Cette surcharge est constante et prévisible, mais suffisamment significative pour compter lors de la comparaison entre moteurs.

### Puissance — Watts GPU

Puissance GPU moyenne pendant l'exécution, mesurée via le framework Apple IOReport Energy Model (sans sudo requis). Une mesure par moteur — pas de moyenne sur la session entière.

### tok/s/W — Efficacité énergétique

```
tok_per_sec_per_watt = tok_per_sec / power_watts
```

### Variance — Stddev poolée

Écart-type intra-prompt poolé qui capture le bruit inter-exécutions **sans** mélanger la variance inter-prompts. Utilise la correction de Bessel (dénominateur N-1) pour une variance d'échantillon non biaisée.

Classification de stabilité :

- CV < 5% → `stable`
- CV < 10% → `variable`
- CV >= 10% → `unstable`

Où CV = `(std_dev / mean) * 100`.

### VRAM — Utilisation mémoire

**Primaire** : API native du moteur (Ollama `/api/ps`, LM Studio `/v1/models`).
**Repli** : `ri_phys_footprint` via ctypes (identique au Moniteur d'activité). Marqué « (est.) » dans l'interface.

## Sécurité de l'environnement

asiai effectue des vérifications pré-benchmark :

1. **Pression mémoire** : refuse de démarrer si critique
2. **Throttling thermique** : avertit si la limite de vitesse < 80%
3. **Processus dupliqués** : avertit si plusieurs instances du même moteur sont en cours (ex. deux processus `ollama serve` sur le même port)
4. **Type de runner du moteur** : pour Ollama, détecte si le runner `--mlx-engine` ou `--ollama-engine` est actif

Ces vérifications préviennent les erreurs de mesure causées par la contention de ressources ou le routage incorrect.

## Conformité

| Pratique | Statut |
|----------|--------|
| Vérification pré-vol (pression mémoire + thermique) | Implémenté |
| Détection de processus dupliqués | Implémenté (v1.5.0) |
| Détection du type de runner Ollama (MLX vs llama.cpp) | Implémenté (v1.5.0) |
| TTFT séparé du tok/s | Implémenté |
| Étiquetage de la source TTFT (server vs client) | Implémenté (v1.5.0) |
| Double mesure TTFT (server + client) | Implémenté (v1.6.0) |
| Échantillonnage déterministe (temperature=0) | Implémenté |
| Comptage de tokens via l'API serveur (pas les chunks SSE) | Implémenté (avertissement en repli) |
| Monitoring de puissance par moteur (IOReport, sans sudo) | Implémenté |
| 1 génération de warmup par moteur | Implémenté |
| 3 exécutions par défaut (minimum SPEC) | Implémenté |
| Médiane comme métrique principale (standard SPEC) | Implémenté |
| Stddev intra-prompt poolée (Bessel N-1) | Implémenté (corrigé v1.5.0) |
| Déchargement du modèle entre les moteurs | Implémenté |
| Refroidissement adaptatif (sensible à la pression mémoire) | Implémenté |
| Contrôles de cohérence (tok/s, bornes TTFT) | Implémenté |
| Détection du throttling thermique + avertissement | Implémenté |
| Détection de la dérive thermique (diminution monotone) | Implémenté |
| Version du moteur + type de runner stockés par résultat | Implémenté (v1.5.0) |
| VRAM universelle via ri_phys_footprint | Implémenté |
| Détection de régression historique | Implémenté |
| Script de validation croisée (3 méthodes comparées) | Disponible (scripts/cross-validate-bench.py) |

## Considérations Apple Silicon

### Mémoire unifiée

Apple Silicon partage la mémoire entre CPU et GPU. asiai exécute les moteurs **séquentiellement** et **décharge les modèles entre les moteurs** pour éviter la contention mémoire et le swapping. La VRAM est rapportée nativement par Ollama et LM Studio ; pour les autres moteurs, asiai estime l'utilisation mémoire via `ri_phys_footprint` (la métrique d'empreinte physique macOS, identique au Moniteur d'activité). Les valeurs estimées sont étiquetées « (est.) » dans l'interface.

### Throttling thermique

- **MacBook Air** (sans ventilateur) : throttling sévère sous charge soutenue
- **MacBook Pro** (ventilateur) : throttling léger
- **Mac Mini/Studio/Pro** : refroidissement actif, throttling minimal

asiai enregistre `thermal_speed_limit` par résultat et avertit si un throttling est détecté.

### KV Cache

Les grandes tailles de contexte (32k+) peuvent causer de l'instabilité sur les moteurs qui pré-allouent le KV cache. Réglez la longueur de contexte du moteur pour correspondre à la taille réelle du test pour des résultats équitables.

## Mesure de puissance

asiai mesure la consommation GPU, CPU, ANE et DRAM via le framework Apple IOReport Energy Model — **sans sudo requis**. La puissance est mesurée automatiquement dans chaque benchmark et chaque snapshot de monitoring.

IOReport lit les mêmes compteurs d'énergie matériels que `sudo powermetrics`, mais via une API en espace utilisateur (`libIOReport.dylib` via ctypes). Cela élimine le besoin de configuration sudo sans mot de passe.

### Validation

Nous avons validé IOReport par rapport à `sudo powermetrics` sous charge d'inférence LLM sur M4 Pro 64 Go, avec 10 échantillons appariés par moteur à intervalles de 2 secondes :

| Moteur | Moy. IOReport | Moy. powermetrics | Écart moyen | Écart max |
|--------|---------------|-------------------|-------------|-----------|
| LM Studio (MLX) | 12.6 W | 12.6 W | 0.9% | 2.1% |
| Ollama (llama.cpp) | 15.6 W | 15.4 W | 1.3% | 4.1% |

Les deux moteurs confirment un écart moyen <1,5% avec 10/10 échantillons appariés. La puissance ANE était de 0.000W sur les 20 échantillons, confirmant qu'aucun moteur LLM n'utilise actuellement le Neural Engine.

Le flag `--power` active une validation croisée supplémentaire en exécutant simultanément IOReport et `sudo powermetrics`, stockant les deux mesures pour comparaison.

### Efficacité énergétique

L'efficacité énergétique (tok/s par watt) est calculée comme `tok_per_sec / gpu_watts` pour chaque résultat de benchmark. Cette métrique permet de comparer le coût d'inférence entre moteurs et matériels.

## Métadonnées

Chaque résultat de benchmark stocke : engine, engine_version, model, model_format, model_quantization, hw_chip, os_version, thermal_level, thermal_speed_limit, power_watts, power_source, metrics_version. Cela permet une comparaison de régression équitable et des benchmarks inter-machines.
