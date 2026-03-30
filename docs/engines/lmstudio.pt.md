---
description: "Benchmark do LM Studio no Apple Silicon: motor MLX mais rápido, configuração na porta 1234, uso de VRAM e como se compara ao Ollama."
---

# LM Studio

LM Studio é o motor de inferência MLX mais rápido no Apple Silicon, servindo modelos na porta 1234 com API compatível com OpenAI. No M4 Pro 64GB, atinge 130 tok/s no Qwen3-Coder-30B (MLX), quase 2x mais rápido que o backend llama.cpp do Ollama para modelos MoE.

[LM Studio](https://lmstudio.ai) fornece uma API compatível com OpenAI com interface gráfica para gerenciamento de modelos.

## Configuração

```bash
brew install --cask lm-studio
```

Inicie o servidor local a partir do app LM Studio, depois carregue um modelo.

## Detalhes

| Propriedade | Valor |
|-------------|-------|
| Porta padrão | 1234 |
| Tipo de API | Compatível com OpenAI |
| Reporte de VRAM | Sim (via CLI `lms ps --json`) |
| Formato de modelo | GGUF, MLX |
| Detecção | Endpoint `/lms/version` ou plist do app bundle |

## Reporte de VRAM

Desde a v0.7.0, o asiai obtém o uso de VRAM do CLI do LM Studio (`~/.lmstudio/bin/lms ps --json`). Isso fornece dados precisos de tamanho de modelo que a API compatível com OpenAI não expõe.

Se o CLI `lms` não estiver instalado ou disponível, o asiai faz fallback gracioso reportando VRAM como 0 (mesmo comportamento de antes da v0.7.0).

## Notas

- O LM Studio suporta formatos de modelo GGUF e MLX.
- A detecção de versão usa o endpoint `/lms/version` da API, com fallback para o plist do app bundle no disco.
- Os nomes de modelos tipicamente usam o formato HuggingFace (ex: `gemma-2-9b-it`).

## Veja também

Veja como o LM Studio se compara: [Benchmark Ollama vs LM Studio](../ollama-vs-lmstudio.md)
