---
description: "Servidor llama.cpp no Mac: controle de baixo nível, porta 8080, métricas de cache KV e resultados de benchmark no Apple Silicon."
---

# llama.cpp

llama.cpp é o motor de inferência C++ fundamental para modelos GGUF, oferecendo controle máximo de baixo nível sobre cache KV, contagem de threads e tamanho de contexto na porta 8080. Ele alimenta o backend do Ollama mas pode ser executado standalone para ajuste fino no Apple Silicon.

[llama.cpp](https://github.com/ggml-org/llama.cpp) é um motor de inferência C++ de alta performance que suporta modelos GGUF.

## Configuração

```bash
brew install llama.cpp
llama-server -m model.gguf
```

## Detalhes

| Propriedade | Valor |
|-------------|-------|
| Porta padrão | 8080 |
| Tipo de API | Compatível com OpenAI |
| Reporte de VRAM | Não |
| Formato de modelo | GGUF |
| Detecção | Endpoints `/health` + `/props` ou detecção de processo via `lsof` |

## Notas

- llama.cpp compartilha a porta 8080 com mlx-lm. O asiai o detecta pelos endpoints `/health` e `/props`.
- O servidor pode ser iniciado com tamanhos de contexto e contagens de threads customizados para ajuste.

## Veja também

Compare motores com `asiai bench --engines llamacpp` --- [saiba como](../benchmark-llm-mac.md)
