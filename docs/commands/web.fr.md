---
description: Dashboard de monitoring LLM en temps réel dans votre navigateur. Métriques GPU, santé des moteurs, historique de performance. Aucune configuration requise.
---

# asiai web

Lancer le dashboard web pour le monitoring visuel et le benchmarking.

## Utilisation

```bash
asiai web
asiai web --port 9000
asiai web --host 0.0.0.0
asiai web --no-open
```

## Options

| Option | Par défaut | Description |
|--------|-----------|-------------|
| `--port` | `8899` | Port HTTP d'écoute |
| `--host` | `127.0.0.1` | Adresse d'écoute |
| `--no-open` | | Ne pas ouvrir le navigateur automatiquement |
| `--db` | `~/.local/share/asiai/asiai.db` | Chemin vers la base de données SQLite |

## Prérequis

Le dashboard web nécessite des dépendances supplémentaires :

```bash
pip install asiai[web]
# ou tout installer :
pip install asiai[all]
```

## Pages

### Dashboard (`/`)

Vue d'ensemble du système avec le statut des moteurs, les modèles chargés, l'utilisation mémoire et les derniers résultats de benchmark.

### Benchmark (`/bench`)

Lancez des benchmarks inter-moteurs directement depuis le navigateur :

- Bouton **Quick Bench** — 1 prompt, 1 exécution, ~15 secondes
- Options avancées : moteurs, prompts, exécutions, taille de contexte (4K/16K/32K/64K), puissance
- Progression en direct via SSE
- Tableau de résultats avec mise en avant du gagnant
- Graphiques de débit et TTFT
- **Carte partageable** — générée automatiquement après le benchmark (PNG via API, SVG en secours)
- **Section partage** — copier le lien, télécharger PNG/SVG, partager sur X/Reddit, exporter JSON

### Historique (`/history`)

Visualisez les métriques de benchmark et système dans le temps :

- Graphiques système : charge CPU, mémoire %, utilisation GPU (avec détail renderer/tiler)
- Activité des moteurs : connexions TCP, requêtes en cours, utilisation KV cache %
- Graphiques benchmark : débit (tok/s) et TTFT par moteur
- Métriques processus : CPU % et mémoire RSS des moteurs pendant les benchmarks
- Filtrer par plage temporelle (1h / 24h / 7j / 30j / 90j) ou plage personnalisée
- Tableau de données avec indication de taille de contexte (ex. « code (64K ctx) »)

### Monitor (`/monitor`)

Monitoring système en temps réel avec rafraîchissement toutes les 5 secondes :

- Sparkline de charge CPU
- Jauge mémoire
- État thermique
- Liste des modèles chargés

### Doctor (`/doctor`)

Vérification de santé interactive pour le système, les moteurs et la base de données. Mêmes vérifications que `asiai doctor` avec une interface visuelle.

## Endpoints API

Le dashboard web expose des endpoints API REST pour l'accès programmatique.

### `GET /api/status`

Vérification de santé légère. En cache 10s, répond en < 500ms.

```json
{
  "status": "ok",
  "ts": 1709700000,
  "uptime": 86400,
  "engines": {"ollama": true, "lmstudio": false},
  "memory_pressure": "normal",
  "thermal_level": "nominal"
}
```

Valeurs de statut : `ok` (tous les moteurs accessibles), `degraded` (certains hors ligne), `error` (tous hors ligne).

### `GET /api/snapshot`

Snapshot complet système + moteurs. En cache 5s. Inclut charge CPU, mémoire, état thermique et statut par moteur avec modèles chargés.

### `GET /api/benchmarks`

Résultats de benchmark avec filtres. Retourne les données par exécution incluant tok/s, TTFT, puissance, context_size, engine_version.

| Paramètre | Par défaut | Description |
|-----------|-----------|-------------|
| `hours` | `168` | Plage temporelle en heures (0 = tout) |
| `model` | | Filtrer par nom de modèle |
| `engine` | | Filtrer par nom de moteur |
| `since` / `until` | | Plage de timestamps Unix (remplace hours) |

### `GET /api/engine-history`

Historique de statut des moteurs (accessibilité, connexions TCP, KV cache, tokens prédits).

| Paramètre | Par défaut | Description |
|-----------|-----------|-------------|
| `hours` | `168` | Plage temporelle en heures |
| `engine` | | Filtrer par nom de moteur |

### `GET /api/benchmark-process`

Métriques CPU et mémoire au niveau processus des exécutions de benchmark (rétention 7 jours).

| Paramètre | Par défaut | Description |
|-----------|-----------|-------------|
| `hours` | `168` | Plage temporelle en heures |
| `engine` | | Filtrer par nom de moteur |

### `GET /api/metrics`

Format d'exposition Prometheus. Jauges couvrant les métriques système, moteur, modèle et benchmark.

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'asiai'
    static_configs:
      - targets: ['localhost:8899']
    metrics_path: '/api/metrics'
    scrape_interval: 30s
```

Les métriques incluent :

| Métrique | Type | Description |
|----------|------|-------------|
| `asiai_cpu_load_1m` | gauge | Charge CPU moyenne (1 min) |
| `asiai_memory_used_bytes` | gauge | Mémoire utilisée |
| `asiai_thermal_speed_limit_pct` | gauge | Limite de vitesse CPU % |
| `asiai_engine_reachable{engine}` | gauge | Accessibilité moteur (0/1) |
| `asiai_engine_models_loaded{engine}` | gauge | Nombre de modèles chargés |
| `asiai_engine_tcp_connections{engine}` | gauge | Connexions TCP établies |
| `asiai_engine_requests_processing{engine}` | gauge | Requêtes en cours de traitement |
| `asiai_engine_kv_cache_usage_ratio{engine}` | gauge | Ratio de remplissage KV cache (0-1) |
| `asiai_engine_tokens_predicted_total{engine}` | counter | Total cumulé de tokens prédits |
| `asiai_model_vram_bytes{engine,model}` | gauge | VRAM par modèle |
| `asiai_bench_tok_per_sec{engine,model}` | gauge | Dernier benchmark tok/s |

## Notes

- Le dashboard se lie à `127.0.0.1` par défaut (localhost uniquement)
- Utilisez `--host 0.0.0.0` pour exposer sur le réseau (ex. monitoring à distance)
- Le port `8899` est choisi pour éviter les conflits avec les ports des moteurs d'inférence
