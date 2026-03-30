---
description: "Ejecuta asiai como servicio en segundo plano en Mac: monitoreo automático, panel web y métricas Prometheus al iniciar."
---

# asiai daemon

Gestiona servicios en segundo plano mediante LaunchAgents de macOS launchd.

## Servicios

| Servicio | Descripción | Modelo |
|---------|-------------|-------|
| `monitor` | Recopila métricas del sistema e inferencia a intervalos regulares | Periódico (`StartInterval`) |
| `web` | Ejecuta el panel web como servicio persistente | Larga ejecución (`KeepAlive`) |

## Uso

```bash
# Daemon de monitoreo (por defecto)
asiai daemon start                     # Iniciar monitoreo (cada 60s)
asiai daemon start --interval 30       # Intervalo personalizado
asiai daemon start --alert-webhook URL # Activar alertas por webhook

# Servicio del panel web
asiai daemon start web                 # Iniciar web en 127.0.0.1:8899
asiai daemon start web --port 9000     # Puerto personalizado
asiai daemon start web --host 0.0.0.0  # Exponer en la red (¡sin autenticación!)

# Estado (muestra todos los servicios)
asiai daemon status

# Detener
asiai daemon stop                      # Detener monitor
asiai daemon stop web                  # Detener web
asiai daemon stop --all                # Detener todos los servicios

# Logs
asiai daemon logs                      # Logs del monitor
asiai daemon logs web                  # Logs del web
asiai daemon logs web -n 100           # Últimas 100 líneas
```

## Cómo funciona

Cada servicio instala un plist de LaunchAgent de launchd separado en `~/Library/LaunchAgents/`:

- **Monitor**: ejecuta `asiai monitor --quiet` en el intervalo configurado (por defecto: 60s). Los datos se almacenan en SQLite. Si se proporciona `--alert-webhook`, las alertas se envían por POST en transiciones de estado (presión de memoria, térmica, motor caído).
- **Web**: ejecuta `asiai web --no-open` como proceso persistente. Se reinicia automáticamente si falla (`KeepAlive: true`, `ThrottleInterval: 10s`).

Ambos servicios se inician automáticamente al iniciar sesión (`RunAtLoad: true`).

## Seguridad

- Los servicios se ejecutan a **nivel de usuario** (no requieren root)
- El panel web se enlaza a `127.0.0.1` por defecto (solo localhost)
- Se muestra una advertencia al usar `--host 0.0.0.0` — no hay autenticación configurada
- Los logs se almacenan en `~/.local/share/asiai/`
