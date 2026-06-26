# Qwen-AgentWorld-35B su Apple Silicon: merita un posto nel tuo agent loop?

> Una nota di valutazione per chi esegue modelli locali e costruisce agenti autonomi.
> **Cos'è**: un *world-model linguistico* — predice ciò che un terminale
> restituirebbe dopo un'azione, non agisce. **Cosa gira**: MLX, oppure llama.cpp/Metal
> con un override dei metadati su una riga (un GGUF semplice non si carica senza di esso); nessuna
> build MLX ufficiale. **L'unico elemento distintivo che abbiamo misurato**:
> mantiene il ruolo di simulatore lungo sequenze multi-step dove un generalista deriva.
> **Il suo costo**: pesante over-reasoning — limitabile. I numeri sono small-N e direzionali,
> ciascuno etichettato con la sua dimensione campionaria; le cifre di benchmark degli autori sono segnalate come affermazioni.
>
> Misurato con `asiai` su un M5 Max, MLX 4-bit, un motore alla volta, 2026-06.
> Correzioni benvenute su [github.com/druide67/asiai](https://github.com/druide67/asiai/issues).

!!! tip "Quando usarlo / quando no"
    **Usalo come** simulatore d'ambiente per rollout di agenti economici, un mock per
    output di tool/terminale, o un verificatore di traiettorie al posto di un LLM-as-judge
    (*il caso d'uso come verificatore non è testato qui — vedi §6*). Regge anche come
    semplice generalista 35B se lo istruisci come un assistente.

    **Non usarlo come** assistente quotidiano: gli autori non forniscono alcun percorso d'uso chat/code
    e porta con sé una pesante tassa di over-reasoning (limitabile, vedi §5). E non
    aspettare la variante 397B che "batte GPT-5.4" — **non è scaricabile**
    (HF restituisce 401 nonostante l'annuncio Apache-2.0).

## 1. Eseguibilità e riproduzione (leggi prima questo)

Se non gira sulla tua macchina, niente altro conta. Verdetto, senza giri di parole:

- **Oggi funzionano due percorsi; nessuno dei due è chiavi-in-mano.** Non esiste **alcuna build MLX ufficiale** —
  abbiamo usato una conversione MLX della community, ed è il percorso su cui abbiamo misurato. Il GGUF
  **si carica anch'esso** su llama.cpp / Metal, ma non out of the box: così com'è fallisce con
  `missing tensor 'blk.40.attn_norm.weight'` (build 9780, riconfermato 2026-06-25).
  La causa è un off-by-one del convertitore, **non pesi mancanti** — il GGUF dichiara
  `block_count=41` (un layer MTP extra all'indice 40) pur fornendo solo i 40 layer reali
  0–39, quindi llama.cpp chiede un layer che non avrebbe mai dovuto esistere. Effettua l'override
  dei metadati al caricamento e si carica *e genera*:
  `--override-kv qwen35moe.block_count=int:40 --override-kv qwen35moe.nextn_predict_layers=int:0`.
  Ollama e LM Studio incapsulano llama.cpp ma non espongono in modo affidabile `--override-kv`, quindi
  considera questi due come non testati. Il deployment server ufficiale è vLLM / SGLang / Transformers.
- **Un quant che si carica non è prova che emetta una catena-di-pensiero lunga e corretta** —
  valida la generazione, non solo il caricamento.

Setup di riproduzione:

| | Repo (Hugging Face) | Dimensione |
|---|---|---|
| AgentWorld (specialista) | `jedisct1/Qwen-AgentWorld-35B-A3B-oQ4-MLX` | ~20 GB |
| Qwen3.6 (baseline generalista) | `mlx-community/Qwen3.6-35B-A3B-4bit` | ~19 GB |

`mlx-lm` 0.31.3 · M5 Max 128 GB · sampling temp 0.6 / top-p 0.95 / top-k 20 · un modello caricato alla volta.

!!! warning "Il budget di token è una variabile di setup di prima classe"
    AgentWorld emette una traccia di reasoning molto lunga. Con `max_tokens=4096` il suo output
    viene **troncato prima della risposta** e conta come falso fallimento. Necessita di
    **8192–12288** token di reasoning per terminare su alcuni casi banali. Chiunque
    ri-esegua con un budget basso otterrà numeri peggiori in apparenza per AgentWorld che
    sono artefatti dell'harness, non errori del modello.

**Adattamento RAM / contesto**: pesi ~20 GB; picco ~27 GB a 64K di contesto su un Mac da 128 GB;
la cache KV cresce solo di ~5 GB da 4K a 64K (una proprietà dell'architettura ibrida
condivisa). Un Mac da 64 GB lo esegue comodamente a contesto ridotto; 36–48 GB è
stretto ma utilizzabile a 4K–32K.

## 2. Cos'è, e come lo posizionano gli autori

Un **world-model linguistico**: dato uno stato e un'azione (un comando tipizzato), esso
predice l'osservazione successiva (ciò che il terminale restituisce) tramite una lunga
catena-di-pensiero. Sette domini digitali (MCP, Search, Terminal, SWE, Android, Web,
OS). È addestrato a *essere l'ambiente*, non ad agire in esso.

Gli autori lo forniscono **come world-model, non come assistente**: i system prompt sono
prompt di simulazione, e non esiste alcun percorso d'uso chat/code documentato. Quindi una preoccupazione
legittima è che, usato come assistente, simuli un output di console invece di
rispondere. Il nostro test sfuma questo punto (§4): con un prompt assistente standard scrive codice
e ragiona alla pari del generalista. **Il comportamento è deciso dal prompt,
non da una capacità persa.**

!!! note "Sulla parola *world-model*"
    L'obiezione più comune della community è terminologica: questo è un
    LLM autoregressivo che fa predizione next-text-state, non un world-model non-autoregressivo /
    energy-based nel senso di LeCun. Vale la pena saperlo prima che il nome crei
    un'aspettativa che il modello non pretende di soddisfare.

Specifiche verificate (model card HF, in chiaro):

| | |
|---|---|
| Parametri | **34.66 B** totali · ~3 B attivi (MoE) |
| Architettura | `qwen3_5_moe`, ibrida **Attention + Gated-DeltaNet** |
| Esperti | 256 (8 routed + 1 shared) |
| Contesto | fino a **256K** token |
| Licenza | **Apache-2.0** (~65 GB in BF16) |

## 3. L'elemento distintivo: fedeltà di ruolo multi-step

Questo è l'unico risultato nuovo e difendibile — ed esattamente ciò che il benchmark
degli stessi autori non misura mai (è solo single-step). Il test: concatenare comandi che
costruiscono stato (creare una dir, entrarci, scrivere un file, rileggerlo) e, a ogni passo,
far predire al modello l'esatto output del terminale.

Inquadralo come una proprietà di **affidabilità** — disciplina di formato/ruolo — **non** come un
vantaggio di comprensione. Qwen3.6 comprende il terminale perfettamente (traccia
la directory di lavoro, conta le righe giuste); la differenza è che a volte
*esce dal ruolo*.

| Test | AgentWorld | Qwen3.6 | Nota |
|---|---|---|---|
| Output plausibile (`ls`, `git`, `ps`) — N=3 | 9/9 | 9/9 | parità |
| Sequenza A — 6 step, ancorata (4 run) | 0 role-break / 24 step | intermittente | tiene il ruolo |
| Sequenza B — 8 step, ancorata (3 run) | 0 role-break / 24 step | intermittente | tiene il ruolo |
| Closed-loop (si alimenta da solo) — N=2 | 6/6 ×2 | intermittente | tiene il ruolo |

**Lettura onesta**: AgentWorld ha rotto il ruolo in **0 step su 48 osservati** lungo due
sequenze e quattro run. Qwen3.6 rompe il ruolo in modo intermittente — i suoi run ancorati
hanno oscillato 0/6 → 6/6 tra ripetizioni (N=2), quindi questo è **direzionale, non un tasso**. Quando
fallisce, **rigurgita il JSON dell'azione** invece di simulare l'output:

```text
$ cat log.txt              # log.txt was just deleted → env must return an error

AgentWorld (in role):
  root@host:/home/user# cat log.txt
  cat: log.txt: No such file or directory
  root@host:/home/user#

Qwen3.6 (out of role, ~1 run in 2 here):
  [{"keystrokes": "cat log.txt\n", "duration": 0.1}]    # echoes the input command
                                                        # instead of the output
```

La risposta corretta è spesso presente nell'output di Qwen3.6 — è un fallimento di
**formato/ruolo**, non un'incomprensione. Per un loop in cui ogni passo deve essere leggibile dalla
macchina al passo successivo, un singolo role-break avvelena la catena, ed è proprio ciò che AgentWorld evita.

!!! note "Riserve sulla misurazione (dichiarate)"
    Lo scoring byte-exact sulla riga di echo del comando è severo, e le nostre fixture Sequenza-D vs
    Sequenza-E erano incoerenti sul fatto che un'osservazione di `cd` includa
    l'echo — quindi la metrica di fedeltà di ruolo ha una nota irregolarità. La direzione è
    robusta su quattro file; lo scarto preciso no.

## 4. Capacità generalista: la base non è degradata

La domanda del proprietario (il fine-tune del world-model ha rotto l'LLM di base?) ottiene una
sezione sobria, non il titolo. Risposta breve: no — N=3, direzionale.

| Task | AgentWorld | Qwen3.6 | |
|---|---|---|---|
| Reasoning (5 enigmi verificabili incl. il trap strawberry-'r') | 15/15 | 15/15 | parità |
| Generazione di codice (4 funzioni, **eseguite contro unit test**) | 12/12 | 12/12 | parità |

Eseguito con un prompt assistente (non il prompt simulatore), AgentWorld scrive codice
corretto e ragiona correttamente, alla pari del generalista. Non "deraglia" — è
un generalista competente che si dà il caso ragioni troppo.

## 5. Il costo: una tassa di over-reasoning — e il rimedio

Promuovi questo da nota a piè di pagina a criterio di adozione, perché per un verificatore per-step è
il numero decisivo — ma ha una soluzione.

Misurato su casi di terminale deterministici (N=2 per caso):

| Modalità | AgentWorld | Qwen3.6 |
|---|---|---|
| Reasoning **on** (modalità simulatore di default) | mediana **1140 tok/pred**, max 2558 · ~14 s · 8/8 esatti | 504 tok · ~4.5 s · 8/8 |
| Reasoning **off** (`enable_thinking=false`) | **45 tok/pred · ~0.5 s · 8/8 esatti** | 45 tok · ~0.4 s · 8/8 |

AgentWorld emette ~2.3× più token del generalista e su un banale `cd ; pwd` il
suo reasoning è andato **oltre gli 8192 token in 2 run su 3**. La risposta finale è corretta —
si tratta di una tassa di latenza/calcolo per passo, non di un difetto di correttezza.

!!! tip "Il rimedio: limitalo"
    Disattivare il reasoning **off** per il ruolo di simulatore taglia i token di ~25× e la latenza
    di ~28× **senza alcuna perdita di fedeltà byte-exact** sui casi deterministici (ancora 8/8).
    Per un verificatore o mock per-step, eseguilo con `enable_thinking=false` e un
    tetto di `max_tokens`. **Riserva**: questo è testato solo su casi deterministici —
    su output dove il reasoning aiuta davvero (stato ambiguo, contenuto
    complesso), reasoning-off potrebbe costare fedeltà. Non testato qui.

## 6. Prestazioni (single-run, indicative ★)

Stessa famiglia, stessa architettura, quindi i profili sono vicini. Leggi questi come tendenze.

| Misura | AgentWorld | Qwen3.6 | Lettura |
|---|---|---|---|
| Time to first token ★ | ~360 ms | ~510 ms | AW in vantaggio |
| Throughput di decode ★ | ~110 t/s | ~117 t/s | ~7% più lento |
| Decode a 64K di contesto | ~132 t/s | ~160 t/s | ~73% mantenuto |
| Memoria 4K → 64K | +5 GB | +5 GB | arch ibrida, non specifica di AW |
| Cache di contesto (riuso prefisso di 13K token) | ~×21 | ~×23 | **proprietà MLX**, non del modello |

Lo scarto di decode di ~7% è molto probabilmente la ricetta 4-bit (AgentWorld protegge la sua
proiezione linear-attention in 6-bit; Qwen3.6 protegge il gate MoE in 8-bit), su
lunghezze di output disuguali — un confondente, non uno svantaggio del modello. Il prompt caching è una
feature di mlx-lm identica su entrambi i modelli; il suo guadagno di ~20× scala con la lunghezza del prefisso
in cache, non è una proprietà di AgentWorld.

**Non testato ma di alto valore (il caso d'uso #2 della community)**: usare la predizione
next-state come *verificatore di traiettorie* — quando l'ambiente reale diverge dalla
predizione, ciò segnala un agente fuori-rotta. Non abbiamo misurato il suo comportamento
falso-positivo / falso-negativo. Domanda aperta.

## 7. Cosa affermano gli autori

!!! quote "Benchmark degli autori — un'affermazione, non una misurazione"
    Sul loro benchmark (AgentWorldBench), AgentWorld-35B totalizza **56.4**, allo stesso livello
    di Claude Sonnet 4.6 (56.0). I guadagni che attribuiscono alla specializzazione, per
    ablazione contro la **base Qwen3.5** (auto-riportato, non un confronto diretto vs
    Qwen3.6): **+21.9** tool-use (MCP), **+18.1** software engineering, **+10.2**
    terminal. Tesi: *la specializzazione world-model batte il miglioramento generazionale* —
    il generalista Qwen3.6 totalizza **al di sotto** della base (42.9 vs 47.7) sulla fedeltà di
    simulazione, perché è tarato per *agire*, non per *predire lo stato*.

    Queste cifre provengono da un benchmark interno a fonte singola, valutato da un giudice
    LLM, su un modello con meno di 48 h di vita alla pubblicazione — **nessuna replica
    di terze parti**. La cima della loro tabella sta entro ~2 punti sotto un solo giudice, quindi
    l'ordinamento vicino alla cima è dentro il rumore; il margine 397B "batte GPT-5.4" è +0.46
    (rumore), e quella variante è non pubblica (HF 401) nonostante l'annuncio Apache-2.0.

Il nostro risultato multi-step (§3) è su una *metrica diversa e non replicata* rispetto al loro
bench single-step; punta nella stessa direzione (Qwen3.6 più debole sulla simulazione), ma
questa è convergenza di tesi, non conferma.

## 8. Come lo collegherei

- **Prompt**: usa il system prompt ufficiale di **simulazione** del terminale per eseguirlo come
  ambiente; usa un semplice prompt assistente solo se vuoi output generalista. Le
  due modalità sono lavori diversi.
- **Controllo dei costi**: `enable_thinking=false` + un tetto di `max_tokens` per il
  ruolo di simulatore (§5). Con reasoning attivo, prevedi ~1000–2500 token/passo.
- **Closed loop**: ri-alimenta le predizioni del modello stesso, ma àncorati all'ambiente
  reale quando lo hai; aspettati che la severità di formato conti (la riga di echo).
- **Footprint**: ~20 GB di pesi, ~27 GB di picco a 64K.
- **La questione build-vs-adopt**: il "non esce mai dal ruolo" è intrinseco all'addestramento
  world-model, oppure un generalista + decoding vincolato da grammatica potrebbe colmare
  gran parte dello scarto? Non abbiamo testato l'alternativa generalista-vincolato — ponderala
  prima di adottare un modello dedicato.

## Limiti di questo bench

- **Campioni piccoli** (N=1–5, nessuna deviazione standard). Ogni scarto numerico è una tendenza,
  non un risultato statistico.
- **Un solo dominio** per i due risultati chiave (sequenze di terminale). Il tenere il ruolo "in un loop"
  resta da confermare altrove.
- **Quantizzazione non isolata**: le due ricette 4-bit differiscono leggermente; lo scarto di
  decode è probabilmente legato a ciò ma non è provato qui.
- **Non ancora testati**: scenari casuali/complessi, un secondo dominio, un confronto a tre contro
  la base Qwen3.5 per isolare l'effetto esatto del fine-tune, e il caso d'uso del verificatore
  di traiettorie.
- **Solo il 35B è pubblico.** La variante 397B non è scaricabile.

---

*Fonti: arXiv 2606.24597 · [Qwen-AgentWorld-35B-A3B](https://huggingface.co/Qwen/Qwen-AgentWorld-35B-A3B) (Apache-2.0). Risultati revisionati internamente in modo incrociato per il bias prima della pubblicazione. ★ = misurazione singola, indicativa.*
