---
description: "Come ottenere risultati di benchmark LLM accurati su Mac: gestione termica, app in background, numero di esecuzioni e consigli per la riproducibilità."
---

# Best practice per i benchmark

> **Versione**: 0.3.2
> **Stato**: Documento vivo — aggiornato con l'evoluzione della metodologia
> **Riferimenti**: MLPerf Inference, SPEC CPU 2017, NVIDIA GenAI-Perf

## Panoramica

`asiai bench` segue standard di benchmarking consolidati per produrre risultati **affidabili, riproducibili e comparabili** tra motori di inferenza su Apple Silicon. Questo documento traccia quali best practice sono implementate, pianificate o intenzionalmente escluse.

## Riepilogo di conformità

| Categoria | Pratica | Stato | Da |
|----------|----------|--------|-------|
| **Metriche** | TTFT separato da tok/s | Implementato | v0.3.1 |
| | Campionamento deterministico (temperature=0) | Implementato | v0.3.2 |
| | Conteggio token da API del server (non chunk SSE) | Implementato | v0.3.1 |
| | Monitoraggio energetico per motore | Implementato | v0.3.1 |
| | Campo esplicito generation_duration_ms | Implementato | v0.3.1 |
| **Warmup** | 1 generazione di warmup per motore (non cronometrata) | Implementato | v0.3.2 |
| **Esecuzioni** | Default 3 esecuzioni (minimo SPEC) | Implementato | v0.3.2 |
| | Mediana come metrica primaria (standard SPEC) | Implementato | v0.3.2 |
| | Media + stddev come secondaria | Implementato | v0.3.0 |
| **Varianza** | Stddev combinata intra-prompt | Implementato | v0.3.1 |
| | Classificazione stabilità basata su CV | Implementato | v0.3.0 |
| **Ambiente** | Esecuzione sequenziale dei motori (isolamento memoria) | Implementato | v0.1 |
| | Rilevamento throttling termico + avviso | Implementato | v0.3.2 |
| | Livello termico + speed_limit registrato | Implementato | v0.1 |
| **Riproducibilità** | Versione motore salvata per benchmark | Implementato | v0.3.2 |
| | Formato modello + quantizzazione salvati | Implementato | v0.3.2 |
| | Chip hardware + versione macOS salvati | Implementato | v0.3.2 |
| | Codice benchmark open-source | Implementato | v0.1 |
| **Regressione** | Confronto con baseline storico (SQLite) | Implementato | v0.3.0 |
| | Confronto per (engine, model, prompt_type) | Implementato | v0.3.1 |
| | Filtraggio metrics_version | Implementato | v0.3.1 |
| **Prompt** | 4 tipi di prompt diversi + context fill | Implementato | v0.1 |
| | max_tokens fisso per prompt | Implementato | v0.1 |

## Miglioramenti pianificati

### P1 — Rigore statistico

| Pratica | Descrizione | Standard |
|----------|-------------|----------|
| **Intervalli di confidenza al 95%** | CI = media +/- 2*SE. Più informativo di +/- stddev. | Accademico |
| **Percentili (P50/P90/P99)** | Per TTFT in particolare — la latenza di coda conta. | NVIDIA GenAI-Perf |
| **Rilevamento outlier (IQR)** | Segnalare esecuzioni fuori [Q1 - 1.5*IQR, Q3 + 1.5*IQR]. | Standard statistico |
| **Rilevamento tendenze** | Rilevare degradazione monotona delle prestazioni tra le esecuzioni (deriva termica). | Accademico |

### P2 — Riproducibilità

| Pratica | Descrizione | Standard |
|----------|-------------|----------|
| **Raffreddamento tra motori** | Pausa di 3-5s tra motori per stabilizzare la termica. | Benchmark GPU |
| **Verifica rapporto token** | Avvisare se tokens_generated < 90% di max_tokens. | MLPerf |
| **Formato di esportazione** | JSON `asiai bench --export` per invii comunitari. | Invii MLPerf |

### P3 — Avanzati

| Pratica | Descrizione | Standard |
|----------|-------------|----------|
| **Opzione `ignore_eos`** | Forzare la generazione fino a max_tokens per benchmark di throughput. | NVIDIA |
| **Test richieste concorrenti** | Testare il throughput del batching (rilevante per vllm-mlx). | NVIDIA |
| **Audit processi in background** | Avvisare se processi pesanti sono in esecuzione durante il benchmark. | SPEC |

## Deviazioni intenzionali

| Pratica | Motivo della deviazione |
|----------|---------------------|
| **Durata minima MLPerf 600s** | Progettato per GPU da datacenter. L'inferenza locale su Apple Silicon con 3 esecuzioni + 4 prompt richiede già ~2-5 minuti. Sufficiente per risultati stabili. |
| **SPEC 2 workload di warmup non cronometrati** | Usiamo 1 generazione di warmup (non 2 workload completi). Un singolo warmup è sufficiente per motori di inferenza locali dove il warmup JIT è minimo. |
| **Stddev popolazione vs campione** | Usiamo la stddev di popolazione (divisore N) invece della stddev campionaria (divisore N-1). Con N piccolo (3-5 esecuzioni), la differenza è minima e la popolazione è più conservativa. |
| **Controllo scaling frequenza** | Apple Silicon non espone controlli del governor CPU. Registriamo thermal_speed_limit per rilevare il throttling. |

## Considerazioni specifiche per Apple Silicon

### Architettura a memoria unificata

Apple Silicon condivide la memoria tra CPU e GPU. Due implicazioni chiave:

1. **Non fare mai benchmark di due motori simultaneamente** — competono per lo stesso pool di memoria.
   `asiai bench` esegue i motori in sequenza per design.
2. **Reporting VRAM** — Ollama e LM Studio riportano `size_vram` nativamente. Per gli altri motori
   (llama.cpp, mlx-lm, oMLX, vLLM-MLX, Exo), asiai usa `ri_phys_footprint` via libproc come
   stima di fallback. È quello che mostra Monitor Attività e include le allocazioni Metal/GPU.
   I valori stimati sono etichettati "(est.)" nell'interfaccia.

### Throttling termico

- **MacBook Air** (senza ventola): throttling severo sotto carico sostenuto. I risultati degradano dopo 5-10 min.
- **MacBook Pro** (con ventola): il throttling è lieve e solitamente gestito dall'accelerazione della ventola.
- **Mac Mini/Studio/Pro**: raffreddamento attivo, throttling minimo.

`asiai bench` registra `thermal_speed_limit` per risultato e avvisa se viene rilevato throttling
(speed_limit < 100%) durante qualsiasi esecuzione.

### KV Cache e lunghezza contesto

Dimensioni di contesto grandi (32k+) possono causare instabilità delle prestazioni sui motori che pre-allocano
la KV cache al caricamento del modello. Esempio: LM Studio ha come default `loaded_context_length: 262144`
(256k), che alloca ~15-25 GB di KV cache per un modello 35B, potenzialmente saturando
64 GB di memoria unificata.

**Raccomandazioni**:
- Per benchmark con contesti grandi, imposta la lunghezza del contesto del motore in modo che corrisponda alla dimensione effettiva del test
  (es. `lms load model --context-length 65536` per test a 64k).
- Confronta i motori con impostazioni di lunghezza contesto equivalenti per risultati equi.

## Metadati salvati per benchmark

Ogni risultato di benchmark in SQLite include:

| Campo | Esempio | Scopo |
|-------|---------|---------|
| `engine` | "ollama" | Identificazione motore |
| `engine_version` | "0.17.4" | Rilevare cambiamenti di prestazioni tra aggiornamenti |
| `model` | "qwen3.5:35b-a3b" | Identificazione modello |
| `model_format` | "gguf" | Differenziare varianti di formato |
| `model_quantization` | "Q4_K_M" | Differenziare livelli di quantizzazione |
| `hw_chip` | "Apple M4 Pro" | Identificazione hardware |
| `os_version` | "15.3" | Tracciamento versione macOS |
| `thermal_level` | "nominal" | Condizione ambientale |
| `thermal_speed_limit` | 100 | Rilevamento throttling |
| `metrics_version` | 2 | Versione formula (previene regressione tra versioni) |

Questi metadati consentono:
- **Confronto di regressione equo**: confrontare solo risultati con metadati corrispondenti
- **Benchmark tra macchine**: identificare differenze hardware
- **Condivisione dati comunitari**: risultati auto-descrittivi (pianificato per v1.x)
