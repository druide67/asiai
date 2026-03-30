---
description: "Elenca tutti i modelli LLM caricati sui motori: vedi utilizzo VRAM, quantizzazione, lunghezza contesto e formato per ogni modello."
---

# asiai models

Elenca i modelli caricati su tutti i motori rilevati.

## Uso

```bash
asiai models
```

## Output

```
ollama  v0.17.5  http://localhost:11434
  ● qwen3.5:35b-a3b                             26.0 GB Q4_K_M

lmstudio  v0.4.6  http://localhost:1234
  ● qwen3.5-35b-a3b                              9.2 GB    MLX
```

Mostra la versione del motore, nome del modello, utilizzo VRAM (quando disponibile), formato e livello di quantizzazione per ogni motore.

La VRAM è riportata nativamente da Ollama e LM Studio. Per gli altri motori, asiai stima l'utilizzo di memoria tramite `ri_phys_footprint` (l'impronta fisica di macOS, come Monitor Attività). I valori stimati sono etichettati "(est.)".
