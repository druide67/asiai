---
description: Führen Sie LLM-Benchmarks auf Apple Silicon im Direktvergleich durch. Vergleichen Sie Engines, messen Sie tok/s, TTFT, Energieeffizienz. Teilen Sie Ergebnisse.
---

# asiai bench

Engine-übergreifender Benchmark mit standardisierten Prompts.

## Verwendung

```bash
asiai bench [options]
```

## Optionen

| Option | Beschreibung |
|--------|-------------|
| `-m, --model MODEL` | Zu benchmarkendes Modell (Standard: Auto-Erkennung) |
| `-e, --engines LIST` | Engines filtern (z.B. `ollama,lmstudio,mlxlm`) |
| `-p, --prompts LIST` | Prompt-Typen: `code`, `tool_call`, `reasoning`, `long_gen` |
| `-r, --runs N` | Durchläufe pro Prompt (Standard: 3, für Median + Stddev) |
| `--power` | Kreuzvalidierung der Leistung mit sudo powermetrics (IOReport immer aktiv) |
| `--context-size SIZE` | Kontext-Füll-Prompt: `4k`, `16k`, `32k`, `64k` |
| `--export FILE` | Ergebnisse als JSON-Datei exportieren |
| `-H, --history PERIOD` | Vergangene Benchmarks anzeigen (z.B. `7d`, `24h`) |
| `-Q, --quick` | Schnellbenchmark: 1 Prompt (code), 1 Durchlauf (~15 Sekunden) |
| `--compare MODEL [MODEL...]` | Modellübergreifender Vergleich (2-8 Modelle, gegenseitig exklusiv mit `-m`) |
| `--card` | Teilbare Benchmark-Karte generieren (SVG lokal, PNG mit `--share`) |
| `--share` | Ergebnisse in die Community-Benchmark-Datenbank übermitteln |

## Beispiel

```bash
asiai bench -m qwen3.5 --runs 3 --power
```

```
  Mac Mini M4 Pro — Apple M4 Pro  RAM: 64.0 GB (42% used)  Pressure: normal

Benchmark: qwen3.5

  Engine       tok/s (±stddev)    Tokens   Duration     TTFT       VRAM    Thermal
  ────────── ───────────────── ───────── ────────── ──────── ────────── ──────────
  lmstudio    72.6 ± 0.0 (stable)   435    6.20s    0.28s        —    nominal
  ollama      30.4 ± 0.1 (stable)   448   15.28s    0.25s   26.0 GB   nominal

  Winner: lmstudio (2.4x faster)
  Power: lmstudio 13.2W (5.52 tok/s/W) — ollama 16.0W (1.89 tok/s/W)
```

## Prompts

Vier standardisierte Prompts testen verschiedene Generierungsmuster:

| Name | Tokens | Testet |
|------|--------|--------|
| `code` | 512 | Strukturierte Code-Generierung (BST in Python) |
| `tool_call` | 256 | JSON-Funktionsaufrufe / Instruktionsbefolgung |
| `reasoning` | 384 | Mehrstufiges Mathematikproblem |
| `long_gen` | 1024 | Dauerhafter Durchsatz (Bash-Skript) |

Verwenden Sie `--context-size` für Tests mit Prompts mit großem Kontext.

## Engine-übergreifende Modellzuordnung

Der Runner löst Modellnamen automatisch über Engines auf — `gemma2:9b` (Ollama) und `gemma-2-9b` (LM Studio) werden als dasselbe Modell erkannt.

## JSON-Export

Ergebnisse für Austausch oder Analyse exportieren:

```bash
asiai bench -m qwen3.5 --export bench.json
```

Das JSON enthält Maschinenmetadaten, Statistiken pro Engine (Median, CI 95%, P50/P90/P99), rohe Daten pro Durchlauf und eine Schemaversion für Vorwärtskompatibilität.

## Regressionserkennung

Nach jedem Benchmark vergleicht asiai die Ergebnisse mit dem Verlauf der letzten 7 Tage und warnt bei Leistungsregressionen (z.B. nach einem Engine-Update oder macOS-Upgrade).

## Schnellbenchmark

Führen Sie einen schnellen Benchmark mit einem einzelnen Prompt und einem Durchlauf durch (~15 Sekunden):

```bash
asiai bench --quick
asiai bench -Q -m qwen3.5
```

Ideal für Demos, GIFs und schnelle Überprüfungen. Der `code`-Prompt wird standardmäßig verwendet. Sie können ihn mit `--prompts` überschreiben.

## Modellübergreifender Vergleich

Vergleichen Sie mehrere Modelle in einer Sitzung mit `--compare`:

```bash
# Auto-Expansion über alle verfügbaren Engines
asiai bench --compare qwen3.5:4b deepseek-r1:7b

# Auf eine bestimmte Engine filtern
asiai bench --compare qwen3.5:4b deepseek-r1:7b -e ollama

# Jedes Modell einer Engine mit @ zuordnen
asiai bench --compare qwen3.5:4b@lmstudio deepseek-r1:7b@ollama
```

Die `@`-Notation trennt beim **letzten** `@` im String, sodass Modellnamen mit `@` korrekt behandelt werden.

### Regeln

- `--compare` und `--model` sind **gegenseitig exklusiv** — verwenden Sie eines von beiden.
- Akzeptiert 2 bis 8 Modellslots.
- Ohne `@` wird jedes Modell auf jede Engine erweitert, bei der es verfügbar ist.

### Sitzungstypen

Der Sitzungstyp wird automatisch anhand der Slot-Liste erkannt:

| Typ | Bedingung | Beispiel |
|-----|-----------|---------|
| **engine** | Gleiches Modell, verschiedene Engines | `--compare qwen3.5:4b@lmstudio qwen3.5:4b@ollama` |
| **model** | Verschiedene Modelle, gleiche Engine | `--compare qwen3.5:4b deepseek-r1:7b -e ollama` |
| **matrix** | Gemischte Modelle und Engines | `--compare qwen3.5:4b@lmstudio deepseek-r1:7b@ollama` |

### Kombination mit anderen Flags

`--compare` funktioniert mit allen Ausgabe- und Durchlauf-Flags:

```bash
asiai bench --compare qwen3.5:4b deepseek-r1:7b --quick
asiai bench --compare qwen3.5:4b deepseek-r1:7b --card --share
asiai bench --compare qwen3.5:4b deepseek-r1:7b --runs 5 --power
```

## Benchmark-Karte

Generieren Sie eine teilbare Benchmark-Karte:

```bash
asiai bench --card                    # SVG lokal gespeichert
asiai bench --card --share            # SVG + PNG (über Community-API)
asiai bench --quick --card --share    # Schnellbench + Karte + Teilen
```

Die Karte ist ein 1200x630 Bild im dunklen Design mit:
- Modellname und Hardware-Chip-Badge
- Spezifikations-Banner: Quantisierung, RAM, GPU-Kerne, Kontextgröße
- Terminal-Stil-Balkendiagramm der tok/s pro Engine
- Gewinner-Hervorhebung mit Delta (z.B. „2.4x")
- Metrik-Chips: tok/s, TTFT, Stabilität, VRAM, Leistung (W + tok/s/W), Engine-Version
- asiai-Branding

Das SVG wird in `~/.local/share/asiai/cards/` gespeichert. Mit `--share` wird auch ein PNG von der API heruntergeladen.

## Community-Sharing

Teilen Sie Ihre Ergebnisse anonym:

```bash
asiai bench --share
```

Community-Leaderboard ansehen mit `asiai leaderboard`.

## Thermische Drift-Erkennung

Bei 3+ Durchläufen erkennt asiai monotone tok/s-Degradation über aufeinanderfolgende Durchläufe. Wenn tok/s konsistent sinken (>5%), wird eine Warnung ausgegeben, die auf möglichen kumulativen thermischen Drosselungsaufbau hinweist.
