---
description: "Lister tous les modèles LLM chargés sur les moteurs : voir l'utilisation VRAM, la quantification, la longueur de contexte et le format de chaque modèle."
---

# asiai models

Lister les modèles chargés sur tous les moteurs détectés.

## Utilisation

```bash
asiai models
```

## Sortie

```
ollama  v0.17.5  http://localhost:11434
  ● qwen3.5:35b-a3b                             26.0 GB Q4_K_M

lmstudio  v0.4.6  http://localhost:1234
  ● qwen3.5-35b-a3b                              9.2 GB    MLX
```

Affiche la version du moteur, le nom du modèle, l'utilisation VRAM (quand disponible), le format et le niveau de quantification pour chaque moteur.

La VRAM est rapportée nativement par Ollama et LM Studio. Pour les autres moteurs, asiai estime l'utilisation mémoire via `ri_phys_footprint` (l'empreinte physique macOS, identique au Moniteur d'activité). Les valeurs estimées sont étiquetées « (est.) ».
