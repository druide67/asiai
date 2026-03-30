---
description: "Interfaz de terminal para asiai: monitorea motores de inferencia LLM en tiempo real con un panel interactivo en tu terminal."
---

# asiai tui

Panel interactivo de terminal con actualización automática.

## Uso

```bash
asiai tui
```

## Requisitos

Requiere el extra `tui`:

```bash
pip install asiai[tui]
```

Esto instala [Textual](https://textual.textualize.io/) para la interfaz de terminal.

## Funcionalidades

- Métricas del sistema en tiempo real (CPU, memoria, térmica)
- Estado de motores y modelos cargados
- Actualización automática con intervalo configurable
