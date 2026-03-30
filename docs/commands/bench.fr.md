---
description: Lancez des benchmarks LLM côte à côte sur Apple Silicon. Comparez les moteurs, mesurez tok/s, TTFT, efficacité énergétique. Partagez vos résultats.
---

# asiai bench

Benchmark inter-moteurs avec des prompts standardisés.

## Utilisation

```bash
asiai bench [options]
```

## Options

| Option | Description |
|--------|-------------|
| `-m, --model MODEL` | Modèle à benchmarker (par défaut : auto-détection) |
| `-e, --engines LIST` | Filtrer les moteurs (ex. `ollama,lmstudio,mlxlm`) |
| `-p, --prompts LIST` | Types de prompts : `code`, `tool_call`, `reasoning`, `long_gen` |
| `-r, --runs N` | Exécutions par prompt (par défaut : 3, pour médiane + stddev) |
| `--power` | Validation croisée de la puissance avec sudo powermetrics (IOReport toujours actif) |
| `--context-size SIZE` | Prompt de remplissage de contexte : `4k`, `16k`, `32k`, `64k` |
| `--export FILE` | Exporter les résultats au format JSON |
| `-H, --history PERIOD` | Afficher les benchmarks passés (ex. `7d`, `24h`) |
| `-Q, --quick` | Benchmark rapide : 1 prompt (code), 1 exécution (~15 secondes) |
| `--compare MODEL [MODEL...]` | Comparaison inter-modèles (2-8 modèles, mutuellement exclusif avec `-m`) |
| `--card` | Générer une carte de benchmark partageable (SVG local, PNG avec `--share`) |
| `--share` | Partager les résultats dans la base de données communautaire |

## Exemple

```bash
asiai bench -m qwen3.5 --runs 3 --power
```

```
  Mac Mini M4 Pro — Apple M4 Pro  RAM: 64.0 GB (42% used)  Pressure: normal

Benchmark: qwen3.5

  Engine       tok/s (±stddev)    Tokens   Duration     TTFT       VRAM    Thermal
  ────────── ───────────────── ───────── ────────── ──────── ────────── ──────────
  lmstudio    72.6 ± 0.0 (stable)   435    6.20s    0.28s        —    nominal
  ollama      30.4 ± 0.1 (stable)   448   15.28s    0.25s   26.0 GB   nominal

  Winner: lmstudio (2.4x faster)
  Power: lmstudio 13.2W (5.52 tok/s/W) — ollama 16.0W (1.89 tok/s/W)
```

## Prompts

Quatre prompts standardisés testent différents schémas de génération :

| Nom | Tokens | Teste |
|-----|--------|-------|
| `code` | 512 | Génération de code structuré (BST en Python) |
| `tool_call` | 256 | Appel de fonctions JSON / suivi d'instructions |
| `reasoning` | 384 | Problème de mathématiques en plusieurs étapes |
| `long_gen` | 1024 | Débit soutenu (script bash) |

Utilisez `--context-size` pour tester avec des prompts de remplissage à grand contexte.

## Correspondance des modèles inter-moteurs

Le runner résout automatiquement les noms de modèles entre les moteurs — `gemma2:9b` (Ollama) et `gemma-2-9b` (LM Studio) sont reconnus comme le même modèle.

## Export JSON

Exportez les résultats pour le partage ou l'analyse :

```bash
asiai bench -m qwen3.5 --export bench.json
```

Le JSON inclut les métadonnées de la machine, les statistiques par moteur (médiane, CI 95%, P50/P90/P99), les données brutes par exécution et une version de schéma pour la compatibilité future.

## Détection de régression

Après chaque benchmark, asiai compare les résultats avec l'historique des 7 derniers jours et avertit en cas de régressions de performance (ex. après une mise à jour de moteur ou un upgrade macOS).

## Benchmark rapide

Lancez un benchmark rapide avec un seul prompt et une exécution (~15 secondes) :

```bash
asiai bench --quick
asiai bench -Q -m qwen3.5
```

Idéal pour les démos, GIFs et vérifications rapides. Le prompt `code` est utilisé par défaut. Vous pouvez le remplacer avec `--prompts` si nécessaire.

## Comparaison inter-modèles

Comparez plusieurs modèles en une seule session avec `--compare` :

```bash
# Expansion automatique sur tous les moteurs disponibles
asiai bench --compare qwen3.5:4b deepseek-r1:7b

# Filtrer sur un moteur spécifique
asiai bench --compare qwen3.5:4b deepseek-r1:7b -e ollama

# Associer chaque modèle à un moteur avec @
asiai bench --compare qwen3.5:4b@lmstudio deepseek-r1:7b@ollama
```

La notation `@` sépare au **dernier** `@` de la chaîne, donc les noms de modèles contenant `@` sont gérés correctement.

### Règles

- `--compare` et `--model` sont **mutuellement exclusifs** — utilisez l'un ou l'autre.
- Accepte 2 à 8 emplacements de modèles.
- Sans `@`, chaque modèle est étendu à chaque moteur où il est disponible.

### Types de session

Le type de session est détecté automatiquement en fonction de la liste d'emplacements :

| Type | Condition | Exemple |
|------|-----------|---------|
| **engine** | Même modèle, moteurs différents | `--compare qwen3.5:4b@lmstudio qwen3.5:4b@ollama` |
| **model** | Modèles différents, même moteur | `--compare qwen3.5:4b deepseek-r1:7b -e ollama` |
| **matrix** | Modèles et moteurs mixtes | `--compare qwen3.5:4b@lmstudio deepseek-r1:7b@ollama` |

### Combinaison avec d'autres flags

`--compare` fonctionne avec tous les flags de sortie et d'exécution :

```bash
asiai bench --compare qwen3.5:4b deepseek-r1:7b --quick
asiai bench --compare qwen3.5:4b deepseek-r1:7b --card --share
asiai bench --compare qwen3.5:4b deepseek-r1:7b --runs 5 --power
```

## Carte de benchmark

Générez une carte de benchmark partageable :

```bash
asiai bench --card                    # SVG sauvegardé localement
asiai bench --card --share            # SVG + PNG (via l'API communautaire)
asiai bench --quick --card --share    # Bench rapide + carte + partage
```

La carte est une image de 1200x630 au thème sombre avec :
- Nom du modèle et badge de puce matérielle
- Bannière de spécifications : quantification, RAM, cœurs GPU, taille de contexte
- Graphique en barres style terminal des tok/s par moteur
- Mise en avant du gagnant avec delta (ex. « 2.4x »)
- Pastilles de métriques : tok/s, TTFT, stabilité, VRAM, puissance (W + tok/s/W), version du moteur
- Branding asiai

Le SVG est sauvegardé dans `~/.local/share/asiai/cards/`. Avec `--share`, un PNG est aussi téléchargé depuis l'API.

## Partage communautaire

Partagez vos résultats anonymement :

```bash
asiai bench --share
```

Consultez le classement communautaire avec `asiai leaderboard`.

## Détection de dérive thermique

Avec 3+ exécutions, asiai détecte la dégradation monotone des tok/s entre les exécutions consécutives. Si les tok/s diminuent régulièrement (>5%), un avertissement est émis indiquant un possible throttling thermique cumulatif.
