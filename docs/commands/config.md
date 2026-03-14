# asiai config

Manage persistent engine configuration. Engines discovered by `asiai detect` are automatically saved to `~/.config/asiai/engines.json` for faster subsequent detection.

## Usage

```bash
asiai config show              # Show known engines
asiai config add <engine> <url> [--label NAME]  # Add engine manually
asiai config remove <url>      # Remove an engine
asiai config reset             # Clear all configuration
```

## Subcommands

### show

Display all known engines with their URL, version, source (auto/manual), and last seen timestamp.

```
$ asiai config show
Known engines (3):
  ollama v0.17.7 at http://localhost:11434  (auto)  last seen 2m ago
  lmstudio v0.4.6 at http://localhost:1234  (auto)  last seen 2m ago
  omlx v0.9.2 at http://localhost:8800 [mac-mini]  (manual)  last seen 5m ago
```

### add

Manually register an engine on a non-standard port. Manual engines are never auto-pruned.

```bash
asiai config add omlx http://localhost:8800 --label mac-mini
asiai config add ollama http://192.168.0.16:11434 --label mini
```

### remove

Remove an engine entry by URL.

```bash
asiai config remove http://localhost:8800
```

### reset

Delete the entire configuration file. The next `asiai detect` will re-discover engines from scratch.

## How it works

The configuration file stores engines discovered during detection:

- **Auto entries** (`source: auto`): created automatically when `asiai detect` finds a new engine. Pruned after 7 days of inactivity.
- **Manual entries** (`source: manual`): created via `asiai config add`. Never pruned automatically.

The 3-layer detection cascade in `asiai detect` uses this config as Layer 1 (fastest), followed by port scanning (Layer 2) and process detection (Layer 3). See [detect](detect.md) for details.

## Config file location

```
~/.config/asiai/engines.json
```
