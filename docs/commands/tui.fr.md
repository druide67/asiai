---
description: "Interface terminal pour asiai : surveillez les moteurs d'inférence LLM en temps réel avec un dashboard interactif dans votre terminal."
---

# asiai tui

Dashboard terminal interactif avec rafraîchissement automatique.

## Utilisation

```bash
asiai tui
```

## Prérequis

Nécessite l'extra `tui` :

```bash
pip install asiai[tui]
```

Cela installe [Textual](https://textual.textualize.io/) pour l'interface terminal.

## Fonctionnalités

- Métriques système en temps réel (CPU, mémoire, thermique)
- Statut des moteurs et modèles chargés
- Rafraîchissement automatique avec intervalle configurable
