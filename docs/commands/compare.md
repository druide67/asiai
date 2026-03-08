# asiai compare

Compare your local benchmarks against community data.

## Usage

```bash
asiai compare [options]
```

## Options

| Option | Description |
|--------|-------------|
| `--chip CHIP` | Apple Silicon chip to compare against (default: auto-detect) |
| `--model MODEL` | Filter by model name |
| `--db PATH` | Path to local benchmark database |

## Example

```bash
asiai compare --model qwen3.5
```

```
  Compare: qwen3.5 — M4 Pro

  Engine       Your tok/s   Community median   Delta
  ────────── ──────────── ────────────────── ────────
  lmstudio        72.6           70.1          +3.6%
  ollama          30.4           31.0          -1.9%

  Chip: Apple M4 Pro (auto-detected)
```

## Notes

- If `--chip` is not specified, asiai auto-detects your Apple Silicon chip.
- Delta shows the percentage difference between your local median and the community median.
- Positive deltas mean your setup is faster than the community average.
- Local results come from your benchmark history database (`~/.local/share/asiai/benchmarks.db` by default).
