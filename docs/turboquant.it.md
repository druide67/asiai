---
title: "Benchmark TurboQuant su Apple Silicon: eseguire modelli 70B su Mac"
description: "Benchmark reali della compressione KV cache TurboQuant su Mac Mini M4 Pro 64 GB: Llama 70B a 6,3 tok/s con 5x di risparmio di memoria. Guida all'installazione e risultati."
type: article
date: 2026-03-31
updated: 2026-03-31
faq:
  - q: "Posso eseguire un modello 70B su un Mac con 64 GB di RAM?"
    a: "Sì, con TurboQuant. La KV cache viene compressa 5x, quindi Llama 70B Q4_K_M (40 GB di pesi) entra comodamente in 64 GB con un contesto di 32K. Abbiamo misurato 6,3 tok/s su un Mac Mini M4 Pro."
  - q: "TurboQuant riduce la qualità?"
    a: "Nessuna perdita di qualità misurabile. L'aumento della perplessità è inferiore all'1 % rispetto a q8_0, e il punteggio di recupero Needle-in-a-Haystack raggiunge il 100 % su un contesto di 32K."
  - q: "Quale formato TurboQuant dovrei usare?"
    a: "Raccomandiamo asimmetrico: q8_0 per le chiavi (sensibili alla compressione) e turbo3 per i valori (compressione 5x, nessun impatto sulla qualità). Questo si basa sui risultati del progetto turboquant_plus."
  - q: "TurboQuant funziona con i motori MLX?"
    a: "Esistono implementazioni MLX della comunità ma sono meno mature del fork llama.cpp. Per l'uso in produzione su Apple Silicon, raccomandiamo TheTom/llama-cpp-turboquant con kernel Metal."
  - q: "Quanto è più veloce TurboQuant?"
    a: "La velocità di decodifica è circa 0,9x di q8_0 (leggermente più lento per token), ma il prefill può essere più veloce su contesti lunghi grazie alla riduzione della larghezza di banda della memoria. Il vero vantaggio è far entrare modelli più grandi e contesti più lunghi nella stessa RAM."
---

# Benchmark TurboQuant su Apple Silicon

TurboQuant (Google Research, ICLR 2026) comprime la KV cache dei LLM di 5x senza perdita di qualità, permettendo di eseguire modelli 70B su un Mac Mini con 64 GB di RAM. Questi sono benchmark reali misurati con [asiai](/) su hardware reale.

## Risultati

**Llama-3.1-70B-Instruct Q4_K_M su Mac Mini M4 Pro 64 GB**

| Metrica | Valore |
|---------|--------|
| **Throughput** | 6,3 tok/s (stabile, IC 95 %: 6,3-6,3) |
| **TTFT** | 196 ms (mediana) |
| **Potenza GPU** | 23,8 W |
| **VRAM modello** | 44,1 GB (40 GB pesi + 4 GB KV turbo3) |
| **Contesto** | 32.768 token |
| **GPU Offload** | 81/81 strati su Metal |
| **Termico** | Nominale (nessun throttling) |
| **Stabilità** | Stabile (deviazione standard 0,04 tok/s su 3 esecuzioni) |

Configurazione della KV cache: chiavi a q8_0 (alta precisione), valori a turbo3 (3 bit, compressione 5x).

## Prima vs Dopo TurboQuant

| | Senza TurboQuant | Con TurboQuant (turbo3) |
|--|-------------------|--------------------------|
| **KV cache (ctx 32K)** | ~20 GB (q8_0) | ~4 GB (turbo3) |
| **RAM totale necessaria** | 60+ GB (OOM su 64 GB) | 44 GB (entra in 64 GB) |
| **Si può eseguire 70B su 64 GB?** | No | **Sì** |
| **Qualità** | Riferimento | -1 % PPL (trascurabile) |
| **Recupero NIAH** | 100 % | 100 % |

## Cos'è TurboQuant?

TurboQuant è un algoritmo di compressione della KV cache di Google Research, presentato all'ICLR 2026. Durante l'inferenza dei LLM, la KV cache memorizza gli stati di attenzione intermedi e cresce linearmente con la lunghezza del contesto. Per un modello 70B con contesto di 128K in FP16, questa cache da sola può consumare 20-40 GB di RAM.

TurboQuant comprime questa cache a 3 bit per valore utilizzando:

- **Rotazione casuale** (trasformata di Walsh-Hadamard) per gaussianizzare i dati
- **Quantizzazione scalare ottimale** (PolarQuant) vicino al limite di Shannon
- **QJL** (Quantized Johnson-Lindenstrauss) per preservare i prodotti scalari

Il risultato: 5x di riduzione della memoria, nessun fine-tuning necessario e perdita di qualità quasi nulla.

## Guida all'installazione

### Hardware

- Mac Mini M4 Pro, 64 GB di memoria unificata (2.700 $)
- Qualsiasi Mac Apple Silicon con 32+ GB dovrebbe funzionare (regolare le dimensioni del modello di conseguenza)

### Installare TurboQuant llama.cpp

```bash
# Install build tools
brew install cmake

# Clone the TurboQuant fork
git clone https://github.com/TheTom/llama-cpp-turboquant.git
cd llama-cpp-turboquant
git checkout feature/turboquant-kv-cache

# Build with Metal (Apple Silicon GPU)
cmake -B build -DGGML_METAL=ON -DGGML_METAL_EMBED_LIBRARY=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(sysctl -n hw.ncpu)
```

### Scaricare un modello

```bash
# Llama 3.1 70B Q4_K_M (~40 GB)
curl -L -o llama-3.1-70b-q4_k_m.gguf \
  "https://huggingface.co/bartowski/Meta-Llama-3.1-70B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-70B-Instruct-Q4_K_M.gguf"
```

### Aumentare il limite di memoria GPU di macOS

```bash
sudo sysctl iogpu.wired_limit_mb=61440
```

### Avviare il server

```bash
./build/bin/llama-server \
  -m llama-3.1-70b-q4_k_m.gguf \
  --cache-type-k q8_0 --cache-type-v turbo3 \
  -c 32768 \
  --port 8081 \
  --host 0.0.0.0 \
  -fa 1 \
  -ngl 99 \
  -t 10 \
  --no-mmap \
  --chat-template chatml
```

### Spiegazione della configurazione

| Parametro | Valore | Perché |
|-----------|--------|--------|
| `--cache-type-k q8_0` | Chiavi a 8 bit | Le chiavi sono sensibili alla compressione |
| `--cache-type-v turbo3` | Valori a 3 bit | I valori tollerano una compressione estrema (5x) |
| `-fa 1` | Flash Attention | Richiesto per TurboQuant |
| `-ngl 99` | GPU offload completo | Tutti gli 81 strati su Metal |
| `-t 10` | 10 thread | M4 Pro ha 10 core ad alte prestazioni |
| `--no-mmap` | Nessun memory mapping | Carica tutto all'avvio, evita i page fault |
| `--chat-template chatml` | Formato ChatML | Migliore compatibilità con questo fork |

## Benchmark con asiai

```bash
pip install asiai
asiai detect --url http://localhost:8081
asiai bench --engines llamacpp --prompts code --runs 3 --kv-cache turbo3 --card
```

## Modelli che entrano in 64 GB con TurboQuant

| Modello | Pesi (Q4_K_M) | KV Cache (32K, turbo3) | Totale | Stato |
|---------|---------------|----------------------|--------|-------|
| Llama 3.1 70B | 40 GB | ~4 GB | 44 GB | **Testato: 6,3 tok/s** |
| Qwen2.5 72B | 40 GB | ~4 GB | 44 GB | Dovrebbe funzionare |
| Llama 70B ctx 128K | 40 GB | ~16 GB (turbo3) | 56 GB | Stretto ma possibile |
| Command-R+ 104B | 58 GB | ~4 GB | 62 GB | Molto stretto |

## FAQ

**Posso eseguire un modello 70B su un Mac con 64 GB di RAM?**

Sì, con TurboQuant. La KV cache viene compressa 5x, quindi Llama 70B Q4_K_M (40 GB di pesi) entra comodamente in 64 GB con un contesto di 32K. Abbiamo misurato 6,3 tok/s su un Mac Mini M4 Pro.

**TurboQuant riduce la qualità?**

Nessuna perdita di qualità misurabile. L'aumento della perplessità è inferiore all'1 % rispetto a q8_0, e il punteggio di recupero Needle-in-a-Haystack raggiunge il 100 % su un contesto di 32K.

**Quale formato TurboQuant dovrei usare?**

Asimmetrico: q8_0 per le chiavi + turbo3 per i valori. Le chiavi sono sensibili alla compressione (tutta la degradazione della qualità proviene dalla compressione delle K). I valori possono essere compressi a 2-3 bit senza alcun effetto sulla qualità dell'attenzione.

**TurboQuant funziona con MLX?**

Esistono implementazioni della comunità ([turboquant-mlx](https://github.com/helgklaizar/turboquant_mlx)) ma sono meno mature del fork llama.cpp. Per l'uso in produzione, raccomandiamo [TheTom/llama-cpp-turboquant](https://github.com/TheTom/llama-cpp-turboquant).

**Come si confronta con il llama.cpp standard?**

La velocità di decodifica è di circa 0,9x di q8_0 (leggermente più lento per token), ma il vero vantaggio è poter utilizzare modelli e contesti che semplicemente non entravano prima. Il prefill può effettivamente essere più veloce su contesti lunghi grazie alla riduzione della pressione sulla larghezza di banda della memoria.

## Riferimenti

- [Google Research Blog — TurboQuant](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/)
- [TurboQuant Paper (ICLR 2026)](https://arxiv.org/abs/2504.19874)
- [TheTom/turboquant_plus](https://github.com/TheTom/turboquant_plus) — Implementazione estesa con Sparse V
- [TheTom/llama-cpp-turboquant](https://github.com/TheTom/llama-cpp-turboquant) — Fork llama.cpp con kernel Metal
- [llama.cpp Discussion #20969](https://github.com/ggml-org/llama.cpp/discussions/20969) — Discussione della comunità
