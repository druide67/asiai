---
description: Donnez à vos agents IA une visibilité en temps réel sur l'inférence LLM. Serveur MCP avec 11 outils pour la surveillance autonome des moteurs.
type: faq
faq:
  - q: "asiai nécessite-t-il root/sudo ?"
    a: "Non. L'observabilité GPU utilise ioreg (sans privilèges). Les métriques de puissance utilisent IOReport qui ne nécessite pas non plus sudo. Le flag optionnel --power pour la validation croisée utilise sudo powermetrics."
  - q: "Quel est le temps de réponse de l'API ?"
    a: "/api/status répond en moins de 500ms (cache de 10s). /api/snapshot prend 1 à 3s car il collecte les données en direct depuis tous les moteurs."
  - q: "Puis-je utiliser asiai sur Linux ?"
    a: "Non. asiai est exclusivement pour macOS Apple Silicon. Il utilise sysctl, vm_stat, ioreg, IOReport et launchd — toutes des API spécifiques à macOS."
  - q: "Comment surveiller plusieurs Macs ?"
    a: "Lancez asiai daemon start web --host 0.0.0.0 sur chaque Mac. Collectez /api/metrics avec Prometheus. Visualisez dans Grafana."
  - q: "Que se passe-t-il si un moteur plante pendant la surveillance ?"
    a: "asiai détecte automatiquement les pannes de moteur. Utilisez asiai doctor pour le diagnostic. Configurez des alertes webhook avec asiai alert add pour des notifications automatiques."
---

# Guide d'intégration pour agents

> **Si vous êtes un agent IA** : utilisez [MCP](#mcp-model-context-protocol) si votre framework le prend en charge, sinon utilisez l'[API REST](#référence-de-lapi-rest). Pour la mise en route, voir [Démarrage rapide](#démarrage-rapide).

## Vue d'ensemble

asiai expose l'infrastructure d'inférence LLM de votre Mac aux agents IA via deux mécanismes :

- **Serveur MCP** — Intégration native d'outils via le [Model Context Protocol](https://modelcontextprotocol.io). Idéal pour les agents IA compatibles MCP (Claude Code, Cursor, Cline et autres clients compatibles MCP).
- **API REST** — Endpoints HTTP/JSON standard. Idéal pour les frameworks d'agents, les orchestrateurs de swarm et tout système capable de HTTP (CrewAI, AutoGen, LangGraph, agents personnalisés).

Les deux donnent accès aux mêmes capacités :

- **Surveiller** la santé du système (CPU, RAM, GPU, thermique, swap)
- **Détecter** quels moteurs d'inférence tournent et quels modèles sont chargés
- **Diagnostiquer** les problèmes de performance grâce à l'observabilité GPU et aux signaux d'activité d'inférence
- **Benchmarker** les modèles de manière programmatique et suivre les régressions
- **Obtenir des recommandations** pour le meilleur modèle/moteur en fonction de votre matériel

Aucune authentification requise pour l'accès local. Toutes les interfaces se lient à `127.0.0.1` par défaut.

### Quelle intégration choisir ?

| Critère | MCP | API REST |
|---------|-----|----------|
| Votre agent supporte MCP | **Utilisez MCP** | — |
| Orchestrateur swarm / multi-agents | — | **Utilisez l'API REST** |
| Polling / surveillance planifiée | — | **Utilisez l'API REST** |
| Intégration Prometheus / Grafana | — | **Utilisez l'API REST** |
| Assistant IA interactif (Claude Code, Cursor) | **Utilisez MCP** | — |
| Agent dans un conteneur Docker | — | **Utilisez l'API REST** |
| Scripts personnalisés ou automatisation | — | **Utilisez l'API REST** |

## Démarrage rapide

### Installer asiai

```bash
# Homebrew (recommandé)
brew tap druide67/tap && brew install asiai

# pip (avec support MCP)
pip install "asiai[mcp]"

# pip (API REST uniquement)
pip install asiai
```

### Option A : Serveur MCP (pour les agents compatibles MCP)

```bash
# Démarrer le serveur MCP (transport stdio — utilisé par Claude Code, Cursor, etc.)
asiai mcp
```

Aucun démarrage manuel du serveur nécessaire — le client MCP lance `asiai mcp` automatiquement. Voir la [configuration MCP](#mcp-model-context-protocol) ci-dessous.

### Option B : API REST (pour les agents basés sur HTTP)

```bash
# Premier plan (développement)
asiai web --no-open

# Daemon en arrière-plan (production)
asiai daemon start web
```

L'API est disponible à `http://127.0.0.1:8899`. Le port est configurable avec `--port` :

```bash
asiai daemon start web --port 8642
```

Pour l'accès distant (par ex. agent IA sur une autre machine ou depuis un conteneur Docker) :

```bash
asiai daemon start web --host 0.0.0.0
```

> **Note :** Si votre agent tourne dans Docker, `127.0.0.1` est inaccessible. Utilisez l'IP réseau de l'hôte (par ex. `192.168.0.16`) ou `host.docker.internal` sur Docker Desktop pour Mac.

### Vérification

```bash
# API REST
curl http://127.0.0.1:8899/api/status

# MCP (lister les outils disponibles)
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | asiai mcp
```

---

## MCP (Model Context Protocol)

asiai implémente un [serveur MCP](https://modelcontextprotocol.io) qui expose la surveillance de l'inférence sous forme d'outils natifs. Tout client compatible MCP peut se connecter et utiliser ces outils directement — pas de configuration HTTP, pas de gestion d'URL.

### Configuration

#### Local (même machine)

Ajoutez à la configuration de votre client MCP (par ex. `~/.claude/settings.json` pour Claude Code) :

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

Si asiai est installé dans un virtualenv :

```json
{
  "mcpServers": {
    "asiai": {
      "command": "/path/to/.venv/bin/asiai",
      "args": ["mcp"]
    }
  }
}
```

#### Distant (autre machine via SSH)

```json
{
  "mcpServers": {
    "asiai": {
      "command": "ssh",
      "args": [
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        "your-mac-host",
        "cd /path/to/asiai && .venv/bin/asiai mcp"
      ]
    }
  }
}
```

#### Transport SSE (réseau)

Pour les environnements qui préfèrent le transport MCP basé sur HTTP :

```bash
asiai mcp --transport sse --host 127.0.0.1 --port 8900
```

### Référence des outils MCP

Tous les outils retournent du JSON. Les outils en lecture seule répondent en < 2 secondes. `run_benchmark` est la seule opération active.

| Outil | Description | Paramètres |
|-------|-------------|------------|
| `check_inference_health` | Bilan de santé rapide — moteurs en ligne/hors ligne, pression mémoire, thermique, utilisation GPU | — |
| `get_inference_snapshot` | Instantané complet de l'état du système (stocké dans SQLite pour l'historique) | — |
| `list_models` | Tous les modèles chargés sur tous les moteurs avec VRAM, quantification, taille de contexte | — |
| `detect_engines` | Détection en 3 couches : config, scan de ports, détection de processus. Trouve automatiquement les moteurs sur des ports non standard. | — |
| `run_benchmark` | Lancer un benchmark sur un modèle ou une comparaison inter-modèles. Limité à 1 par 60 secondes | `model` (optionnel), `runs` (1–10, défaut 3), `compare` (liste de chaînes, optionnel, mutuellement exclusif avec `model`, max 8) |
| `get_recommendations` | Recommandations modèle/moteur adaptées au matériel, basées sur votre puce et RAM | — |
| `diagnose` | Lancer des vérifications de diagnostic (système, moteurs, santé du daemon) | — |
| `get_metrics_history` | Historique des métriques système depuis SQLite | `hours` (1–168, défaut 24) |
| `get_benchmark_history` | Historique des résultats de benchmark | `hours` (1–720, défaut 24), `model` (optionnel), `engine` (optionnel) |
| `compare_engines` | Comparaison classée des moteurs avec verdict pour un modèle donné ; supporte la comparaison multi-modèles depuis l'historique | `model` (requis) |
| `refresh_engines` | Re-détecter les moteurs sans redémarrer le serveur MCP | — |

### Ressources MCP

Points de données statiques, accessibles sans appeler un outil :

| URI | Description |
|-----|-------------|
| `asiai://status` | État de santé actuel (mémoire, thermique, GPU) |
| `asiai://models` | Tous les modèles chargés sur tous les moteurs |
| `asiai://system` | Informations matérielles (puce, RAM, cœurs, OS, uptime) |

### Sécurité MCP

- **Pas de sudo** : Les métriques de puissance sont désactivées en mode MCP (`power=False` forcé)
- **Limitation de débit** : Les benchmarks sont limités à 1 par 60 secondes
- **Bridage des entrées** : `hours` bridé à 1–168, `runs` bridé à 1–10
- **Local par défaut** : Le transport stdio n'a aucune exposition réseau ; SSE se lie à `127.0.0.1`

### Limitations MCP

- **Pas de reconnexion** : Si la connexion SSH est coupée (problème réseau, mise en veille du Mac), le serveur MCP s'arrête et le client doit se reconnecter manuellement. Pour une surveillance non supervisée, l'API REST avec polling est plus résiliente.
- **Client unique** : Le transport stdio dessert un seul client à la fois. Utilisez le transport SSE si plusieurs clients ont besoin d'un accès concurrent.

---

## Référence de l'API REST

L'API d'asiai est **en lecture seule** — elle surveille et rapporte, mais ne contrôle pas les moteurs. Pour charger/décharger des modèles, utilisez les commandes natives du moteur (`ollama pull`, `lms load`, etc.).

Tous les endpoints retournent du JSON avec HTTP 200. Si un moteur est inaccessible, la réponse retourne quand même 200 avec `"running": false` pour ce moteur — l'API elle-même ne tombe pas en erreur.

| Endpoint | Temps de réponse typique | Timeout recommandé |
|----------|--------------------------|---------------------|
| `GET /api/status` | < 500ms (cache 10s) | 2s |
| `GET /api/snapshot` | 1–3s (collecte en direct) | 10s |
| `GET /api/metrics` | < 500ms | 2s |
| `GET /api/history` | < 500ms | 5s |
| `GET /api/engine-history` | < 500ms | 5s |

### `GET /api/status`

Bilan de santé rapide. Cache de 10 secondes. Temps de réponse < 500ms.

**Réponse :**

```json
{
  "hostname": "mac-mini",
  "chip": "Apple M4 Pro",
  "ram_gb": 64.0,
  "cpu_percent": 12.3,
  "memory_pressure": "normal",
  "gpu_utilization_percent": 45.2,
  "engines": {
    "ollama": {
      "running": true,
      "models_loaded": 2,
      "port": 11434
    },
    "lmstudio": {
      "running": true,
      "models_loaded": 1,
      "port": 1234
    }
  },
  "asiai_version": "1.0.1",
  "uptime_seconds": 86400
}
```

### `GET /api/snapshot`

État complet du système. Inclut tout ce qui est dans `/api/status` plus les informations détaillées sur les modèles, les métriques GPU et les données thermiques.

**Réponse :**

```json
{
  "system": {
    "hostname": "mac-mini",
    "chip": "Apple M4 Pro",
    "cores_p": 12,
    "cores_e": 4,
    "gpu_cores": 20,
    "ram_total_gb": 64.0,
    "ram_used_gb": 41.2,
    "ram_percent": 64.4,
    "swap_used_gb": 0.0,
    "memory_pressure": "normal",
    "cpu_percent": 12.3,
    "thermal_state": "nominal",
    "gpu_utilization_percent": 45.2,
    "gpu_renderer_percent": 38.1,
    "gpu_tiler_percent": 12.4,
    "gpu_memory_allocated_bytes": 8589934592
  },
  "engines": [
    {
      "name": "ollama",
      "running": true,
      "port": 11434,
      "models": [
        {
          "name": "qwen3.5:latest",
          "size_params": "35B",
          "size_vram_bytes": 21474836480,
          "quantization": "Q4_K_M",
          "context_length": 32768
        }
      ]
    }
  ],
  "timestamp": "2026-03-09T14:30:00Z"
}
```

### `GET /api/metrics`

Métriques compatibles Prometheus. Collectez avec Prometheus, Datadog ou tout outil compatible.

**Réponse (text/plain) :**

```
# HELP asiai_cpu_percent CPU usage percentage
# TYPE asiai_cpu_percent gauge
asiai_cpu_percent 12.3

# HELP asiai_ram_used_gb RAM used in GB
# TYPE asiai_ram_used_gb gauge
asiai_ram_used_gb 41.2

# HELP asiai_gpu_utilization_percent GPU utilization percentage
# TYPE asiai_gpu_utilization_percent gauge
asiai_gpu_utilization_percent 45.2

# HELP asiai_engine_up Engine availability (1=up, 0=down)
# TYPE asiai_engine_up gauge
asiai_engine_up{engine="ollama"} 1
asiai_engine_up{engine="lmstudio"} 1

# HELP asiai_models_loaded Number of models loaded per engine
# TYPE asiai_models_loaded gauge
asiai_models_loaded{engine="ollama"} 2
```

### `GET /api/history?hours=N`

Historique des métriques système depuis SQLite. Par défaut : `hours=24`. Maximum : `hours=2160` (90 jours).

**Réponse :**

```json
{
  "points": [
    {
      "timestamp": "2026-03-09T14:00:00Z",
      "cpu_percent": 15.2,
      "ram_used_gb": 40.1,
      "ram_percent": 62.7,
      "swap_used_gb": 0.0,
      "memory_pressure": "normal",
      "thermal_state": "nominal",
      "gpu_utilization_percent": 42.0,
      "gpu_renderer_percent": 35.0,
      "gpu_tiler_percent": 10.0,
      "gpu_memory_allocated_bytes": 8589934592
    }
  ],
  "count": 144,
  "hours": 24
}
```

### `GET /api/engine-history?engine=X&hours=N`

Historique d'activité par moteur. Utile pour détecter les schémas d'inférence.

**Paramètres :**

| Paramètre | Requis | Défaut | Description |
|-----------|--------|--------|-------------|
| `engine`  | Oui    | —      | Nom du moteur (ollama, lmstudio, etc.) |
| `hours`   | Non    | 24     | Plage temporelle |

**Réponse :**

```json
{
  "engine": "ollama",
  "points": [
    {
      "timestamp": "2026-03-09T14:00:00Z",
      "running": true,
      "tcp_connections": 3,
      "requests_processing": 1,
      "kv_cache_usage_percent": 45.2
    }
  ],
  "count": 144,
  "hours": 24
}
```

## Interprétation des métriques

### Seuils de santé système

| Métrique | Normal | Attention | Critique |
|----------|--------|-----------|----------|
| `memory_pressure` | `normal` | `warn` | `critical` |
| `ram_percent` | < 75% | 75–90% | > 90% |
| `swap_used_gb` | 0 | 0.1–2.0 | > 2.0 |
| `thermal_state` | `nominal` | `fair` | `serious` / `critical` |
| `cpu_percent` | < 80% | 80–95% | > 95% |

### Seuils GPU

| Métrique | Au repos | Inférence active | Surchargé |
|----------|----------|-------------------|-----------|
| `gpu_utilization_percent` | 0–5% | 20–80% | > 90% maintenu |
| `gpu_renderer_percent` | 0–5% | 15–70% | > 85% maintenu |
| `gpu_memory_allocated_bytes` | < 1 Go | 2–48 Go | > 90% de la RAM |

> **Important :** `gpu_utilization_percent = 0` signifie que le GPU est au repos, pas en panne. Une valeur de `-1.0` signifie que la métrique est indisponible (par ex. matériel non supporté ou échec de collecte) — ne l'interprétez pas comme « GPU mort ».

### Performance d'inférence

| Métrique | Excellent | Bon | Dégradé |
|----------|-----------|-----|---------|
| `tok/s` (modèle 7B) | > 80 | 40–80 | < 40 |
| `tok/s` (modèle 35B) | > 40 | 20–40 | < 20 |
| `tok/s` (modèle 70B) | > 15 | 8–15 | < 8 |
| `TTFT` | < 100ms | 100–500ms | > 500ms |

## Arbres de décision diagnostiques

### Génération lente (tok/s faible)

``` mermaid
graph TD
    A["tok/s below expected?"] --> B["Check memory_pressure"]
    A --> C["Check thermal_state"]
    A --> D["Check gpu_utilization_percent"]
    A --> E["Check swap_used_gb"]

    B -->|critical| B1["Models swapping to disk.<br/>Unload models or add RAM."]
    B -->|normal| B2["Continue"]

    C -->|"serious / critical"| C1["Thermal throttling.<br/>Cool down, check airflow."]
    C -->|nominal| C2["Continue"]

    D -->|"< 10%"| D1["GPU not being used.<br/>Check engine config (num_gpu layers)."]
    D -->|"> 90%"| D2["GPU saturated.<br/>Reduce concurrent requests."]
    D -->|"20-80%"| D3["Normal. Check model<br/>quantization and context size."]

    E -->|"> 0"| E1["Model too large for RAM.<br/>Use smaller quantization."]
    E -->|"0"| E2["Check engine version,<br/>try different engine."]
```

### Moteur ne répond pas

``` mermaid
graph TD
    A["engine.running == false?"] --> B["Check process: lsof -i :port"]
    A --> C["Check memory_pressure"]
    A --> D["Try: asiai doctor"]

    B -->|No process| B1["Engine crashed. Restart it."]
    B -->|Process exists| B2["Engine hung."]

    C -->|critical| C1["OOM killed.<br/>Unload other models first."]
    C -->|normal| C2["Check engine logs."]

    D --> D1["Comprehensive diagnostics"]
```

### Pression mémoire élevée / Débordement VRAM

``` mermaid
graph TD
    A["memory_pressure == warn/critical?"] --> B["Check swap_used_gb"]
    A --> C["Check models loaded"]
    A --> D["Check gpu_memory_allocated_bytes"]

    B -->|"> 2 GB"| B1["VRAM overflow.<br/>Latency 5-50x worse (disk swap).<br/>Unload models or use Q3_K_S."]
    B -->|"< 2 GB"| B2["Manageable.<br/>Monitor closely."]

    C -->|"Multiple large models"| C1["Unload unused models.<br/>ollama rm / lms unload"]
    C -->|"Single model > 80% RAM"| C2["Use smaller quantization."]

    D --> D1["If > 80% of RAM,<br/>next model load triggers swap."]
```

## Signaux d'activité d'inférence

asiai détecte l'inférence active via plusieurs signaux :

### Utilisation GPU

```
GET /api/snapshot → system.gpu_utilization_percent
```

- **< 5%** : Aucune inférence en cours
- **20–80%** : Inférence active (plage normale pour la mémoire unifiée Apple Silicon)
- **> 90%** : Inférence intense ou requêtes simultanées multiples

### Connexions TCP

```
GET /api/engine-history?engine=ollama&hours=1
```

Chaque requête d'inférence active maintient une connexion TCP. Un pic de `tcp_connections` indique une génération active.

### Métriques spécifiques au moteur

Pour les moteurs qui exposent `/metrics` (llama.cpp, vllm-mlx) :

- `requests_processing > 0` : Inférence active
- `kv_cache_usage_percent > 0` : Le modèle a un contexte actif

### Schéma de corrélation

La détection d'inférence la plus fiable combine plusieurs signaux :

```python
snapshot = get_snapshot()
gpu_active = snapshot["system"]["gpu_utilization_percent"] > 15
engine_busy = any(
    e.get("tcp_connections", 0) > 0
    for e in snapshot.get("engine_status", [])
)
inference_running = gpu_active and engine_busy
```

## Exemples de code

### Bilan de santé (Python, bibliothèque standard uniquement)

```python
import json
import urllib.request

ASIAI_URL = "http://127.0.0.1:8899"  # Docker : utiliser l'IP de l'hôte ou host.docker.internal

def check_health():
    """Bilan de santé rapide. Retourne un dict avec l'état."""
    req = urllib.request.Request(f"{ASIAI_URL}/api/status")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())

def is_healthy(status):
    """Interpréter l'état de santé."""
    issues = []
    if status.get("memory_pressure") != "normal":
        issues.append(f"memory_pressure: {status['memory_pressure']}")
    gpu = status.get("gpu_utilization_percent", 0)
    if gpu > 90:
        issues.append(f"gpu_utilization: {gpu}%")
    engines = status.get("engines", {})
    for name, info in engines.items():
        if not info.get("running"):
            issues.append(f"engine_down: {name}")
    return {"healthy": len(issues) == 0, "issues": issues}

# Utilisation
status = check_health()
health = is_healthy(status)
if not health["healthy"]:
    print(f"Problèmes détectés : {health['issues']}")
```

### État complet du système

```python
def get_full_state():
    """Obtenir l'instantané complet du système."""
    req = urllib.request.Request(f"{ASIAI_URL}/api/snapshot")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

def get_history(hours=24):
    """Obtenir l'historique des métriques."""
    req = urllib.request.Request(f"{ASIAI_URL}/api/history?hours={hours}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

# Détecter une tendance de performance
history = get_history(hours=6)
points = history["points"]
if len(points) >= 2:
    recent_gpu = points[-1].get("gpu_utilization_percent", 0)
    earlier_gpu = points[0].get("gpu_utilization_percent", 0)
    if recent_gpu > earlier_gpu * 1.5:
        print("L'utilisation GPU est en hausse significative")
```

## Cartes de benchmark (images partageables)

Générez une carte de benchmark partageable en ligne de commande :

```bash
asiai bench --card                    # SVG enregistré localement (zéro dépendance)
asiai bench --card --share            # SVG + PNG via l'API communautaire
asiai bench --quick --card --share    # Benchmark rapide + carte + partage (~15s)
```

Une **carte au thème sombre de 1200x630** avec le modèle, la puce, un graphique à barres de comparaison des moteurs, la mise en évidence du gagnant et des puces de métriques. Optimisée pour Reddit, X, Discord et les READMEs GitHub.

Les cartes sont enregistrées dans `~/.local/share/asiai/cards/` en SVG. Ajoutez `--share` pour obtenir un téléchargement PNG et une URL partageable — le PNG est nécessaire pour publier sur Reddit, X et Discord.

### Via MCP

L'outil MCP `run_benchmark` prend en charge la génération de cartes avec le paramètre `card` :

```json
{"tool": "run_benchmark", "arguments": {"model": "qwen3.5", "card": true}}
```

La réponse inclut `card_path` — le chemin absolu vers le fichier SVG sur le système de fichiers du serveur MCP.

## Alertes webhook (notifications push)

Au lieu du polling, configurez asiai pour envoyer des notifications lors des changements d'état :

```bash
# Ajouter un webhook (Slack, Discord ou toute URL)
asiai alert add https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Les alertes se déclenchent sur :
# - Un moteur tombe / revient en ligne
# - Transitions de pression mémoire (normal → warn → critical)
# - Throttling thermique détecté
```

Les alertes se déclenchent uniquement lors des **transitions** (pas à chaque vérification) avec un cooldown de 5 minutes pour éviter le flooding. C'est idéal pour les orchestrateurs de swarm qui doivent réagir aux changements d'infrastructure sans polling continu.

Pour lister ou supprimer des alertes : `asiai alert list`, `asiai alert remove <id>`.

## Identifiez votre agent

Nous **recommandons** d'inclure un en-tête `User-Agent` identifiant votre agent dans les requêtes API REST :

```
User-Agent: asiai-agent/<framework>/<version>
```

Exemples :

- `User-Agent: asiai-agent/openclaw/1.2.0`
- `User-Agent: asiai-agent/crewai/0.5`
- `User-Agent: asiai-agent/custom-orchestrator/1.0`

Ce n'est **pas obligatoire** — les requêtes sans en-tête User-Agent fonctionnent parfaitement. Mais cela aide pour :

- **Le débogage** — distinguer les requêtes d'agents des accès navigateur humains dans les logs
- **L'analytique par agent** — voir quels agents utilisent l'API, à quelle fréquence et quels endpoints
- **Les environnements multi-agents** — quand plusieurs agents partagent la même instance asiai, identifier qui est qui

Pour les clients MCP, l'identification est automatique (le protocole MCP inclut les métadonnées du client).

---

## Enregistrer votre agent (optionnel)

L'enregistrement est **entièrement optionnel** — asiai fonctionne pleinement sans lui. Pas de phoning home, pas de télémétrie par défaut.

Si vous choisissez de vous enregistrer, vous rejoignez le réseau d'agents asiai : un appel API, pas d'email, pas de données personnelles — juste les informations de votre matériel.

```bash
curl -X POST https://api.asiai.dev/api/v1/agent-register \
  -H "Content-Type: application/json" \
  -d '{
    "chip": "Apple M4 Pro",
    "ram_gb": 64,
    "engines": ["ollama", "lmstudio"],
    "framework": "my-agent",
    "asiai_version": "1.0.1"
  }'
```

**Réponse :**

```json
{
  "status": "registered",
  "agent_id": "a1b2c3d4e5f6",
  "agent_token": "secret_...",
  "total_agents": 42
}
```

Stockez `agent_id` et `agent_token` de manière sécurisée dans `~/.local/share/asiai/agent.json`. Vous en aurez besoin pour les appels à l'API communautaire et les soumissions de benchmarks.

### Ce que l'enregistrement débloque

| Fonctionnalité | Sans agent_id | Avec agent_id |
|----------------|---------------|---------------|
| bench/monitor/web local | Oui | Oui |
| `/api/status`, `/api/snapshot` | Oui | Oui |
| Benchmarks `--share` | Non | **Oui** |
| `asiai compare` (communauté) | Non | **Oui** |
| `asiai recommend --community` | Non | **Oui** |
| Statistiques de percentiles | Non | **Oui** |
| Annuaire d'agents (trouver des pairs sur la même puce) | Non | **Oui** |
| Alertes de performance (un nouveau moteur bat le vôtre) | Non | **Bientôt** |

### Heartbeat

Maintenez votre enregistrement actif avec des heartbeats périodiques :

```bash
curl -X POST https://api.asiai.dev/api/v1/agent-heartbeat \
  -H "Content-Type: application/json" \
  -H "X-Agent-Id: a1b2c3d4e5f6" \
  -H "X-Agent-Token: secret_..." \
  -d '{
    "engines": ["ollama", "lmstudio"],
    "version": "1.0.1",
    "models_loaded": 3,
    "uptime_hours": 72
  }'
```

### Confidentialité

- **Aucune adresse IP stockée** — votre IP est utilisée uniquement pour la limitation de débit et jamais conservée dans le registre d'agents
- **Aucune donnée personnelle** — uniquement les informations matérielles (puce, RAM), les noms de moteurs et le nom du framework
- **Opt-in uniquement** — asiai ne contacte jamais de serveur sauf si vous vous enregistrez explicitement
- **Sécurité du token** — votre `agent_token` est haché (SHA-256) avant stockage ; le texte en clair n'est retourné qu'une seule fois lors de l'enregistrement
- **Données de limitation de débit** — les hachages d'IP (SHA-256 avec sel quotidien) dans la table de limitation de débit sont automatiquement purgés après 30 jours

## FAQ

**Q : asiai nécessite-t-il root/sudo ?**
R : Non. L'observabilité GPU utilise `ioreg` (sans privilèges). Les métriques de puissance (flag `--power` dans les benchmarks) nécessitent `sudo powermetrics`, mais c'est optionnel.

**Q : Quel est le temps de réponse de l'API ?**
R : `/api/status` répond en < 500ms (cache de 10s). `/api/snapshot` prend 1–3s (collecte les données en direct depuis tous les moteurs).

**Q : Puis-je utiliser asiai sur Linux ?**
R : Non. asiai est exclusivement pour macOS Apple Silicon. Il utilise `sysctl`, `vm_stat`, `ioreg` et `launchd` — toutes des API spécifiques à macOS.

**Q : Comment surveiller plusieurs Macs ?**
R : Lancez `asiai daemon start web --host 0.0.0.0` sur chaque Mac. Collectez `/api/metrics` avec Prometheus. Visualisez dans Grafana.

**Q : Que se passe-t-il si un moteur plante ?**
R : asiai détecte automatiquement les pannes de moteur. Utilisez `asiai doctor` pour le diagnostic. Configurez des alertes webhook avec `asiai alert add` pour des notifications automatiques.
