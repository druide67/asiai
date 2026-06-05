---
description: Risultati dei benchmark di qualità dev e di ritenzione multilingue su Apple Silicon — affidabilità delle tool call (il bug di troncamento degli argomenti JSON / oggetto vuoto), error-recovery agentico, disciplina del thinking e ritenzione delle lingue. Deterministici, nessun giudice LLM necessario per il segnale principale. Una pagina di risultati in continuo aggiornamento.
---

# Benchmark di qualità dev e di lingua

Il throughput non è la qualità. Un modello può fare decode veloce ed essere
comunque inutilizzabile per il coding agentico — tronca gli argomenti delle tool
call, va in loop sugli errori, oppure il suo finetune ha silenziosamente rotto
un'altra lingua. Questa pagina riporta risultati reali di
`asiai bench --code` e `asiai bench --language`: segnali **deterministici**
(nessun giudice LLM necessario per il nucleo) che misurano se un modello funziona
davvero, non quanto velocemente emette token.

> **Documento in continuo aggiornamento.** I numeri vengono rinfrescati man mano
> che cambiano le revisioni dei modelli, gli engine e i template. Ogni blocco
> riporta il file esatto del modello e la configurazione di serving, così un
> risultato è sempre riproducibile.

## Cosa viene misurato

`asiai bench --code` (deterministico, senza giudice):

- **tool-call** — una sessione agentica di file-editing su 8 turni con contesto
  che si accumula. Valuta l'emissione della tool call, la validità JSON, il
  non-troncamento, il tool corretto, la conformità allo schema e il **bug
  dell'oggetto vuoto**: il troncamento del template `|items` che collassa un
  array `edit_file.edits` a `{}` / `[]`.
- **tool-call-stress** — lo stesso, più difficile: contesto più profondo, array
  di edit da 8–10 elementi, pressione di escaping JSON (newline, virgolette,
  backslash, unicode). Usato per distinguere i modelli che superano la baseline a
  pieni voti.
- **recovery** — inietta un errore di tool sintetico a metà sessione; valuta
  un'azione correttiva contro un loop bloccato (la ri-emissione della chiamata
  che fallisce).
- **thinking** — disciplina della thinking-mode: nessun leak di `<think>` nel
  contenuto, output non vuoto a budget ridotto, e `enable_thinking=false`
  rispettato.
- **coding** / **coding-hard** *(giudice opzionale)* — task di coding multi-turn
  valutati 1–5 da un giudice LLM a `--judge-url` (qualsiasi endpoint
  OpenAI-compatibile).

`asiai bench --instruct` (instruction-following deterministico):

- **verifiable** — prompt single-turn in stile IFEval con istruzioni
  verificabili programmaticamente (conteggi di parole/frasi/sezioni, keyword,
  solo JSON, maiuscole/minuscole, niente virgole, frase finale, titolo in
  `<<>>`, lingua…). Riportati come accuratezza strict/loose a livello di prompt e
  a livello di istruzione — il formato delle leaderboard pubbliche.
  Reimplementazione asiai-native del paradigma IFEval (Zhou et al. 2023); nessun
  codice o dato IFEval è incorporato.
- **research-brief** — un task agentico: ricerca diversi argomenti tramite tool,
  poi scrive un briefing multi-sezione, poi un'azione di tool secondaria (save)
  **per ultima**. Il modello produce il briefing principale, oppure fa il lavoro
  di tool e restituisce solo la conferma del passo secondario? Un modello può
  superare a pieni voti l'affidabilità delle tool call e saltare comunque il
  deliverable principale — valutato deterministicamente verificando che le
  sezioni richieste compaiano dopo i turni di tool. **order-control** scambia
  l'ordine (prima il secondario) come diagnostica.

`asiai bench --language <code>` (deterministico, 8 lingue):

- **adherence** — il modello resta nella lingua target? (rapporto di
  function-word target vs. inglese per gli script latini; rapporto di caratteri
  nello script target per ja/ko/zh).
- **diacritics** — prompt trabocchetto la cui risposta corretta deve contenere
  token accentati specifici (`café`, `préféré`); una risposta privata degli
  accenti ASCII fallisce.

Tutte e tre le modalità sono solo JSON e confrontano i modelli facendo il diff
dell'output.

## Esempio svolto — Qwen3.6-35B-A3B vs Qwopus3.6-35B-A3B vs Qwen3.6-27B dense

Un finetune (`Qwopus3.6`, un finetune distillato da Opus del MoE
`Qwen3.6-35B-A3B`) contro la sua base, contro un modello dense grande la metà.
Stesso llama.cpp, **stesso chat template tenuto costante** (solo il file del
modello scambiato), thinking disabilitato, 3 ripetizioni. Apple Silicon M5 Max,
High Power Mode.

### Affidabilità delle tool call

| model · quant | tool-call clean | empty-object bug | under stress |
|---|--:|--:|--:|
| Qwen3.6-35B-A3B base · Q4 / Q5 | 87.5% | **3** | 87.5% · **3 bugs** |
| **Qwopus3.6-35B-A3B · Q4** | **100%** | **0** | **100% · 0** |
| Qwen3.6-27B dense · Q5 | 100% | 0 | 88.9% · **3 bugs** |

- **Il MoE 35B base ha un difetto residuo nelle tool call che il fix del template
  non chiude del tutto.** Collassa `edit_file.edits` nel bug dell'oggetto vuoto
  3/3 su un turno a contesto profondo — a **entrambi** i quant Q4 e Q5 (quindi è
  un comportamento di generazione, non quantizzazione). Il template della
  community `froggeric`, che corregge il bug `|items` sulle chiamate semplici,
  non salva il MoE base in profondità nel contesto.
- **Il finetune distillato da Opus lo ripara completamente** — 0 bug, 100% clean
  — e a un quant *inferiore* (Q4 vs Q5), il che rende la vittoria ancora più
  netta.
- **Sotto stress, il finetune è l'agente più robusto rispetto al 27B dense**: il
  27B cede (3 bug dell'oggetto vuoto sulla suite più dura) mentre il finetune
  resta a 0. Pareggiano sulla baseline; la suite di stress li separa.

### Correttezza del codice (task difficili giudicati da LLM)

Su due task di coding multi-turn più insidiosi si **dividono**: su un rate
limiter a sliding-window entrambi gestiscono i casi limite di
boundary/eviction; su un valutatore di espressioni il **27B dense ottiene
correttamente la precedenza degli operatori** (`-2**2 == -4`, il meno unario come
operatore vero) mentre il **finetune no** (incorpora il meno unario nel numero →
`4.0`). La robustezza delle tool call e la correttezza algoritmica sono assi
*diversi* — misurali entrambi.

### Ritenzione della lingua

Eseguendo `--language fr` sul finetune e sulla sua base, stesso quant:

| model | adherence | diacritic traps | ASCII-stripped |
|---|--:|--:|--:|
| Qwen3.6-35B-A3B base | 100% | 4/4 | 0 |
| **Qwopus3.6-35B-A3B** | 100% | 4/4 | 0 |

**Zero regressione del francese.** Il finetune orientato al coding ha mantenuto
intatto il francese del modello base (adherence, diacritici, nessuna rimozione
degli accenti ASCII) — un finetune task-specifico *non* è costato un'altra lingua,
cosa che vale la pena verificare anziché dare per scontata.

## Come leggere questa pagina

- **Verdetto prima di tutto, non velocità prima di tutto.** Questi sono segnali
  di correttezza/affidabilità. Per il throughput, vedi i
  [Benchmark agentic](agentic-benchmarks.md).
- **Nucleo deterministico, giudice opzionale.** tool-call / recovery / thinking /
  adherence / diacritics non hanno bisogno di un giudice LLM — sono riproducibili.
  Le valutazioni `coding`/`fluency` sono giudicate da LLM (soggettive,
  opzionali).
- **Confronta all'interno di un cambiamento controllato.** L'esempio tiene
  costante il template e varia solo il modello, così una differenza è del modello,
  non dell'harness.

## Metodologia e avvertenze

- `asiai bench --code` / `--language`, thinking disabilitato
  (`chat_template_kwargs.enable_thinking=false`), un engine residente alla volta.
- **La quant differisce nell'esempio** (il finetune Q4 vs i modelli Qwen Q5): il
  bug dell'oggetto vuoto in primo piano è guidato dal template/generazione ed è
  stato confermato a **entrambi** i quant per la base, quindi la quant non spiega
  il divario — e il finetune vince partendo dal quant inferiore.
- **Il giudice della qualità del codice non è strettamente cieco** qui (un
  modello di frontiera ha letto i transcript nel merito); i numeri deterministici
  di tool-call/stress sono oggettivi.
- **La recovery è sensibile ai pesi**, non un segnale cross-model pulito — il dato
  in primo piano è l'affidabilità tool-call/oggetto-vuoto, che è stabile tra le
  ripetizioni.

Vedi anche: [Benchmark agentic](agentic-benchmarks.md) ·
[Metodologia dei benchmark](methodology.md) · [Specifica delle metriche](metrics-spec.md).
