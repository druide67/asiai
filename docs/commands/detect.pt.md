---
description: Auto-detecte motores de inferência LLM rodando no seu Mac. Cascata em 3 camadas — config, varredura de portas, detecção de processos.
---

# asiai detect

Auto-detecta motores de inferência usando uma cascata em 3 camadas.

## Uso

```bash
asiai detect                      # Auto-detectar (cascata 3 camadas)
asiai detect --url http://host:port  # Verificar apenas URL(s) específica(s)
```

## Saída

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

## Como funciona: detecção em 3 camadas

O asiai usa uma cascata de três camadas de detecção, da mais rápida à mais abrangente:

### Camada 1: Config (mais rápida, ~100ms)

Lê `~/.config/asiai/engines.json` — motores descobertos em execuções anteriores. Isso encontra motores em portas não padrão (ex: oMLX na 8800) sem precisar re-escanear.

### Camada 2: Varredura de portas (~200ms)

Verifica portas padrão mais um range estendido:

| Porta | Motor |
|-------|-------|
| 11434 | Ollama |
| 1234 | LM Studio |
| 8080 | mlx-lm ou llama.cpp |
| 8000-8009 | oMLX ou vllm-mlx |
| 52415 | Exo |

### Camada 3: Detecção de processos (fallback)

Usa `ps` e `lsof` para encontrar processos de motores ouvindo em qualquer porta. Encontra motores rodando em portas completamente inesperadas.

### Auto-persistência

Qualquer motor descoberto nas Camadas 2 ou 3 é automaticamente salvo no arquivo de configuração (Camada 1) para detecção mais rápida na próxima vez. Entradas auto-descobertas são removidas após 7 dias de inatividade.

Quando múltiplos motores compartilham uma porta (ex: mlx-lm e llama.cpp na 8080), o asiai usa probing de endpoints de API para identificar o motor correto.

## URLs explícitas

Ao usar `--url`, apenas as URLs especificadas são verificadas. Nenhuma configuração é lida ou escrita — útil para verificações pontuais.

```bash
asiai detect --url http://192.168.0.16:11434,http://localhost:8800
```

## Veja também

- [config](config.md) — Gerencie configuração persistente de motores
