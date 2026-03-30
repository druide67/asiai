---
description: "Benchmark do oMLX no Apple Silicon: cache KV em SSD, batching contínuo, porta 8000 e comparação de performance."
---

# oMLX

oMLX é um servidor de inferência nativo macOS que usa cache KV paginado em SSD para lidar com janelas de contexto maiores do que a memória sozinha permitiria, com batching contínuo para requisições concorrentes na porta 8000. Suporta APIs compatíveis com OpenAI e Anthropic no Apple Silicon.

[oMLX](https://omlx.ai/) é um servidor de inferência LLM nativo macOS com cache KV paginado em SSD e batching contínuo, gerenciado pela barra de menu. Construído com MLX para Apple Silicon.

## Configuração

```bash
brew tap jundot/omlx https://github.com/jundot/omlx
brew install omlx
```

Ou baixe o `.dmg` das [releases do GitHub](https://github.com/jundot/omlx/releases).

## Detalhes

| Propriedade | Valor |
|-------------|-------|
| Porta padrão | 8000 |
| Tipo de API | Compatível com OpenAI + compatível com Anthropic |
| Reporte de VRAM | Não |
| Formato de modelo | MLX (safetensors) |
| Detecção | Endpoint JSON `/admin/info` ou página HTML `/admin` |
| Requisitos | macOS 15+, Apple Silicon (M1+), 16 GB RAM mínimo |

## Notas

- oMLX compartilha a porta 8000 com vllm-mlx. O asiai usa probing do `/admin/info` para distinguir entre eles.
- O cache KV em SSD permite janelas de contexto maiores com menor pressão de memória.
- O batching contínuo melhora o throughput sob requisições concorrentes.
- Suporta LLMs de texto, modelos vision-language, modelos OCR, embeddings e rerankers.
- O dashboard admin em `/admin` fornece métricas do servidor em tempo real.
- Atualização automática in-app quando instalado via `.dmg`.

## Veja também

Compare motores com `asiai bench --engines omlx` --- [saiba como](../benchmark-llm-mac.md)
