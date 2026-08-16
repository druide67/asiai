---
title: "Quale motore per Qwen3.8-27B su Apple Silicon"
description: "Otto motori di inferenza misurati su un solo M5 Max con lo stesso modello. Due motori che leggono lo stesso identico file di pesi divergono del 50%, e il flag che vale il 20% è disattivato di default in quasi tutti."
type: article
date: 2026-08-16
updated: 2026-08-16
---

# Quale motore per Qwen3.8-27B su Apple Silicon

La questione del modello è chiusa: Qwen3.8-27B gira su un portatile e regge 262.144 token
di contesto. La questione del motore no, e costa più di quanto si creda.

Abbiamo misurato otto motori su un solo M5 Max. I due risultati più interessanti non
riguardano affatto la velocità: riguardano due motori che leggono lo *stesso file* e
divergono del 50%, e un flag che nessuno attiva.

## Le condizioni, prima dei numeri

M5 Max 128 GB, alimentazione di rete, High Power Mode, un solo motore residente alla
volta. Reasoning disattivato su ogni motore per renderli confrontabili tra loro.
Throttling termico al 50% entro 1-2 minuti su ogni cella: **questi sono valori minimi,
non massimi**. Validità dell'output al 100% su ogni riga. Prompt da 7.530 token (fasi
brevi) e 55.839 (lunghe), output limitato a 400 e 200 token.

**Non sosteniamo che queste siano le velocità che otterrete.** Sosteniamo che siano gli
scarti tra i motori sotto un unico protocollo.

## La tabella

| Motore | Pesi | n | A caldo | A 56k | Primo token | Memoria | Ctx dichiarato |
|---|---|---|---|---|---|---|---|
| **MTPLX** Bare-Speed | MTPLX 4-bit g64 | 3 | **56,0** | **46,5** | 101 ms | 22,0 GB | default del motore |
| **MTPLX** Optimized-Speed | MTPLX 4-bit g32 | **5** | **44,4** | 37,5 | 99 ms | 27,0 GB | default del motore |
| **mlx-vlm** + drafter MTP | MLX 4-bit ⁽¹⁾ | 3 | **43,3** | 28,9 | **9.982 ms** | 15,5 GB | default del motore |
| **MTPLX** Optimized-Quality | MTPLX 8-bit g64 | 3 | 40,8 | 30,3 | 118 ms | 32,9 GB | default del motore |
| Ollama 0.32.13 | GGUF (non dichiarato) | 3 | 32,8 | 21,7 | 240 ms | 30,3 GB | 65.536 |
| llama.cpp b10434 + MTP | GGUF Q5_K_XL ⁽²⁾ | 3 | 31,8 | 22,7 | **125 ms** | 36,8 GB | 131.072 |
| rapid-mlx 0.12.11 | MLX 4-bit ⁽¹⁾ | 3 | 30,2 | 24,7 | **33.195 ms** | 15,0 GB | default del motore |
| oMLX 0.6.0-dev | oQ4e-mtp (di terze parti) | 3 | 29,8 | 24,6 | 1.968 ms | 16,7 GB | default del motore |
| mlx-lm 0.31.3 | MLX 4-bit ⁽¹⁾ | 3 | 28,8 | 24,0 | 432 ms | **14,6 GB** | default del motore |
| LM Studio 0.4.21 **+ MTP** | GGUF Q5_K_XL ⁽²⁾ | 3 | 27,8 | 23,4 | 419 ms | 36,3 GB | 65.536 |
| LM Studio 0.4.21 default | GGUF Q5_K_XL ⁽²⁾ | 3 | 23,1 | 18,7 | 359 ms | 35,2 GB | 65.536 |

⁽¹⁾ e ⁽²⁾ segnalano le righe che condividono un **file di pesi identico byte per byte**.
Ogni riga è una cella, un export: nessun valore mescolato tra run diversi.

⚠️ **La memoria non è confrontabile tra famiglie.** llama.cpp e Ollama mappano il proprio
GGUF con mmap: il loro resident set è appoggiato al file ed è liberabile (llama.cpp:
36,8 GB di RSS ma 19,8 GB di footprint fisico). I motori MLX allocano. La colonna va letta
all'interno di una famiglia, non da una famiglia all'altra.

⚠️ **Il contesto dichiarato non è lo stesso.** A tre motori è stata imposta una finestra
esplicita; gli altri hanno usato il proprio default. Basta questo a vietare una classifica
globale della colonna memoria.

## Due motori, un solo file, 50% di scarto ⁽¹⁾

mlx-vlm, mlx-lm e rapid-mlx hanno servito tutti `lmstudio-community/Qwen3.8-27B-MLX-4bit`,
snapshot `6067b15c`: lo stesso file su disco.

| Motore | A caldo | Primo token | Memoria |
|---|---|---|---|
| mlx-vlm + drafter MTP | **43,3** | 9.982 ms | 15,5 GB |
| rapid-mlx | 30,2 | 33.195 ms | 15,0 GB |
| mlx-lm | 28,8 | **432 ms** | 14,6 GB |

**+50% da mlx-lm a mlx-vlm, senza cambiare nulla se non il server.** È il confronto più
pulito della campagna: nessuna differenza di quantizzazione su cui discutere.

E si ribalta subito: il vantaggio del 50% di mlx-vlm costa un **tempo al primo token 23×
peggiore**, perché non ha alcuna prefix cache. Per una generazione one-shot vince. Per un
agente è inutilizzabile, e il motivo è nella sezione successiva.

## Il flag che vale il 20%, e perché è disattivato ⁽²⁾

Qwen3.8 include una **testa di predizione multi-token dentro i pesi**. Il modello propone
diversi token in anticipo, il motore li verifica in un solo forward pass. I motori che
implementano la regola di accettazione basata sul rapporto di probabilità preservano
esattamente la distribuzione dell'output; questa proprietà non l'abbiamo verificata noi, e
non va presa per buona sulla parola di un benchmark: leggete l'implementazione del vostro
motore.

Quasi tutti i motori lo consegnano **disattivato**.

| Motore | Flag | Attivo di default? |
|---|---|---|
| vmlx | `--native-mtp-depth` | **sì** |
| MTPLX | `--mtp --depth 3` | sì |
| vllm-mlx | `--enable-mtp` | no |
| llama.cpp | `--spec-type draft-mtp` | no |
| LM Studio | `--speculative-draft-mtp` | no |
| mlx-vlm | `--draft-kind mtp` + repo drafter separato | no |
| oMLX | non si è attivato su Qwen3.8 nei nostri run | — |
| Ollama · mlx-lm · rapid-mlx | nessun supporto | — |

Abbiamo misurato il costo di non saperlo sullo stesso file di pesi, stesso contesto da
65.536, tutto uguale tranne due flag: **LM Studio passa da 23,1 a 27,8 tok/s, +20%.**
Nessuna GUI lo espone.

Effetto di secondo ordine, e conta di più: **confrontare due motori con i loro default
significa confrontare due regimi diversi.** vmlx fa drafting, llama.cpp no.

## Il primo token varia di 350×. Il prefill non lo spiega.

Da 99 ms a 33.195 ms lungo la tabella. A decidere è la **granularità della prefix cache**:
quanta parte di un prompt ripetuto sopravvive da un turno all'altro. Misurato sulla stessa
fase (il turno a caldo, da cui si preleva la latenza al primo token):

| Motore | Riutilizza | Ri-prefill a ogni turno | Primo token |
|---|---|---|---|
| llama.cpp | 7.526 / 7.530 — **a livello di token** | 4 token | 125 ms |
| oMLX | 6.144 / 7.530 — **blocchi da 1024 token** | 1.386 token | 1.944 ms |
| mlx-vlm | 0 / 7.530 | 7.530 token | 9.982 ms |

6.144 è sei volte 1.024. oMLX riutilizza blocchi interi e rifà il prefill di tutto ciò che
non ne riempie uno: 1.386 token, a ogni turno, per sempre. È tutto qui lo scarto tra
125 ms e 2 secondi.

⚠️ **Non confrontate tra motori i tassi di riutilizzo aggregati sulla sessione.** Hanno
soffitti diversi a seconda di quanta parte del prompt di test sia memorizzabile in cache, e
confrontarli produce paradossi che spariscono quando si confronta la stessa fase. È
l'errore che abbiamo commesso in una versione precedente di questa pagina.

**Non** pubblichiamo una colonna di throughput di prefill. La nostra veniva da una singola
richiesta a freddo non ripetuta, che per i motori a caricamento lazy comprende la lettura
di 20 GB da disco: LM Studio ha misurato 216 tok/s su quella richiesta e 938 su quella
immediatamente successiva. Sarebbe stato un numero inventato.

## I token al secondo non sono una velocità

Tra quantizzazioni dello stesso modello, i tok/s misurano in parte quanto sono lunghi gli
output, non quanto in fretta arrivano:

| Build | tok/s | caratteri/s |
|---|---|---|
| Bare-Speed | 56,0 | 200,8 |
| Optimized-Speed | 44,4 | **203,1** |
| Optimized-Quality | 40,8 | 165,7 |

Bare-Speed è in testa del 26% in token al secondo ed è **dietro** in caratteri al secondo.
Stesso tokenizer su tutte e tre: ciò che cambia è quello che le quantizzazioni hanno
scelto di scrivere. Pubblicate la definizione insieme al numero.

## Cosa consigliamo

**Per un agente autonomo locale: MTPLX con `Qwen3.8-27B-MTPLX-Optimized-Speed`, MTP depth
3.** Veloce, 99 ms al primo token, riutilizzo del prefisso a livello di token, 27 GB.

Non Bare-Speed, per quanto sia in testa sulla carta. Suite di tool-calling, stesso
protocollo su tutte e tre:

| Build | tool-call (24 turni) | stress (33 turni) | turni di edit (9) |
|---|---|---|---|
| Optimized-Quality | **83,3%** | 81,8% | **55,6%** |
| Optimized-Speed | 79,2% | **81,8%** | 44,4% |
| Bare-Speed | 62,5% | 72,7% | 22,2% |

⚠️ **Vanno letti onestamente.** Sulla suite di stress, più ampia, Optimized-Speed e
Optimized-Quality **pareggiano esattamente**. E il test esatto di Fisher sulla suite da
24 turni dà **p = 0,34** per Bare-Speed contro Optimized-Speed e **p = 1,00** per Quality
contro Speed: nessuno dei due scarti è statisticamente significativo con questa dimensione
campionaria. I 24 turni sono 3 ripetizioni di 8 task, quindi l'n effettivo è ancora più
piccolo.

Quello che abbiamo davvero è una **direzione coerente su tre suite e due metodi
indipendenti**: i nostri risultati di tool-calling ordinano le tre build nello stesso
ordine dei valori di divergenza da bf16 pubblicati dall'autore delle quantizzazioni
(0,00105 / 0,0220 / 0,0376 — misura sua, non nostra, non riprodotta). L'accordo tra metodi
non correlati vale più di entrambi i p-value. È per questo che sconsigliamo Bare-Speed, ed
è una prova più debole di quanto sembri guardando una tabella di percentuali.

Nemmeno Optimized-Quality: costa **8,3 GB in più** per un vantaggio che non riusciamo a
dimostrare.

## Cosa non siamo riusciti a misurare

**vmlx e vllm-mlx sono stati tentati e mancano all'appello.** Entrambi supportano l'MTP
nativo — vmlx ce l'ha attivo di default — quindi la loro assenza è una lacuna reale di
questo confronto, non un errore di arrotondamento. vllm-mlx è morto all'avvio per un
errore di quoting nella riga di comando; vmlx era ancora in esecuzione al momento della
pubblicazione.

**Il reasoning era disattivato, e non è così che questo modello andrebbe fatto girare.**
Qwen afferma che nei task agentici multi-turno un reasoning effort più basso *"can lead to
insufficient analysis, more failures, and repeated retries, which may increase total
latency"* (può portare ad analisi insufficienti, più fallimenti e tentativi ripetuti, che
possono aumentare la latenza totale). MTPLX 2.7.1 elenca il reasoning disattivato tra i
problemi noti per Qwen3.8. L'abbiamo disattivato per rendere i motori confrontabili: una
decisione di misura, non di messa in produzione.

**Riserve sulle versioni.** Le righe MTPLX hanno girato su **2.6.0**, prima che il motore
introducesse una famiglia di modelli `qwen3_8`: ha servito Qwen3.8 con i default di
Qwen3.6, incluso un contratto di sampling diverso. Questo non incide sul throughput; incide
su tutto ciò che riguarda il comportamento. La riga oMLX proviene da una build di sviluppo
temporanea la cui stringa di versione non è stata catturata dall'export, quindi quella riga
non è riproducibile così come è pubblicata. E il nostro export mlx-vlm si autodichiara come
`mlxlm 0.31.3_2`: solo il log di avvio dimostra che il server era `mlx_vlm.server`.

**La classifica sul primo token tra le tre build MTPLX sta dentro il proprio rumore**:
coefficienti di variazione da 0,33 a 0,66 su quella metrica. 99, 101 e 118 ms non sono
distinguibili. La colonna del throughput è molto più stabile (CV 0,01-0,04).

**La dispersione test-retest su riesecuzioni identiche dello stesso comando ha raggiunto il
7,5%** (37,97 / 40,82 / 39,35 tok/s su tre run di Optimized-Quality), e la memoria si è
spostata di 5 GB tra una riesecuzione e l'altra. Qualsiasi scarto sotto l'8% va considerato
nullo.

**Il tuning non è stato simmetrico.** llama.cpp ha ricevuto flag di cache espliciti
(`--cache-reuse 256 --slot-prompt-similarity 0.5`, flash attention, KV da 131k) che i
motori MLX non hanno avuto. MTPLX ha girato con `--profile turbo`, non con il suo default.
Questo è un confronto tra configurazioni che metteremmo in produzione, non tra i default
out-of-the-box.

## Come riprodurre

Ogni numero proviene da una card certificata prodotta da [asiai](https://asiai.dev),
attraverso un unico percorso scriptato con gate di solitudine, prove d'identità del modello
servito e campionamento termico. Export grezzi disponibili.

Se dovete portarvi via una cosa sola: **verificate se il vostro motore ha la predizione
multi-token, e se è attiva.**
