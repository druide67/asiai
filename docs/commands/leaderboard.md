---
description: "Browse and query the asiai community leaderboard: compare benchmark results across Apple Silicon chips and inference engines."
---

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
| `--agentic DIR` | Render the local **decision-tier** view from a directory of `--agentic-mode` result JSON (no network) instead of the community feed |
| `--grid` | With `--agentic`: show the full **archive grid** (every column) instead of the tier view |

## Example

```bash
asiai leaderboard --chip "M4 Pro"
```

### Local agentic results — decision tiers

Render your own `asiai bench --agentic-mode --agentic-output` results, grouped by
deterministic gates into tiers (★ best validated throughput · ✓ viable · ⚠ reserve
· ✗ eliminated), per `(machine, power mode)` block:

```bash
asiai leaderboard --agentic ./my-bench-results/
asiai leaderboard --agentic ./my-bench-results/ --grid   # full archive table
```

```
Agentic bench — decision tiers
  ★ best validated throughput · ✓ viable · ⚠ reserve · ✗ eliminated.
  gates: valid≥80% · ttft≤1500ms (hard≤3000) · reuse>0.

  ▰ M5 · Q4_K_S · Apple M5 Max · powermode 2
     model · engine                 dec    peak    50K    ttft  reuse   t/s/W   RAMg  val%
  ★ TIER 1 — winner + fast
  ★  Qwopus-35B · llamacpp b9430 ▲MTP  123.3  127.5   83.8     67    0.8   1.590   29.0   100
```

Each row is self-describing from schema `agentic-v4`: the machine, chip, power
mode and engine version are read from the JSON, so the table needs no filename
parsing or hardcoded version map. Gates match the community ranking
(`valid ≥ 80%`); `★` ranks throughput only — the final pick also weighs output
quality. A throttled (power mode 0) run is never tiered against a High Power one.

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
- Contribute your own results with `asiai bench --share`.
