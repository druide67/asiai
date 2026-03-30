---
description: Wie asiai tok/s, TTFT und Leistung misst. Warmup, statistische Methodik und warum die Ergebnisse reproduzierbar sind.
---

# Benchmark-Methodik

asiai folgt etablierten Benchmarking-Standards ([MLPerf](https://mlcommons.org/benchmarks/inference-server/), [SPEC CPU 2017](https://www.spec.org/cpu2017/), [NVIDIA GenAI-Perf](https://docs.nvidia.com/deeplearning/nemo/user-guide/docs/en/stable/benchmarking/genai_perf.html)), um zuverlässige, reproduzierbare und vergleichbare Ergebnisse zu liefern.

## Protokoll

1. **Pre-Flight-Prüfung**: Start verweigern, wenn der Speicherdruck kritisch ist oder das System stark gedrosselt wird (<80%)
2. **Warmup**: 1 nicht gemessene Generierung pro Engine, um JIT-Compiler und Caches aufzuwärmen
3. **Gemessene Durchläufe**: Standard 3 Durchläufe pro Prompt pro Engine (konfigurierbar über `--runs`)
4. **Sampling**: `temperature=0` (greedy) für deterministische Ausgabe
5. **Modell-Entladung**: Nach dem Benchmarking jeder Engine wird das Modell entladen, um Unified Memory freizugeben, bevor die nächste Engine startet. Dies verhindert Speicherakkumulation und Swapping beim Vergleich mehrerer Engines mit großen Modellen
6. **Adaptives Abkühlen**: Nach dem Entladen wartet asiai, bis der macOS-Speicherdruck auf „normal" zurückkehrt (max 30s), dann folgen mindestens 5s thermische Abkühlung
7. **Plausibilitätsprüfungen**: Ergebnisse mit tok/s <= 0 werden verworfen. TTFT > 60s oder tok/s > 500 lösen Warnungen aus (wahrscheinlich Swapping oder Messfehler)
8. **Reporting**: Median tok/s als primäre Metrik (SPEC-Standard), Mittelwert +/- Stddev als sekundär
9. **Drosselung**: Warnung, wenn `thermal_speed_limit < 100%` während eines Durchlaufs. Thermische Drift (monotoner tok/s-Rückgang über Durchläufe, >= 5% Abfall) wird erkannt und gemeldet
10. **Metadaten**: Engine-Version, Modellformat, Quantisierung, Hardware-Chip, macOS-Version pro Ergebnis gespeichert

## Metriken

### tok/s — Generierungsgeschwindigkeit

Tokens pro Sekunde der **reinen Generierungszeit**, ohne Prompt-Verarbeitung (TTFT).

```
generation_s = total_duration_s - ttft_s
tok_per_sec  = tokens_generated / generation_s
```

Bei großen Kontextgrößen (z.B. 64k Tokens) kann die TTFT die Gesamtdauer dominieren. Sie aus tok/s auszuschließen verhindert, dass schnelle Generatoren langsam erscheinen.

### TTFT — Time to First Token

Zeit zwischen dem Senden der Anfrage und dem Empfang des ersten Ausgabe-Tokens, in Millisekunden. Serverseitig gemessen (Ollama) oder clientseitig beim ersten SSE-Content-Chunk (OpenAI-kompatible Engines).

### Leistung — GPU Watt

Durchschnittliche GPU-Leistung während der Ausführung jeder spezifischen Engine, gemessen über `sudo powermetrics`. Ein `PowerMonitor` pro Engine — kein sitzungsweiter Durchschnitt.

### tok/s/W — Energieeffizienz

```
tok_per_sec_per_watt = tok_per_sec / power_watts
```

### Varianz — Gepoolte Stddev

Gepoolte Intra-Prompt-Standardabweichung erfasst das Rauschen zwischen Durchläufen **ohne** Inter-Prompt-Varianz einzumischen.

Stabilitätsklassifikation:

- CV < 5% → `stable`
- CV < 10% → `variable`
- CV >= 10% → `unstable`

Wobei CV = `(std_dev / mean) * 100`.

## Konformität

| Praxis | Status |
|--------|--------|
| Pre-Flight-Prüfung (Speicherdruck + Thermal) | Implementiert |
| TTFT getrennt von tok/s | Implementiert |
| Deterministisches Sampling (temperature=0) | Implementiert |
| Token-Zählung über Server-API (nicht SSE-Chunks) | Implementiert |
| Leistungsüberwachung pro Engine (IOReport, ohne sudo) | Implementiert |
| 1 Warmup-Generierung pro Engine | Implementiert |
| Standard 3 Durchläufe (SPEC-Minimum) | Implementiert |
| Median als primäre Metrik (SPEC-Standard) | Implementiert |
| Gepoolte Intra-Prompt-Stddev | Implementiert |
| Modell-Entladung zwischen Engines | Implementiert |
| Adaptives Abkühlen (speicherdruckbewusst) | Implementiert |
| Plausibilitätsprüfungen (tok/s, TTFT-Grenzen) | Implementiert |
| Thermische Drosselungserkennung + Warnung | Implementiert |
| Thermische Drift-Erkennung (monotone Abnahme) | Implementiert |
| Engine-Version + Modell-Metadaten gespeichert | Implementiert |
| Universelles VRAM über ri_phys_footprint | Implementiert |
| Historische Regressionserkennung | Implementiert |

## Apple-Silicon-Aspekte

### Unified Memory

Apple Silicon teilt den Speicher zwischen CPU und GPU. asiai führt Engines **sequentiell** aus und **entlädt Modelle zwischen Engines**, um Speicherkonflikte und Swapping zu vermeiden. VRAM wird von Ollama und LM Studio nativ gemeldet; für andere Engines schätzt asiai die Speichernutzung über `ri_phys_footprint` (die macOS-Physical-Footprint-Metrik, identisch mit der Aktivitätsanzeige). Geschätzte Werte sind in der Oberfläche mit „(est.)" gekennzeichnet.

### Thermische Drosselung

- **MacBook Air** (ohne Lüfter): starke Drosselung unter Dauerlast
- **MacBook Pro** (Lüfter): leichte Drosselung
- **Mac Mini/Studio/Pro**: aktive Kühlung, minimale Drosselung

asiai zeichnet `thermal_speed_limit` pro Ergebnis auf und warnt bei erkannter Drosselung.

### KV Cache

Große Kontextgrößen (32k+) können bei Engines, die den KV Cache vorab zuweisen, Instabilität verursachen. Stellen Sie die Engine-Kontextlänge auf die tatsächliche Testgröße für faire Ergebnisse ein.

## Leistungsmessung

asiai misst den Stromverbrauch von GPU, CPU, ANE und DRAM über Apples IOReport Energy Model Framework — **kein sudo erforderlich**. Die Leistung wird automatisch in jedem Benchmark und jedem Monitoring-Snapshot gemessen.

IOReport liest dieselben Hardware-Energiezähler wie `sudo powermetrics`, aber über eine User-Space-API (`libIOReport.dylib` über ctypes). Dies macht die Konfiguration von passwortlosem sudo überflüssig.

### Validierung

Wir haben IOReport gegen `sudo powermetrics` unter LLM-Inferenzlast auf M4 Pro 64 GB kreuzvalidiert, mit 10 gepaarten Proben pro Engine in 2-Sekunden-Intervallen:

| Engine | IOReport Durchschn. | powermetrics Durchschn. | Mittlere Abweichung | Max. Abweichung |
|--------|---------------------|------------------------|---------------------|-----------------|
| LM Studio (MLX) | 12,6 W | 12,6 W | 0,9% | 2,1% |
| Ollama (llama.cpp) | 15,6 W | 15,4 W | 1,3% | 4,1% |

Beide Engines bestätigen <1,5% durchschnittliche Abweichung mit 10/10 gepaarten Proben. Die ANE-Leistung betrug 0,000W über alle 20 Proben, was bestätigt, dass keine LLM-Engine derzeit die Neural Engine nutzt.

Das `--power`-Flag aktiviert zusätzliche Kreuzvalidierung, indem IOReport und `sudo powermetrics` gleichzeitig ausgeführt werden und beide Messwerte zum Vergleich gespeichert werden.

### Energieeffizienz

Die Energieeffizienz (tok/s pro Watt) wird als `tok_per_sec / gpu_watts` für jedes Benchmark-Ergebnis berechnet. Diese Metrik ermöglicht den Vergleich der Inferenzkosten über Engines und Hardware hinweg.

## Metadaten

Jedes Benchmark-Ergebnis speichert: engine, engine_version, model, model_format, model_quantization, hw_chip, os_version, thermal_level, thermal_speed_limit, power_watts, power_source, metrics_version. Dies ermöglicht fairen Regressionsvergleich und maschinenübergreifende Benchmarks.
