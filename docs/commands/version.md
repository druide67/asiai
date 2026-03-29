---
description: "Check asiai version, Python environment, and agent registration status with a single command."
---

# asiai version

Display version and system information.

## Usage

```bash
asiai version
asiai --version
```

## Output

The `version` subcommand shows enriched system context:

```
asiai 1.0.1
  Apple M4 Pro, 64 GB RAM
  Engines: ollama, lmstudio
  Daemon: monitor, web
```

The `--version` flag shows only the version string:

```
asiai 1.0.1
```

## Use cases

- Quick system check in issues and bug reports
- Agent context gathering (chip, RAM, available engines)
- Scripting: `VERSION=$(asiai version | head -1)`
