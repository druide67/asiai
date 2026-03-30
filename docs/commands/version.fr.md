---
description: "Vérifier la version d'asiai, l'environnement Python et le statut d'inscription de l'agent en une seule commande."
---

# asiai version

Afficher la version et les informations système.

## Utilisation

```bash
asiai version
asiai --version
```

## Sortie

La sous-commande `version` affiche le contexte système enrichi :

```
asiai 1.0.1
  Apple M4 Pro, 64 GB RAM
  Engines: ollama, lmstudio
  Daemon: monitor, web
```

Le flag `--version` n'affiche que la chaîne de version :

```
asiai 1.0.1
```

## Cas d'usage

- Vérification rapide du système dans les issues et rapports de bugs
- Collecte de contexte pour les agents (puce, RAM, moteurs disponibles)
- Scripting : `VERSION=$(asiai version | head -1)`
