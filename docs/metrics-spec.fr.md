---
description: "Définitions détaillées de toutes les métriques de benchmark asiai : tok/s, TTFT, puissance watts, efficacité, VRAM, stabilité, état thermique."
---

# Spécification des métriques de benchmark

> **Version** : 0.4.0
> **Statut** : Implémenté
> **Périmètre** : `asiai bench` — tous les moteurs

## Motivation

Les résultats de benchmark doivent être **comparables entre les moteurs**. Chaque métrique a une définition unique que toutes les implémentations de moteur doivent respecter. L'implémentation peut varier (API côté serveur vs mesure côté client), mais la sémantique doit être identique.

## Métriques

### M1. `tok_per_sec` — Vitesse de génération

**Définition** : Tokens produits par seconde du **temps de génération uniquement**, hors traitement du prompt (TTFT).

```
generation_s = total_duration_s - ttft_s
tok_per_sec  = tokens_generated / generation_s    (si generation_s >= 0.01)
             = 0.0                                 (sinon)
```

| Moteur | Source de `generation_s` |
|--------|------------------------|
| Ollama | `eval_duration / 1e9` (API serveur — direct) |
| OpenAI-compat | `elapsed_s - (ttft_ms / 1000)` (côté client) |

**Justification** : Pour les grandes tailles de contexte (ex. 64k tokens), le TTFT peut dominer la durée totale. L'inclure dans tok/s fait paraître les générateurs rapides lents (ex. 3.2 tok/s au lieu de 42 tok/s).

### M2. `ttft_ms` — Time to First Token

**Définition** : Temps entre l'envoi de la requête et la réception du premier token de sortie, en ms.

| Moteur | Source |
|--------|--------|
| Ollama | `prompt_eval_duration / 1e6` (API serveur) |
| OpenAI-compat | `(time.monotonic() au 1er chunk de contenu - t0) * 1000` (client) |

Note : La sémantique diffère légèrement (mesure serveur vs client), mais sur localhost l'écart est de ~1ms — acceptable.

### M3. `total_duration_ms` — Durée totale

**Définition** : Durée totale de la requête en temps réel (traitement du prompt + génération), en ms.

**Invariant** : `total_duration_ms >= ttft_ms` — toujours.

| Moteur | Source |
|--------|--------|
| Ollama | `total_duration / 1e6` (API serveur) |
| OpenAI-compat | `elapsed_s * 1000` (temps réel côté client) |

### M4. `tokens_generated` — Nombre de tokens

**Définition** : Nombre de tokens de sortie produits par le modèle.

**Source (par priorité)** :
1. Compteur serveur : Ollama `eval_count`, OpenAI-compat `usage.completion_tokens`
2. Estimation par longueur de texte : `max(1, len(text) // 4)` (heuristique : ~4 caractères/token)
3. **Jamais** `len(text_parts)` (les chunks SSE != tokens)

### M5. `generation_duration_ms` — Durée de génération

**Définition** : Temps de génération uniquement (hors TTFT), en ms.
Rend la décomposition `total = ttft + generation` explicite et auditable.

| Moteur | Source |
|--------|--------|
| Ollama | `eval_duration / 1e6` (API serveur — direct) |
| OpenAI-compat | `max(0, elapsed_s - ttft_s) * 1000` (calculé) |

### M6. `power_watts` — Puissance GPU

**Définition** : Puissance GPU moyenne pendant l'exécution de **ce moteur spécifique**, en watts.

**Périmètre** : Un `PowerMonitor` par moteur. Démarré avant le premier prompt, arrêté après la dernière exécution. Chaque moteur a sa propre mesure — pas de moyenne sur la session entière.

Source : `sudo powermetrics` (macOS).

### M7. `tok_per_sec_per_watt` — Efficacité énergétique

```
tok_per_sec_per_watt = tok_per_sec / power_watts
```

Utilise le tok/s corrigé (M1) et la puissance par moteur (M6).

### M8. `std_dev_tok_s` — Variance (poolée)

**Définition** : Écart-type intra-prompt poolé — capture le bruit inter-exécutions **sans** mélanger la variance inter-prompts.

```
Pour chaque type de prompt p avec les exécutions [v1, v2, ..., vn] :
    var_p = sum((vi - mean_p)^2) / n    (variance de population)

pooled_variance = mean(var_p pour tous les p avec n >= 2)
std_dev_tok_s   = sqrt(pooled_variance)
```

**Classification de stabilité** (inchangée) :
- CV < 5% → `stable`
- CV < 10% → `variable`
- CV >= 10% → `unstable`

Où CV = `(std_dev_tok_s / avg_tok_s) * 100`.

## Carte d'implémentation

| Métrique | `base.py` | `ollama.py` | `openai_compat.py` | `runner.py` | `reporter.py` |
|----------|-----------|-------------|--------------------|-----------  |----------------|
| M1 tok/s | champ | API serveur | client (hors TTFT) | passthrough | avg |
| M2 ttft_ms | champ | API serveur | client streaming | passthrough | avg |
| M3 total_duration_ms | champ | API serveur | client temps réel | passthrough | avg |
| M4 tokens_generated | champ | API serveur | serveur ou `len//4` | passthrough | avg |
| M5 generation_duration_ms | champ | API serveur | calculé | stocké dans dict | — |
| M6 power_watts | — | — | — | moniteur par moteur | passthrough |
| M7 tok/s/W | — | — | — | calculé | passthrough |
| M8 std_dev | — | — | — | — | intra-prompt poolé |

## Protocole de benchmark

1. **Warmup** : 1 génération non chronométrée par moteur (`"Hello"`, max_tokens=1) pour amorcer les caches.
2. **Exécutions mesurées** : Par défaut 3 exécutions par prompt par moteur (configurable via `--runs`).
3. **Échantillonnage** : `temperature=0` (greedy) sur tous les moteurs pour une sortie déterministe.
4. **Reporting** : Médiane tok/s comme métrique principale (standard SPEC), moyenne +/- stddev en secondaire.
5. **Throttling** : Avertissement émis si `thermal_speed_limit < 100%` pendant une exécution.
6. **Métadonnées** : engine_version, model_format, model_quantization, hw_chip, os_version stockés par résultat pour la reproductibilité.

Voir [benchmark-best-practices.md](benchmark-best-practices.md) pour l'audit complet de la méthodologie.
