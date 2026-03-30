---
description: "Verifique a versão do asiai, ambiente Python e status de registro de agente com um único comando."
---

# asiai version

Exibe informações de versão e sistema.

## Uso

```bash
asiai version
asiai --version
```

## Saída

O subcomando `version` mostra contexto enriquecido do sistema:

```
asiai 1.0.1
  Apple M4 Pro, 64 GB RAM
  Engines: ollama, lmstudio
  Daemon: monitor, web
```

A flag `--version` mostra apenas a string de versão:

```
asiai 1.0.1
```

## Casos de uso

- Verificação rápida do sistema em issues e bug reports
- Coleta de contexto por agentes (chip, RAM, motores disponíveis)
- Scripting: `VERSION=$(asiai version | head -1)`
