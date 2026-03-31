---
title: "TurboQuant Benchmark auf Apple Silicon: 70B-Modelle auf dem Mac ausführen"
description: "Echte Benchmarks der TurboQuant KV Cache Kompression auf dem Mac Mini M4 Pro 64 GB: Llama 70B mit 6,3 tok/s und 5-facher Speichereinsparung. Installationsanleitung und Ergebnisse."
type: article
date: 2026-03-31
updated: 2026-03-31
faq:
  - q: "Kann ich ein 70B-Modell auf einem Mac mit 64 GB RAM ausführen?"
    a: "Ja, mit TurboQuant. Der KV Cache wird 5-fach komprimiert, sodass Llama 70B Q4_K_M (40 GB Gewichte) bequem in 64 GB mit 32K Kontext passt. Wir haben 6,3 tok/s auf einem Mac Mini M4 Pro gemessen."
  - q: "Verringert TurboQuant die Qualität?"
    a: "Kein messbarer Qualitätsverlust. Der Perplexitätsanstieg liegt unter 1 % gegenüber q8_0, und der Needle-in-a-Haystack-Abruf erreicht 100 % über den gesamten 32K-Kontext."
  - q: "Welches TurboQuant-Format sollte ich verwenden?"
    a: "Wir empfehlen asymmetrisch: q8_0 für Schlüssel (kompressionsempfindlich) und turbo3 für Werte (5-fache Kompression, kein Qualitätsverlust). Dies basiert auf Erkenntnissen des turboquant_plus-Projekts."
  - q: "Funktioniert TurboQuant mit MLX-Engines?"
    a: "Community-MLX-Implementierungen existieren, sind aber weniger ausgereift als der llama.cpp-Fork. Für den Produktionseinsatz auf Apple Silicon empfehlen wir TheTom/llama-cpp-turboquant mit Metal-Kernels."
  - q: "Wie viel schneller ist TurboQuant?"
    a: "Die Dekodiergeschwindigkeit beträgt etwa 0,9x von q8_0 (etwas langsamer pro Token), aber der Prefill kann bei langem Kontext durch reduzierte Speicherbandbreite schneller sein. Der eigentliche Gewinn besteht darin, größere Modelle und längere Kontexte in denselben RAM zu bekommen."
---

# TurboQuant Benchmark auf Apple Silicon

TurboQuant (Google Research, ICLR 2026) komprimiert den KV Cache von LLMs um das 5-fache ohne Qualitätsverlust und ermöglicht es, 70B-Modelle auf einem Mac Mini mit 64 GB RAM auszuführen. Dies sind echte Benchmarks, gemessen mit [asiai](/) auf realer Hardware.

## Ergebnisse

**Llama-3.1-70B-Instruct Q4_K_M auf Mac Mini M4 Pro 64 GB**

| Metrik | Wert |
|--------|------|
| **Durchsatz** | 6,3 tok/s (stabil, KI 95 %: 6,3-6,3) |
| **TTFT** | 196 ms (Median) |
| **GPU-Leistung** | 23,8 W |
| **Modell-VRAM** | 44,1 GB (40 GB Gewichte + 4 GB KV turbo3) |
| **Kontext** | 32.768 Tokens |
| **GPU Offload** | 81/81 Schichten auf Metal |
| **Thermisch** | Nominal (kein Throttling) |
| **Stabilität** | Stabil (Standardabweichung 0,04 tok/s über 3 Durchläufe) |

KV Cache Konfiguration: Schlüssel bei q8_0 (hohe Präzision), Werte bei turbo3 (3 Bit, 5-fache Kompression).

## Vor und nach TurboQuant

| | Ohne TurboQuant | Mit TurboQuant (turbo3) |
|--|-----------------|-------------------------|
| **KV Cache (32K Ctx)** | ~20 GB (q8_0) | ~4 GB (turbo3) |
| **Benötigter Gesamt-RAM** | 60+ GB (OOM bei 64 GB) | 44 GB (passt in 64 GB) |
| **70B auf 64 GB möglich?** | Nein | **Ja** |
| **Qualität** | Referenz | -1 % PPL (vernachlässigbar) |
| **NIAH-Abruf** | 100 % | 100 % |

## Was ist TurboQuant?

TurboQuant ist ein KV Cache Kompressionsalgorithmus von Google Research, vorgestellt auf der ICLR 2026. Während der LLM-Inferenz speichert der KV Cache Zwischen-Attention-Zustände und wächst linear mit der Kontextlänge. Für ein 70B-Modell bei 128K Kontext in FP16 kann dieser Cache allein 20-40 GB RAM verbrauchen.

TurboQuant komprimiert diesen Cache auf 3 Bit pro Wert durch:

- **Zufällige Rotation** (Walsh-Hadamard-Transformation) zur Gaussianisierung der Daten
- **Optimale skalare Quantisierung** (PolarQuant) nahe der Shannon-Grenze
- **QJL** (Quantized Johnson-Lindenstrauss) zur Erhaltung der Skalarprodukte

Das Ergebnis: 5-fache Speicherreduktion, kein Fine-Tuning nötig und nahezu kein Qualitätsverlust.

## Installationsanleitung

### Hardware

- Mac Mini M4 Pro, 64 GB Unified Memory (2.700 $)
- Jeder Apple Silicon Mac mit 32+ GB sollte funktionieren (Modellgröße entsprechend anpassen)

### TurboQuant llama.cpp installieren

```bash
# Install build tools
brew install cmake

# Clone the TurboQuant fork
git clone https://github.com/TheTom/llama-cpp-turboquant.git
cd llama-cpp-turboquant
git checkout feature/turboquant-kv-cache

# Build with Metal (Apple Silicon GPU)
cmake -B build -DGGML_METAL=ON -DGGML_METAL_EMBED_LIBRARY=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(sysctl -n hw.ncpu)
```

### Ein Modell herunterladen

```bash
# Llama 3.1 70B Q4_K_M (~40 GB)
curl -L -o llama-3.1-70b-q4_k_m.gguf \
  "https://huggingface.co/bartowski/Meta-Llama-3.1-70B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-70B-Instruct-Q4_K_M.gguf"
```

### macOS-GPU-Speicherlimit erhöhen

```bash
sudo sysctl iogpu.wired_limit_mb=61440
```

### Server starten

```bash
./build/bin/llama-server \
  -m llama-3.1-70b-q4_k_m.gguf \
  --cache-type-k q8_0 --cache-type-v turbo3 \
  -c 32768 \
  --port 8081 \
  --host 0.0.0.0 \
  -fa 1 \
  -ngl 99 \
  -t 10 \
  --no-mmap \
  --chat-template chatml
```

### Konfiguration erklärt

| Parameter | Wert | Warum |
|-----------|------|-------|
| `--cache-type-k q8_0` | Schlüssel bei 8 Bit | Schlüssel sind kompressionsempfindlich |
| `--cache-type-v turbo3` | Werte bei 3 Bit | Werte tolerieren extreme Kompression (5x) |
| `-fa 1` | Flash Attention | Erforderlich für TurboQuant |
| `-ngl 99` | Vollständiges GPU Offload | Alle 81 Schichten auf Metal |
| `-t 10` | 10 Threads | M4 Pro hat 10 Performance-Kerne |
| `--no-mmap` | Kein Memory Mapping | Lädt alles beim Start, vermeidet Seitenfehler |
| `--chat-template chatml` | ChatML-Format | Beste Kompatibilität mit diesem Fork |

## Benchmark mit asiai

```bash
pip install asiai
asiai detect --url http://localhost:8081
asiai bench --engines llamacpp --prompts code --runs 3 --kv-cache turbo3 --card
```

## Modelle, die mit TurboQuant in 64 GB passen

| Modell | Gewichte (Q4_K_M) | KV Cache (32K, turbo3) | Gesamt | Status |
|--------|-------------------|----------------------|--------|--------|
| Llama 3.1 70B | 40 GB | ~4 GB | 44 GB | **Getestet: 6,3 tok/s** |
| Qwen2.5 72B | 40 GB | ~4 GB | 44 GB | Sollte funktionieren |
| Llama 70B 128K Ctx | 40 GB | ~16 GB (turbo3) | 56 GB | Knapp aber möglich |
| Command-R+ 104B | 58 GB | ~4 GB | 62 GB | Sehr knapp |

## FAQ

**Kann ich ein 70B-Modell auf einem Mac mit 64 GB RAM ausführen?**

Ja, mit TurboQuant. Der KV Cache wird 5-fach komprimiert, sodass Llama 70B Q4_K_M (40 GB Gewichte) bequem in 64 GB mit 32K Kontext passt. Wir haben 6,3 tok/s auf einem Mac Mini M4 Pro gemessen.

**Verringert TurboQuant die Qualität?**

Kein messbarer Qualitätsverlust. Der Perplexitätsanstieg liegt unter 1 % gegenüber q8_0, und der Needle-in-a-Haystack-Abruf erreicht 100 % über den gesamten 32K-Kontext.

**Welches TurboQuant-Format sollte ich verwenden?**

Asymmetrisch: q8_0 für Schlüssel + turbo3 für Werte. Schlüssel sind kompressionsempfindlich (die gesamte Qualitätsverschlechterung kommt von der K-Kompression). Werte können auf 2-3 Bit komprimiert werden, ohne die Attention-Qualität zu beeinflussen.

**Funktioniert TurboQuant mit MLX?**

Community-Implementierungen existieren ([turboquant-mlx](https://github.com/helgklaizar/turboquant_mlx)), sind aber weniger ausgereift als der llama.cpp-Fork. Für den Produktionseinsatz empfehlen wir [TheTom/llama-cpp-turboquant](https://github.com/TheTom/llama-cpp-turboquant).

**Wie schneidet dies im Vergleich zum Standard-llama.cpp ab?**

Die Dekodiergeschwindigkeit beträgt etwa 0,9x von q8_0 (etwas langsamer pro Token), aber der eigentliche Gewinn besteht darin, Modelle und Kontexte einzusetzen, die vorher einfach nicht passten. Der Prefill kann bei langem Kontext tatsächlich schneller sein, da der Druck auf die Speicherbandbreite reduziert wird.

## Referenzen

- [Google Research Blog — TurboQuant](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/)
- [TurboQuant Paper (ICLR 2026)](https://arxiv.org/abs/2504.19874)
- [TheTom/turboquant_plus](https://github.com/TheTom/turboquant_plus) — Erweiterte Implementierung mit Sparse V
- [TheTom/llama-cpp-turboquant](https://github.com/TheTom/llama-cpp-turboquant) — llama.cpp-Fork mit Metal-Kernels
- [llama.cpp Discussion #20969](https://github.com/ggml-org/llama.cpp/discussions/20969) — Community-Diskussion
