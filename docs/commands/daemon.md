# asiai daemon

Manage background services via macOS launchd LaunchAgents.

## Services

| Service | Description | Model |
|---------|-------------|-------|
| `monitor` | Collects system + inference metrics at regular intervals | Periodic (`StartInterval`) |
| `web` | Runs the web dashboard as a persistent service | Long-running (`KeepAlive`) |

## Usage

```bash
# Monitor daemon (default)
asiai daemon start                     # Start monitoring (every 60s)
asiai daemon start --interval 30       # Custom interval
asiai daemon start --alert-webhook URL # Enable webhook alerts

# Web dashboard service
asiai daemon start web                 # Start web on 127.0.0.1:8899
asiai daemon start web --port 9000     # Custom port
asiai daemon start web --host 0.0.0.0  # Expose on network (no auth!)

# Status (shows all services)
asiai daemon status

# Stop
asiai daemon stop                      # Stop monitor
asiai daemon stop web                  # Stop web
asiai daemon stop --all                # Stop all services

# Logs
asiai daemon logs                      # Monitor logs
asiai daemon logs web                  # Web logs
asiai daemon logs web -n 100           # Last 100 lines
```

## How it works

Each service installs a separate launchd LaunchAgent plist in `~/Library/LaunchAgents/`:

- **Monitor**: runs `asiai monitor --quiet` at the configured interval (default: 60s). Data is stored in SQLite. If `--alert-webhook` is provided, alerts are POSTed on state transitions (memory pressure, thermal, engine down).
- **Web**: runs `asiai web --no-open` as a persistent process. Automatically restarts if it crashes (`KeepAlive: true`, `ThrottleInterval: 10s`).

Both services start automatically on login (`RunAtLoad: true`).

## Security

- Services run at **user level** (no root required)
- Web dashboard binds to `127.0.0.1` by default (localhost only)
- A warning is displayed when using `--host 0.0.0.0` — no authentication is configured
- Logs are stored in `~/.local/share/asiai/`
