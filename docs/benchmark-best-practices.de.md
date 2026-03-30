---
description: "Wie Sie genaue LLM-Benchmark-Ergebnisse auf dem Mac erhalten: Wärmemanagement, Hintergrundanwendungen, Durchlaufanzahl und Tipps zur Reproduzierbarkeit."
---

# Benchmark Best Practices

> **Version**: 0.3.2
> **Status**: Lebendes Dokument — wird mit der Weiterentwicklung der Methodik aktualisiert
> **Referenzen**: MLPerf Inference, SPEC CPU 2017, NVIDIA GenAI-Perf

## Überblick

`asiai bench` folgt etablierten Benchmarking-Standards, um **zuverlässige, reproduzierbare und vergleichbare** Ergebnisse über Inferenz-Engines auf Apple Silicon zu liefern. Dieses Dokument erfasst, welche Best Practices implementiert, geplant oder absichtlich ausgeschlossen sind.

## Konformitätsübersicht

| Kategorie | Praxis | Status | Seit |
|-----------|--------|--------|------|
| **Metriken** | TTFT getrennt von tok/s | Implementiert | v0.3.1 |
| | Deterministisches Sampling (temperature=0) | Implementiert | v0.3.2 |
| | Token-Zählung über Server-API (nicht SSE-Chunks) | Implementiert | v0.3.1 |
| | Leistungsüberwachung pro Engine | Implementiert | v0.3.1 |
| | Explizites Feld generation_duration_ms | Implementiert | v0.3.1 |
| **Warmup** | 1 Warmup-Generierung pro Engine (nicht gemessen) | Implementiert | v0.3.2 |
| **Durchläufe** | Standard 3 Durchläufe (SPEC-Minimum) | Implementiert | v0.3.2 |
| | Median als primäre Metrik (SPEC-Standard) | Implementiert | v0.3.2 |
| | Mittelwert + Stddev als sekundär | Implementiert | v0.3.0 |
| **Varianz** | Gepoolte Intra-Prompt-Stddev | Implementiert | v0.3.1 |
| | CV-basierte Stabilitätsklassifikation | Implementiert | v0.3.0 |
| **Umgebung** | Sequentielle Engine-Ausführung (Speicherisolation) | Implementiert | v0.1 |
| | Thermische Drosselungserkennung + Warnung | Implementiert | v0.3.2 |
| | Thermisches Niveau + speed_limit aufgezeichnet | Implementiert | v0.1 |
| **Reproduzierbarkeit** | Engine-Version pro Benchmark gespeichert | Implementiert | v0.3.2 |
| | Modellformat + Quantisierung gespeichert | Implementiert | v0.3.2 |
| | Hardware-Chip + macOS-Version gespeichert | Implementiert | v0.3.2 |
| | Open-Source-Benchmark-Code | Implementiert | v0.1 |
| **Regression** | Historischer Baseline-Vergleich (SQLite) | Implementiert | v0.3.0 |
| | Vergleich nach (Engine, Modell, Prompt-Typ) | Implementiert | v0.3.1 |
| | metrics_version-Filterung | Implementiert | v0.3.1 |
| **Prompts** | 4 diverse Prompt-Typen + Kontext-Füllung | Implementiert | v0.1 |
| | Festes max_tokens pro Prompt | Implementiert | v0.1 |

## Geplante Verbesserungen

### P1 — Statistische Strenge

| Praxis | Beschreibung | Standard |
|--------|-------------|----------|
| **95%-Konfidenzintervalle** | CI = Mittelwert +/- 2*SE. Informativer als +/- Stddev. | Akademisch |
| **Perzentile (P50/P90/P99)** | Besonders für TTFT — Tail-Latenz ist wichtig. | NVIDIA GenAI-Perf |
| **Ausreißererkennung (IQR)** | Durchläufe außerhalb von [Q1 - 1.5*IQR, Q3 + 1.5*IQR] markieren. | Statistischer Standard |
| **Trenderkennung** | Monotone Leistungsdegradation über Durchläufe erkennen (thermische Drift). | Akademisch |

### P2 — Reproduzierbarkeit

| Praxis | Beschreibung | Standard |
|--------|-------------|----------|
| **Abkühlung zwischen Engines** | 3-5s Pause zwischen Engines zur thermischen Stabilisierung. | GPU-Benchmark |
| **Token-Verhältnis-Überprüfung** | Warnung wenn tokens_generated < 90% von max_tokens. | MLPerf |
| **Exportformat** | `asiai bench --export` JSON für Community-Einreichungen. | MLPerf-Einreichungen |

### P3 — Fortgeschritten

| Praxis | Beschreibung | Standard |
|--------|-------------|----------|
| **`ignore_eos`-Option** | Generierung bis max_tokens erzwingen für Durchsatz-Benchmarks. | NVIDIA |
| **Test gleichzeitiger Anfragen** | Batch-Durchsatz testen (relevant für vllm-mlx). | NVIDIA |
| **Hintergrundprozess-Audit** | Warnung bei schweren Prozessen während des Benchmarks. | SPEC |

## Absichtliche Abweichungen

| Praxis | Grund für die Abweichung |
|--------|-------------------------|
| **MLPerf Mindestdauer 600s** | Für Rechenzentrum-GPUs konzipiert. Lokale Inferenz auf Apple Silicon mit 3 Durchläufen + 4 Prompts dauert bereits ~2-5 Minuten. Ausreichend für stabile Ergebnisse. |
| **SPEC 2 nicht gemessene Warmup-Workloads** | Wir verwenden 1 Warmup-Generierung (nicht 2 vollständige Workloads). Ein einzelnes Warmup reicht für lokale Inferenz-Engines, bei denen JIT-Warmup minimal ist. |
| **Populations- vs. Stichproben-Stddev** | Wir verwenden die Populations-Stddev (Divisor N) statt der Stichproben-Stddev (Divisor N-1). Bei kleinem N (3-5 Durchläufe) ist der Unterschied minimal und Population ist konservativer. |
| **Frequenzskalierungskontrolle** | Apple Silicon bietet keine CPU-Governor-Steuerung. Wir zeichnen stattdessen thermal_speed_limit auf, um Drosselung zu erkennen. |

## Apple-Silicon-spezifische Aspekte

### Unified Memory Architektur

Apple Silicon teilt den Speicher zwischen CPU und GPU. Zwei wichtige Implikationen:

1. **Niemals zwei Engines gleichzeitig benchmarken** — sie konkurrieren um denselben Speicherpool.
   `asiai bench` führt Engines absichtlich sequentiell aus.
2. **VRAM-Berichterstattung** — Ollama und LM Studio melden `size_vram` nativ. Für andere Engines
   (llama.cpp, mlx-lm, oMLX, vLLM-MLX, Exo) verwendet asiai `ri_phys_footprint` über libproc als
   Fallback-Schätzung. Dies entspricht der Anzeige in der Aktivitätsanzeige und beinhaltet Metal/GPU-Zuweisungen.
   Geschätzte Werte sind in der Oberfläche mit „(est.)" gekennzeichnet.

### Thermische Drosselung

- **MacBook Air** (ohne Lüfter): starke Drosselung unter Dauerlast. Ergebnisse verschlechtern sich nach 5-10 Min.
- **MacBook Pro** (Lüfter): leichte Drosselung, meist durch Lüfterdrehzahlerhöhung aufgefangen.
- **Mac Mini/Studio/Pro**: aktive Kühlung, minimale Drosselung.

`asiai bench` zeichnet `thermal_speed_limit` pro Ergebnis auf und warnt, wenn Drosselung erkannt wird
(speed_limit < 100%) während eines Durchlaufs.

### KV Cache und Kontextlänge

Große Kontextgrößen (32k+) können Leistungsinstabilität bei Engines verursachen, die den KV Cache beim Laden des Modells vorab zuweisen. Beispiel: LM Studio verwendet standardmäßig `loaded_context_length: 262144` (256k), was ~15-25 GB KV Cache für ein 35B-Modell zuweist und möglicherweise 64 GB Unified Memory ausschöpft.

**Empfehlungen**:
- Beim Benchmarking großer Kontexte die Engine-Kontextlänge auf die tatsächliche Testgröße einstellen
  (z.B. `lms load model --context-length 65536` für 64k-Tests).
- Engines mit äquivalenten Kontextlängeneinstellungen für faire Ergebnisse vergleichen.

## Gespeicherte Metadaten pro Benchmark

Jedes Benchmark-Ergebnis in SQLite enthält:

| Feld | Beispiel | Zweck |
|------|---------|-------|
| `engine` | "ollama" | Engine-Identifikation |
| `engine_version` | "0.17.4" | Leistungsänderungen über Updates erkennen |
| `model` | "qwen3.5:35b-a3b" | Modell-Identifikation |
| `model_format` | "gguf" | Formatvarianten unterscheiden |
| `model_quantization` | "Q4_K_M" | Quantisierungsstufen unterscheiden |
| `hw_chip` | "Apple M4 Pro" | Hardware-Identifikation |
| `os_version` | "15.3" | macOS-Versionsverfolgung |
| `thermal_level` | "nominal" | Umgebungsbedingung |
| `thermal_speed_limit` | 100 | Drosselungserkennung |
| `metrics_version` | 2 | Formelversion (verhindert versionsübergreifende Regression) |

Diese Metadaten ermöglichen:
- **Fairen Regressionsvergleich**: nur Ergebnisse mit übereinstimmenden Metadaten vergleichen
- **Maschinenübergreifende Benchmarks**: Hardwareunterschiede identifizieren
- **Community-Datenaustausch**: selbstbeschreibende Ergebnisse (geplant für v1.x)
