---
description: "Diagnostique problemas de inferência LLM no Mac: asiai doctor verifica saúde dos motores, conflitos de porta, carregamento de modelos e status da GPU."
---

# asiai doctor

Diagnostica instalação, motores, saúde do sistema e banco de dados.

## Uso

```bash
asiai doctor
```

## Saída

```
Doctor

  System
    ✓ Apple Silicon       Mac Mini M4 Pro — Apple M4 Pro
    ✓ RAM                 64 GB total, 42% used
    ✓ Memory pressure     normal
    ✓ Thermal             nominal (100%)

  Engine
    ✓ Ollama              v0.17.5 — 1 model(s): qwen3.5:35b-a3b
    ✓ Ollama config       host=0.0.0.0:11434, num_parallel=1 (default), ...
    ✓ LM Studio           v0.4.6 — 1 model(s): qwen3.5-35b-a3b
    ✗ mlx-lm              not installed
    ✗ llama.cpp           not installed
    ✗ vllm-mlx            not installed

  Database
    ✓ SQLite              2.4 MB, last entry: 1m ago

  Daemon
    ✓ Monitoring daemon   running PID 1234
    ✓ Web dashboard       not installed

  Alerting
    ✓ Webhook URL         https://hooks.slack.com/services/...
    ✓ Webhook reachable   HTTP 200

  9 ok, 0 warning(s), 3 failed
```

## Verificações

- **Sistema**: Detecção de Apple Silicon, RAM, pressão de memória, estado térmico
- **Motores**: Acessibilidade e versão para todos os 7 motores suportados; parâmetros de runtime do Ollama (host, num_parallel, max_loaded_models, keep_alive, flash_attention)
- **Banco de dados**: Versão do schema SQLite, tamanho, timestamp da última entrada
- **Daemon**: Status do LaunchAgent para serviços monitor e web
- **Alertas**: Configuração de URL de webhook e conectividade
