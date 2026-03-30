---
description: Auto-détection des moteurs d'inférence LLM sur votre Mac. Cascade à 3 niveaux — config, scan de ports, détection de processus.
---

# asiai detect

Auto-détection des moteurs d'inférence via une cascade à 3 niveaux.

## Utilisation

```bash
asiai detect                      # Auto-détection (cascade 3 niveaux)
asiai detect --url http://host:port  # Scanner des URL spécifiques uniquement
```

## Sortie

```
Detected engines:

  ● ollama 0.17.4
    URL: http://localhost:11434

  ● lmstudio 0.4.5
    URL: http://localhost:1234
    Running: 1 model(s)
      - qwen3.5-35b-a3b  MLX

  ● omlx 0.9.2
    URL: http://localhost:8800
```

## Fonctionnement : détection à 3 niveaux

asiai utilise une cascade de trois niveaux de détection, du plus rapide au plus approfondi :

### Niveau 1 : Config (le plus rapide, ~100ms)

Lit `~/.config/asiai/engines.json` — les moteurs découverts lors des exécutions précédentes. Cela attrape les moteurs sur des ports non standard (ex. oMLX sur 8800) sans rescanner.

### Niveau 2 : Scan de ports (~200ms)

Scanne les ports par défaut plus une plage étendue :

| Port | Moteur |
|------|--------|
| 11434 | Ollama |
| 1234 | LM Studio |
| 8080 | mlx-lm ou llama.cpp |
| 8000-8009 | oMLX ou vllm-mlx |
| 52415 | Exo |

### Niveau 3 : Détection de processus (secours)

Utilise `ps` et `lsof` pour trouver les processus moteurs écoutant sur n'importe quel port. Attrape les moteurs sur des ports totalement inattendus.

### Persistance automatique

Tout moteur découvert au Niveau 2 ou 3 est automatiquement sauvegardé dans le fichier de config (Niveau 1) pour une détection plus rapide la prochaine fois. Les entrées auto-découvertes sont supprimées après 7 jours d'inactivité.

Quand plusieurs moteurs partagent un port (ex. mlx-lm et llama.cpp sur 8080), asiai utilise le sondage des endpoints API pour identifier le bon moteur.

## URL explicites

Avec `--url`, seules les URL spécifiées sont scannées. Aucune config n'est lue ni écrite — utile pour des vérifications ponctuelles.

```bash
asiai detect --url http://192.168.0.16:11434,http://localhost:8800
```

## Voir aussi

- [config](config.md) — Gérer la configuration persistante des moteurs
