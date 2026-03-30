---
description: "vLLM-MLX no Apple Silicon: API compatível com vLLM no MLX, porta 8000, métricas Prometheus e dados de benchmark."
---

# vllm-mlx

vLLM-MLX traz o framework de serving vLLM para Apple Silicon via MLX, oferecendo batching contínuo e API compatível com OpenAI na porta 8000. Pode atingir 400+ tok/s em modelos otimizados, tornando-o uma das opções mais rápidas para inferência concorrente no Mac.

[vllm-mlx](https://github.com/vllm-project/vllm) traz batching contínuo para Apple Silicon via MLX.

## Configuração

```bash
pip install vllm-mlx
vllm serve mlx-community/gemma-2-9b-it-4bit
```

## Detalhes

| Propriedade | Valor |
|-------------|-------|
| Porta padrão | 8000 |
| Tipo de API | Compatível com OpenAI |
| Reporte de VRAM | Não |
| Formato de modelo | MLX (safetensors) |
| Detecção | Endpoint `/version` ou detecção de processo via `lsof` |

## Notas

- vllm-mlx suporta batching contínuo, tornando-o adequado para lidar com requisições concorrentes.
- Pode atingir 400+ tok/s no Apple Silicon com modelos otimizados.
- Usa a API padrão compatível com OpenAI do vLLM.

## Veja também

Compare motores com `asiai bench --engines vllm-mlx` --- [saiba como](../benchmark-llm-mac.md)
