---
description: "Configuração rápida do asiai: configure motores, teste conexões e verifique se seu Mac com Apple Silicon está pronto para benchmark de LLMs."
---

# asiai setup

Assistente de configuração interativo para novos usuários. Detecta seu hardware, verifica motores de inferência e sugere próximos passos.

## Uso

```bash
asiai setup
```

## O que faz

1. **Detecção de hardware** — identifica seu chip Apple Silicon e RAM
2. **Varredura de motores** — verifica motores de inferência instalados (Ollama, LM Studio, mlx-lm, llama.cpp, oMLX, vllm-mlx, Exo)
3. **Verificação de modelos** — lista modelos carregados em todos os motores detectados
4. **Status do daemon** — mostra se o daemon de monitoramento está rodando
5. **Próximos passos** — sugere comandos baseados no estado da sua configuração

## Exemplo de saída

```
  Setup Wizard

  Hardware:  Apple M4 Pro, 64 GB RAM

  Engines:
    ✓ ollama (v0.17.7) — 3 models loaded
    ✓ lmstudio (v0.4.5) — 1 model loaded

  Daemon: running (monitor + web)

  Suggested next steps:
    • asiai bench              Run your first benchmark
    • asiai monitor --watch    Watch metrics live
    • asiai web                Open the dashboard
```

## Quando nenhum motor é encontrado

Se nenhum motor for detectado, o setup fornece orientações de instalação:

```
  Engines:
    No inference engines detected.

  To get started, install an engine:
    brew install ollama && ollama serve
    # or download LM Studio from https://lmstudio.ai
```
