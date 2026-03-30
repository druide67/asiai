---
description: "Benchmark do servidor mlx-lm no Mac: ideal para modelos MoE, configuração na porta 8080 e dados de performance no Apple Silicon."
---

# mlx-lm

mlx-lm é o servidor de inferência MLX de referência da Apple, executando modelos nativamente na GPU Metal via porta 8080. É particularmente eficiente para modelos MoE (Mixture of Experts) no Apple Silicon, aproveitando a memória unificada para carregamento zero-copy de modelos.

[mlx-lm](https://github.com/ml-explore/mlx-examples) executa modelos nativamente no Apple MLX, proporcionando utilização eficiente de memória unificada.

## Configuração

```bash
brew install mlx-lm
mlx_lm.server --model mlx-community/gemma-2-9b-it-4bit
```

## Detalhes

| Propriedade | Valor |
|-------------|-------|
| Porta padrão | 8080 |
| Tipo de API | Compatível com OpenAI |
| Reporte de VRAM | Não |
| Formato de modelo | MLX (safetensors) |
| Detecção | Endpoint `/version` ou detecção de processo via `lsof` |

## Notas

- mlx-lm compartilha a porta 8080 com llama.cpp. O asiai usa probing de API e detecção de processo para distinguir entre eles.
- Os modelos usam o formato da comunidade HuggingFace/MLX (ex: `mlx-community/gemma-2-9b-it-4bit`).
- A execução nativa MLX tipicamente proporciona excelente performance no Apple Silicon.

## Veja também

Compare motores com `asiai bench --engines mlxlm` --- [saiba como](../benchmark-llm-mac.md)
