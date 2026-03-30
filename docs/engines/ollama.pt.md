---
description: "Quão rápido é o Ollama no Apple Silicon? Configuração de benchmark, porta padrão (11434), dicas de performance e comparação com outros motores."
---

# Ollama

Ollama é o motor de inferência LLM mais popular para Mac, usando backend llama.cpp com modelos GGUF na porta 11434. Em nossos benchmarks no M4 Pro 64GB, atinge 70 tok/s no Qwen3-Coder-30B mas é 46% mais lento que o LM Studio (MLX) em throughput.

[Ollama](https://ollama.com) é o runner de LLM local mais popular. O asiai usa sua API nativa.

## Configuração

```bash
brew install ollama
ollama serve
ollama pull gemma2:9b
```

## Detalhes

| Propriedade | Valor |
|-------------|-------|
| Porta padrão | 11434 |
| Tipo de API | Nativa (não-OpenAI) |
| Reporte de VRAM | Sim |
| Formato de modelo | GGUF |
| Medição de tempo de carregamento | Sim (via cold start `/api/generate`) |

## Notas

- O Ollama reporta uso de VRAM por modelo, que o asiai exibe na saída de benchmark e monitoramento.
- Os nomes de modelos usam o formato `name:tag` (ex: `gemma2:9b`, `qwen3.5:35b-a3b`).
- O asiai envia `temperature: 0` para resultados determinísticos de benchmark.

## Veja também

Veja como o Ollama se compara: [Benchmark Ollama vs LM Studio](../ollama-vs-lmstudio.md)
