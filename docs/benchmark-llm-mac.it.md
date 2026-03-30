---
title: "Come fare benchmark di LLM su Mac"
description: "Come fare benchmark dell'inferenza LLM su Mac: guida passo passo per misurare tok/s, TTFT, potenza e VRAM su Apple Silicon con più motori."
type: howto
date: 2026-03-28
updated: 2026-03-29
duration: PT5M
steps:
  - name: "Installa asiai"
    text: "Installa asiai tramite pip (pip install asiai) o Homebrew (brew tap druide67/tap && brew install asiai)."
  - name: "Rileva i tuoi motori"
    text: "Esegui 'asiai detect' per trovare automaticamente i motori di inferenza in esecuzione (Ollama, LM Studio, llama.cpp, mlx-lm, oMLX, vLLM-MLX, Exo) sul tuo Mac."
  - name: "Esegui un benchmark"
    text: "Esegui 'asiai bench' per auto-rilevare il miglior modello tra i motori ed eseguire un confronto cross-engine misurando tok/s, TTFT, potenza e VRAM."
---

# Come fare benchmark di LLM su Mac

Esegui un LLM locale sul tuo Mac? Ecco come misurare le prestazioni reali — non sensazioni, non "sembra veloce", ma tok/s, TTFT, consumo energetico e utilizzo di memoria effettivi.

## Perché fare benchmark?

Lo stesso modello gira a velocità molto diverse a seconda del motore di inferenza. Su Apple Silicon, i motori basati su MLX (LM Studio, mlx-lm, oMLX) possono essere **2x più veloci** rispetto ai motori basati su llama.cpp (Ollama) per lo stesso modello. Senza misurare, stai lasciando prestazioni sul tavolo.

## Avvio rapido (2 minuti)

### 1. Installa asiai

```bash
pip install asiai
```

Oppure tramite Homebrew:

```bash
brew tap druide67/tap
brew install asiai
```

### 2. Rileva i tuoi motori

```bash
asiai detect
```

asiai trova automaticamente i motori in esecuzione (Ollama, LM Studio, llama.cpp, mlx-lm, oMLX, vLLM-MLX, Exo) sul tuo Mac.

### 3. Esegui un benchmark

```bash
asiai bench
```

È tutto. asiai rileva automaticamente il miglior modello tra i tuoi motori e esegue un confronto cross-engine.

## Cosa viene misurato

| Metrica | Cosa significa |
|--------|--------------|
| **tok/s** | Token generati al secondo (solo generazione, esclusa l'elaborazione del prompt) |
| **TTFT** | Time to First Token — latenza prima dell'inizio della generazione |
| **Potenza** | Watt GPU + CPU durante l'inferenza (tramite IOReport, nessun sudo necessario) |
| **tok/s/W** | Efficienza energetica — token al secondo per watt |
| **VRAM** | Memoria usata dal modello (API nativa o stimata tramite `ri_phys_footprint`) |
| **Stabilità** | Varianza tra esecuzioni: stabile (<5% CV), variabile (<10%), instabile (>10%) |
| **Termica** | Se il tuo Mac ha subito throttling durante il benchmark |

## Output di esempio

```
Mac16,11 — Apple M4 Pro  RAM: 64.0 GB  Pressure: normal

Benchmark: qwen3-coder-30b

  Engine        tok/s   Tokens Duration     TTFT       VRAM    Thermal
  lmstudio      102.2      537    7.00s    0.29s    24.2 GB    nominal
  ollama         69.8      512   17.33s    0.18s    32.0 GB    nominal

  Winner: lmstudio (+46% tok/s)

  Power Efficiency
    lmstudio     102.2 tok/s @ 12.4W = 8.23 tok/s/W
    ollama        69.8 tok/s @ 15.4W = 4.53 tok/s/W
```

*Output di esempio da un benchmark reale su M4 Pro 64GB. I tuoi numeri varieranno in base a hardware e modello. [Vedi altri risultati →](ollama-vs-lmstudio.md)*

## Opzioni avanzate

### Confronta motori specifici

```bash
asiai bench --engines ollama,lmstudio,omlx
```

### Prompt multipli e più esecuzioni

```bash
asiai bench --prompts code,reasoning,tool_call --runs 3
```

### Benchmark con contesto grande

```bash
asiai bench --context-size 64K
```

### Genera una scheda condivisibile

```bash
asiai bench --card --share
```

Crea un'immagine di scheda benchmark e condivide i risultati con la [classifica comunitaria](leaderboard.md).

## Consigli per Apple Silicon

### La memoria conta

Su un Mac da 16GB, resta con modelli sotto i 14GB (caricati). I modelli MoE (Qwen3.5-35B-A3B, 3B attivi) sono ideali — offrono qualità da 35B con utilizzo di memoria da 7B.

### La scelta del motore conta più di quanto pensi

I motori MLX sono significativamente più veloci di llama.cpp su Apple Silicon per la maggior parte dei modelli. [Vedi il nostro confronto Ollama vs LM Studio](ollama-vs-lmstudio.md) per numeri reali.

### Throttling termico

MacBook Air (senza ventola) subisce throttling dopo 5-10 minuti di inferenza sostenuta. Mac Mini/Studio/Pro gestiscono carichi di lavoro sostenuti senza throttling. asiai rileva e riporta il throttling termico automaticamente.

## Confronta con la community

Guarda come si posiziona il tuo Mac rispetto ad altre macchine Apple Silicon:

```bash
asiai compare
```

Oppure visita la [classifica online](leaderboard.md).

## FAQ

**D: Qual è il motore di inferenza LLM più veloce su Apple Silicon?**
R: Nei nostri benchmark su M4 Pro 64GB, LM Studio (backend MLX) è il più veloce per la generazione di token — 46% più veloce di Ollama (llama.cpp). Tuttavia, Ollama ha un TTFT (time to first token) più basso. Vedi il nostro [confronto dettagliato](ollama-vs-lmstudio.md).

**D: Quanta RAM serve per eseguire un modello 30B su Mac?**
R: Un modello 30B quantizzato Q4_K_M usa 24-32 GB di memoria unificata a seconda del motore. Servono almeno 32 GB di RAM, idealmente 64 GB per evitare pressione di memoria. I modelli MoE come Qwen3.5-35B-A3B usano solo ~7 GB di parametri attivi.

**D: asiai funziona su Mac Intel?**
R: No. asiai richiede Apple Silicon (M1/M2/M3/M4). Usa API specifiche di macOS per metriche GPU, monitoraggio energetico e rilevamento hardware disponibili solo su Apple Silicon.

**D: Ollama o LM Studio è più veloce su M4?**
R: LM Studio è più veloce per il throughput (102 tok/s vs 70 tok/s su Qwen3-Coder-30B). Ollama è più veloce per la latenza del primo token (0.18s vs 0.29s) e per finestre di contesto grandi (>32K token) dove il prefill di llama.cpp è fino a 3x più veloce.

**D: Quanto dura un benchmark?**
R: Un benchmark rapido richiede circa 2 minuti. Un confronto completo cross-engine con prompt multipli e più esecuzioni richiede 10-15 minuti. Usa `asiai bench --quick` per un test rapido a singola esecuzione.

**D: Posso confrontare i miei risultati con altri utenti Mac?**
R: Sì. Esegui `asiai bench --share` per inviare anonimamente i risultati alla [classifica comunitaria](leaderboard.md). Usa `asiai compare` per vedere come si confronta il tuo Mac con altre macchine Apple Silicon.

## Approfondimenti

- [Metodologia di benchmark](methodology.md) — come asiai garantisce misurazioni affidabili
- [Best practice per i benchmark](benchmark-best-practices.md) — consigli per risultati accurati
- [Confronto motori](ollama-vs-lmstudio.md) — Ollama vs LM Studio testa a testa
