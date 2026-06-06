# Apple Silicon Agentic Inference Panel

> Vergleichendes Benchmark-Panel über Inferenz-Engines hinweg (llama.cpp, mlx-lm,
> LM Studio, Rapid-MLX, vLLM-MLX, oMLX, vMLX, Ollama), die Modelle der Qwen-3.6-
> Familie auf Apple Silicon M-Serie ausführen, gemessen mit
> `asiai bench --agentic-mode` und `asiai bench --burst-mode`.
>
> **Workload-Ziel**: Klasse Agent-Orchestrator — ~60-80 Tool-Calls pro Turn,
> identischer System-Prompt von ~7 KB, Benutzernachricht ändert sich pro Aufruf. Dies ist
> der schlimmste Fall für naives Prefix-Caching: eine echte Cache-Wiederverwendung über USER hinweg
> ist erforderlich, nicht nur Cache-auf-demselben-Prompt.
>
> **Die Throughput-Zahlen lesen**: Die Decode-Raten in Abschnitt 1 verwenden das Qwen3-
> Standard-Chat-Template (Thinking ON), enthalten also Reasoning-Tokens —
> der effektive Agent-Throughput auf einem Thinking-Modell ist niedriger. Thinking ist ein
> Trade-off pro Aufgabe (Caveat 1), kein globaler An/Aus-Schalter.
>
> Veröffentlicht 2026-06 · Beiträge und Korrekturen willkommen über
> [github.com/druide67/asiai](https://github.com/druide67/asiai/issues).

## ⚠️ Bekannte Caveats vor dem Weiterlesen

1. **Thinking-Modus ist ein Trade-off pro Aufgabe.** Mit dem Qwen3-Standard-Template
   (Thinking ON) emittieren Qwen 3.6 / Qwopus ~6-7× mehr Tokens, sodass die Decode-Zahlen
   in Abschnitt 1 **Reasoning-Tokens enthalten** und der effektive Agent-Throughput
   niedriger ist. Thinking ON ist **erforderlich** für schriftliche mehrteilige Deliverables (ein
   Modell mit Thinking OFF überspringt das Deliverable), **kostet** aber
   die Sauberkeit atomarer Tool-Calls (asiai misst ~100% saubere Tool-Calls mit Thinking OFF vs.
   ~77,8% mit Thinking ON + `preserve_thinking` ON, deterministisch über Läufe hinweg;
   `enable_thinking=on` + `preserve_thinking=off` ist unbrauchbar — ein deterministischer
   HTTP 500, sobald sich Reasoning im Kontext anhäuft). Setze Thinking **pro
   Aufgaben-Dimension**, nicht als ein globales Flag.
2. **Rapid-MLX und vLLM-MLX teilen sich eine Engine.** Rapid-MLX ist ein Community-Fork von
   `waybarrios/vllm-mlx`; sie erscheinen unten als separate Zeilen, weil sie sich
   in Version und Funktionen auseinanderentwickelt haben, aber der Prefix-Cache-Snapshot-Mechanismus ist
   dieselbe Abstammung.
3. **MTP: Qwen 3.6 hat einen echten Head; das Backend ist entscheidend.** Die offizielle
   `config.json` von Qwen 3.6 trägt `mtp_num_hidden_layers=1` (Qwen-Benennung — **nicht** der
   DeepSeek-Schlüssel `num_nextn_predict_layers`, sodass eine nur auf `nextn` basierende Prüfung fälschlich
   auf "kein Head" schließt). Einige requantisierte GGUF/MLX-Artefakte lassen die MTP-
   Tensoren fallen, behalten aber das Config-Flag — verifiziere die Tensoren im Gewichts-
   Index, nicht nur das Flag. llama.cpp natives MTP (`--spec-type draft-mtp`)
   **erfordert ein `-MTP-GGUF`**, das den Head einbettet; ein einfaches GGUF kann nicht draften.
   Veröffentlichtes mlx-lm führt den Head nicht als natives Speculative Decoding aus (PR
   [ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990) fügt
   ihn hinzu). LM Studio leitet GGUF durch sein von llama.cpp abgeleitetes Backend und MLX
   durch `mlx-engine`.
4. **Single-Pass-Messungen, keine Varianz-Berichterstattung** — die Zahlen in Abschnitt 1 / 2
   sind Einzelbeobachtungen. Varianz-Berichterstattung (Median + Min + Max
   über N Durchläufe) wird ab `--burst-runs N` unterstützt, aber das Rebench
   steht noch aus.

| Abschnitt | Thema | Status |
|---------|-------|--------|
| 1 | Single-Call-Performance | 🟡 8 cells, thinking-mode ON (decode includes reasoning tokens) |
| 2 | Paralleler Burst (30/60/80 parallele Calls) | 🟡 smoke cell + 2 partial concurrent points; no normalized 30/60/80 panel |
| 3 | Caches & Optimierungen | ✅ 8 engines covered |
| 4 | Speicher & Ressourcen | ✅ idle + under-load swap (+0) + footprint measured |
| 5 | Modellqualität (öffentliche Leaderboards) | 🟡 vendor/self-reported figures (llm-stats) |
| — | **asiai direct measurements** | ✅ dev-quality, thinking ablation, MTP, instruction-following |
| 6 | Operativ (Lizenz, Endpoints, Wartung) | ✅ 8 engines covered |
| 7 | Gewichtung der Qualitäts-Benchmarks | 🟡 default weighting, override via `--weights` planned |
| 8 | Eigener Long-Horizon-Eval (Vorschlag) | 🟡 scoped, not yet built |

---

## Section 1 — Single-call performance

> 🟠 **Mai-2026-Snapshot — indikativ, nicht die Referenzzahlen.** Diese Tabelle wurde
> im Mai erfasst (Thinking-Modus ON, Single-Pass) und ihre Quell-Fixtures wurden nicht
> erneut verifiziert. Für **aktuellen, reproduzierbaren Decode-Throughput** verwende den Abschnitt *asiai
> direct measurements* weiter unten (Juni, llama.cpp b9430, deterministisch). Wofür
> diese Tabelle zuverlässig ist, ist die **relative TTFT-/Prefix-Cache-Story**
> (Wiederverwendung über USER hinweg), nicht absolute t/s. Beachte insbesondere, dass die 123.9 t/s in
> Zeile 5 (LM Studio GGUF+MTP) direkt neben den Juni-Werten **llama.cpp Qwopus+MTP
> 123.3 t/s** liegen — der GGUF-Pfad von LM Studio ist ein von llama.cpp abgeleitetes Backend, sodass beide
> im Wesentlichen dieselbe Engine messen.

> ⚠️ **Mit Caveat 1 oben lesen**: jede Zahl in dieser Tabelle enthält die
> Tokens des Qwen3-Standard-Thinking-Modus (reasoning_content). Effektiver
> Agent-Throughput erfordert ein erneutes Ausführen mit
> `chat_template_kwargs={"enable_thinking": false}`. Die Spalte ist mit
> "decode (t/s)" beschriftet, nicht mit "effective throughput".
>
> Die Spalte "lower-bound estimate" ist `60 × (TTFT + max_tokens/decode)`,
> unter Annahme sequentiellen Dispatchs (den Rapid-MLX mit einem einzigen Slot erzwingt). Sie ist
> **keine** Produktions-Tick-Vorhersage — siehe [Section 7](#section-7) für den
> methodischen Caveat.
>
> 📌 **Getestete Versionen (Mai 2026)**: Rapid-MLX 0.6.66, LM Studio 0.4.14,
> llama.cpp b9270. Engine-Versionen wechseln wöchentlich auf Apple Silicon — behandle jede
> Zahl als datiert, nicht aktuell. (Der Abschnitt asiai-measurements verwendet llama.cpp
> b9430.)

| # | Engine | Model | Format | Warm decode (t/s) ¹ | TTFT warm (ms) | TTFT prefix-test median (ms) | TTFT cold (ms) | Lower-bound estimate (60 calls × single-call, optimistic) | Source fixture |
|---|--------|-------|--------|--------------------:|---------------:|----------------------------:|---------------:|----------------------------------------------------------:|----------------|
| 1 | Rapid-MLX 0.6.66 (fork of vllm-mlx) | Qwopus 3.6-35B-A3B-v1 (zaydiscold MLX-4bit) | MLX-4bit | **109.1** ¹ | 139 | **131** | 2074 | ~3.6 min | `cell-rapidmlx-qwopus35b.json` |
| 2 | Rapid-MLX 0.6.66 | Qwen 3.6-35B-A3B-UD (MLX-4bit) | MLX-4bit | 106.9 ¹ | 321 | 319 | 2095 | ~4 min | `cell-rapidmlx-35b-a3b.json` |
| 3 | Rapid-MLX 0.6.66 | Qwopus 3.6-27B-v2 (Jackrong MLX-4bit) | MLX-4bit | 31.8 ¹ | 323 | 323 | 8647 | ~13 min | `cell-rapidmlx-qwopus.json` |
| 4 | Rapid-MLX 0.6.66 | Qwen 3.6-27B-UD (MLX-4bit) | MLX-4bit | 20.5 ¹ | 527 | 527 | 8954 | ~23 min | `cell-rapidmlx-full-27bud.json` |
| 5 | LM Studio 0.4.14 (GGUF backend) ² | Qwen 3.6-35B-A3B-MTP (Unsloth GGUF) | GGUF Q4 + MTP | **123.9** ¹ ² | 309 | 5965 | 6063 | ~3.5 min warm / ~9.2 min prefix-changing | `cell-lmstudio-mtp-qwen35b.json` |
| 6 | LM Studio 0.4.14 (GGUF backend) ² | Qwopus 3.6-35B-A3B-v1 (Jackrong GGUF) | GGUF Q4_K_S | 105.6 ¹ | 292 | 5785 | 5624 | ~3.5 min warm / ~9.6 min prefix-changing | `cell-lmstudio-qwopus35b.json` |
| 7 | llama.cpp b9270 | Qwen 3.6-35B-A3B (UD Q5_K_XL) | GGUF Q5_K_XL | 80.9 ¹ | 3000 | 3000 | n/a | ~8 min | (baseline reference) |
| 8 | llama.cpp b9270 | Qwopus 3.6-27B-v2 (Jackrong GGUF Q4) | GGUF Q4 | 25.3 ¹ | 13000 | 13000 | n/a | ~30 min | (baseline reference) |

¹ **Thinking-Modus-Caveat**: Zahlen mit dem Standard-Chat-Template erfasst
(Thinking ON). Der reale effektive Throughput bei Tool-Call-Workloads liegt
typischerweise bei 4-12 t/s auf Qwopus/Qwen3.6-Finetunes, wenn Reasoning-Tokens
die Ausgabe um das 6-7-Fache aufblähen. Um diese Decode-Zahlen zu reproduzieren, übergib
`chat_template_kwargs={"enable_thinking": false}` in der Request-Payload.

² **LM Studio Backend**: Zeilen 5-6 verwendeten eine GGUF-Datei, die durch
das von llama.cpp abgeleitete Backend von LM Studio geleitet wird (NICHT die MLX-Runtime `mlx-engine`).
Die MTP-Behauptung in Zeile 5 spiegelt die Implementierung dieses Backends wider, nicht
das Speculative Decoding von mlx-engine. Veröffentlichtes mlx-lm führt den MTP-Head nicht
als natives Speculative Decoding aus (sein `sanitize()` hat MTP-Gewichte historisch
während der Konvertierung verworfen; native Unterstützung liegt in PR
[ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990)),
sodass ein hypothetisches MTP-Modell im MLX-Format auf dem veröffentlichten
mlx-engine ebenfalls keinen Vorteil hätte.

### Wichtige Beobachtungen

- Beim realistischen Agent-Muster (identisches System + wechselnde Benutzer-Prompts)
  liefert **Rapid-MLX + Qwopus 35B-A3B-v1** 131 ms median TTFT prefix-test
  vs. 5965 ms für das LM Studio GGUF Backend (**~44× schneller**). Der Vorteil
  kommt vom vllm-mlx-Prefix-Cache-Snapshot-Mechanismus (siehe Abschnitt 3
  für die Quellcode-Disambiguierung).
- Beim reinen Decode-Throughput (Warm-Pfad) verzeichnet das **LM Studio GGUF Backend mit
  Unsloth MTP** 123.9 t/s vs. Rapid-MLX 109.1 t/s (+13.5%). Dieses Delta
  spiegelt das Speculative Decoding des von llama.cpp abgeleiteten Backends von LM Studio auf einem
  GGUF mit MTP-Head wider, nicht einen Apple-MLX-Gewinn (veröffentlichtes mlx-engine
  führt den Head nicht aus — siehe Fußnote 2). Auf dem nativen llama.cpp-Pfad ist MTP
  netto positiv auf dem MoE 35B-A3B — siehe Abschnitt 3.
- Alle Konfigurationen der `Qwen 3.6 family` (hybrid DeltaNet + full-attention) scheitern
  am Prefix-Cache über USER hinweg **außer Rapid-MLX**, das einen RNN-State-
  Snapshot behält. Auf llama.cpp / LM Studio GGUF `llama_memory_can_shift=false`; auf
  mlx-lm / oMLX kann der recurrent/SSM-State nicht an einer beliebigen Token-
  Grenze geteilt werden. Der Upstream-llama.cpp-Fix für diese Architektur ist nicht gemergt
  ([#23121](https://github.com/ggml-org/llama.cpp/pull/23121) geschlossen;
  `preserve_thinking` adressiert ihn nicht,
  [#22615](https://github.com/ggml-org/llama.cpp/issues/22615)).
- **Single-Slot-Serialisierung bestätigt**: Smoke-Burst-Test (Abschnitt 2)
  zeigt, dass Rapid-MLX 0.6.66 parallele Calls FIFO serialisiert (p50 ≈ p95 ≈ max
  bei burst=5). Für 60-80 Calls/Turn skaliert die gesamte Wall-Time linear mit der
  Burst-Größe auf dieser Engine. Eine Multi-Slot-Engine (z. B. llama.cpp
  `--parallel N`) würde sich anders verhalten, aber `--parallel N` auf Qwen3.6
  hybrid deaktiviert den Prefix-Cache pro Slot (architektonische Einschränkung).

---

## Section 2 — Concurrent burst (30/60/80 parallel calls)

> Muster: 30 bis 80 parallele `POST /v1/chat/completions`-Calls, abgefeuert innerhalb eines
> ~200 ms Fensters. Simuliert eine Agent-Loop, die mehrere MCP/Tool-Calls parallel
> dispatcht. Nativ gemessen über `asiai bench --burst-mode`.
>
> 🟡 **Status**: 1 Smoke-Cell gemessen (Rapid-MLX burst-5). Vollständiges Panel steht aus.

### Smoke cell (Rapid-MLX 0.6.66 + Qwopus 35B-A3B-v1, burst=5)

| burst N | wall-time (s) | p50 latency (ms) | p95 latency (ms) | max latency (ms) | agg throughput (t/s) |
|--------:|--------------:|-----------------:|-----------------:|-----------------:|---------------------:|
| 5 | 2.8 | 2615 | 2792 | 2812 | 88.8 |

**Smoke-Finding**: `p50 ≈ p95 ≈ max` zeigt an, dass die 5 Calls **serverseitig
serialisiert** wurden (Single-Slot-Engine). Rapid-MLX 0.6.66 scheint kein
paralleles Request-Scheduling zu unterstützen — Calls reihen sich intern FIFO ein. Zu validieren auf der Skala von 60/80
Calls.

### Vollständiges Concurrent-Panel — noch nicht gemessen

Ein normalisiertes 30/60/80-Concurrent-Panel wurde nicht ausgeführt (die Messungen hier sind
sequentieller Agentic-Mode, kein paralleler Burst). Die zwei partiellen Concurrent-Datenpunkte,
die anderswo existieren:

- **TurboQuant** (K=`q8_0` V=`turbo2`, Qwen3-4B, M4 Pro): **+9% aggregiert bei
  4-parallel** (68.5 → 74.7 t/s), obwohl der Single-Stream −8% beträgt — die KV-
  Kompression kauft den parallelen Headroom zurück.
- **oMLX** Continuous Batching (mlx-lm `BatchGenerator`): **×1.8 aggregiert bei
  burst-8** (12.8 → 22.9 t/s), aber es **kollabiert bei burst-30** (17.3 t/s), sobald ein
  27B-dense RAM in den Swap sättigt — 0 Crashes.

Ein dediziertes Burst-Mode-Panel über alle Engines hinweg wird zurückgestellt.

---

## Section 3 — Caches & optimizations

| # | Couple | Cache reuse cross-USER | Snapshot persists cross-restart | MTP support | MTP accept rate | TurboQuant compat | KV cache native types | Native parallel slots |
|---|--------|---|---|---|---|---|---|---|
| 1 | Rapid-MLX + Qwopus 35B-A3B-v1 | ✅ YES (RNN-state snapshot, see ³ below) | ✅ persistent in `~/.cache/vllm-mlx/` | ❌ released MLX runtime doesn't run the MTP head as speculative decode (mlx-lm PR #990 pending) | n/a | ❌ MLX only | MLX native (no quant flag exposed) | ⚠️ single slot (smoke burst confirms FIFO serialization) |
| 2 | Rapid-MLX + Qwen 35B-A3B-UD | ✅ YES ³ | ✅ persistent | ❌ | n/a | ❌ | MLX native | ⚠️ single slot |
| 3 | LM Studio + Qwen 35B-A3B-MTP | ❌ NO (architectural hybrid limitation) | n/a | ✅ via mlx-engine v1.8.1 | **82.1 %** (on coding task) | ❌ | mlx-engine v1.8.1 (4bit MLX) | configurable via GUI |
| 4 | LM Studio + Qwopus 35B-A3B-v1 | ❌ NO | n/a | ❌ no heads | n/a | ❌ | mlx-engine v1.8.1 (Q4_K_S GGUF) | configurable via GUI |
| 5 | llama.cpp + Qwen 3.6-35B-A3B | ❌ NO (architectural hybrid limitation) | n/a | ✅ `--spec-type draft-mtp` on a `-MTP-GGUF` (a plain GGUF cannot draft). Net-positive on the MoE 35B-A3B — asiai measures **+38%** decode (base) / **+17%** (Qwopus) on M5 Max (see § asiai measurements) | benefit = intra-session decode delta (no acceptance rate logged) | ✅ turbo2/3/4 V cache | `fp16`, `q8_0`, `q5_0`, `turbo2/3/4` | ⚠️ `--parallel N` works mechanically but **disables prefix cache per slot on hybrid arch** (each slot owns its KV, the `--cache-reuse N` flag is already silently disabled here). Use with caution. |
| 6 | mlx-lm | ❌ NO (PRs #923, #188, #192 pending upstream) | n/a | ❌ broken on hybrid arch | n/a | ❌ | MLX native | ❌ (single slot) |
| 7 | oMLX | ❌ NO (tool calling lost post-cache-hit, issue #825) | partial | ❌ | n/a | ❌ | MLX native + tiered SSD cache | ❌ |
| 8 | vLLM-MLX (`waybarrios`, upstream of Rapid-MLX) | ⚠️ trie prefix-cache, no documented hybrid/DeltaNet support (Rapid-MLX rows 1-2 add the RNN-state snapshot on top) | n/a | ⚠️ MTP added in prerelease 0.4.0rc1 | n/a | ❌ | MLX + paged-attention | ✅ |

³ **Rapid-MLX-Prefix-Cache**: der Cache speichert hybrid-attention KV-Slabs +
RNN-State-Snapshots, gekeyt pro `<repo>--<sys_prompt_hash>` und persistiert unter
`~/.cache/vllm-mlx/`. Die beobachteten ~131 ms TTFT prefix-test sind ein In-RAM-KV-Slab-
Reattach plus der geänderte User-Forward-Pass, kein From-Disk-Reload.

**oMLX Large-Context-Cache.** Der 2-stufige Paged-SSD-KV-Cache von oMLX verwandelt einen 55K-Token-
Prefill von ~115 s in ~**3.5 s** TTFT bei einem Same-Prompt-Cache-Hit (×33; 55,296 /
55,837 Tokens gecacht). Bei kleinen Prompts (~7.5K) gibt es keinen Vorteil (~2-5 s, =
mlx-lm) und das Decode liegt bei ~19 t/s (kein Raw-Speed-Gewinn). Dies ist Same-Prompt-Wiederverwendung, nicht
über USER hinweg (was oMLX nicht macht); Cross-Restart-Persistenz ist dokumentiert, aber
noch nicht A/B-getestet.

**TurboQuant KV-Kompression** (llama.cpp). K=`q8_0` V=`turbo2` schneidet das KV-RAM um ~**28%**
(22.9 → 16.4 GB auf einem 4B-Modell, M4 Pro) bei unveränderter Tool-Call-Gültigkeit (10/10),
und gewinnt **+9% aggregiert bei 4-parallel** trotz −8% Single-Stream. Das symmetrische
K=`turbo3` V=`turbo3` erreicht ~−56% RAM, verschlechtert aber die Qualität (Early-Stop,
Wiederholung) — das asymmetrische `q8_0`/`turbo2` ist die brauchbare Konfiguration.

---

## Section 4 — Memory & resources (Apple Silicon M5 Max 128 GB)

| # | Couple | Working-set RAM (GB) | Disk footprint (GB) | Swap Δ idle | Swap Δ under load | SOLO required? | Cohabitation safe? |
|---|--------|---|---|---|---|---|---|
| 1 | Rapid-MLX + Qwopus 35B-A3B-v1 | ~22 | 19.9 (MLX-4bit) | +0 | **+0 MB** | ⚠️ SOLO (cohabit thrash to 0.4 t/s) | ❌ |
| 2 | Rapid-MLX + Qwen 35B-A3B-UD | ~24 | 20.0 (MLX-4bit) | +0 | **+0 MB** | ⚠️ SOLO | ❌ |
| 3 | LM Studio + Qwen 35B-A3B-MTP | 21.6 | 23.2 (Q4 + MTP heads) | +0 | **+0 MB** | not tested | not tested |
| 4 | LM Studio + Qwopus 35B-A3B-v1 | 18.5 | 19.9 (Q4_K_S) | +0 | **+0 MB** | not tested | not tested |
| 5 | llama.cpp + Qwen 3.6-35B-A3B (reference) | ~16 | ~16 (Q5_K_XL) | +0 | **+0 MB** | ❌ | ✅ with `--parallel 2/3` |

> **"Unter Last"** = der 8-Phasen-Agentic-Bench einschließlich eines 50K-Token-Prefills (der
> schwerste *sequentielle* gemessene Speicherstress), M5 Max 128 GB, SOLO: Swap-Delta
> **0 MB / 0 swapouts für jede Engine** — Modell + KV passen in den freien/inaktiven Speicher
> mit >100 GB Headroom. Dies ist Sequential-Load-Speicher, **nicht** 60-Concurrent-
> Speicher (siehe Abschnitt 2). Working-Set-RAM ist eine Schätzung; der gemessene RSS enthält
> mmap'd GGUF / wired MLX pages, sodass der tatsächliche inkrementelle Footprint niedriger ist (der
> MTP-Head fügt ~+3 GB hinzu).

### Beobachtungen

- **Rapid-MLX erfordert SOLO-Betrieb auf der GPU**: Kohabitation mit einer anderen
  aktiv dekodierenden Engine löst ein Swap-Delta von 5.4 → 14.2 GB und einen Decode-
  Kollaps auf 0.4 t/s aus. Starte keine zweite Engine auf derselben Apple-Silicon-
  GPU.
- Der Disk-Footprint von **LM Studio MTP** ist +13 % vs. Q4_K_S ohne MTP-Heads, aufgrund
  der MTP-Gewichtsblöcke. Vernachlässigbare Kosten relativ zum +17 % Decode-Gewinn.
- Auf M5 Max 128 GB Unified Memory: jede getestete 35B-A3B-Konfiguration lässt
  mehr als 100 GB Headroom nach dem Laden — RAM ist nicht der limitierende Faktor.
- Auf M4 Pro 64 GB: `Q5_K_XL` passt **nicht** neben Hilfsmodelle (Swap-
  Thrash in der Produktion beobachtet). `Q4_K_S` passt.

---

## Section 5 — Model quality

> Die öffentlichen Benchmark-Zahlen hier sind **vendor / self-reported** und von
> Leaderboards (llm-stats) aggregiert, nicht unabhängig verifiziert. Kreuzvalidiere bei
> [llm-stats](https://llm-stats.com) · [LiveBench](https://livebench.ai) ·
> [SWE-bench](https://swebench.com), bevor du dich auf sie verlässt. asiais eigene direkte
> Messungen auf Apple Silicon stehen im nächsten Abschnitt.
>
> Nur vom Autor stammende Behauptungen (Jackrong/Qwopus, Unsloth-Self-Eval) werden separat gekennzeichnet
> und aus den öffentlichen Leaderboard-Spalten herausgehalten.
>
> 🔴 **Kritisches Finding**: der auf mehreren Community-Model-Cards zitierte Benchmark "Hessling agentic"
> ist **nicht unabhängig reproduzierbar** — 16 Prompts,
> einzelner Kurator, keine neutrale Leaderboard-Integration. Alle drei Berater
> empfehlen, ihn nur als Smoke-Test zu behandeln.

### Open-Weight Qwen 3.6 Basismodelle

> Öffentliche Leaderboard-Zahlen (llm-stats), self-reported. Das 27B-dense übertrifft
> das 35B-A3B MoE auf SWE-bench — konsistent mit asiais eigenem Dev-Quality-Finding
> unten (das MoE-Base ist dasjenige, das auf den Tool-Call-Empty-Object-Bug stößt). MTP-
> Heads sind ein Decode-Speed-Feature und ändern nicht die Qualitäts-Scores eines Modells.

| Model | Architecture | SWE-bench Verified | GPQA Diamond | MMLU-Pro | Terminal-Bench 2.0 | BFCL |
|-------|--------------|-------------------:|-------------:|---------:|-------------------:|------|
| Qwen 3.6-35B-A3B-Instruct | MoE 35B / 3B active | 73.4% | 86.0% | 85.2% | 24.6% | absent from board |
| Qwen 3.6-27B-Dense Instruct | Dense 27B hybrid | 77.2% | 87.8% | 86.2% | 59.3% (vendor) | absent from board |

> Terminal-Bench **2.0** ist weitaus schwerer als das ältere Terminal-Bench v1 (Community-
> Cards nennen ~51.5% für das 35B-A3B auf v1); die 24.6% hier sind die 2.0-Generation.

### Qwopus 3.6 Familie — nur vom Autor berichtet, **nicht unabhängig verifiziert**

Die von Jackrong auf HuggingFace veröffentlichten Qwopus-3.6-Finetunes behaupten
substanzielle Gewinne gegenüber dem Qwen-Base. Stand Mai 2026 wurden diese Behauptungen
**nicht unabhängig** auf neutralen Leaderboards **reproduziert**. Als
experimentell behandeln, bis BFCL- / SWE-bench-Reruns durch eine dritte Partei
verfügbar sind.

| Model (author claims) | MMLU-Pro | SWE-bench Verified | Hessling agentic (16 prompts) |
|-----------------------|---------:|-------------------:|------------------------------:|
| Qwopus 3.6-35B-A3B-v1 (Jackrong) | claimed 88+ | claimed 75+ | claimed 88.6 ⚠ non-reproducible |
| Qwopus 3.6-27B-v2 (Jackrong) | claimed 87.43 | claimed 75.25 | n/a |

⚠ Der auf den Jackrong-Model-Cards zitierte Benchmark "Hessling agentic"
scheint eine kuratorspezifische 16-Prompt-Evaluation ohne neutrale
Leaderboard-Integration zu sein. Alle drei abgefragten Berater (Grok-4, GPT-5,
Gemini Advanced) empfehlen, ihn nur als Smoke-Test zu behandeln.

### Frontier-Anker (Mitte 2026)

> Alle Zahlen sind **vendor / self-reported**, aggregiert von llm-stats — keine sind
> dort unabhängig verifiziert. **Terminal-Bench 2.0** ist die Ausnahme (das
> tbench-Team führt Submissions erneut aus; Zeilen sind Peak-Agent×Model-Scores). GPQA sind
> Vendor-"Diamond"-Zahlen und das Set ist nahezu gesättigt — als approximativ behandeln.

| Model | SWE-bench Verified | GPQA Diamond | MMLU-Pro | Terminal-Bench 2.0 | Source |
|-------|-------------------:|-------------:|---------:|-------------------:|--------|
| Claude Opus 4.8 | 88.6% | 93.6% | n/a | — (no TB submission) | llm-stats / Anthropic |
| Claude Opus 4.7 | 87.6% | 94.2% | n/a | **90.2%** | llm-stats / tbench |
| Claude Sonnet 4.6 | 79.6% | 89.9% | n/a | 53.4% | llm-stats / tbench |
| GPT-5.5 | n/a\* (SWE-Pro 58.6%) | 93.6% | n/a | 84.7% | OpenAI / tbench |
| GPT-5 (base) | 74.9% | 85.7% | n/a | 49.6% | llm-stats / tbench |
| Gemini 3.1 Pro | 80.6% | ~94.4% | n/a | 80.2% | llm-stats / tbench |
| DeepSeek-V4-Pro-Max | 80.6% | 90.1% | 87.5% | n/a | vendor (DeepSeek) |
| Llama-3.3-70B-Instruct | n/a | n/a | 68.9% | n/a | Meta (baseline) |

\* GPT-5.5 hat keinen öffentlichen SWE-bench-*Verified*-Score (OpenAI berichtet SWE-bench Pro
Public 58.6%); die kursierende Zahl "88.7% SWE-bench" ist auf keiner Primärquelle. Anmerkung: **Qwen 3.6 hat kein 235B-A22B** — die offene Familie ist das 27B-dense
und das 35B-A3B (unten); das 235B-A22B ist die vorherige Qwen3-Generation.

### Open-Weights-Baselines derselben Klasse

| Model | MMLU-Pro | SWE-bench Verified | Notes |
|-------|---------:|-------------------:|-------|
| Llama-3.3-70B-Instruct | ~75-80 | ~40-50 | Older but well-characterized baseline |
| Mistral Codestral 25.05 / Devstral | high (coding-specialized) | medium-high | Strong editor-style completion fidelity, weaker on reasoning |
| GLM-4.6-Coder (Zhipu) | vendor claims very high | disputed | Significant skepticism around evaluation methodology (consensus) |

### Für diese Entscheidung deprecate Qualitäts-Benchmarks

- **HumanEval / HumanEval+** — in 2026 gesättigt, alle Frontier-Modelle über 90 %, kein Signal übrig.
- **GSM8K** — gesättigt, kein Signal für Coding-Agents.
- **MMLU (original)** — abgelöst durch MMLU-Pro.
- **Author-reported "Hessling agentic" 16-prompt** — nicht reproduzierbar, nur als Smoke-Test behandeln.

### Offene Qualitätsfragen (Forschungslücken)

1. **Quality-per-GB-RAM-Benchmark**: kein Standard existiert. Vorgeschlagene Proxy-Formel:
   `AgentScorePerGB = (0.5·SWE + 0.3·BFCL + 0.2·TerminalBench) / RAM_resident`.
2. **Long-Horizon-Stabilität (60+ Tool-Calls)**: die nächstgelegenen existierenden Benchmarks sind
   τ-bench, PencilPuzzleBench (>1000 turns), MultiAgentBench, TRAIL. Keiner
   von ihnen misst spezifisch "Schema-Korrektheit und strategische Kohärenz über
   60-80 sequentielle Tool-Calls hinweg" — diese Benchmark-Lücke wird von allen
   drei Beratern anerkannt.
3. **Conversion-aware Evaluation (MLX-4bit vs. GGUF Q4_K_M vs. Q5_K_XL)**: kein
   standardisiertes Leaderboard. Community-Berichte divergieren — einige behaupten, MLX-4bit
   bewahre die Tool-Calling-Stabilität schlechter als GGUF Q5_K_M, andere sagen das
   Gegenteil. **Praktischer Rat**: Führe deinen eigenen Produktions-Workload gegen
   jeden Quant aus, bevor du dich festlegst.
4. **Qwopus 3.6 Familie Qualitätsvalidierung**: benötigt Drittpartei-BFCL- +
   SWE-bench-Reruns. Autorenbehauptungen sollten keine Produktionsentscheidungen treiben.

---

## asiai direct measurements — Apple Silicon, mid-2026

> Was die obigen öffentlichen Leaderboards nicht zeigen: Messungen, die asiai direkt
> auf Apple Silicon ausgeführt hat (M5 Max 128 GB im High Power Mode, M4 Pro 64 GB), llama.cpp
> b9430, deterministisch (temp 0), auf der öffentlichen Qwen-3.6-Familie und dem
> Opus-destillierten **Qwopus**-Finetune. Caveat: der absolute cross-session Throughput auf
> dem M5-Laptop ist ±15% (thermisch/Last); nur die **intra-session ±MTP-Back-to-Back-
> Deltas** sind eng, und M5↔M4-Absolutwerte sind nicht vergleichbar (unterschiedliche Quants).

### Dev-quality / tool-call (`asiai bench --code`)

- Das **Base Qwen 3.6-35B-A3B (MoE)** kollabiert `edit_file.edits` zu einem leeren
  Objekt auf dem Deep-Context-Turn — **3/3 runs, at both Q4_K_S and Q5_K_XL**, gleiches
  Chat-Template. Tool-Call clean **87.5%**, edit-turns clean **66.7%**. Es ist das
  Tool-Call-Generierungsverhalten des MoE-Base, nicht der Quant und nicht das Template.
- Das **dense 27B** (Q5_K_XL) und **Qwopus-35B-A3B** (Q4_K_S) erzielen beide **100%
  clean / 0 bugs** — Qwopus erreicht die Tool-Call-Zuverlässigkeit des dense-27B bei der
  ~4× Decode-Rate des MoE.
- Unter einer härteren Tool-Call-Stress-Suite bleibt Qwopus bei **100% / 0**, während das dense
  27B auf **88.9% / 3 bugs** fällt (derselbe Empty-Object-Fehler). Aber bei einer
  Expression-Evaluator-Falle (Präzedenz von `**` vs. unärem Minus) ist das **dense 27B
  korrekt und Qwopus falsch** — sie teilen sich. (Recovery Rate ist gewichtssensitiv
  und verrauscht — keine Schlagzeile.)

### Thinking ablation (`asiai bench --thinking-ablation`, Qwopus-35B-A3B, 3 deterministic runs)

| Config | Tool-call clean | Note |
|--------|----------------:|------|
| `enable_thinking=off` | **100%** | the only fully-clean config |
| `enable_thinking=on` + `preserve_thinking=on` | 77.8% | 2/9 turns dirty |
| `enable_thinking=on` + `preserve_thinking=off` | 11.1% | turns 2-8 → HTTP 500 (context corruption); avoid |

### MTP throughput (`--spec-type draft-mtp`, warm decode, intra-session ±MTP)

| Model / hardware | MTP off | MTP on | Δ |
|------------------|--------:|-------:|--:|
| 35B-A3B base · M5 Max | 85.5 t/s | **118.4 t/s** | **+38%** |
| Qwopus 35B-A3B · M5 Max | 105.7 t/s | 123.3 t/s | +17% |
| 27B-dense · M5 Max | 23.8 t/s | 28.0 t/s | +18% |
| Qwopus 27B · M5 Max | 25.9 t/s | 26.7 t/s | +3% |
| 35B-A3B MoE · M4 Pro | 36.3 t/s | 44.6 t/s | +23% |
| 27B-dense · M4 Pro | 10.4 t/s | 9.7 t/s | **−6%** |

Der MTP-Gewinn skaliert als **(MoE > dense) × (M5 > M4)** — stark positiv auf dem MoE,
marginal-bis-negativ auf dem langsamen Dense-Pfad (der Draft-Overhead wird nicht amortisiert). Der MTP-Head des Qwopus-Finetunes ist zudem schwächer als der des Base-Modells (Qwopus 27B +3% / 35B +17%, gegenüber Base 27B-dense +18% / 35B-A3B +38%) — Finetuning erodiert den Draft-Head.
Das MLX-seitige MTP (mlx_vlm) ist disqualifiziert: es bricht langen Kontext (leere Ausgabe,
75% valid). Schlagzeile: das 35B-A3B MoE + MTP auf llama.cpp hält **~118 t/s**
Decode auf M5 Max (~44 t/s auf M4 Pro), ~4× das 27B-dense, bei ~1.5 tok/s/W, TTFT
~62 ms, 100% Output-Gültigkeit.

### Instruction-following (`asiai bench --instruct`, research-brief)

Der Thinking-Trade-off hat Biss bei mehrstufigen Deliverables: mit
`enable_thinking=false` erledigt Qwopus-35B die Tool-Arbeit, liefert aber den angeforderten
mehrteiligen Brief in **0%** der Fälle (es stoppt beim sekundären Schritt); mit
Thinking on liefert das Base-Modell ihn zu **100%** (5/5 Abschnitte). Dies zieht in die
entgegengesetzte Richtung zum Tool-Call-Ergebnis oben — Thinking-off ist am saubersten für atomare
Tool-Calls, unterdrückt aber schriftliche Deliverables — weshalb asiai Thinking
**pro Aufgaben-Dimension** setzt, nicht als einen globalen Schalter.

### Perfektionistische Recherche-Schleife (`asiai bench --instruct loop-search`)

Single-Turn-IFEval und research-brief sättigen über diese Modelle hinweg bei 100%,
sodass keines die *perfektionistische Recherche-Schleife* zutage fördert: ein Modell,
das ein mehrdeutiges, nicht bestätigbares Suchresultat nicht akzeptieren will und
semantisch äquivalente Anfragen erneut absetzt, bis ein No-Progress-Guardrail es
stoppt, ohne je zu liefern. Ein `loop-search`-Sweep (9 Konfigurationen, M5, b9430,
Thinking on/off, zwei Mehrdeutigkeitsmodi) isoliert sie:

- Das **35B-A3B MoE dreht bis zum Cap in Schleifen** — für **sowohl die Basis als
  auch das Qwopus-Finetune, in Q4 und Q8 gleichermaßen**. Der höhere Quant behebt es
  nicht, die Schleife ist also **architektonisch zum A3B MoE**, kein Quant-Artefakt.
- Das **Dense-27B dreht nie in Schleifen** (Q4 / Q5 / Q8): es akzeptiert das
  mehrdeutige Resultat und schreibt das Briefing.

Der Throughput-Spitzenreiter (das MoE, ~118-123 t/s) und der Spitzenreiter der
agentischen Eignung (das Dense-27B, ~25 t/s) sind also *verschiedene Modelle*. Für
ein Harness wie den Hermes Agent von NousResearch kann Schleifenresistenz den
Roh-Decode überwiegen — das schnellste Modell ist nicht immer der richtige Agent.
(Dies ist die Umkehrung des Tool-Call-Ergebnisses, wo das MoE-Finetune der robustere
Agent war: **Eignung ist pro Fehlermodus, also miss mehrere.**)

---

## Section 6 — Operational

> 📌 Capability-Snapshot (Mitte 2026). Engine-Versionen wechseln wöchentlich auf Apple
> Silicon — diese Zellen sind Point-in-Time, keine versionsgepinnte Garantie.

| # | Engine | License | Stream OAI-compat | `/v1/models` | `/health` | `/metrics` (Prometheus) | Tool calling | Auto-DL HF | Persisted prefix cache | Maintainer activity |
|---|--------|---------|---|---|---|---|---|---|---|---|
| 1 | Rapid-MLX 0.6.66 | Apache-2.0 | ✅ | ✅ | ✅ (HTML page) | ❌ (logs only) | ✅ | ✅ HF Hub auto-DL on serve | ✅ `~/.cache/vllm-mlx/prefix_cache/` | community (raullenchai) |
| 2 | LM Studio 0.4.14 | proprietary | ✅ | ✅ | partial (websocket) | ❌ | ✅ | ✅ via `lms get` CLI | ❌ | Element Labs |
| 3 | llama.cpp b9270 | MIT | ✅ | ✅ | ✅ | ✅ `--metrics` | ✅ | manual (GGUF on disk) | ❌ (`--cache-reuse N` arch-disabled on hybrid) | ggerganov very active |
| 4 | mlx-lm | MIT | ✅ | ✅ | ✅ | ❌ | partial | ✅ HF auto | ❌ | Apple ml-explore active |
| 5 | oMLX | MIT | ✅ | ✅ | ✅ | ❌ | ✅ (caveat: post-cache-hit bug) | ✅ | partial (tiered SSD) | jundot active |
| 6 | vLLM-MLX | Apache-2.0 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ paged-attention | vllm-project active |
| 7 | vMLX (Mamba/SSM) | Apache-2.0 | ✅ | ✅ | ✅ | partial | untested | partial | untested | community |
| 8 | Ollama | MIT | ✅ | partial | ✅ `/api/version` | ❌ | partial | ✅ `ollama pull` | ❌ | Ollama Inc. very active |

---

## Section 7 — Quality benchmark weighting for agentic-coding workloads

> Dies ist die **asiai-Standardgewichtung** für einen Workload der Orchestrator-Klasse
> (60-80 sequentielle Tool-Calls pro Turn, schema-validierte Ausgabe, Long-Context-
> System-Prompts). Sie ist von drei Frontier-LLM-Beratungen
> (Grok-4, GPT-5, Gemini Advanced) informiert, die im Mai 2026 abgefragt wurden, ist aber **kein Community-
> Konsens** — als Ausgangspunkt behandeln, nicht autoritativ. Override über
> ein zukünftiges `--weights`-Flag (geplant).

| Benchmark | What it measures | Why it matters here | Consensus weight |
|-----------|------------------|---------------------|-----------------:|
| **SWE-bench Verified** | Real GitHub repo navigation + patch + test repair | Best proxy for code-editing fidelity inside an agent loop | **35 %** |
| **BFCL v3** (Berkeley Function Calling Leaderboard) | Multi-turn function-call accuracy, argument fidelity, schema adherence | Direct predictor of orchestrator stability across many tool calls | **25 %** |
| **TerminalBench 2.0 / MCP-Atlas** | CLI and MCP task execution autonomy | "Does the agent survive 40+ actions without derailing" | **20 %** |
| **LiveBench Coding** | Contamination-resistant coding tasks (refreshed monthly) | Catches train-test leakage that inflates HumanEval-class scores | **10 %** |
| **Custom long-horizon stability eval** | 60-80 sequential tool calls with cumulative context growth, malformed JSON recovery | The benchmark that does not exist yet in public form — see Section 8 | **10 %** |

### Bewusst aus der Gewichtung herausgenommene Benchmarks

- MMLU-Pro, GPQA Diamond, HumanEval+ — nützlich als allgemeines Capability-Signal,
  aber **schwach korreliert** mit Agent-Loop-Zuverlässigkeit laut Evidenz von 2026.
  Frontier-Lab-Bestätigungen zeigen, dass Single-Shot-Reasoning-Scores nicht mehr
  autonomen Agent-Erfolg mit ausreichender Granularität vorhersagen.
- Vom Autor berichtete Aggregate ohne Drittpartei-Reruns (Jackrong Hessling,
  Unsloth-Self-Eval, GLM-4.6-Coder-Vendor-Behauptungen).

---

## Section 8 — Custom "endurance" benchmark proposal (research opportunity)

Alle drei Berater konvergieren auf dieselbe Lücke: **der Benchmark, der einen
Orchestrator-Workload am besten charakterisieren würde, existiert öffentlich noch nicht**. Einen zu bauen,
ist der einzige Weg, das fehlende Signal zu bekommen.

### Vorgeschlagener Scope

- **80 sequentielle Tool-Calls** pro Trajektorie
- **Schema-Validierung bei jedem Turn** (strict JSON / structured output)
- **Kumulatives Kontextwachstum** (10K → 50K Tokens über die Trajektorie)
- **Interruption- / Recovery-Tests** (Mid-Trajectory-Cancel + Resume)
- **Malformed-XML/JSON-Recovery** (korrigiert sich der Agent selbst?)
- **Repo-Edit-Persistenz** (halten die bei Turn N gemachten Edits noch bei Turn 60?)

Dies steht auf der asiai-Roadmap (ein Long-Horizon-Endurance-Mode, nach dem Burst-Mode).
Falls gebaut, wäre es der erste öffentliche Benchmark in dieser spezifischen Nische.

---

## Methodology

- **Hardware**: MacBook Pro M5 Max 128 GB Unified Memory, macOS 26.4.1.
- **Workload**: Orchestrator-Klasse — System-Prompt ~7 KB, User-Prompt ~150-200
  Tokens, 60-80 Calls pro Turn.
- **Gemessene Phasen** (single-call, agentic-mode v1.6.0):
  - `cold`: erster Call nach frischem Start
  - `warm`: exakt gleicher Prompt wie cold (warm cache)
  - `prefix-test-1/2/3`: identisches System, User wechselt — misst Cache-Wiederverwendung über USER hinweg
  - `cold-prefix`: identisches System, nach Neustart — misst persistenten Cache
- **Verdict Prefix-Cache-Wiederverwendung**: `YES` wenn `median(prefix-test) / cold < 0.2`,
  sonst `NO`.
- **Anti-Bias-Maßnahmen**: SOLO-Modus (keine kohabitierenden Engines), thermische Idle-
  Baseline, mmap-Warm-up-Phase.
- **Quality Gates** (auto-getrackt von asiai bench):
  - `early_stop`: mindestens 2 Läufe mit `<0.5×` median completion
  - `memory_pressure`: swap delta `>500 MB` ODER swapouts delta `>1000`
  - `duplicate_processes`: mehrere Engine-Prozesse während des Benches erkannt

Das vollständige Protokoll ist die `asiai bench --agentic-mode` / `--burst-mode`-
Instrumentierung (power/thermal, engine footprint, KV occupancy, prefix-cache
phases) — siehe die asiai-CLI-Dokumentation.

---

## Open questions

1. **MTP auf vLLM-MLX/Rapid-MLX — beantwortet (teilweise).** vLLM-MLX hat MTP in
   Prerelease **0.4.0rc1** (2026-05-21) hinzugefügt; die theoretische Kombination "MLX + MTP-ausgestattetes
   Qwopus 35B-A3B + Cross-USER-Snapshot" könnte sowohl bei Decode als auch bei TTFT gewinnen, sobald
   der Rapid-MLX-Fork 0.4.x verfolgt. Verfolge, wann Rapid-MLX den MTP-Pfad aufnimmt.
2. **MTP auf der MLX-Runtime — aktueller Stand.** Veröffentlichtes mlx-lm führt den
   MTP-Head nicht als natives Speculative Decoding aus (`sanitize()` verwirft die MTP-Gewichte
   während der Konvertierung; native Unterstützung liegt im ungemergten PR
   [ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990)).
   Das `mlx-engine` von LM Studio wrappt mlx-lm, erbt dies also — der +13.5%
   Decode-Gewinn in Abschnitt 1 Zeile 5 kommt vom **llama.cpp-abgeleiteten Backend**
   von LM Studio (die Datei ist GGUF), nicht vom mlx-engine-Speculative-Decoding.
3. **Burst-Verhalten auf Rapid-MLX/vllm-mlx bei der Skala von 60-80 Calls**: Smoke-
   Test bestätigt Single-Slot-FIFO bei burst=5. Vollständiges Panel steht aus (Abschnitt
   2). Die relevante Upstream-Frage ist, ob vllm-mlx
   Continuous-Batching / Multi-Slot-Scheduling für Hybrid-Arch-Modelle plant.
4. **`llama_memory_can_shift=false` auf Qwen 3.6 hybrid** — immer noch kaputt
   upstream. [#18497](https://github.com/ggml-org/llama.cpp/issues/18497) ist
   geschlossen (dokumentiert volle Neuverarbeitung); [#22384](https://github.com/ggml-org/llama.cpp/issues/22384)
   ist ein *Issue* (closed-as-completed), **kein** gemergter Fix; der eigentliche Fix-PR
   [#23121](https://github.com/ggml-org/llama.cpp/pull/23121) wurde **ungemergt
   geschlossen** (Patches leben nur auf Forks). Der Workaround "einfach `preserve_thinking` aktivieren"
   wird durch das offene Issue
   [#22615](https://github.com/ggml-org/llama.cpp/issues/22615) widerlegt (0.67× Speedup =
   Cache bleibt inert). Die Hybrid-DeltaNet-Layers exponieren bauartbedingt keinen shiftbaren Cache-
   State.
5. **Qwopus 3.6 Qualitäts-Unabhängigkeitsreproduktion**: benötigt Drittpartei-
   BFCL- / SWE-bench-Reruns. Vom Autor veröffentlichte Zahlen sollten keine
   Produktionsentscheidungen treiben, bis sie kreuzverifiziert sind.
6. **vllm-mlx vs. Rapid-MLX Abstammung — beantwortet.** Rapid-MLX ist ein Community-
   **Hard-Fork** von `waybarrios/vllm-mlx`, kein dünner Wrapper: er vendort die
   Engine in-tree (Paket weiterhin `vllm_mlx` benannt), hängt nicht per pip vom
   Upstream-Paket ab und hat sich substanziell auseinanderentwickelt (Rapid-MLX 0.6.74 vs. Upstream
   0.3.0). Der geteilte Paketname `vllm_mlx` und das Verzeichnis `~/.cache/vllm-mlx/` sind eine
   häufige Quelle von Zuordnungsverwirrung (siehe Abschnitt 3, Caveat 2).

---

*Dieses Panel ist ein lebendes Dokument. Beiträge, Korrekturen und zusätzliche
Bench-Cells willkommen über [github.com/druide67/asiai](https://github.com/druide67/asiai/issues).*
