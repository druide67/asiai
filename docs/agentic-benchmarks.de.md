---
description: Agentic-Mode-Benchmark-Ergebnisse auf Apple Silicon — Qwen3.6 und Qwopus3.6 (27B Dense vs. 35B-A3B MoE), mit und ohne MTP Speculative Decoding, über llama.cpp und die MLX-Engine-Familie hinweg. Decode, TTFT, Energie, RAM, Validität. Eine lebende Ergebnisseite.
---

# Agentic-Benchmark-Ergebnisse

Diese Seite berichtet über reale `asiai bench --agentic-mode`-Ergebnisse auf Apple
Silicon. Das agentische Protokoll führt eine 8-phasige, Prefix-Cache-bewusste
Konversation aus (`--runs 5` für die Varianz), die die Art und Weise nachstellt,
wie ein Agent ein Modell tatsächlich nutzt — über mehrere Turns hinweg, mit langem
System-Prefix, mit einer Long-Context-Phase über 50K Tokens — anstatt einer
einzelnen One-Shot-Generierung.

**Warum Agentic-Mode — für wen ist das gedacht?** Agent-Frameworks treiben ein
Modell nicht wie einen Chatbot an: Sie verwenden einen großen System-Prefix über
viele Turns hinweg wieder, setzen Tool-Calls ab und tragen langen Kontext mit. Eine
One-Shot-Throughput-Zahl verfehlt all das — und das Ranking kann sogar kippen (eine
Engine mit großartigem Roh-Decode, aber mehrere Sekunden TTFT oder einem kaputten
Prefix-Cache ist für einen Agenten unbrauchbar). Der Agentic-Mode misst das Modell
so, wie es tatsächlich von **Agent-Orchestratoren und Coding-Assistenten**
angetrieben wird — z. B.
[Hermes Agent](https://github.com/nousresearch/hermes-agent),
[OpenClaw](https://github.com/openclaw/openclaw),
[opencode](https://github.com/sst/opencode), Aider, Cline oder Continue — sodass das
Ergebnis reale Agent-Workloads widerspiegelt und kein Benchmark-Artefakt.

> **Lebendes Dokument.** Diese Zahlen werden aktualisiert, sobald sich Engine-Versionen,
> Modellrevisionen und die Instrumentierung verbessern (z. B. Peak-RAM-Erfassung). Jede
> Zeile trägt die exakte Engine-Version und die Modelldatei, sodass ein Ergebnis stets
> reproduzierbar ist.

**Kampagne 2026-06-03.** Modelle: Qwen3.6 und das Qwopus3.6-Finetune, in zwei
Architekturen — **27B Dense** und **35B-A3B MoE** (Mixture-of-Experts, ~3B aktive
Parameter pro Token). Engines: llama.cpp (b9430) und die MLX-Familie (mlx-lm,
mlx_vlm, omlx, rapid-mlx, vllm-mlx). MTP = der modelleigene Multi-Token-Prediction-Head,
der für Speculative Decoding genutzt wird (`--spec-type draft-mtp`).
Hardware: **MacBook Pro M5 Max (128 GB)** und **Mac mini M4 Pro (64 GB)**, beide im
High Power Mode.

## So liest du die Tabelle

Verdict-first. Die Zeilen sind nach einem deterministischen Gate-Ergebnis gruppiert,
nicht bloß sortiert:

- **★** bester validierter Throughput im Block · **✓** brauchbar · **⚠** Reserve
  (besteht die harten Gates, aber mit mittelmäßiger Latenz) · **✗** eliminiert (hat ein Gate nicht bestanden).
- Gates: `valid ≥ 80%` · `TTFT ≤ 1500 ms` (Hard-Fail > 3000) · `prefix-cache reuse > 0`.
- **dec** = anhaltender Warm-Decode (tok/s) · **50K** = Decode bei 50K Kontext ·
  **TTFT** = Time-to-First-Token (ms) · **t/s/W** = Tokens pro Sekunde pro SoC-Watt
  (Effizienz, höher ist besser) · **RAMpk** = Peak-Engine-RSS (GB, die Kennzahl, die
  über den Speicher-Fit entscheidet) · `—` = nicht gemessen (niemals 0).
- ★ rankt nur nach *Throughput*. Die Auswahl eines Modells für reale Arbeit wägt auch
  die Output-Qualität mit ein (siehe die Dev/Code-Evaluierung), die der Throughput
  nicht erfasst.

> M4 Pro und M5 Max sind hier in absoluten Zahlen **nicht** vergleichbar — unterschiedliche
> Quant (Q5_K_XL vs. Q4_K_S). Vergleiche innerhalb eines Maschinen-Blocks.

## MacBook Pro M5 Max 128 GB · Q4

<div class="wide-table" markdown>

| | model · engine · MTP | dec t/s | peak | 50K | TTFT ms | reuse | t/s/W | RAMpk GB | valid% |
|:--|---|--:|--:|--:|--:|--:|--:|--:|--:|
| **★ Tier 1 — Gewinner + schnell** |||||||||| |
| ★ | Qwopus-35B · llamacpp b9430 ▲MTP | 123.3 | 127.5 | 83.8 | 67 | 0.8 | 1.590 | — | 100 |
| ✓ | Qwen-35B · llamacpp b9430 ▲MTP | 118.3 | 123.5 | 82.9 | 62 | 0.8 | 1.513 | — | 100 |
| ✓ | Qwopus-35B · llamacpp b9430 | 105.7 | 108.3 | 76.1 | 63 | 0.8 | 1.507 | — | 100 |
| ✓ | Qwen-35B · llamacpp b9430 | 85.5 | 90.8 | 66.7 | 59 | 0.8 | 1.403 | — | 100 |
| **✓ Tier 2 — brauchbar (langsamer)** |||||||||| |
| ✓ | Qwen-27B · llamacpp b9430 ▲MTP | 28.0 | 29.5 | 22.9 | 118 | 0.8 | 0.378 | 32.2 | 100 |
| ✓ | Qwopus-27B · llamacpp b9430 ▲MTP | 26.7 | 29.8 | 22.0 | 118 | 0.8 | 0.367 | 31.5 | 100 |
| ✓ | Qwopus-27B · llamacpp b9430 | 25.9 | 27.1 | 20.8 | 110 | 0.8 | 0.342 | 28.4 | 100 |
| ✓ | Qwen-27B · llamacpp b9430 | 23.8 | 24.0 | 19.2 | 111 | 0.8 | 0.340 | 28.9 | 100 |
| **⚠ Tier 3 — Reserve (schlechte Latenz)** |||||||||| |
| ⚠ | Qwopus-27B · mlx-lm 0.31.3 | 29.2 | 29.3 | 24.3 | 600 | 1.0 | 0.461 | 26.4 | 100 |
| ⚠ | Qwen-27B · rapid-mlx 0.6.71 | 20.6 | 20.7 | 17.9 | 798 | — | 0.357 | — | 85 |
| ⚠ | Qwen-27B · omlx 0.4.0 | 20.0 | 20.2 | 17.5 | 2150 | 0.82 | 0.346 | 26.7 | 100 |
| **✗ Tier 4 — eliminiert** |||||||||| |
| ✗ | ~~Qwen-27B · mlx_vlm 0.6.0 ▲MTP~~ | ~~41.0~~ | — | — | ~~10879~~ | 0.0 | — | — | 75 |
| ✗ | ~~Qwen-27B · mlx_vlm 0.6.0~~ | ~~31.9~~ | — | 26.0 | ~~9578~~ | 0.0 | — | — | 100 |
| ✗ | ~~Qwen-27B · vllm-mlx 0.3.0~~ | ~~20.5~~ | — | 18.1 | ~~9578~~ | — | — | 24.3 | 100 |

</div>

Eliminierungen: mlx_vlm+MTP scheitert an der Validität (75%) und bricht Long-Context;
sowohl die mlx_vlm-Läufe als auch vllm-mlx haben ~9,6 s TTFT (pro Agent-Turn
unbrauchbar).

## Mac mini M4 Pro 64 GB · Q5

<div class="wide-table" markdown>

| | model · engine · MTP | dec t/s | peak | 50K | TTFT ms | reuse | t/s/W | RAMpk GB | valid% |
|:--|---|--:|--:|--:|--:|--:|--:|--:|--:|
| **★ Tier 1** |||||||||| |
| ★ | Qwen-35B · llamacpp b9430 ▲MTP | 44.6 | 50.7 | 32.6 | 143 | 0.8 | 1.557 | 33.0 | 100 |
| ✓ | Qwen-35B · llamacpp b9430 | 36.3 | 45.6 | 29.6 | 133 | 0.8 | 1.553 | 30.8 | 100 |
| **✓ Tier 2** |||||||||| |
| ✓ | Qwen-27B · llamacpp b9430 | 10.4 | 10.4 | 7.2 | 397 | 0.8 | 0.279 | 31.9 | 100 |
| ✓ | Qwen-27B · llamacpp b9430 ▲MTP | 9.7 | 9.8 | 7.5 | 409 | 0.8 | 0.272 | 35.4 | 100 |

</div>

## Zentrale Erkenntnisse

- **Das 35B-A3B MoE schlägt das 27B Dense auf jeder Throughput-Achse** auf beiden
  Maschinen — es aktiviert nur ~3B Parameter pro Token, dekodiert also ~4× schneller
  als das Dense-27B und ist ~3,5× energieeffizienter (1,5 vs. ~0,4 tok/s/W).
  Throughput ist allerdings nicht gleich Qualität — siehe den Vorbehalt unten.
- **Throughput ist nicht gleich agentische Eignung.** Bei einer mehrdeutigen
  Suchaufgabe — dem `loop-search`-Szenario (`asiai bench --instruct`, siehe die
  [Dev/Code-Evaluierung](dev-quality-benchmarks.md)) — **dreht das 35B-A3B MoE
  perfektionistisch in Schleifen**: es setzt zu einer nicht auflösbaren Tatsache
  immer wieder semantisch äquivalente Anfragen ab, bis ein No-Progress-Guardrail
  es stoppt, und produziert das Deliverable nie. Das gilt in **sowohl Q4 als auch
  Q8** (architektonisch, kein Quant-Artefakt), während das **Dense-27B nie in
  Schleifen dreht**. Für ein agentisches Harness wie den Hermes Agent von
  NousResearch kann diese Schleifenresistenz den Roh-Decode-Vorsprung des MoE
  überwiegen — d. h. das schnellste Modell ist nicht immer der richtige Agent.
- **Der MTP-Gewinn hängt von Architektur × Hardware ab.** Gemessener Decode-Zuwachs:
  MoE +38% (M5) / +23% (M4); Dense +16% (M5), aber **−7% (M4)** — auf der langsameren
  M4-GPU wird der Draft-Overhead des Dense nicht amortisiert. MTP ist also eine
  pro-Modell-, pro-Maschine-Messung, kein universeller Gewinn.
- **Die MLX-Server-Familie ist hier reiner Throughput**: mlx-lm hat den besten
  MLX-Decode, aber einen TTFT-Boden von 600 ms; mlx_vlm, vllm-mlx und omlx werden
  durch TTFT (2–11 s) und/oder einen kaputten Prefix-Cache ausgeschaltet. llama.cpp
  dominiert die First-Token-Latenz (~60–120 ms).
- **Peak vs. Steady-State RAM.** Der RSS von mlx-lm liegt im Steady-State bei ~14,5 GB,
  **erreicht aber Peaks von 26,4 GB** (lazy KV-Allokation + kompakte MLX-4bit-Gewichte);
  llama.cpp allokiert den vollen Kontext-KV im Voraus (~29 GB flach). Im Peak sind sie
  vergleichbar — nutze für Speicher-Fit-Entscheidungen **RAMpk**, nicht den
  Steady-State-Wert.

## Methodik & Vorbehalte

- `asiai bench --agentic-mode --runs 5`, Thinking deaktiviert
  (`chat_template_kwargs.enable_thinking=false`), Server-Kontext ≥ 65536.
- Eine Engine zur Zeit resident (SOLO); der Page-Cache wird zwischen GGUF-Läufen, die
  sich eine Datei teilen, geleert.
- **Quant unterscheidet sich je Maschine** (M5 Q4_K_S/Q4_K_XL, M4 Q5_K_XL) → absolute
  Zahlen sind nicht maschinenübergreifend vergleichbar, nur innerhalb eines Blocks.
- **High Power Mode** ist auf dem M5-Laptop erforderlich (sonst wird die anhaltende GPU
  um ~40% gedrosselt); der M4-Mini-Desktop verhält sich ihm gegenüber weitgehend neutral.
- **Bekannte Instrumentierungslücken** (werden behoben): Peak-RAM fehlt (`—`) auf
  einigen manuell gestarteten llama.cpp-Servern; die Engine-Version wird noch nicht pro
  Lauf eingestempelt (hier aus einer Version-Map gezeigt); der Prefix-Cache-`reuse` ist
  ein grober Bruchteil, bis eine echte Hit-Rate vorliegt.

Siehe auch: [Benchmark-Methodik](methodology.md) · [Metrik-Spezifikation](metrics-spec.md)
· [Community-Leaderboard](leaderboard.md).
