---
description: Esegui benchmark comparativi di LLM su Apple Silicon. Confronta motori, misura tok/s, TTFT, efficienza energetica. Condividi i risultati.
---

# asiai bench

Benchmark cross-engine con prompt standardizzati.

## Uso

```bash
asiai bench [options]
```

## Opzioni

| Opzione | Descrizione |
|--------|-------------|
| `-m, --model MODEL` | Modello da valutare (default: rilevamento automatico) |
| `-e, --engines LIST` | Filtra motori (es. `ollama,lmstudio,mlxlm`) |
| `-p, --prompts LIST` | Tipi di prompt: `code`, `tool_call`, `reasoning`, `long_gen` |
| `-r, --runs N` | Esecuzioni per prompt (default: 3, per mediana + deviazione standard) |
| `--power` | Validazione incrociata potenza con sudo powermetrics (IOReport sempre attivo) |
| `--context-size SIZE` | Prompt di riempimento contesto: `4k`, `16k`, `32k`, `64k` |
| `--export FILE` | Esporta risultati in file JSON |
| `-H, --history PERIOD` | Mostra benchmark precedenti (es. `7d`, `24h`) |
| `-Q, --quick` | Benchmark rapido: 1 prompt (code), 1 esecuzione (~15 secondi) |
| `--compare MODEL [MODEL...]` | Confronto tra modelli (2-8 modelli, mutuamente esclusivo con `-m`) |
| `--card` | Genera una scheda benchmark condivisibile (SVG locale, PNG con `--share`) |
| `--share` | Condividi i risultati nel database comunitario |

## Esempio

```bash
asiai bench -m qwen3.5 --runs 3 --power
```

```
  Mac Mini M4 Pro — Apple M4 Pro  RAM: 64.0 GB (42% used)  Pressure: normal

Benchmark: qwen3.5

  Engine       tok/s (±stddev)    Tokens   Duration     TTFT       VRAM    Thermal
  ────────── ───────────────── ───────── ────────── ──────── ────────── ──────────
  lmstudio    72.6 ± 0.0 (stable)   435    6.20s    0.28s        —    nominal
  ollama      30.4 ± 0.1 (stable)   448   15.28s    0.25s   26.0 GB   nominal

  Winner: lmstudio (2.4x faster)
  Power: lmstudio 13.2W (5.52 tok/s/W) — ollama 16.0W (1.89 tok/s/W)
```

## Prompt

Quattro prompt standardizzati testano diversi pattern di generazione:

| Nome | Token | Testa |
|------|--------|-------|
| `code` | 512 | Generazione di codice strutturato (BST in Python) |
| `tool_call` | 256 | Chiamate a funzioni JSON / seguimento istruzioni |
| `reasoning` | 384 | Problema matematico multi-step |
| `long_gen` | 1024 | Throughput sostenuto (script bash) |

Usa `--context-size` per testare con prompt di riempimento contesto grande.

## Corrispondenza modelli cross-engine

Il runner risolve i nomi dei modelli tra motori automaticamente — `gemma2:9b` (Ollama) e `gemma-2-9b` (LM Studio) vengono riconosciuti come lo stesso modello.

## Esportazione JSON

Esporta i risultati per condivisione o analisi:

```bash
asiai bench -m qwen3.5 --export bench.json
```

Il JSON include metadati della macchina, statistiche per motore (mediana, IC 95%, P50/P90/P99), dati grezzi per esecuzione e una versione dello schema per compatibilità futura.

## Rilevamento regressione

Dopo ogni benchmark, asiai confronta i risultati con lo storico degli ultimi 7 giorni e avvisa su regressioni di prestazioni (es. dopo un aggiornamento del motore o di macOS).

## Benchmark rapido

Esegui un benchmark rapido con un singolo prompt e un'esecuzione (~15 secondi):

```bash
asiai bench --quick
asiai bench -Q -m qwen3.5
```

Ideale per demo, GIF e controlli rapidi. Il prompt `code` viene usato di default. Puoi sovrascriverlo con `--prompts` se necessario.

## Confronto tra modelli

Confronta più modelli in una singola sessione con `--compare`:

```bash
# Espansione automatica a tutti i motori disponibili
asiai bench --compare qwen3.5:4b deepseek-r1:7b

# Filtra a un motore specifico
asiai bench --compare qwen3.5:4b deepseek-r1:7b -e ollama

# Fissa ogni modello a un motore con @
asiai bench --compare qwen3.5:4b@lmstudio deepseek-r1:7b@ollama
```

La notazione `@` divide sull'**ultimo** `@` nella stringa, quindi i nomi di modelli contenenti `@` vengono gestiti correttamente.

### Regole

- `--compare` e `--model` sono **mutuamente esclusivi** — usa uno o l'altro.
- Accetta da 2 a 8 slot di modello.
- Senza `@`, ogni modello viene espanso a tutti i motori dove è disponibile.

### Tipi di sessione

Il tipo di sessione viene rilevato automaticamente in base alla lista degli slot:

| Tipo | Condizione | Esempio |
|------|-----------|---------|
| **engine** | Stesso modello, motori diversi | `--compare qwen3.5:4b@lmstudio qwen3.5:4b@ollama` |
| **model** | Modelli diversi, stesso motore | `--compare qwen3.5:4b deepseek-r1:7b -e ollama` |
| **matrix** | Mix di modelli e motori | `--compare qwen3.5:4b@lmstudio deepseek-r1:7b@ollama` |

### Combinato con altre opzioni

`--compare` funziona con tutte le opzioni di output e esecuzione:

```bash
asiai bench --compare qwen3.5:4b deepseek-r1:7b --quick
asiai bench --compare qwen3.5:4b deepseek-r1:7b --card --share
asiai bench --compare qwen3.5:4b deepseek-r1:7b --runs 5 --power
```

## Scheda benchmark

Genera una scheda benchmark condivisibile:

```bash
asiai bench --card                    # SVG salvato localmente
asiai bench --card --share            # SVG + PNG (via API comunitaria)
asiai bench --quick --card --share    # Benchmark rapido + scheda + condivisione
```

La scheda è un'immagine 1200x630 a tema scuro con:
- Nome del modello e badge del chip hardware
- Banner specifiche: quantizzazione, RAM, core GPU, dimensione contesto
- Grafico a barre stile terminale dei tok/s per motore
- Evidenziazione del vincitore con delta (es. "2.4x")
- Chip di metriche: tok/s, TTFT, stabilità, VRAM, potenza (W + tok/s/W), versione motore
- Branding asiai

L'SVG è salvato in `~/.local/share/asiai/cards/`. Con `--share`, viene anche scaricato un PNG dall'API.

## Condivisione comunitaria

Condividi i tuoi risultati in modo anonimo:

```bash
asiai bench --share
```

Consulta la classifica comunitaria con `asiai leaderboard`.

## Rilevamento deriva termica

Eseguendo 3+ esecuzioni, asiai rileva la degradazione monotona dei tok/s tra esecuzioni consecutive. Se i tok/s calano costantemente (>5%), viene emesso un avvertimento che indica possibile accumulo di throttling termico.
