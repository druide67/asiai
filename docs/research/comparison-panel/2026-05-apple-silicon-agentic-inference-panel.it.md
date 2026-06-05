# Panel di inferenza agentica su Apple Silicon

> Panel comparativo di benchmark tra motori di inferenza (llama.cpp, mlx-lm,
> LM Studio, Rapid-MLX, vLLM-MLX, oMLX, vMLX, Ollama) che eseguono modelli della
> famiglia Qwen 3.6 su Apple Silicon serie M, misurati con
> `asiai bench --agentic-mode` e `asiai bench --burst-mode`.
>
> **Carico di lavoro target**: classe agent-orchestrator — ~60-80 chiamate a strumenti per turno,
> system prompt identico di ~7 KB, messaggio utente che cambia a ogni chiamata. Questo è
> il caso peggiore per il prefix caching ingenuo: è richiesto un vero riuso della cache
> cross-USER, non solo una cache sullo stesso prompt.
>
> **Come leggere le cifre di throughput**: i tassi di decode della Sezione 1 usano il template
> di chat di default di Qwen3 (thinking ON), quindi includono i token di ragionamento —
> il throughput agentico effettivo su un modello thinking è inferiore. Il thinking è un
> compromesso per-task (caveat 1), non un on/off globale.
>
> Pubblicato 2026-06 · contributi e correzioni benvenuti via
> [github.com/druide67/asiai](https://github.com/druide67/asiai/issues).

## ⚠️ Caveat noti prima di proseguire

1. **La modalità thinking è un compromesso per-task.** Con il template di default di Qwen3
   (thinking ON), Qwen 3.6 / Qwopus emettono ~6-7× più token, quindi le cifre di
   decode della Sezione 1 **includono i token di ragionamento** e il throughput agentico effettivo è
   inferiore. Il thinking ON è **richiesto** per i deliverable scritti multi-sezione (un
   modello con thinking OFF salta il deliverable) ma **costa** in pulizia delle chiamate a strumenti
   atomiche (asiai misura ~100% di chiamate a strumenti pulite con thinking OFF vs
   ~77.8% con thinking ON + `preserve_thinking` ON, deterministico tra le esecuzioni;
   `enable_thinking=on` + `preserve_thinking=off` è inutilizzabile — un HTTP 500
   deterministico una volta che il ragionamento si accumula nel contesto). Imposta il thinking **per
   dimensione-di-task**, non come un singolo flag globale.
2. **Rapid-MLX e vLLM-MLX condividono un motore.** Rapid-MLX è un fork community di
   `waybarrios/vllm-mlx`; appaiono come righe separate qui sotto perché hanno
   divergito per versione e funzionalità, ma il meccanismo di snapshot della prefix-cache è
   la stessa stirpe.
3. **MTP: Qwen 3.6 ha una vera head; il backend conta.** Il `config.json` ufficiale di Qwen 3.6
   porta `mtp_num_hidden_layers=1` (naming Qwen — **non** la chiave DeepSeek
   `num_nextn_predict_layers`, quindi un controllo solo-`nextn` conclude erroneamente
   "nessuna head"). Alcuni artefatti GGUF/MLX ri-quantizzati eliminano i tensori MTP
   pur mantenendo il flag di config — verifica i tensori nell'indice dei pesi,
   non solo il flag. L'MTP nativo di llama.cpp (`--spec-type draft-mtp`)
   **richiede un `-MTP-GGUF`** che incorpori la head; un GGUF semplice non può fare drafting.
   Il mlx-lm rilasciato non esegue la head come speculative decoding nativo (la PR
   [ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990) lo aggiunge). LM Studio instrada il GGUF attraverso il suo backend derivato da llama.cpp e l'MLX
   attraverso `mlx-engine`.
4. **Misurazioni a passaggio singolo, nessun reporting della varianza** — le cifre delle Sezioni 1 / 2
   sono osservazioni singole. Il reporting della varianza (mediana + min + max
   su N passaggi) è supportato a partire da `--burst-runs N` ma il re-bench
   è in sospeso.

| Sezione | Argomento | Stato |
|---------|-------|--------|
| 1 | Prestazioni a chiamata singola | 🟡 8 celle, thinking-mode ON (il decode include i token di ragionamento) |
| 2 | Burst concorrente (30/60/80 chiamate parallele) | 🟡 cella smoke + 2 punti concorrenti parziali; nessun panel 30/60/80 normalizzato |
| 3 | Cache e ottimizzazioni | ✅ 8 motori coperti |
| 4 | Memoria e risorse | ✅ idle + swap sotto carico (+0) + footprint misurato |
| 5 | Qualità dei modelli (leaderboard pubbliche) | 🟡 cifre vendor/self-reported (llm-stats) |
| — | **Misurazioni dirette asiai** | ✅ dev-quality, ablazione thinking, MTP, instruction-following |
| 6 | Operativo (licenza, endpoint, manutenzione) | ✅ 8 motori coperti |
| 7 | Ponderazione dei benchmark di qualità | 🟡 ponderazione di default, override via `--weights` pianificato |
| 8 | Eval custom long-horizon (proposta) | 🟡 inquadrata, non ancora costruita |

---

## Sezione 1 — Prestazioni a chiamata singola

> 🟠 **Snapshot maggio 2026 — indicativo, non sono le cifre di riferimento.** Questa tabella è stata
> catturata a maggio (thinking-mode ON, passaggio singolo) e le sue fixture sorgente non sono state
> ri-verificate. Per il **throughput di decode attuale e riproducibile**, usa la sezione *misurazioni
> dirette asiai* qui sotto (giugno, llama.cpp b9430, deterministica). Ciò per cui
> questa tabella è affidabile è la storia **relativa TTFT / prefix-cache**
> (riuso cross-USER), non i t/s assoluti. Nota in particolare che i 123.9 t/s nella
> riga 5 (LM Studio GGUF+MTP) si trovano proprio accanto ai **llama.cpp Qwopus+MTP
> 123.3 t/s** di giugno — il percorso GGUF di LM Studio è un backend derivato da llama.cpp, quindi i due
> misurano essenzialmente lo stesso motore.

> ⚠️ **Da leggere con il caveat 1 sopra**: ogni cifra in questa tabella include i
> token della modalità thinking di default di Qwen3 (reasoning_content). Il throughput
> agentico effettivo richiede di ri-eseguire con
> `chat_template_kwargs={"enable_thinking": false}`. La colonna è etichettata
> "decode (t/s)" non "throughput effettivo".
>
> La colonna "stima limite inferiore" è `60 × (TTFT + max_tokens/decode)`,
> assumendo dispatch sequenziale (che il single-slot di Rapid-MLX impone). **Non** è
> una predizione di tick di produzione — vedi [Sezione 7](#section-7) per il
> caveat metodologico.
>
> 📌 **Versioni testate (maggio 2026)**: Rapid-MLX 0.6.66, LM Studio 0.4.14,
> llama.cpp b9270. Le versioni dei motori cambiano settimanalmente su Apple Silicon — tratta ogni
> cifra come datata, non attuale. (La sezione delle misurazioni asiai usa llama.cpp
> b9430.)

| # | Motore | Modello | Formato | Decode warm (t/s) ¹ | TTFT warm (ms) | TTFT prefix-test mediana (ms) | TTFT cold (ms) | Stima limite inferiore (60 chiamate × chiamata singola, ottimistica) | Fixture sorgente |
|---|--------|-------|--------|--------------------:|---------------:|----------------------------:|---------------:|----------------------------------------------------------:|----------------|
| 1 | Rapid-MLX 0.6.66 (fork of vllm-mlx) | Qwopus 3.6-35B-A3B-v1 (zaydiscold MLX-4bit) | MLX-4bit | **109.1** ¹ | 139 | **131** | 2074 | ~3.6 min | `cell-rapidmlx-qwopus35b.json` |
| 2 | Rapid-MLX 0.6.66 | Qwen 3.6-35B-A3B-UD (MLX-4bit) | MLX-4bit | 106.9 ¹ | 321 | 319 | 2095 | ~4 min | `cell-rapidmlx-35b-a3b.json` |
| 3 | Rapid-MLX 0.6.66 | Qwopus 3.6-27B-v2 (Jackrong MLX-4bit) | MLX-4bit | 31.8 ¹ | 323 | 323 | 8647 | ~13 min | `cell-rapidmlx-qwopus.json` |
| 4 | Rapid-MLX 0.6.66 | Qwen 3.6-27B-UD (MLX-4bit) | MLX-4bit | 20.5 ¹ | 527 | 527 | 8954 | ~23 min | `cell-rapidmlx-full-27bud.json` |
| 5 | LM Studio 0.4.14 (GGUF backend) ² | Qwen 3.6-35B-A3B-MTP (Unsloth GGUF) | GGUF Q4 + MTP | **123.9** ¹ ² | 309 | 5965 | 6063 | ~3.5 min warm / ~9.2 min prefix-changing | `cell-lmstudio-mtp-qwen35b.json` |
| 6 | LM Studio 0.4.14 (GGUF backend) ² | Qwopus 3.6-35B-A3B-v1 (Jackrong GGUF) | GGUF Q4_K_S | 105.6 ¹ | 292 | 5785 | 5624 | ~3.5 min warm / ~9.6 min prefix-changing | `cell-lmstudio-qwopus35b.json` |
| 7 | llama.cpp b9270 | Qwen 3.6-35B-A3B (UD Q5_K_XL) | GGUF Q5_K_XL | 80.9 ¹ | 3000 | 3000 | n/a | ~8 min | (baseline reference) |
| 8 | llama.cpp b9270 | Qwopus 3.6-27B-v2 (Jackrong GGUF Q4) | GGUF Q4 | 25.3 ¹ | 13000 | 13000 | n/a | ~30 min | (baseline reference) |

¹ **Caveat modalità thinking**: cifre catturate con il template di chat di default
(thinking ON). Il throughput effettivo nel mondo reale sui carichi di lavoro con chiamate a strumenti è
tipicamente 4-12 t/s su Qwopus/Qwen3.6 finetune quando i token di ragionamento
gonfiano l'output di 6-7×. Per riprodurre queste cifre di decode, passa
`chat_template_kwargs={"enable_thinking": false}` nel payload della richiesta.

² **Backend LM Studio**: le righe 5-6 hanno usato un file GGUF, che instrada attraverso
il backend di LM Studio derivato da llama.cpp (NON il runtime MLX `mlx-engine`).
La claim MTP nella riga 5 riflette l'implementazione di questo backend, non
lo speculative decoding di mlx-engine. Il mlx-lm rilasciato non esegue la head MTP
come speculative decoding nativo (il suo `sanitize()` storicamente eliminava i pesi MTP
durante la conversione; il supporto nativo è nella PR
[ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990)),
quindi un ipotetico modello MTP in formato MLX non ne trarrebbe beneficio nemmeno sul
mlx-engine rilasciato.

### Osservazioni chiave

- Sul pattern agentico realistico (system identico + prompt utente che cambiano),
  **Rapid-MLX + Qwopus 35B-A3B-v1** offre 131 ms di TTFT mediano prefix-test
  vs 5965 ms per il backend GGUF di LM Studio (**~44× più veloce**). Il vantaggio
  proviene dal meccanismo di snapshot della prefix-cache di vllm-mlx (vedi Sezione 3
  per la disambiguazione del codice sorgente).
- Sul throughput di decode puro (percorso warm), il **backend GGUF di LM Studio con
  MTP Unsloth** registra 123.9 t/s vs Rapid-MLX 109.1 t/s (+13.5%). Questo delta
  riflette lo speculative decoding del backend di LM Studio derivato da llama.cpp su un
  GGUF che porta la head MTP, non un guadagno Apple-MLX (il mlx-engine rilasciato non
  esegue la head — vedi nota 2). Sul percorso llama.cpp nativo, l'MTP è
  net-positivo sul MoE 35B-A3B — vedi Sezione 3.
- Tutte le configurazioni della `Qwen 3.6 family` (hybrid DeltaNet + full-attention) falliscono
  la prefix cache cross-USER **eccetto Rapid-MLX**, che mantiene uno snapshot dello
  stato RNN. Su llama.cpp / LM Studio GGUF `llama_memory_can_shift=false`; su
  mlx-lm / oMLX lo stato recurrent/SSM non può essere diviso a un confine di token
  arbitrario. La fix upstream di llama.cpp per questa architettura non è merged
  ([#23121](https://github.com/ggml-org/llama.cpp/pull/23121) chiusa;
  `preserve_thinking` non la affronta,
  [#22615](https://github.com/ggml-org/llama.cpp/issues/22615)).
- **Serializzazione single-slot confermata**: il test smoke burst (Sezione 2)
  mostra che Rapid-MLX 0.6.66 serializza le chiamate concorrenti FIFO (p50 ≈ p95 ≈ max
  su burst=5). Per 60-80 chiamate/turno, il wall-time totale scala linearmente con
  la dimensione del burst su questo motore. Un motore multi-slot (es. llama.cpp
  `--parallel N`) si comporterebbe diversamente, ma `--parallel N` su Qwen3.6
  hybrid disabilita la prefix cache per slot (limitazione architetturale).

---

## Sezione 2 — Burst concorrente (30/60/80 chiamate parallele)

> Pattern: da 30 a 80 chiamate `POST /v1/chat/completions` concorrenti lanciate entro una
> finestra di ~200 ms. Simula un loop agentico che dispaccia molteplici chiamate MCP/strumenti in
> parallelo. Misurato nativamente via `asiai bench --burst-mode`.
>
> 🟡 **Stato**: 1 cella smoke misurata (Rapid-MLX burst-5). Panel completo in sospeso.

### Cella smoke (Rapid-MLX 0.6.66 + Qwopus 35B-A3B-v1, burst=5)

| burst N | wall-time (s) | latenza p50 (ms) | latenza p95 (ms) | latenza max (ms) | throughput agg (t/s) |
|--------:|--------------:|-----------------:|-----------------:|-----------------:|---------------------:|
| 5 | 2.8 | 2615 | 2792 | 2812 | 88.8 |

**Risultato smoke**: `p50 ≈ p95 ≈ max` indica che le 5 chiamate sono state **serializzate
lato server** (motore single-slot). Rapid-MLX 0.6.66 **non** sembra supportare
lo scheduling di richieste concorrenti — le chiamate si accodano FIFO internamente. Da validare alla scala di 60/80
chiamate.

### Panel concorrente completo — non ancora misurato

Un panel concorrente normalizzato 30/60/80 non è stato eseguito (le misurazioni qui sono
agentic-mode sequenziali, non burst concorrenti). I due punti dati concorrenti
parziali che esistono altrove:

- **TurboQuant** (K=`q8_0` V=`turbo2`, Qwen3-4B, M4 Pro): **+9% aggregato a
  4-parallel** (68.5 → 74.7 t/s) anche se single-stream è −8% — la compressione
  della KV ricompra l'headroom parallelo.
- **oMLX** continuous batching (mlx-lm `BatchGenerator`): **×1.8 aggregato a
  burst-8** (12.8 → 22.9 t/s), ma **collassa a burst-30** (17.3 t/s) una volta che un
  27B-dense satura la RAM in swap — 0 crash.

Un panel dedicato burst-mode su tutti i motori è rinviato.

---

## Sezione 3 — Cache e ottimizzazioni

| # | Coppia | Riuso cache cross-USER | Lo snapshot persiste tra i riavvii | Supporto MTP | Tasso di accettazione MTP | Compat TurboQuant | Tipi nativi di KV cache | Slot paralleli nativi |
|---|--------|---|---|---|---|---|---|---|
| 1 | Rapid-MLX + Qwopus 35B-A3B-v1 | ✅ YES (RNN-state snapshot, see ³ below) | ✅ persistent in `~/.cache/vllm-mlx/` | ❌ released MLX runtime doesn't run the MTP head as speculative decode (mlx-lm PR #990 pending) | n/a | ❌ MLX only | MLX native (no quant flag exposed) | ⚠️ single slot (smoke burst confirms FIFO serialization) |
| 2 | Rapid-MLX + Qwen 35B-A3B-UD | ✅ YES ³ | ✅ persistent | ❌ | n/a | ❌ | MLX native | ⚠️ single slot |
| 3 | LM Studio + Qwen 35B-A3B-MTP | ❌ NO (architectural hybrid limitation) | n/a | ✅ via mlx-engine v1.8.1 | **82.1 %** (on coding task) | ❌ | mlx-engine v1.8.1 (4bit MLX) | configurable via GUI |
| 4 | LM Studio + Qwopus 35B-A3B-v1 | ❌ NO | n/a | ❌ no heads | n/a | ❌ | mlx-engine v1.8.1 (Q4_K_S GGUF) | configurable via GUI |
| 5 | llama.cpp + Qwen 3.6-35B-A3B | ❌ NO (architectural hybrid limitation) | n/a | ✅ `--spec-type draft-mtp` on a `-MTP-GGUF` (a plain GGUF cannot draft). Net-positive on the MoE 35B-A3B — asiai measures **+38%** decode (base) / **+17%** (Qwopus) on M5 Max (see § asiai measurements) | benefit = intra-session decode delta (no acceptance rate logged) | ✅ turbo2/3/4 V cache | `fp16`, `q8_0`, `q5_0`, `turbo2/3/4` | ⚠️ `--parallel N` works mechanically but **disables prefix cache per slot on hybrid arch** (each slot owns its KV, the `--cache-reuse N` flag is already silently disabled here). Use with caution. |
| 6 | mlx-lm | ❌ NO (PRs #923, #188, #192 pending upstream) | n/a | ❌ broken on hybrid arch | n/a | ❌ | MLX native | ❌ (single slot) |
| 7 | oMLX | ❌ NO (tool calling lost post-cache-hit, issue #825) | partial | ❌ | n/a | ❌ | MLX native + tiered SSD cache | ❌ |
| 8 | vLLM-MLX (`waybarrios`, upstream of Rapid-MLX) | ⚠️ trie prefix-cache, no documented hybrid/DeltaNet support (Rapid-MLX rows 1-2 add the RNN-state snapshot on top) | n/a | ⚠️ MTP added in prerelease 0.4.0rc1 | n/a | ❌ | MLX + paged-attention | ✅ |

³ **Prefix cache di Rapid-MLX**: la cache memorizza slab KV hybrid-attention +
snapshot dello stato RNN, indicizzati per `<repo>--<sys_prompt_hash>` e persistiti sotto
`~/.cache/vllm-mlx/`. I ~131 ms di TTFT prefix-test osservati sono un reattach in-RAM di una slab KV
più il forward pass dell'utente cambiato, non un reload da disco.

**Cache large-context di oMLX.** La KV cache SSD paginata a 2 livelli di oMLX trasforma un prefill di 55K token
da ~115 s a ~**3.5 s** di TTFT su un cache-hit stesso-prompt (×33; 55,296 /
55,837 token in cache). Sui prompt piccoli (~7.5K) non c'è vantaggio (~2-5 s, =
mlx-lm) e il decode è ~19 t/s (nessun guadagno di velocità grezza). Questo è riuso stesso-prompt, non
cross-USER (che oMLX non fa); la persistenza tra i riavvii è documentata ma
non ancora testata in A/B.

**Compressione KV TurboQuant** (llama.cpp). K=`q8_0` V=`turbo2` taglia la RAM della KV ~**28%**
(22.9 → 16.4 GB su un modello 4B, M4 Pro) con validità delle chiamate a strumenti invariata (10/10),
e guadagna **+9% aggregato a 4-parallel** nonostante −8% single-stream. Il simmetrico
K=`turbo3` V=`turbo3` raggiunge ~−56% di RAM ma degrada la qualità (early-stop,
ripetizione) — l'asimmetrico `q8_0`/`turbo2` è la config utilizzabile.

---

## Sezione 4 — Memoria e risorse (Apple Silicon M5 Max 128 GB)

| # | Coppia | RAM working-set (GB) | Footprint su disco (GB) | Swap Δ idle | Swap Δ sotto carico | SOLO richiesto? | Coabitazione sicura? |
|---|--------|---|---|---|---|---|---|
| 1 | Rapid-MLX + Qwopus 35B-A3B-v1 | ~22 | 19.9 (MLX-4bit) | +0 | **+0 MB** | ⚠️ SOLO (cohabit thrash to 0.4 t/s) | ❌ |
| 2 | Rapid-MLX + Qwen 35B-A3B-UD | ~24 | 20.0 (MLX-4bit) | +0 | **+0 MB** | ⚠️ SOLO | ❌ |
| 3 | LM Studio + Qwen 35B-A3B-MTP | 21.6 | 23.2 (Q4 + MTP heads) | +0 | **+0 MB** | not tested | not tested |
| 4 | LM Studio + Qwopus 35B-A3B-v1 | 18.5 | 19.9 (Q4_K_S) | +0 | **+0 MB** | not tested | not tested |
| 5 | llama.cpp + Qwen 3.6-35B-A3B (reference) | ~16 | ~16 (Q5_K_XL) | +0 | **+0 MB** | ❌ | ✅ with `--parallel 2/3` |

> **"Sotto carico"** = il bench agentico a 8 fasi incluso un prefill da 50K token (il
> più pesante stress di memoria *sequenziale* misurato), M5 Max 128 GB, SOLO: delta di swap
> **0 MB / 0 swapout per ogni motore** — modello + KV stanno nella memoria free/inactive
> con >100 GB di headroom. Questa è memoria a carico-sequenziale, **non** memoria a
> 60-concorrenti (vedi Sezione 2). La RAM working-set è una stima; l'RSS misurato include
> pagine GGUF mmap'd / pagine MLX wired, quindi il vero footprint incrementale è inferiore (la
> head MTP aggiunge ~+3 GB).

### Osservazioni

- **Rapid-MLX richiede operazione SOLO sulla GPU**: la coabitazione con un altro
  motore in decode attivo innesca un delta di swap di 5.4 → 14.2 GB e un collasso
  del decode a 0.4 t/s. Non avviare un secondo motore sulla stessa GPU Apple Silicon.
- Il footprint su disco di **LM Studio MTP** è +13 % vs Q4_K_S senza head MTP, a causa
  dei blocchi di pesi MTP. Costo trascurabile rispetto al guadagno di decode di +17 %.
- Su M5 Max 128 GB di memoria unificata: ogni configurazione 35B-A3B testata lascia
  più di 100 GB di headroom dopo il caricamento — la RAM non è il fattore limitante.
- Su M4 Pro 64 GB: `Q5_K_XL` **non** sta accanto ai modelli ausiliari (swap
  thrash osservato in produzione). `Q4_K_S` sta.

---

## Sezione 5 — Qualità dei modelli

> Le cifre dei benchmark pubblici qui sono **vendor / self-reported** e aggregate da
> leaderboard (llm-stats), non verificate indipendentemente. Cross-valida su
> [llm-stats](https://llm-stats.com) · [LiveBench](https://livebench.ai) ·
> [SWE-bench](https://swebench.com) prima di affidartene. Le misurazioni dirette
> di asiai su Apple Silicon sono nella prossima sezione.
>
> Le claim del solo autore (Jackrong/Qwopus, self-eval Unsloth) sono segnalate separatamente
> e tenute fuori dalle colonne delle leaderboard pubbliche.
>
> 🔴 **Risultato critico**: il benchmark "Hessling agentic" citato su diverse
> model card della community **non è riproducibile indipendentemente** — 16 prompt,
> singolo curatore, nessuna integrazione in leaderboard neutrali. Tutti e tre i consulenti
> raccomandano di trattarlo solo come uno smoke test.

### Modelli base open-weight Qwen 3.6

> Cifre delle leaderboard pubbliche (llm-stats), self-reported. Il 27B-dense supera
> il MoE 35B-A3B su SWE-bench — coerente con il risultato di dev-quality di asiai
> qui sotto (il base MoE è quello che incappa nel bug dell'oggetto-vuoto delle chiamate a strumenti). Le head MTP
> sono una funzionalità di velocità del decode e non cambiano i punteggi di qualità di un modello.

| Modello | Architettura | SWE-bench Verified | GPQA Diamond | MMLU-Pro | Terminal-Bench 2.0 | BFCL |
|-------|--------------|-------------------:|-------------:|---------:|-------------------:|------|
| Qwen 3.6-35B-A3B-Instruct | MoE 35B / 3B active | 73.4% | 86.0% | 85.2% | 24.6% | absent from board |
| Qwen 3.6-27B-Dense Instruct | Dense 27B hybrid | 77.2% | 87.8% | 86.2% | 59.3% (vendor) | absent from board |

> Terminal-Bench **2.0** è molto più difficile del vecchio Terminal-Bench v1 (le model card
> della community citano ~51.5% per il 35B-A3B su v1); il 24.6% qui è la generazione 2.0.

### Famiglia Qwopus 3.6 — solo author-reported, **non verificata indipendentemente**

I finetune Qwopus 3.6 pubblicati da Jackrong su HuggingFace dichiarano
guadagni sostanziali rispetto al base Qwen. A maggio 2026 queste claim **non sono
state riprodotte indipendentemente** su leaderboard neutrali. Da trattare come
sperimentali finché non saranno disponibili re-run BFCL / SWE-bench da parte di
terzi.

| Modello (claim dell'autore) | MMLU-Pro | SWE-bench Verified | Hessling agentic (16 prompt) |
|-----------------------|---------:|-------------------:|------------------------------:|
| Qwopus 3.6-35B-A3B-v1 (Jackrong) | claimed 88+ | claimed 75+ | claimed 88.6 ⚠ non-reproducible |
| Qwopus 3.6-27B-v2 (Jackrong) | claimed 87.43 | claimed 75.25 | n/a |

⚠ Il benchmark "Hessling agentic" citato sulle model card Jackrong
sembra essere una valutazione specifica del curatore a 16 prompt senza integrazione
in leaderboard neutrali. Tutti e tre i consulenti interpellati (Grok-4, GPT-5,
Gemini Advanced) raccomandano di trattarlo solo come smoke test.

### Ancore di frontiera (metà-2026)

> Tutte le cifre sono **vendor / self-reported**, aggregate da llm-stats — nessuna è
> verificata indipendentemente lì. **Terminal-Bench 2.0** è l'eccezione (il
> team tbench ri-esegue le submission; le righe sono i punteggi di picco agente×modello). I GPQA sono
> cifre "Diamond" del vendor e il set è quasi saturo — da trattare come approssimativi.

| Modello | SWE-bench Verified | GPQA Diamond | MMLU-Pro | Terminal-Bench 2.0 | Fonte |
|-------|-------------------:|-------------:|---------:|-------------------:|--------|
| Claude Opus 4.8 | 88.6% | 93.6% | n/a | — (no TB submission) | llm-stats / Anthropic |
| Claude Opus 4.7 | 87.6% | 94.2% | n/a | **90.2%** | llm-stats / tbench |
| Claude Sonnet 4.6 | 79.6% | 89.9% | n/a | 53.4% | llm-stats / tbench |
| GPT-5.5 | n/a\* (SWE-Pro 58.6%) | 93.6% | n/a | 84.7% | OpenAI / tbench |
| GPT-5 (base) | 74.9% | 85.7% | n/a | 49.6% | llm-stats / tbench |
| Gemini 3.1 Pro | 80.6% | ~94.4% | n/a | 80.2% | llm-stats / tbench |
| DeepSeek-V4-Pro-Max | 80.6% | 90.1% | 87.5% | n/a | vendor (DeepSeek) |
| Llama-3.3-70B-Instruct | n/a | n/a | 68.9% | n/a | Meta (baseline) |

\* GPT-5.5 non ha un punteggio pubblico SWE-bench *Verified* (OpenAI riporta SWE-bench Pro
Public 58.6%); la cifra "88.7% SWE-bench" che circola non è su nessuna fonte
primaria. Nota: **Qwen 3.6 non ha un 235B-A22B** — la famiglia open è il 27B-dense
e il 35B-A3B (sotto); il 235B-A22B è la precedente generazione Qwen3.

### Baseline open-weights della stessa classe

| Modello | MMLU-Pro | SWE-bench Verified | Note |
|-------|---------:|-------------------:|-------|
| Llama-3.3-70B-Instruct | ~75-80 | ~40-50 | Older but well-characterized baseline |
| Mistral Codestral 25.05 / Devstral | high (coding-specialized) | medium-high | Strong editor-style completion fidelity, weaker on reasoning |
| GLM-4.6-Coder (Zhipu) | vendor claims very high | disputed | Significant skepticism around evaluation methodology (consensus) |

### Benchmark di qualità deprecati per questa decisione

- **HumanEval / HumanEval+** — saturi nel 2026, tutti i modelli di frontiera sopra il 90 %, nessun segnale rimasto.
- **GSM8K** — saturo, nessun segnale per gli agenti di coding.
- **MMLU (original)** — superato da MMLU-Pro.
- **"Hessling agentic" a 16 prompt author-reported** — non riproducibile, da trattare solo come smoke test.

### Domande aperte sulla qualità (lacune di ricerca)

1. **Benchmark di qualità-per-GB-RAM**: non esiste uno standard. Formula proxy proposta:
   `AgentScorePerGB = (0.5·SWE + 0.3·BFCL + 0.2·TerminalBench) / RAM_resident`.
2. **Stabilità long-horizon (60+ chiamate a strumenti)**: i benchmark esistenti più vicini sono
   τ-bench, PencilPuzzleBench (>1000 turni), MultiAgentBench, TRAIL. Nessuno di
   essi misura specificamente "correttezza dello schema e coerenza strategica attraverso
   60-80 chiamate a strumenti sequenziali" — quella lacuna di benchmark è riconosciuta da tutti e
   tre i consulenti.
3. **Valutazione conversion-aware (MLX-4bit vs GGUF Q4_K_M vs Q5_K_XL)**: nessuna
   leaderboard standardizzata. I report della community divergono — alcuni dichiarano che MLX-4bit
   preserva la stabilità delle chiamate a strumenti peggio di GGUF Q5_K_M, altri dicono il
   contrario. **Consiglio pratico**: esegui il tuo carico di lavoro di produzione contro
   ogni quant prima di impegnarti.
4. **Validazione di qualità della famiglia Qwopus 3.6**: richiede re-run BFCL +
   SWE-bench di terze parti. Le claim dell'autore non dovrebbero guidare le decisioni di produzione.

---

## Misurazioni dirette asiai — Apple Silicon, metà-2026

> Ciò che le leaderboard pubbliche sopra non mostrano: misurazioni che asiai ha eseguito direttamente
> su Apple Silicon (M5 Max 128 GB in High Power Mode, M4 Pro 64 GB), llama.cpp
> b9430, deterministiche (temp 0), sulla famiglia pubblica Qwen 3.6 e sul
> finetune **Qwopus** distillato da Opus. Caveat: il throughput assoluto cross-session sul
> laptop M5 è ±15% (termico/carico); solo i **delta ±MTP back-to-back intra-session**
> sono stretti, e gli assoluti M5↔M4 non sono comparabili (quant diversi).

### Dev-quality / chiamate a strumenti (`asiai bench --code`)

- Il **base Qwen 3.6-35B-A3B (MoE)** collassa `edit_file.edits` a un oggetto
  vuoto sul turno deep-context — **3/3 run, sia a Q4_K_S che a Q5_K_XL**, stesso
  template di chat. Chiamate a strumenti pulite **87.5%**, edit-turns puliti **66.7%**. È il
  comportamento di generazione delle chiamate a strumenti del base MoE, non il quant e non il template.
- Il **dense 27B** (Q5_K_XL) e **Qwopus-35B-A3B** (Q4_K_S) ottengono entrambi **100%
  pulito / 0 bug** — Qwopus raggiunge l'affidabilità delle chiamate a strumenti del dense-27B al tasso di
  decode ~4× del MoE.
- Sotto una suite di stress più dura per le chiamate a strumenti, Qwopus resta **100% / 0** mentre il dense
  27B scende a **88.9% / 3 bug** (lo stesso fallimento dell'oggetto-vuoto). Ma su una
  trappola di valutazione di espressioni (precedenza di `**` vs meno unario) il **dense 27B è
  corretto e Qwopus è sbagliato** — si dividono. (Il tasso di recovery è sensibile ai pesi
  e rumoroso — non un titolo.)

### Ablazione thinking (`asiai bench --thinking-ablation`, Qwopus-35B-A3B, 3 run deterministici)

| Config | Chiamate a strumenti pulite | Nota |
|--------|----------------:|------|
| `enable_thinking=off` | **100%** | the only fully-clean config |
| `enable_thinking=on` + `preserve_thinking=on` | 77.8% | 2/9 turns dirty |
| `enable_thinking=on` + `preserve_thinking=off` | 11.1% | turns 2-8 → HTTP 500 (context corruption); avoid |

### Throughput MTP (`--spec-type draft-mtp`, decode warm, ±MTP intra-session)

| Modello / hardware | MTP off | MTP on | Δ |
|------------------|--------:|-------:|--:|
| 35B-A3B base · M5 Max | 85.5 t/s | **118.4 t/s** | **+38%** |
| Qwopus 35B-A3B · M5 Max | 105.7 t/s | 123.3 t/s | +17% |
| 27B-dense · M5 Max | 23.8 t/s | 28.0 t/s | +18% |
| Qwopus 27B · M5 Max | 25.9 t/s | 26.7 t/s | +3% |
| 35B-A3B MoE · M4 Pro | 36.3 t/s | 44.6 t/s | +23% |
| 27B-dense · M4 Pro | 10.4 t/s | 9.7 t/s | **−6%** |

Il guadagno MTP scala come **(MoE > dense) × (M5 > M4)** — fortemente positivo sul MoE,
da marginale a negativo sul percorso dense lento (l'overhead del draft non viene ammortizzato). Anche la head MTP del finetune Qwopus è più debole di quella del base (Qwopus 27B +3% / 35B +17%, contro base 27B-dense +18% / 35B-A3B +38%) — il finetuning erode la draft head.
L'MTP lato MLX (mlx_vlm) è squalificato: rompe il long context (output vuoto,
75% valido). Titolo: il MoE 35B-A3B + MTP su llama.cpp sostiene **~118 t/s**
di decode su M5 Max (~44 t/s su M4 Pro), ~4× il 27B-dense, a ~1.5 tok/s/W, TTFT
~62 ms, 100% di validità dell'output.

### Instruction-following (`asiai bench --instruct`, research-brief)

Il compromesso del thinking ha mordente sui deliverable multi-step: con
`enable_thinking=false`, Qwopus-35B fa il lavoro con gli strumenti ma consegna il brief
multi-sezione richiesto lo **0%** delle volte (si ferma allo step secondario); con
il thinking attivo, il modello base lo consegna il **100%** (5/5 sezioni). Questo tira nella
direzione opposta rispetto al risultato delle chiamate a strumenti sopra — thinking-off è il più pulito per le chiamate a strumenti
atomiche ma sopprime i deliverable scritti — ed è per questo che asiai imposta il thinking
**per dimensione-di-task**, non come un singolo switch globale.

---

## Sezione 6 — Operativo

> 📌 Snapshot delle capacità (metà-2026). Le versioni dei motori cambiano settimanalmente su Apple
> Silicon — queste celle sono point-in-time, non una garanzia version-pinned.

| # | Motore | Licenza | Stream OAI-compat | `/v1/models` | `/health` | `/metrics` (Prometheus) | Tool calling | Auto-DL HF | Prefix cache persistita | Attività del maintainer |
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

## Sezione 7 — Ponderazione dei benchmark di qualità per carichi di lavoro agentic-coding

> Questa è la **ponderazione di default di asiai** per un carico di lavoro di classe orchestrator
> (60-80 chiamate a strumenti sequenziali per turno, output schema-validato, system prompt
> long-context). È informata da tre consulenze di LLM di frontiera
> (Grok-4, GPT-5, Gemini Advanced) interpellate a maggio 2026, ma **non è un consenso
> della community** — da trattare come punto di partenza, non come autorevole. Override via
> un futuro flag `--weights` (pianificato).

| Benchmark | Cosa misura | Perché conta qui | Peso di consenso |
|-----------|------------------|---------------------|-----------------:|
| **SWE-bench Verified** | Real GitHub repo navigation + patch + test repair | Best proxy for code-editing fidelity inside an agent loop | **35 %** |
| **BFCL v3** (Berkeley Function Calling Leaderboard) | Multi-turn function-call accuracy, argument fidelity, schema adherence | Direct predictor of orchestrator stability across many tool calls | **25 %** |
| **TerminalBench 2.0 / MCP-Atlas** | CLI and MCP task execution autonomy | "Does the agent survive 40+ actions without derailing" | **20 %** |
| **LiveBench Coding** | Contamination-resistant coding tasks (refreshed monthly) | Catches train-test leakage that inflates HumanEval-class scores | **10 %** |
| **Custom long-horizon stability eval** | 60-80 sequential tool calls with cumulative context growth, malformed JSON recovery | The benchmark that does not exist yet in public form — see Section 8 | **10 %** |

### Benchmark consapevolmente esclusi dalla ponderazione

- MMLU-Pro, GPQA Diamond, HumanEval+ — utili come segnale di capacità generale,
  ma **debolmente correlati** con l'affidabilità dell'agent-loop secondo l'evidenza 2026.
  Le conferme dei lab di frontiera indicano che i punteggi di ragionamento single-shot non
  predicono più il successo agentico autonomo con sufficiente granularità.
- Aggregati author-reported senza re-run di terze parti (Hessling Jackrong,
  self-eval Unsloth, claim del vendor GLM-4.6-Coder).

---

## Sezione 8 — Proposta di benchmark custom di "endurance" (opportunità di ricerca)

Tutti e tre i consulenti convergono sulla stessa lacuna: **il benchmark che caratterizzerebbe
meglio un carico di lavoro orchestrator non esiste ancora pubblicamente**. Costruirne
uno è l'unico modo per ottenere il segnale mancante.

### Scope proposto

- **80 chiamate a strumenti sequenziali** per traiettoria
- **Validazione dello schema a ogni turno** (JSON strict / output strutturato)
- **Crescita cumulativa del contesto** (10K → 50K token attraverso la traiettoria)
- **Test di interruzione / recovery** (cancel a metà-traiettoria + resume)
- **Recovery da XML/JSON malformato** (l'agente si auto-corregge ?)
- **Persistenza delle modifiche al repo** (le modifiche fatte al turno N reggono ancora al turno 60 ?)

Questo è sulla roadmap di asiai (una modalità di endurance long-horizon, dopo burst-mode).
Se costruito, sarebbe il primo benchmark pubblico in questa specifica nicchia.

---

## Metodologia

- **Hardware**: MacBook Pro M5 Max 128 GB di memoria unificata, macOS 26.4.1.
- **Carico di lavoro**: classe orchestrator — system prompt ~7 KB, user prompt ~150-200
  token, 60-80 chiamate per turno.
- **Fasi misurate** (chiamata singola, agentic-mode v1.6.0):
  - `cold`: prima chiamata dopo avvio fresco
  - `warm`: stesso identico prompt di cold (cache calda)
  - `prefix-test-1/2/3`: system identico, utente che cambia — misura il riuso della cache cross-USER
  - `cold-prefix`: system identico, dopo riavvio — misura la cache persistente
- **Verdetto riuso prefix cache**: `YES` se `median(prefix-test) / cold < 0.2`,
  altrimenti `NO`.
- **Misure anti-bias**: modalità SOLO (nessun motore coabitante), baseline termica idle,
  fase di mmap warm-up.
- **Quality gate** (auto-tracciati da asiai bench):
  - `early_stop`: almeno 2 run con completamento `<0.5×` la mediana
  - `memory_pressure`: delta di swap `>500 MB` OPPURE delta di swapout `>1000`
  - `duplicate_processes`: rilevati molteplici processi del motore durante il bench

Il protocollo completo è la strumentazione `asiai bench --agentic-mode` / `--burst-mode`
(power/thermal, footprint del motore, occupazione KV, fasi della prefix-cache) — vedi la doc della CLI asiai.

---

## Domande aperte

1. **MTP su vLLM-MLX/Rapid-MLX — risposta (in parte).** vLLM-MLX ha aggiunto l'MTP nella
   prerelease **0.4.0rc1** (2026-05-21); il combo teorico "MLX + Qwopus 35B-A3B equipaggiato
   con MTP + snapshot cross-USER" potrebbe vincere sia sul decode che sul TTFT una volta
   che il fork Rapid-MLX traccia la 0.4.x. Da monitorare quando Rapid-MLX adotterà il percorso MTP.
2. **MTP sul runtime MLX — stato attuale.** Il mlx-lm rilasciato non esegue la
   head MTP come speculative decoding nativo (`sanitize()` elimina i pesi MTP
   durante la conversione; il supporto nativo è nella PR non-merged
   [ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990)).
   Il `mlx-engine` di LM Studio avvolge mlx-lm, quindi eredita questo — il guadagno di decode
   +13.5% nella Sezione 1 riga 5 proviene dal **backend di LM Studio derivato da llama.cpp**
   (il file è GGUF), non dallo speculative decoding di mlx-engine.
3. **Comportamento burst su Rapid-MLX/vllm-mlx alla scala di 60-80 chiamate**: il test
   smoke conferma il FIFO single-slot a burst=5. Panel completo in sospeso (Sezione
   2). La questione upstream rilevante è se vllm-mlx pianifichi lo
   scheduling continuous-batching / multi-slot per i modelli ad architettura hybrid.
4. **`llama_memory_can_shift=false` su Qwen 3.6 hybrid** — ancora rotto
   upstream. [#18497](https://github.com/ggml-org/llama.cpp/issues/18497) è
   chiusa (documenta il re-processing completo); [#22384](https://github.com/ggml-org/llama.cpp/issues/22384)
   è un *issue* (chiuso-come-completato), **non** una fix merged; la vera PR di fix
   [#23121](https://github.com/ggml-org/llama.cpp/pull/23121) è stata **chiusa
   non-merged** (le patch vivono solo sui fork). Il workaround "basta abilitare `preserve_thinking`"
   è confutato dall'issue aperto
   [#22615](https://github.com/ggml-org/llama.cpp/issues/22615) (speedup 0.67× =
   la cache resta inerte). I layer hybrid DeltaNet non espongono uno stato di cache
   shiftabile per costruzione.
5. **Riproduzione indipendente della qualità di Qwopus 3.6**: richiede re-run
   BFCL / SWE-bench di terze parti. I numeri pubblicati dall'autore non dovrebbero guidare le
   decisioni di produzione finché non saranno cross-verificati.
6. **Stirpe vllm-mlx vs Rapid-MLX — risposta.** Rapid-MLX è un **hard fork** community
   di `waybarrios/vllm-mlx`, non un wrapper sottile: vendorizza il
   motore in-tree (il package è ancora chiamato `vllm_mlx`), non dipende via pip dal
   package upstream, e ha divergito sostanzialmente (Rapid-MLX 0.6.74 vs upstream
   0.3.0). Il nome di package condiviso `vllm_mlx` e la directory `~/.cache/vllm-mlx/` sono una
   frequente fonte di confusione di attribuzione (vedi Sezione 3, caveat 2).

---

*Questo panel è un documento vivo. Contributi, correzioni e celle di bench
aggiuntive benvenuti via [github.com/druide67/asiai](https://github.com/druide67/asiai/issues).*
