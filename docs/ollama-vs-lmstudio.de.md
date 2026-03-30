---
title: "Ollama vs LM Studio: Apple Silicon Benchmark"
description: "Ollama vs LM Studio Benchmark auf Apple Silicon: tok/s, TTFT, Leistung, VRAM im Direktvergleich auf M4 Pro mit echten Messungen."
type: article
date: 2026-03-28
updated: 2026-03-29
dataset:
  name: "Ollama vs LM Studio Benchmark auf Apple Silicon M4 Pro"
  description: "Direktvergleich zwischen Ollama (llama.cpp) und LM Studio (MLX) auf Mac Mini M4 Pro 64 GB mit Qwen3-Coder-30B. Metriken: tok/s, TTFT, GPU-Leistung, Effizienz, VRAM."
  date: "2026-03"
---

# Ollama vs LM Studio: Apple Silicon Benchmark

Welche Inferenz-Engine ist schneller auf Ihrem Mac? Wir haben Ollama (llama.cpp-Backend) und LM Studio (MLX-Backend) auf demselben Modell und derselben Hardware mit asiai 1.4.0 im März 2026 im Direktvergleich getestet.

## Testaufbau

| | |
|---|---|
| **Hardware** | Mac Mini M4 Pro, 64 GB Unified Memory |
| **Modell** | Qwen3-Coder-30B (MoE-Architektur, Q4_K_M / MLX 4-bit) |
| **asiai-Version** | 1.4.0 |
| **Methodik** | 1 Warmup + 1 gemessener Durchlauf pro Engine, temperature=0, Modell zwischen Engines entladen ([vollständige Methodik](methodology.md)) |

## Ergebnisse

| Metrik | LM Studio (MLX) | Ollama (llama.cpp) | Differenz |
|--------|-----------------|-------------------|-----------|
| **Durchsatz** | 102,2 tok/s | 69,8 tok/s | **+46%** |
| **TTFT** | 291 ms | 175 ms | Ollama schneller |
| **GPU-Leistung** | 12,4 W | 15,4 W | **-20%** |
| **Effizienz** | 8,2 tok/s/W | 4,5 tok/s/W | **+82%** |
| **Prozessspeicher** | 21,4 GB (RSS) | 41,6 GB (RSS) | -49% |

!!! note "Zu den Speicherzahlen"
    Ollama weist den KV Cache für das vollständige Kontextfenster (262K Tokens) vorab zu, was seinen Speicherverbrauch aufbläht. LM Studio weist den KV Cache bei Bedarf zu. Der Prozess-RSS spiegelt den gesamten vom Engine-Prozess genutzten Speicher wider, nicht nur die Modellgewichte.

## Wichtige Erkenntnisse

### LM Studio gewinnt beim Durchsatz (+46%)

Die native Metal-Optimierung von MLX nutzt die Bandbreite von Apple Silicons Unified Memory besser aus. Bei MoE-Architekturen ist der Vorteil erheblich. Bei der größeren Variante Qwen3.5-35B-A3B haben wir einen noch größeren Abstand gemessen: **71,2 vs 30,3 tok/s (2,3x)**.

### Ollama gewinnt bei TTFT

Ollamas llama.cpp-Backend verarbeitet den initialen Prompt schneller (175ms vs 291ms). Für interaktive Nutzung mit kurzen Prompts fühlt sich Ollama dadurch reaktionsschneller an. Bei längeren Generierungsaufgaben dominiert der Durchsatzvorteil von LM Studio die Gesamtzeit.

### LM Studio ist energieeffizienter (+82%)

Mit 8,2 tok/s pro Watt gegenüber 4,5 generiert LM Studio fast doppelt so viele Tokens pro Joule. Das ist wichtig für Laptops im Akkubetrieb und für Dauerlasten auf Always-on-Servern.

### Speichernutzung: der Kontext zählt

Der große Unterschied im Prozessspeicher (21,4 vs 41,6 GB) ist teilweise darauf zurückzuführen, dass Ollama den KV Cache für sein maximales Kontextfenster vorab zuweist. Für einen fairen Vergleich betrachten Sie den tatsächlich während Ihrer Arbeitslast genutzten Kontext, nicht den Spitzen-RSS.

## Wann welche Engine verwenden

| Anwendungsfall | Empfohlen | Warum |
|----------------|----------|-------|
| **Maximaler Durchsatz** | LM Studio (MLX) | +46% schnellere Generierung |
| **Interaktiver Chat (niedrige Latenz)** | Ollama | Niedrigere TTFT (175 vs 291 ms) |
| **Akkulaufzeit / Effizienz** | LM Studio | 82% mehr tok/s pro Watt |
| **Docker / API-Kompatibilität** | Ollama | Breiteres Ökosystem, OpenAI-kompatible API |
| **Speicherbeschränkt (16-GB-Mac)** | LM Studio | Niedrigerer RSS, KV Cache bei Bedarf |
| **Multi-Modell-Serving** | Ollama | Integrierte Modellverwaltung, keep_alive |

## Andere Modelle

Der Durchsatzunterschied variiert je nach Modellarchitektur:

| Modell | LM Studio (MLX) | Ollama (llama.cpp) | Abstand |
|--------|-----------------|-------------------|---------|
| Qwen3-Coder-30B (MoE) | 102,2 tok/s | 69,8 tok/s | +46% |
| Qwen3.5-35B-A3B (MoE) | 71,2 tok/s | 30,3 tok/s | +135% |

MoE-Modelle zeigen die größten Unterschiede, da MLX das Sparse-Expert-Routing auf Metal effizienter handhabt.

## Eigenen Benchmark durchführen

```bash
pip install asiai
asiai bench --engines ollama,lmstudio --prompts code --runs 3 --card
```

asiai vergleicht Engines nebeneinander mit demselben Modell, denselben Prompts und derselben Hardware. Modelle werden automatisch zwischen Engines entladen, um Speicherkonflikte zu vermeiden.

[Vollständige Methodik ansehen](methodology.md) · [Community-Leaderboard ansehen](leaderboard.md) · [Wie man LLMs auf dem Mac benchmarkt](benchmark-llm-mac.md)
