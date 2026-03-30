---
title: "Domande frequenti"
description: "Domande frequenti su asiai: motori supportati, requisiti Apple Silicon, benchmark LLM su Mac, requisiti RAM e altro."
type: faq
faq:
  - q: "Cos'è asiai?"
    a: "asiai è uno strumento CLI open-source che esegue benchmark e monitora i motori di inferenza LLM su Mac con Apple Silicon. Supporta 7 motori (Ollama, LM Studio, mlx-lm, llama.cpp, oMLX, vllm-mlx, Exo) e misura tok/s, TTFT, consumo energetico e utilizzo VRAM."
  - q: "Qual è il motore LLM più veloce su Apple Silicon?"
    a: "Nei benchmark su M4 Pro 64GB con Qwen3-Coder-30B, LM Studio (backend MLX) raggiunge 102 tok/s contro i 70 tok/s di Ollama — 46% più veloce nella generazione di token. Tuttavia, Ollama ha una latenza inferiore per il primo token."
  - q: "asiai funziona su Mac Intel?"
    a: "No. asiai richiede Apple Silicon (M1, M2, M3 o M4). Utilizza API specifiche di macOS per le metriche GPU, il monitoraggio energetico con IOReport e il rilevamento hardware disponibili solo su chip Apple Silicon."
  - q: "Quanta RAM serve per eseguire LLM localmente?"
    a: "Per un modello 7B quantizzato Q4: 8 GB minimo. Per 13B: 16 GB. Per 30B: 32-64 GB. I modelli MoE come Qwen3.5-35B-A3B usano solo circa 7 GB di parametri attivi, rendendoli ideali per Mac da 16 GB."
  - q: "È meglio Ollama o LM Studio per Mac?"
    a: "Dipende dal caso d'uso. LM Studio (MLX) è più veloce per il throughput e più efficiente energeticamente. Ollama (llama.cpp) ha latenza inferiore al primo token e gestisce meglio le finestre di contesto grandi (>32K). Vedi il confronto dettagliato su asiai.dev/ollama-vs-lmstudio."
  - q: "asiai richiede sudo o accesso root?"
    a: "No. Tutte le funzionalità, inclusa l'osservabilità GPU (ioreg) e il monitoraggio energetico (IOReport), funzionano senza sudo. Il flag opzionale --power per la validazione incrociata con powermetrics è l'unica funzione che usa sudo."
  - q: "Come installo asiai?"
    a: "Installa tramite pip (pip install asiai) o Homebrew (brew tap druide67/tap && brew install asiai). Richiede Python 3.11+."
  - q: "Gli agenti IA possono usare asiai?"
    a: "Sì. asiai include un server MCP con 11 strumenti e 3 risorse. Installa con pip install asiai[mcp] e configura come asiai mcp nel tuo client MCP (Claude Code, Cursor, ecc.)."
  - q: "Quanto sono accurate le misurazioni di potenza?"
    a: "Le letture di potenza IOReport hanno meno dell'1,5% di differenza rispetto a sudo powermetrics, validate su 20 campioni sia su LM Studio (MLX) che su Ollama (llama.cpp)."
  - q: "Posso fare benchmark di più modelli contemporaneamente?"
    a: "Sì. Usa asiai bench --compare per eseguire benchmark cross-model. Supporta la sintassi modello@motore per controllo preciso, con fino a 8 slot di confronto."
  - q: "Come condivido i miei risultati di benchmark?"
    a: "Esegui asiai bench --share per inviare i risultati in modo anonimo alla classifica comunitaria. Aggiungi --card per generare un'immagine di scheda benchmark 1200x630 condivisibile."
  - q: "Quali metriche misura asiai?"
    a: "Sette metriche principali: tok/s (velocità di generazione), TTFT (tempo al primo token), potenza (watt GPU+CPU), tok/s/W (efficienza energetica), utilizzo VRAM, stabilità tra esecuzioni e stato di throttling termico."
---

# Domande frequenti

## Generale

**Cos'è asiai?**

asiai è uno strumento CLI open-source che esegue benchmark e monitora i motori di inferenza LLM su Mac con Apple Silicon. Supporta 7 motori (Ollama, LM Studio, mlx-lm, llama.cpp, oMLX, vllm-mlx, Exo) e misura tok/s, TTFT, consumo energetico e utilizzo VRAM senza dipendenze esterne.

**asiai funziona su Mac Intel o Linux?**

No. asiai richiede Apple Silicon (M1, M2, M3 o M4). Utilizza API specifiche di macOS (`sysctl`, `vm_stat`, `ioreg`, `IOReport`, `launchd`) disponibili solo su Mac con Apple Silicon.

**asiai richiede sudo o accesso root?**

No. Tutte le funzionalità, inclusa l'osservabilità GPU (`ioreg`) e il monitoraggio energetico (`IOReport`), funzionano senza sudo. Il flag `--power` per la validazione incrociata con `powermetrics` è l'unica funzione che usa sudo.

## Motori e prestazioni

**Qual è il motore LLM più veloce su Apple Silicon?**

Nei nostri benchmark su M4 Pro 64GB con Qwen3-Coder-30B (Q4_K_M), LM Studio (backend MLX) raggiunge **102 tok/s** contro i **70 tok/s** di Ollama — 46% più veloce nella generazione di token. LM Studio è anche l'82% più efficiente energeticamente (8,23 vs 4,53 tok/s/W). Vedi il nostro [confronto dettagliato](ollama-vs-lmstudio.md).

**È meglio Ollama o LM Studio per Mac?**

Dipende dal caso d'uso:

- **LM Studio (MLX)**: Ideale per il throughput (generazione di codice, risposte lunghe). Più veloce, più efficiente, meno VRAM.
- **Ollama (llama.cpp)**: Ideale per la latenza (chatbot, uso interattivo). TTFT più rapido. Migliore per finestre di contesto grandi (>32K token).

**Quanta RAM serve per eseguire LLM localmente?**

| Dimensione modello | Quantizzazione | RAM necessaria |
|-----------|-------------|-----------|
| 7B | Q4_K_M | 8 GB minimo |
| 13B | Q4_K_M | 16 GB minimo |
| 30B | Q4_K_M | 32-64 GB |
| 35B MoE (3B attivi) | Q4_K_M | 16 GB (solo i parametri attivi vengono caricati) |

## Benchmarking

**Come eseguo il mio primo benchmark?**

Tre comandi:

```bash
pip install asiai     # Installa
asiai detect          # Trova i motori
asiai bench           # Esegui benchmark
```

**Quanto dura un benchmark?**

Un benchmark rapido (`asiai bench --quick`) richiede circa 2 minuti. Un confronto completo cross-engine con prompt multipli e 3 esecuzioni richiede 10-15 minuti.

**Quanto sono accurate le misurazioni di potenza?**

Le letture di potenza IOReport hanno meno dell'1,5% di differenza rispetto a `sudo powermetrics`, validate su 20 campioni sia su LM Studio (MLX) che su Ollama (llama.cpp).

**Posso confrontare i miei risultati con altri utenti Mac?**

Sì. Esegui `asiai bench --share` per inviare i risultati in modo anonimo alla [classifica comunitaria](leaderboard.md). Usa `asiai compare` per vedere come si confronta il tuo Mac.

## Integrazione con agenti IA

**Gli agenti IA possono usare asiai?**

Sì. asiai include un server MCP con 11 strumenti e 3 risorse. Installa con `pip install "asiai[mcp]"` e configura come `asiai mcp` nel tuo client MCP (Claude Code, Cursor, Windsurf). Vedi la [Guida all'integrazione con agenti](agent.md).

**Quali strumenti MCP sono disponibili?**

11 strumenti: `check_inference_health`, `get_inference_snapshot`, `list_models`, `detect_engines`, `run_benchmark`, `get_recommendations`, `diagnose`, `get_metrics_history`, `get_benchmark_history`, `refresh_engines`, `compare_engines`.

3 risorse: `asiai://status`, `asiai://models`, `asiai://system`.
