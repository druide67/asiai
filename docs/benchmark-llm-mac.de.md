---
title: "Wie man LLMs auf dem Mac benchmarkt"
description: "Wie man LLM-Inferenz auf dem Mac benchmarkt: Schritt-für-Schritt-Anleitung zum Messen von tok/s, TTFT, Leistung und VRAM auf Apple Silicon mit mehreren Engines."
type: howto
date: 2026-03-28
updated: 2026-03-29
duration: PT5M
steps:
  - name: "asiai installieren"
    text: "Installieren Sie asiai über pip (pip install asiai) oder Homebrew (brew tap druide67/tap && brew install asiai)."
  - name: "Ihre Engines erkennen"
    text: "Führen Sie 'asiai detect' aus, um automatisch laufende Inferenz-Engines (Ollama, LM Studio, llama.cpp, mlx-lm, oMLX, vLLM-MLX, Exo) auf Ihrem Mac zu finden."
  - name: "Einen Benchmark starten"
    text: "Führen Sie 'asiai bench' aus, um automatisch das beste Modell über alle Engines zu erkennen und einen Engine-übergreifenden Vergleich mit tok/s, TTFT, Leistung und VRAM durchzuführen."
---

# Wie man LLMs auf dem Mac benchmarkt

Sie betreiben ein lokales LLM auf Ihrem Mac? So messen Sie die tatsächliche Leistung — keine Vermutungen, kein „fühlt sich schnell an", sondern echte tok/s, TTFT, Stromverbrauch und Speichernutzung.

## Warum benchmarken?

Dasselbe Modell läuft je nach Inferenz-Engine mit sehr unterschiedlichen Geschwindigkeiten. Auf Apple Silicon können MLX-basierte Engines (LM Studio, mlx-lm, oMLX) **2x schneller** sein als llama.cpp-basierte Engines (Ollama) für dasselbe Modell. Ohne Messung verschenken Sie Leistung.

## Schnellstart (2 Minuten)

### 1. asiai installieren

```bash
pip install asiai
```

Oder über Homebrew:

```bash
brew tap druide67/tap
brew install asiai
```

### 2. Ihre Engines erkennen

```bash
asiai detect
```

asiai findet automatisch laufende Engines (Ollama, LM Studio, llama.cpp, mlx-lm, oMLX, vLLM-MLX, Exo) auf Ihrem Mac.

### 3. Einen Benchmark starten

```bash
asiai bench
```

Das war's. asiai erkennt automatisch das beste Modell über Ihre Engines und führt einen Engine-übergreifenden Vergleich durch.

## Was gemessen wird

| Metrik | Bedeutung |
|--------|----------|
| **tok/s** | Generierte Tokens pro Sekunde (nur Generierung, ohne Prompt-Verarbeitung) |
| **TTFT** | Time to First Token — Latenz vor Beginn der Generierung |
| **Leistung** | GPU + CPU Watt während der Inferenz (über IOReport, kein sudo nötig) |
| **tok/s/W** | Energieeffizienz — Tokens pro Sekunde pro Watt |
| **VRAM** | Vom Modell genutzter Speicher (native API oder geschätzt über `ri_phys_footprint`) |
| **Stabilität** | Varianz zwischen Durchläufen: stabil (<5% CV), variabel (<10%), instabil (>10%) |
| **Thermisch** | Ob Ihr Mac während des Benchmarks gedrosselt wurde |

## Beispielausgabe

```
Mac16,11 — Apple M4 Pro  RAM: 64.0 GB  Pressure: normal

Benchmark: qwen3-coder-30b

  Engine        tok/s   Tokens Duration     TTFT       VRAM    Thermal
  lmstudio      102.2      537    7.00s    0.29s    24.2 GB    nominal
  ollama         69.8      512   17.33s    0.18s    32.0 GB    nominal

  Winner: lmstudio (+46% tok/s)

  Power Efficiency
    lmstudio     102.2 tok/s @ 12.4W = 8.23 tok/s/W
    ollama        69.8 tok/s @ 15.4W = 4.53 tok/s/W
```

*Beispielausgabe eines echten Benchmarks auf M4 Pro 64 GB. Ihre Zahlen variieren je nach Hardware und Modell. [Mehr Ergebnisse ansehen →](ollama-vs-lmstudio.md)*

## Erweiterte Optionen

### Bestimmte Engines vergleichen

```bash
asiai bench --engines ollama,lmstudio,omlx
```

### Mehrere Prompts und Durchläufe

```bash
asiai bench --prompts code,reasoning,tool_call --runs 3
```

### Benchmark mit großem Kontext

```bash
asiai bench --context-size 64K
```

### Teilbare Karte generieren

```bash
asiai bench --card --share
```

Erstellt ein Benchmark-Kartenbild und teilt die Ergebnisse mit dem [Community-Leaderboard](leaderboard.md).

## Apple Silicon Tipps

### Speicher ist entscheidend

Auf einem 16-GB-Mac bleiben Sie bei Modellen unter 14 GB (geladen). MoE-Modelle (Qwen3.5-35B-A3B, 3B aktiv) sind ideal — sie liefern 35B-Klasse-Qualität bei 7B-Klasse-Speichernutzung.

### Die Engine-Wahl ist wichtiger als gedacht

MLX-Engines sind auf Apple Silicon für die meisten Modelle deutlich schneller als llama.cpp. [Sehen Sie unseren Ollama vs LM Studio Vergleich](ollama-vs-lmstudio.md) für echte Zahlen.

### Thermische Drosselung

Das MacBook Air (ohne Lüfter) drosselt nach 5-10 Minuten dauerhafter Inferenz. Mac Mini/Studio/Pro bewältigen Dauerlasten ohne Drosselung. asiai erkennt und meldet thermische Drosselung automatisch.

## Mit der Community vergleichen

Sehen Sie, wie Ihr Mac im Vergleich zu anderen Apple-Silicon-Maschinen abschneidet:

```bash
asiai compare
```

Oder besuchen Sie das [Online-Leaderboard](leaderboard.md).

## FAQ

**F: Welche ist die schnellste LLM-Inferenz-Engine auf Apple Silicon?**
A: In unseren Benchmarks auf M4 Pro 64 GB ist LM Studio (MLX-Backend) am schnellsten bei der Token-Generierung — 46% schneller als Ollama (llama.cpp). Allerdings hat Ollama eine niedrigere TTFT (Time to First Token). Sehen Sie unseren [detaillierten Vergleich](ollama-vs-lmstudio.md).

**F: Wie viel RAM brauche ich, um ein 30B-Modell auf dem Mac zu betreiben?**
A: Ein Q4_K_M-quantisiertes 30B-Modell nutzt je nach Engine 24-32 GB Unified Memory. Sie benötigen mindestens 32 GB RAM, idealerweise 64 GB, um Speicherdruck zu vermeiden. MoE-Modelle wie Qwen3.5-35B-A3B nutzen nur ~7 GB aktive Parameter.

**F: Funktioniert asiai auf Intel-Macs?**
A: Nein. asiai erfordert Apple Silicon (M1/M2/M3/M4). Es nutzt macOS-spezifische APIs für GPU-Metriken, Leistungsüberwachung und Hardwareerkennung, die nur auf Apple Silicon verfügbar sind.

**F: Ist Ollama oder LM Studio schneller auf M4?**
A: LM Studio ist schneller beim Durchsatz (102 tok/s vs 70 tok/s bei Qwen3-Coder-30B). Ollama ist schneller bei der First-Token-Latenz (0,18s vs 0,29s) und bei großen Kontextfenstern (>32K Tokens), wo der llama.cpp-Prefill bis zu 3x schneller ist.

**F: Wie lange dauert ein Benchmark?**
A: Ein Schnellbenchmark dauert etwa 2 Minuten. Ein vollständiger Engine-übergreifender Vergleich mit mehreren Prompts und Durchläufen dauert 10-15 Minuten. Verwenden Sie `asiai bench --quick` für einen schnellen Einzeldurchlauf-Test.

**F: Kann ich meine Ergebnisse mit anderen Mac-Nutzern vergleichen?**
A: Ja. Führen Sie `asiai bench --share` aus, um Ergebnisse anonym an das [Community-Leaderboard](leaderboard.md) zu übermitteln. Verwenden Sie `asiai compare`, um zu sehen, wie Ihr Mac im Vergleich zu anderen Apple-Silicon-Maschinen abschneidet.

## Weiterführend

- [Benchmark-Methodik](methodology.md) — wie asiai zuverlässige Messungen sicherstellt
- [Benchmark Best Practices](benchmark-best-practices.md) — Tipps für genaue Ergebnisse
- [Engine-Vergleich](ollama-vs-lmstudio.md) — Ollama vs LM Studio im direkten Vergleich
