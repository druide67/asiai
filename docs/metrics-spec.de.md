---
description: "Detaillierte Definitionen aller asiai-Benchmark-Metriken: tok/s, TTFT, Leistung Watt, Effizienz, VRAM, Stabilität, thermischer Zustand."
---

# Benchmark-Metriken-Spezifikation

> **Version**: 0.4.0
> **Status**: Implementiert
> **Geltungsbereich**: `asiai bench` — alle Engines

## Motivation

Benchmark-Ergebnisse müssen **über Engines hinweg vergleichbar** sein. Jede Metrik hat eine einzige Definition, die alle Engine-Implementierungen einhalten müssen. Die Implementierung kann variieren (serverseitige API vs. clientseitige Messung), aber die Semantik muss identisch sein.

## Metriken

### M1. `tok_per_sec` — Generierungsgeschwindigkeit

**Definition**: Tokens pro Sekunde der **reinen Generierungszeit**, ohne Prompt-Verarbeitung (TTFT).

```
generation_s = total_duration_s - ttft_s
tok_per_sec  = tokens_generated / generation_s    (wenn generation_s >= 0.01)
             = 0.0                                 (sonst)
```

| Engine | `generation_s`-Quelle |
|--------|----------------------|
| Ollama | `eval_duration / 1e9` (Server-API — direkt) |
| OpenAI-compat | `elapsed_s - (ttft_ms / 1000)` (clientseitig) |

**Begründung**: Bei großen Kontextgrößen (z.B. 64k Tokens) kann TTFT die Gesamtdauer dominieren. Sie in tok/s einzubeziehen lässt schnelle Generatoren langsam erscheinen (z.B. 3,2 tok/s statt 42 tok/s).

### M2. `ttft_ms` — Time to First Token

**Definition**: Zeit zwischen dem Senden der Anfrage und dem Empfang des ersten Ausgabe-Tokens, in ms.

| Engine | Quelle |
|--------|--------|
| Ollama | `prompt_eval_duration / 1e6` (Server-API) |
| OpenAI-compat | `(time.monotonic() beim 1. Content-Chunk - t0) * 1000` (Client) |

Hinweis: Die Semantik unterscheidet sich leicht (Server- vs. Client-Messung), aber auf localhost beträgt die Differenz ~1ms — akzeptabel.

### M3. `total_duration_ms` — Gesamtdauer

**Definition**: Gesamte Anfragedauer in Echtzeit (Prompt-Verarbeitung + Generierung), in ms.

**Invariante**: `total_duration_ms >= ttft_ms` — immer.

| Engine | Quelle |
|--------|--------|
| Ollama | `total_duration / 1e6` (Server-API) |
| OpenAI-compat | `elapsed_s * 1000` (Client-Echtzeit) |

### M4. `tokens_generated` — Token-Anzahl

**Definition**: Anzahl der vom Modell erzeugten Ausgabe-Tokens.

**Quelle (nach Priorität)**:
1. Server-Zähler: Ollama `eval_count`, OpenAI-compat `usage.completion_tokens`
2. Textlängen-Schätzung: `max(1, len(text) // 4)` (Heuristik: ~4 Zeichen/Token)
3. **Niemals** `len(text_parts)` (SSE-Chunks != Tokens)

### M5. `generation_duration_ms` — Generierungsdauer

**Definition**: Reine Generierungszeit (ohne TTFT), in ms.
Macht die Zerlegung `total = ttft + generation` explizit und auditierbar.

| Engine | Quelle |
|--------|--------|
| Ollama | `eval_duration / 1e6` (Server-API — direkt) |
| OpenAI-compat | `max(0, elapsed_s - ttft_s) * 1000` (berechnet) |

### M6. `power_watts` — GPU-Leistung

**Definition**: Durchschnittliche GPU-Leistung während der Ausführung **dieser spezifischen Engine**, in Watt.

**Geltungsbereich**: Ein `PowerMonitor` pro Engine. Gestartet vor dem ersten Prompt, gestoppt nach dem letzten Durchlauf. Jede Engine erhält ihre eigene Messung — kein sitzungsweiter Durchschnitt.

Quelle: `sudo powermetrics` (macOS).

### M7. `tok_per_sec_per_watt` — Energieeffizienz

```
tok_per_sec_per_watt = tok_per_sec / power_watts
```

Verwendet das korrigierte tok/s (M1) und die Engine-spezifische Leistung (M6).

### M8. `std_dev_tok_s` — Varianz (gepoolt)

**Definition**: Gepoolte Intra-Prompt-Standardabweichung — erfasst das Rauschen zwischen Durchläufen **ohne** Inter-Prompt-Varianz einzumischen.

```
Für jeden Prompt-Typ p mit Durchläufen [v1, v2, ..., vn]:
    var_p = sum((vi - mean_p)^2) / n    (Populationsvarianz)

pooled_variance = mean(var_p für alle p mit n >= 2)
std_dev_tok_s   = sqrt(pooled_variance)
```

**Stabilitätsklassifikation** (unverändert):
- CV < 5% → `stable`
- CV < 10% → `variable`
- CV >= 10% → `unstable`

Wobei CV = `(std_dev_tok_s / avg_tok_s) * 100`.

## Implementierungsübersicht

| Metrik | `base.py` | `ollama.py` | `openai_compat.py` | `runner.py` | `reporter.py` |
|--------|-----------|-------------|--------------------|-----------  |----------------|
| M1 tok/s | Feld | Server-API | Client (ohne TTFT) | Passthrough | Avg |
| M2 ttft_ms | Feld | Server-API | Client-Streaming | Passthrough | Avg |
| M3 total_duration_ms | Feld | Server-API | Client-Echtzeit | Passthrough | Avg |
| M4 tokens_generated | Feld | Server-API | Server oder `len//4` | Passthrough | Avg |
| M5 generation_duration_ms | Feld | Server-API | Berechnet | Im Dict gespeichert | — |
| M6 power_watts | — | — | — | Monitor pro Engine | Passthrough |
| M7 tok/s/W | — | — | — | Berechnet | Passthrough |
| M8 std_dev | — | — | — | — | Intra-Prompt gepoolt |

## Benchmark-Protokoll

1. **Warmup**: 1 nicht gemessene Generierung pro Engine (`"Hello"`, max_tokens=1), um Caches aufzuwärmen.
2. **Gemessene Durchläufe**: Standard 3 Durchläufe pro Prompt pro Engine (konfigurierbar über `--runs`).
3. **Sampling**: `temperature=0` (greedy) auf allen Engines für deterministische Ausgabe.
4. **Reporting**: Median tok/s als primäre Metrik (SPEC-Standard), Mittelwert +/- Stddev als sekundär.
5. **Drosselung**: Warnung, wenn `thermal_speed_limit < 100%` während eines Durchlaufs.
6. **Metadaten**: engine_version, model_format, model_quantization, hw_chip, os_version pro Ergebnis für Reproduzierbarkeit gespeichert.

Siehe [benchmark-best-practices.md](benchmark-best-practices.md) für das vollständige Methodik-Audit.
