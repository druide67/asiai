---
description: Serveur MCP exposant 11 outils pour que les agents IA surveillent les moteurs d'inférence, lancent des benchmarks et obtiennent des recommandations adaptées au matériel.
---

# asiai mcp

Démarrer le serveur MCP (Model Context Protocol), permettant aux agents IA de surveiller et benchmarker votre infrastructure d'inférence.

## Utilisation

```bash
asiai mcp                          # Transport stdio (Claude Code)
asiai mcp --transport sse          # Transport SSE (agents réseau)
asiai mcp --transport sse --port 9000
```

## Options

| Option | Description |
|--------|-------------|
| `--transport` | Protocole de transport : `stdio` (par défaut), `sse`, `streamable-http` |
| `--host` | Adresse d'écoute (par défaut : `127.0.0.1`) |
| `--port` | Port pour le transport SSE/HTTP (par défaut : `8900`) |
| `--register` | Inscription optionnelle au réseau d'agents asiai (anonyme) |

## Outils (11)

| Outil | Description | Lecture seule |
|-------|-------------|---------------|
| `check_inference_health` | Vérification rapide de santé : moteurs up/down, pression mémoire, thermique, GPU | Oui |
| `get_inference_snapshot` | Snapshot complet du système avec toutes les métriques | Oui |
| `list_models` | Lister tous les modèles chargés sur tous les moteurs | Oui |
| `detect_engines` | Re-scanner les moteurs d'inférence | Oui |
| `run_benchmark` | Lancer un benchmark ou une comparaison inter-modèles (limité à 1/min) | Non |
| `get_recommendations` | Recommandations moteur/modèle adaptées au matériel | Oui |
| `diagnose` | Lancer les vérifications de diagnostic (comme `asiai doctor`) | Oui |
| `get_metrics_history` | Interroger l'historique des métriques (1-168 heures) | Oui |
| `get_benchmark_history` | Interroger les résultats de benchmarks passés avec filtres | Oui |
| `compare_engines` | Comparer les performances des moteurs pour un modèle avec verdict ; supporte la comparaison multi-modèles depuis l'historique | Oui |
| `refresh_engines` | Re-détecter les moteurs sans redémarrer le serveur | Oui |

## Ressources (3)

| Ressource | URI | Description |
|-----------|-----|-------------|
| Statut système | `asiai://status` | Santé actuelle du système (mémoire, thermique, GPU) |
| Modèles | `asiai://models` | Tous les modèles chargés sur tous les moteurs |
| Infos système | `asiai://system` | Infos matérielles (puce, RAM, cœurs, OS, uptime) |

## Intégration Claude Code

Ajoutez à votre config MCP Claude Code (`~/.claude/claude_desktop_config.json`) :

```json
{
  "mcpServers": {
    "asiai": {
      "command": "asiai",
      "args": ["mcp"]
    }
  }
}
```

Puis demandez à Claude : *« Vérifie la santé de mon inférence »* ou *« Compare Ollama vs LM Studio pour qwen3.5 »*.

## Cartes de benchmark

L'outil `run_benchmark` supporte la génération de cartes via le paramètre `card`. Quand `card=true`, une carte SVG de benchmark 1200x630 est générée et `card_path` est retourné dans la réponse.

```json
{"tool": "run_benchmark", "arguments": {"model": "qwen3.5", "card": true}}
```

Comparaison inter-modèles (mutuellement exclusif avec `model`, max 8 emplacements) :

```json
{"tool": "run_benchmark", "arguments": {"compare": ["qwen3.5:4b", "deepseek-r1:7b"], "card": true}}
```

Équivalent CLI pour PNG + partage :

```bash
asiai bench --quick --card --share    # Bench rapide + carte + partage (~15s)
```

Voir la page [Carte de benchmark](../benchmark-card.md) pour les détails.

## Inscription d'agent

Rejoignez le réseau d'agents asiai pour accéder aux fonctionnalités communautaires (classement, comparaison, statistiques en percentiles) :

```bash
asiai mcp --register                  # S'inscrire au premier lancement, heartbeat aux suivants
asiai unregister                      # Supprimer les identifiants locaux
```

L'inscription est **optionnelle et anonyme** — seules les infos matérielles (puce, RAM) et les noms de moteurs sont envoyés. Aucune IP, nom d'hôte ou donnée personnelle n'est stockée. Les identifiants sont sauvegardés dans `~/.local/share/asiai/agent.json` (chmod 600).

Lors des appels suivants à `asiai mcp --register`, un heartbeat est envoyé au lieu d'une ré-inscription. Si l'API est inaccessible, le serveur MCP démarre normalement sans inscription.

Vérifiez votre statut d'inscription avec `asiai version`.

## Agents réseau

Pour les agents sur d'autres machines (ex. monitoring d'un Mac Mini headless) :

```bash
asiai mcp --transport sse --host 0.0.0.0 --port 8900
```

Voir le [guide d'intégration agent](../agent.md) pour des instructions détaillées.
