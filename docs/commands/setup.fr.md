---
description: "Configuration rapide d'asiai : configurer les moteurs, tester les connexions et vérifier que votre Mac Apple Silicon est prêt pour le benchmarking LLM."
---

# asiai setup

Assistant de configuration interactif pour les nouveaux utilisateurs. Détecte votre matériel, vérifie les moteurs d'inférence et suggère les prochaines étapes.

## Utilisation

```bash
asiai setup
```

## Ce qu'il fait

1. **Détection matérielle** — identifie votre puce Apple Silicon et la RAM
2. **Scan des moteurs** — vérifie les moteurs d'inférence installés (Ollama, LM Studio, mlx-lm, llama.cpp, oMLX, vllm-mlx, Exo)
3. **Vérification des modèles** — liste les modèles chargés sur tous les moteurs détectés
4. **Statut du daemon** — indique si le daemon de monitoring est en cours d'exécution
5. **Prochaines étapes** — suggère des commandes en fonction de l'état de votre configuration

## Exemple de sortie

```
  Setup Wizard

  Hardware:  Apple M4 Pro, 64 GB RAM

  Engines:
    ✓ ollama (v0.17.7) — 3 models loaded
    ✓ lmstudio (v0.4.5) — 1 model loaded

  Daemon: running (monitor + web)

  Suggested next steps:
    • asiai bench              Run your first benchmark
    • asiai monitor --watch    Watch metrics live
    • asiai web                Open the dashboard
```

## Quand aucun moteur n'est trouvé

Si aucun moteur n'est détecté, setup fournit des conseils d'installation :

```
  Engines:
    No inference engines detected.

  To get started, install an engine:
    brew install ollama && ollama serve
    # or download LM Studio from https://lmstudio.ai
```
