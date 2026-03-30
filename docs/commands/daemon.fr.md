---
description: "Exécuter asiai en daemon d'arrière-plan sur Mac : monitoring auto-démarré, dashboard web et métriques Prometheus au boot."
---

# asiai daemon

Gérer les services d'arrière-plan via les LaunchAgents macOS launchd.

## Services

| Service | Description | Modèle |
|---------|-------------|--------|
| `monitor` | Collecte les métriques système + inférence à intervalles réguliers | Périodique (`StartInterval`) |
| `web` | Lance le dashboard web comme service persistant | Longue durée (`KeepAlive`) |

## Utilisation

```bash
# Daemon de monitoring (par défaut)
asiai daemon start                     # Démarrer le monitoring (toutes les 60s)
asiai daemon start --interval 30       # Intervalle personnalisé
asiai daemon start --alert-webhook URL # Activer les alertes webhook

# Service dashboard web
asiai daemon start web                 # Démarrer le web sur 127.0.0.1:8899
asiai daemon start web --port 9000     # Port personnalisé
asiai daemon start web --host 0.0.0.0  # Exposer sur le réseau (pas d'auth !)

# Statut (affiche tous les services)
asiai daemon status

# Arrêt
asiai daemon stop                      # Arrêter le monitor
asiai daemon stop web                  # Arrêter le web
asiai daemon stop --all                # Arrêter tous les services

# Logs
asiai daemon logs                      # Logs du monitor
asiai daemon logs web                  # Logs du web
asiai daemon logs web -n 100           # 100 dernières lignes
```

## Fonctionnement

Chaque service installe un plist LaunchAgent launchd séparé dans `~/Library/LaunchAgents/` :

- **Monitor** : exécute `asiai monitor --quiet` à l'intervalle configuré (par défaut : 60s). Les données sont stockées dans SQLite. Si `--alert-webhook` est fourni, les alertes sont envoyées par POST lors des transitions d'état (pression mémoire, thermique, moteur hors ligne).
- **Web** : exécute `asiai web --no-open` comme processus persistant. Redémarre automatiquement en cas de crash (`KeepAlive: true`, `ThrottleInterval: 10s`).

Les deux services démarrent automatiquement à la connexion (`RunAtLoad: true`).

## Sécurité

- Les services s'exécutent au **niveau utilisateur** (pas de root requis)
- Le dashboard web se lie à `127.0.0.1` par défaut (localhost uniquement)
- Un avertissement est affiché lors de l'utilisation de `--host 0.0.0.0` — aucune authentification n'est configurée
- Les logs sont stockés dans `~/.local/share/asiai/`
