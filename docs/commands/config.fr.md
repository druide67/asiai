---
description: "Comment configurer asiai : gérer les URL des moteurs, les ports et les paramètres persistants pour votre configuration de benchmark LLM sur Mac."
---

# asiai config

Gérer la configuration persistante des moteurs. Les moteurs découverts par `asiai detect` sont automatiquement sauvegardés dans `~/.config/asiai/engines.json` pour une détection ultérieure plus rapide.

## Utilisation

```bash
asiai config show              # Afficher les moteurs connus
asiai config add <engine> <url> [--label NAME]  # Ajouter un moteur manuellement
asiai config remove <url>      # Supprimer un moteur
asiai config reset             # Effacer toute la configuration
```

## Sous-commandes

### show

Affiche tous les moteurs connus avec leur URL, version, source (auto/manual) et dernière date de détection.

```
$ asiai config show
Known engines (3):
  ollama v0.17.7 at http://localhost:11434  (auto)  last seen 2m ago
  lmstudio v0.4.6 at http://localhost:1234  (auto)  last seen 2m ago
  omlx v0.9.2 at http://localhost:8800 [mac-mini]  (manual)  last seen 5m ago
```

### add

Enregistrer manuellement un moteur sur un port non standard. Les moteurs manuels ne sont jamais supprimés automatiquement.

```bash
asiai config add omlx http://localhost:8800 --label mac-mini
asiai config add ollama http://192.168.0.16:11434 --label mini
```

### remove

Supprimer une entrée de moteur par URL.

```bash
asiai config remove http://localhost:8800
```

### reset

Supprimer l'intégralité du fichier de configuration. Le prochain `asiai detect` redécouvrira les moteurs de zéro.

## Fonctionnement

Le fichier de configuration stocke les moteurs découverts lors de la détection :

- **Entrées auto** (`source: auto`) : créées automatiquement quand `asiai detect` trouve un nouveau moteur. Supprimées après 7 jours d'inactivité.
- **Entrées manuelles** (`source: manual`) : créées via `asiai config add`. Jamais supprimées automatiquement.

La cascade de détection à 3 niveaux dans `asiai detect` utilise cette configuration comme Niveau 1 (le plus rapide), suivi du scan de ports (Niveau 2) et de la détection de processus (Niveau 3). Voir [detect](detect.md) pour les détails.

## Emplacement du fichier de configuration

```
~/.config/asiai/engines.json
```
