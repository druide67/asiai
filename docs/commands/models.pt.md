---
description: "Liste todos os modelos LLM carregados em todos os motores: veja uso de VRAM, quantização, comprimento de contexto e formato de cada modelo."
---

# asiai models

Lista modelos carregados em todos os motores detectados.

## Uso

```bash
asiai models
```

## Saída

```
ollama  v0.17.5  http://localhost:11434
  ● qwen3.5:35b-a3b                             26.0 GB Q4_K_M

lmstudio  v0.4.6  http://localhost:1234
  ● qwen3.5-35b-a3b                              9.2 GB    MLX
```

Mostra versão do motor, nome do modelo, uso de VRAM (quando disponível), formato e nível de quantização para cada motor.

A VRAM é reportada nativamente pelo Ollama e LM Studio. Para outros motores, o asiai estima o uso de memória via `ri_phys_footprint` (o footprint físico do macOS, igual ao Monitor de Atividade). Valores estimados são rotulados "(est.)".
