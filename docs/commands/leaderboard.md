# asiai leaderboard

Browse community benchmark data from the asiai network.

## Usage

```bash
asiai leaderboard [options]
```

## Options

| Option | Description |
|--------|-------------|
| `--chip CHIP` | Filter by Apple Silicon chip (e.g., `M4 Pro`, `M2 Ultra`) |
| `--model MODEL` | Filter by model name |

## Example

```bash
asiai leaderboard --chip "M4 Pro"
```

```
  Community Leaderboard — M4 Pro

  Model                  Engine      tok/s (median)   Runs   Contributors
  ──────────────────── ────────── ──────────────── ────── ──────────────
  qwen3.5:35b-a3b       ollama          30.4          42         12
  qwen3.5:35b-a3b       lmstudio        72.6          38         11
  llama3.3:70b           exo            18.2          15          4
  gemma2:9b              mlx-lm        105.3          27          9

  Source: api.asiai.dev — 122 results
```

## Notes

- Requires the community API at `api.asiai.dev`.
- Results are anonymized. No personal or machine-identifying data is shared.
- Contribute your own results with `asiai bench --export` and the upcoming `asiai push` command.
