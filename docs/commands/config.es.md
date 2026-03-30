---
description: "Cómo configurar asiai: gestionar URLs de motores, puertos y ajustes persistentes para tu entorno de benchmark de LLMs en Mac."
---

# asiai config

Gestiona la configuración persistente de motores. Los motores descubiertos por `asiai detect` se guardan automáticamente en `~/.config/asiai/engines.json` para una detección posterior más rápida.

## Uso

```bash
asiai config show              # Mostrar motores conocidos
asiai config add <engine> <url> [--label NAME]  # Añadir motor manualmente
asiai config remove <url>      # Eliminar un motor
asiai config reset             # Borrar toda la configuración
```

## Subcomandos

### show

Muestra todos los motores conocidos con su URL, versión, origen (auto/manual) y última marca de tiempo.

```
$ asiai config show
Known engines (3):
  ollama v0.17.7 at http://localhost:11434  (auto)  last seen 2m ago
  lmstudio v0.4.6 at http://localhost:1234  (auto)  last seen 2m ago
  omlx v0.9.2 at http://localhost:8800 [mac-mini]  (manual)  last seen 5m ago
```

### add

Registra manualmente un motor en un puerto no estándar. Los motores manuales nunca se eliminan automáticamente.

```bash
asiai config add omlx http://localhost:8800 --label mac-mini
asiai config add ollama http://192.168.0.16:11434 --label mini
```

### remove

Elimina una entrada de motor por URL.

```bash
asiai config remove http://localhost:8800
```

### reset

Elimina todo el archivo de configuración. El siguiente `asiai detect` redescubrirá los motores desde cero.

## Cómo funciona

El archivo de configuración almacena los motores descubiertos durante la detección:

- **Entradas automáticas** (`source: auto`): creadas automáticamente cuando `asiai detect` encuentra un nuevo motor. Se eliminan después de 7 días de inactividad.
- **Entradas manuales** (`source: manual`): creadas mediante `asiai config add`. Nunca se eliminan automáticamente.

La cascada de detección de 3 capas de `asiai detect` usa esta configuración como Capa 1 (la más rápida), seguida del escaneo de puertos (Capa 2) y la detección de procesos (Capa 3). Consulta [detect](detect.md) para más detalles.

## Ubicación del archivo de configuración

```
~/.config/asiai/engines.json
```
