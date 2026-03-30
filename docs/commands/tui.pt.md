---
description: "Interface terminal para o asiai: monitore motores de inferência LLM em tempo real com um dashboard interativo no terminal."
---

# asiai tui

Dashboard interativo no terminal com atualização automática.

## Uso

```bash
asiai tui
```

## Requisitos

Requer o extra `tui`:

```bash
pip install asiai[tui]
```

Isso instala o [Textual](https://textual.textualize.io/) para a interface no terminal.

## Funcionalidades

- Métricas de sistema em tempo real (CPU, memória, térmico)
- Status dos motores e modelos carregados
- Atualização automática com intervalo configurável
