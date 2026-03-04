# asiai daemon

Background monitoring via macOS launchd. Collects metrics at regular intervals.

## Usage

```bash
asiai daemon start              # Install and start the daemon
asiai daemon start --interval 30  # Custom interval (seconds)
asiai daemon status             # Check if running
asiai daemon logs               # View recent logs
asiai daemon stop               # Stop and uninstall
```

## How it works

The daemon installs a launchd LaunchAgent plist that runs `asiai monitor --quiet` at the configured interval (default: 60 seconds). Data is stored in the same SQLite database used by all other commands.
