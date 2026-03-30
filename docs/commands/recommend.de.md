---
description: Hardwareangepasste Modellempfehlungen basierend auf RAM, GPU-Kernen und thermischem Spielraum Ihres Macs.
---

# asiai recommend

Engine-Empfehlungen für Ihre Hardware und Ihren Anwendungsfall erhalten.

## Verwendung

```bash
asiai recommend [options]
```

## Optionen

| Option | Beschreibung |
|--------|-------------|
| `--model MODEL` | Modell, für das Empfehlungen gewünscht werden |
| `--use-case USE_CASE` | Optimieren für: `throughput`, `latency` oder `efficiency` |
| `--community` | Community-Benchmark-Daten in die Empfehlungen einbeziehen |
| `--db PATH` | Pfad zur lokalen Benchmark-Datenbank |

## Datenquellen

Empfehlungen werden aus den besten verfügbaren Daten erstellt, in Prioritätsreihenfolge:

1. **Lokale Benchmarks** — Ihre eigenen Durchläufe auf Ihrer Hardware
2. **Community-Daten** — aggregierte Ergebnisse von ähnlichen Chips (mit `--community`)
3. **Heuristiken** — eingebaute Regeln, wenn keine Benchmark-Daten verfügbar sind

## Vertrauensstufen

| Stufe | Kriterien |
|-------|----------|
| Hoch | 5 oder mehr lokale Benchmark-Durchläufe |
| Mittel | 1 bis 4 lokale Durchläufe oder Community-Daten verfügbar |
| Niedrig | Heuristik-basiert, keine Benchmark-Daten |

## Beispiel

```bash
asiai recommend --model qwen3.5 --use-case throughput
```

```
  Recommendation: qwen3.5 — M4 Pro — throughput

  #   Engine       tok/s    Confidence   Source
  ── ────────── ──────── ──────────── ──────────
  1   lmstudio    72.6     high         local (5 runs)
  2   ollama      30.4     high         local (5 runs)
  3   exo         18.2     medium       community

  Tip: lmstudio is 2.4x faster than ollama for this model.
```

## Hinweise

- Führen Sie zuerst `asiai bench` aus, um die genauesten Empfehlungen zu erhalten.
- Verwenden Sie `--community`, um Lücken zu füllen, wenn Sie eine bestimmte Engine lokal noch nicht benchmarkt haben.
- Der Anwendungsfall `efficiency` berücksichtigt den Stromverbrauch (erfordert `--power`-Daten aus vorherigen Benchmarks).
