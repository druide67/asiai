---
description: Risultati dei benchmark in modalità agentic su Apple Silicon — Qwen3.6 e Qwopus3.6 (27B dense vs 35B-A3B MoE), con e senza speculative decoding MTP, sulle famiglie di engine llama.cpp e MLX. Decode, TTFT, energia, RAM, validità. Una pagina di risultati in continuo aggiornamento.
---

# Risultati dei benchmark agentic

Questa pagina riporta risultati reali di `asiai bench --agentic-mode` su Apple
Silicon. Il protocollo agentic esegue una conversazione su 8 fasi consapevole
della prefix-cache (`--runs 5` per la varianza), che mette alla prova il modo in
cui un agente usa davvero un modello — multi-turn, prefisso di sistema lungo, una
fase long-context da 50K token — anziché una singola generazione one-shot.

**Perché la modalità agentic — a chi è rivolta?** I framework agentici non guidano
un modello come un chatbot: riutilizzano un grande prefisso di sistema su molti
turni, emettono tool call e trascinano un contesto lungo. Un numero di throughput
one-shot manca tutto questo — e la classifica può persino ribaltarsi (un engine con
un ottimo decode grezzo ma un TTFT di diversi secondi o una prefix-cache rotta è
inutilizzabile per un agente). La modalità agentic misura il modello nel modo in cui
viene davvero guidato da **orchestratori di agenti e assistenti di coding** — es.
[Hermes Agent](https://github.com/nousresearch/hermes-agent),
[OpenClaw](https://github.com/openclaw/openclaw),
[opencode](https://github.com/sst/opencode), Aider, Cline o Continue — così il
risultato riflette workload reali di agenti, non un artefatto di benchmark.

> **Documento in continuo aggiornamento.** Questi numeri vengono rinfrescati man
> mano che migliorano le versioni degli engine, le revisioni dei modelli e la
> strumentazione (es. cattura del picco di RAM). Ogni riga riporta la versione
> esatta dell'engine e il file del modello, così un risultato è sempre
> riproducibile.

**Campagna 2026-06-03.** Modelli: Qwen3.6 e il finetune Qwopus3.6, in due
architetture — **27B dense** e **35B-A3B MoE** (Mixture-of-Experts, ~3B parametri
attivi per token). Engine: llama.cpp (b9430) e la famiglia MLX (mlx-lm,
mlx_vlm, omlx, rapid-mlx, vllm-mlx). MTP = la testa Multi-Token Prediction
integrata nel modello usata per lo speculative decoding (`--spec-type draft-mtp`).
Hardware: **MacBook Pro M5 Max (128 GB)** e **Mac mini M4 Pro (64 GB)**, entrambi in
High Power Mode.

## Come leggere la tabella

Verdetto prima di tutto. Le righe sono raggruppate per il risultato di un gate
deterministico, non solo ordinate:

- **★** miglior throughput validato nel blocco · **✓** valido · **⚠** riserva
  (supera i gate rigidi ma ha latenza mediocre) · **✗** eliminato (ha fallito un gate).
- Gate: `valid ≥ 80%` · `TTFT ≤ 1500 ms` (hard fail > 3000) · `prefix-cache reuse > 0`.
- **dec** = decode warm sostenuto (tok/s) · **50K** = decode a 50K di contesto ·
  **TTFT** = time-to-first-token (ms) · **t/s/W** = token al secondo per watt del SoC
  (efficienza, più alto è meglio) · **RAMpk** = picco di RSS dell'engine (GB, la cifra che
  governa l'ingombro in memoria) · `—` = non misurato (mai 0).
- ★ classifica solo per il *throughput*. Scegliere un modello per il lavoro reale
  pesa anche la qualità dell'output (vedi la valutazione dev/code), che il throughput
  non cattura.

> M4 Pro e M5 Max **non** sono comparabili in termini assoluti qui — quant diversa
> (Q5_K_XL vs Q4_K_S). Confronta all'interno del blocco di una macchina.

## MacBook Pro M5 Max 128 GB · Q4

| | model · engine · MTP | dec t/s | peak | 50K | TTFT ms | reuse | t/s/W | RAMpk GB | valid% |
|:--|---|--:|--:|--:|--:|--:|--:|--:|--:|
| **★ Tier 1 — vincitore + veloce** |||||||||| |
| ★ | Qwopus-35B · llamacpp b9430 ▲MTP | 123.3 | 127.5 | 83.8 | 67 | 0.8 | 1.590 | — | 100 |
| ✓ | Qwen-35B · llamacpp b9430 ▲MTP | 118.3 | 123.5 | 82.9 | 62 | 0.8 | 1.513 | — | 100 |
| ✓ | Qwopus-35B · llamacpp b9430 | 105.7 | 108.3 | 76.1 | 63 | 0.8 | 1.507 | — | 100 |
| ✓ | Qwen-35B · llamacpp b9430 | 85.5 | 90.8 | 66.7 | 59 | 0.8 | 1.403 | — | 100 |
| **✓ Tier 2 — valido (più lento)** |||||||||| |
| ✓ | Qwen-27B · llamacpp b9430 ▲MTP | 28.0 | 29.5 | 22.9 | 118 | 0.8 | 0.378 | 32.2 | 100 |
| ✓ | Qwopus-27B · llamacpp b9430 ▲MTP | 26.7 | 29.8 | 22.0 | 118 | 0.8 | 0.367 | 31.5 | 100 |
| ✓ | Qwopus-27B · llamacpp b9430 | 25.9 | 27.1 | 20.8 | 110 | 0.8 | 0.342 | 28.4 | 100 |
| ✓ | Qwen-27B · llamacpp b9430 | 23.8 | 24.0 | 19.2 | 111 | 0.8 | 0.340 | 28.9 | 100 |
| **⚠ Tier 3 — riserva (latenza scarsa)** |||||||||| |
| ⚠ | Qwopus-27B · mlx-lm 0.31.3 | 29.2 | 29.3 | 24.3 | 600 | 1.0 | 0.461 | 26.4 | 100 |
| ⚠ | Qwen-27B · rapid-mlx 0.6.71 | 20.6 | 20.7 | 17.9 | 798 | — | 0.357 | — | 85 |
| ⚠ | Qwen-27B · omlx 0.4.0 | 20.0 | 20.2 | 17.5 | 2150 | 0.82 | 0.346 | 26.7 | 100 |
| **✗ Tier 4 — eliminato** |||||||||| |
| ✗ | ~~Qwen-27B · mlx_vlm 0.6.0 ▲MTP~~ | ~~41.0~~ | — | — | ~~10879~~ | 0.0 | — | — | 75 |
| ✗ | ~~Qwen-27B · mlx_vlm 0.6.0~~ | ~~31.9~~ | — | 26.0 | ~~9578~~ | 0.0 | — | — | 100 |
| ✗ | ~~Qwen-27B · vllm-mlx 0.3.0~~ | ~~20.5~~ | — | 18.1 | ~~9578~~ | — | — | 24.3 | 100 |

Eliminazioni: mlx_vlm+MTP fallisce la validità (75%) e rompe il long-context; sia
le run di mlx_vlm sia vllm-mlx hanno ~9,6 s di TTFT (inutilizzabile per turno di agente).

## Mac mini M4 Pro 64 GB · Q5

| | model · engine · MTP | dec t/s | peak | 50K | TTFT ms | reuse | t/s/W | RAMpk GB | valid% |
|:--|---|--:|--:|--:|--:|--:|--:|--:|--:|
| **★ Tier 1** |||||||||| |
| ★ | Qwen-35B · llamacpp b9430 ▲MTP | 44.6 | 50.7 | 32.6 | 143 | 0.8 | 1.557 | 33.0 | 100 |
| ✓ | Qwen-35B · llamacpp b9430 | 36.3 | 45.6 | 29.6 | 133 | 0.8 | 1.553 | 30.8 | 100 |
| **✓ Tier 2** |||||||||| |
| ✓ | Qwen-27B · llamacpp b9430 | 10.4 | 10.4 | 7.2 | 397 | 0.8 | 0.279 | 31.9 | 100 |
| ✓ | Qwen-27B · llamacpp b9430 ▲MTP | 9.7 | 9.8 | 7.5 | 409 | 0.8 | 0.272 | 35.4 | 100 |

## Risultati chiave

- **Il MoE 35B-A3B batte il 27B dense su ogni asse di throughput** su entrambe le
  macchine — attiva solo ~3B parametri per token, quindi fa decode ~4× più veloce
  del 27B dense ed è ~3,5× più efficiente dal punto di vista energetico (1,5 vs ~0,4 tok/s/W).
  Il throughput però non è la qualità — vedi l'avvertenza qui sotto.
- **Il guadagno con MTP dipende da architettura × hardware.** Incremento di decode
  misurato: MoE +38% (M5) / +23% (M4); dense +16% (M5) ma **−7% (M4)** — sulla GPU
  più lenta dell'M4 l'overhead della draft dense non viene ammortizzato. Quindi MTP è una
  misura per-modello e per-macchina, non una vittoria universale.
- **La famiglia di server MLX qui è solo throughput**: mlx-lm ha il miglior decode
  MLX ma un floor di TTFT a 600 ms; mlx_vlm, vllm-mlx e omlx vengono eliminati dal
  TTFT (2–11 s) e/o da una prefix-cache rotta. llama.cpp domina la latenza del primo
  token (~60–120 ms).
- **Picco vs RAM stabile.** L'RSS di mlx-lm si attesta a ~14,5 GB stabile ma **fa
  picco a 26,4 GB** (allocazione lazy della KV + pesi MLX-4bit compatti); llama.cpp
  pre-alloca in anticipo l'intera KV del contesto (~29 GB piatti). Al picco sono
  comparabili — usa **RAMpk** per le decisioni di ingombro in memoria, non il valore stabile.

## Metodologia e avvertenze

- `asiai bench --agentic-mode --runs 5`, thinking disabilitato
  (`chat_template_kwargs.enable_thinking=false`), contesto del server ≥ 65536.
- Un engine residente alla volta (SOLO); la page cache viene purgata tra le run di
  GGUF che condividono un file.
- **La quant differisce per macchina** (M5 Q4_K_S/Q4_K_XL, M4 Q5_K_XL) → i numeri
  assoluti non sono comparabili tra macchine, solo all'interno di un blocco.
- **High Power Mode** è richiesta sul laptop M5 (altrimenti la GPU sostenuta viene
  throttlata ~40%); il desktop mini M4 è all'incirca neutro rispetto a questa.
- **Lacune note nella strumentazione** (in via di correzione): il picco di RAM
  manca (`—`) su alcuni server llama.cpp avviati manualmente; la versione
  dell'engine non è ancora stampata per ogni run (qui mostrata da una mappa di
  versioni); il `reuse` della prefix-cache è una frazione grossolana in attesa di un
  vero hit-rate.

Vedi anche: [Metodologia dei benchmark](methodology.md) · [Specifica delle metriche](metrics-spec.md)
· [Leaderboard della community](leaderboard.md).
