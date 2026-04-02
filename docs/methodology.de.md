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
7. **Plausibilitätsprüfungen**: Ergebnisse mit tok/s ≤ 0 werden verworfen. TTFT > 60s oder tok/s > 500 lösen Warnungen aus (wahrscheinlich Swapping oder Messfehler)
8. **Reporting**: Median tok/s als primäre Metrik (SPEC-Standard), Mittelwert ± Stddev als sekundär
9. **Drosselung**: Warnung, wenn `thermal_speed_limit < 100%` während eines Durchlaufs. Thermische Drift (monotoner tok/s-Rückgang über Durchläufe, ≥ 5% Abfall) wird erkannt und gemeldet
10. **Metadaten**: Engine-Version, Modellformat, Quantisierung, Hardware-Chip, macOS-Version pro Ergebnis gespeichert

## Metriken

### tok/s — Generierungsgeschwindigkeit

Tokens pro Sekunde der **reinen Generierungszeit**, ohne Prompt-Verarbeitung (TTFT).

**Ollama** (native API, `/api/generate`):
```
tok_per_sec = eval_count / (eval_duration_ns / 1e9)
```
Quelle: internes GPU-Timing, berichtet von Ollama. Kein Netzwerk-Overhead. Dies ist die genaueste Messung.

**OpenAI-kompatible Engines** (LM Studio, llama.cpp, mlx-lm, vllm-mlx):
```
generation_s = wall_clock_s - ttft_s
tok_per_sec  = completion_tokens / generation_s
```
Quelle: clientseitige Wanduhr über streaming SSE. Beinhaltet HTTP-Overhead pro Chunk (~1% langsamer als serverseitiges Timing, durch Kreuzvalidierung bestätigt).

**Token-Zählung**: aus `usage.completion_tokens` in der Server-Antwort. Falls der Server dieses Feld nicht liefert, fällt asiai auf `len(text) // 4` zurück und protokolliert eine Warnung. Dieser Fallback kann ~25% abweichen.

**Kreuzvalidierung** (April 2026, Qwen3.5-35B NVFP4, M4 Pro 64GB):

| Methode | tok/s | Delta vs Referenz |
|---------|-------|--------------------|
| Ollama native (internes GPU) | 66.6 | Referenz |
| OpenAI streaming (Client) | 66.1 | -0.8% |

Bei großen Kontextgrößen (z.B. 64k Tokens) kann die TTFT die Gesamtdauer dominieren. Sie aus tok/s auszuschließen verhindert, dass schnelle Generatoren langsam erscheinen.

### TTFT — Time to First Token

Zeit zwischen dem Senden der Anfrage und dem Empfang des ersten Ausgabe-Tokens, in Millisekunden.

Seit v1.6.0 misst asiai **zwei TTFT-Werte** für Ollama und einen für alle anderen Engines:

**Ollama** (duale Messung):

- **Serverseitiges TTFT** (`ttft_ms`): extrahiert aus `prompt_eval_duration` in der Ollama-Antwort. Dies ist reine GPU-Prompt-Verarbeitungszeit ohne Netzwerk-Overhead — die genaueste mögliche Messung. Berichtet als `ttft_source: server`.
- **Clientseitiges TTFT** (`ttft_client_ms`): gemessen beim Eintreffen des ersten SSE-Content-Chunks. Beinhaltet HTTP-Setup, Anfragenübertragung und Serververarbeitung. Dies ist dieselbe Methode, die für alle anderen Engines verwendet wird.

**OpenAI-kompatible Engines** (LM Studio, llama.cpp, mlx-lm, vllm-mlx):

- **Clientseitiges TTFT** (`ttft_client_ms`): gemessen beim ersten SSE-Content-Chunk. Dies ist die einzige verfügbare Messung, da diese Engines kein internes Prompt-Verarbeitungs-Timing bereitstellen. Sowohl `ttft_ms` als auch `ttft_client_ms` enthalten denselben Wert.

**Vergleichbare Metrik**: `ttft_client_ms` ist die **engine-übergreifend vergleichbare** Metrik — sie verwendet unabhängig von der Engine dieselbe Messmethode. Verwenden Sie diese zum Vergleich von TTFT über verschiedene Engines hinweg. Das serverseitige `ttft_ms` von Ollama ist genauer für die absolute Prompt-Verarbeitungszeit, aber nicht direkt mit anderen Engines vergleichbar.

**Kreuzvalidierung** (April 2026, Qwen3.5-35B NVFP4, M4 Pro 64GB):

| Methode | TTFT | Delta |
|---------|------|-------|
| Ollama serverseitig (`ttft_ms`) | 27 ms | Referenz |
| Ollama clientseitig (`ttft_client_ms`) | 51 ms | +24 ms |

Das Delta von 24ms entspricht dem HTTP-Overhead auf localhost. Dieser Overhead ist konsistent und vorhersehbar, aber signifikant genug, um beim Vergleich von Engines relevant zu sein.

### Leistung — GPU Watt

Durchschnittliche GPU-Leistung während der Ausführung, gemessen über Apples IOReport Energy Model Framework (kein sudo erforderlich). Eine Messung pro Engine — kein sitzungsweiter Durchschnitt.

### tok/s/W — Energieeffizienz

```
tok_per_sec_per_watt = tok_per_sec / power_watts
```

### Varianz — Gepoolte Stddev

Gepoolte Intra-Prompt-Standardabweichung erfasst das Rauschen zwischen Durchläufen **ohne** Inter-Prompt-Varianz einzumischen. Verwendet Bessels Korrektur (N-1-Nenner) für unverzerrte Stichprobenvarianz.

Stabilitätsklassifikation:

- CV < 5% → `stable`
- CV < 10% → `variable`
- CV >= 10% → `unstable`

Wobei CV = `(std_dev / mean) * 100`.

### VRAM — Speichernutzung

**Primär**: engine-native API (Ollama `/api/ps`, LM Studio `/v1/models`).
**Fallback**: `ri_phys_footprint` über ctypes (identisch mit der Aktivitätsanzeige). Mit „(est.)" in der Oberfläche gekennzeichnet.

## Umgebungssicherheit

asiai führt Pre-Benchmark-Prüfungen durch:

1. **Speicherdruck**: Start verweigern bei kritischem Zustand
2. **Thermische Drosselung**: Warnung bei Geschwindigkeitslimit < 80%
3. **Doppelte Prozesse**: Warnung, wenn mehrere Instanzen derselben Engine laufen (z.B. zwei `ollama serve`-Prozesse auf demselben Port)
4. **Engine-Runner-Typ**: erkennt bei Ollama, ob der `--mlx-engine`- oder `--ollama-engine`-Runner aktiv ist

Diese Prüfungen verhindern Messfehler durch Ressourcenkonflikte oder fehlerhaftes Routing.

## Konformität

| Praxis | Status |
|--------|--------|
| Pre-Flight-Prüfung (Speicherdruck + Thermal) | Implementiert |
| Erkennung doppelter Prozesse | Implementiert (v1.5.0) |
| Ollama-Runner-Typ-Erkennung (MLX vs llama.cpp) | Implementiert (v1.5.0) |
| TTFT getrennt von tok/s | Implementiert |
| TTFT-Quellenkennzeichnung (server vs client) | Implementiert (v1.5.0) |
| Duale TTFT-Messung (server + client) | Implementiert (v1.6.0) |
| Deterministisches Sampling (temperature=0) | Implementiert |
| Token-Zählung über Server-API (nicht SSE-Chunks) | Implementiert (Warnung bei Fallback) |
| Leistungsüberwachung pro Engine (IOReport, ohne sudo) | Implementiert |
| 1 Warmup-Generierung pro Engine | Implementiert |
| Standard 3 Durchläufe (SPEC-Minimum) | Implementiert |
| Median als primäre Metrik (SPEC-Standard) | Implementiert |
| Gepoolte Intra-Prompt-Stddev (Bessel N-1) | Implementiert (korrigiert v1.5.0) |
| Modell-Entladung zwischen Engines | Implementiert |
| Adaptives Abkühlen (speicherdruckbewusst) | Implementiert |
| Plausibilitätsprüfungen (tok/s, TTFT-Grenzen) | Implementiert |
| Thermische Drosselungserkennung + Warnung | Implementiert |
| Thermische Drift-Erkennung (monotone Abnahme) | Implementiert |
| Engine-Version + Runner-Typ pro Ergebnis gespeichert | Implementiert (v1.5.0) |
| Universelles VRAM über ri_phys_footprint | Implementiert |
| Historische Regressionserkennung | Implementiert |
| Kreuzvalidierungsskript (3 Methoden verglichen) | Verfügbar (scripts/cross-validate-bench.py) |

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
| LM Studio (MLX) | 12.6 W | 12.6 W | 0.9% | 2.1% |
| Ollama (llama.cpp) | 15.6 W | 15.4 W | 1.3% | 4.1% |

Beide Engines bestätigen <1,5% durchschnittliche Abweichung mit 10/10 gepaarten Proben. Die ANE-Leistung betrug 0.000W über alle 20 Proben, was bestätigt, dass keine LLM-Engine derzeit die Neural Engine nutzt.

Das `--power`-Flag aktiviert zusätzliche Kreuzvalidierung, indem IOReport und `sudo powermetrics` gleichzeitig ausgeführt werden und beide Messwerte zum Vergleich gespeichert werden.

### Energieeffizienz

Die Energieeffizienz (tok/s pro Watt) wird als `tok_per_sec / gpu_watts` für jedes Benchmark-Ergebnis berechnet. Diese Metrik ermöglicht den Vergleich der Inferenzkosten über Engines und Hardware hinweg.

## Metadaten

Jedes Benchmark-Ergebnis speichert: engine, engine_version, model, model_format, model_quantization, hw_chip, os_version, thermal_level, thermal_speed_limit, power_watts, power_source, metrics_version. Dies ermöglicht fairen Regressionsvergleich und maschinenübergreifende Benchmarks.
