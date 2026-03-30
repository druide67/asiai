---
description: "Definizioni dettagliate di tutte le metriche di benchmark di asiai: tok/s, TTFT, watt di potenza, efficienza, VRAM, stabilità, stato termico."
---

# Specifica delle metriche di benchmark

> **Versione**: 0.4.0
> **Stato**: Implementato
> **Ambito**: `asiai bench` — tutti i motori

## Motivazione

I risultati dei benchmark devono essere **confrontabili tra motori**. Ogni metrica ha un'unica definizione
che tutte le implementazioni dei motori devono rispettare. L'implementazione può variare (API server vs
misurazione lato client), ma la semantica deve essere identica.

## Metriche

### M1. `tok_per_sec` — Velocità di generazione

**Definizione**: Token prodotti al secondo di **tempo di generazione**, escludendo l'elaborazione
del prompt (TTFT).

```
generation_s = total_duration_s - ttft_s
tok_per_sec  = tokens_generated / generation_s    (if generation_s >= 0.01)
             = 0.0                                 (otherwise)
```

| Motore | Sorgente `generation_s` |
|--------|----------------------|
| Ollama | `eval_duration / 1e9` (API server — diretto) |
| OpenAI-compat | `elapsed_s - (ttft_ms / 1000)` (lato client) |

**Razionale**: Con dimensioni di contesto grandi (es. 64k token), il TTFT può dominare la durata totale.
Includerlo nei tok/s fa apparire generatori veloci come lenti (es. 3,2 tok/s invece di 42 tok/s).

### M2. `ttft_ms` — Tempo al primo token

**Definizione**: Tempo tra l'invio della richiesta e la ricezione del primo token di output, in ms.

| Motore | Sorgente |
|--------|--------|
| Ollama | `prompt_eval_duration / 1e6` (API server) |
| OpenAI-compat | `(time.monotonic() at 1st content chunk - t0) * 1000` (client) |

Nota: La semantica differisce leggermente (misurazione server vs client), ma su localhost la differenza è
~1ms — accettabile.

### M3. `total_duration_ms` — Durata totale

**Definizione**: Tempo totale wall-clock della richiesta (elaborazione prompt + generazione), in ms.

**Invariante**: `total_duration_ms >= ttft_ms` — sempre.

| Motore | Sorgente |
|--------|--------|
| Ollama | `total_duration / 1e6` (API server) |
| OpenAI-compat | `elapsed_s * 1000` (wall-clock client) |

### M4. `tokens_generated` — Conteggio token

**Definizione**: Numero di token di output prodotti dal modello.

**Sorgente (per priorità)**:
1. Contatore server: Ollama `eval_count`, OpenAI-compat `usage.completion_tokens`
2. Stima dalla lunghezza del testo: `max(1, len(text) // 4)` (euristica: ~4 caratteri/token)
3. **Mai** `len(text_parts)` (chunk SSE != token)

### M5. `generation_duration_ms` — Durata della generazione

**Definizione**: Tempo di sola generazione (escludendo TTFT), in ms.
Rende la scomposizione `total = ttft + generation` esplicita e verificabile.

| Motore | Sorgente |
|--------|--------|
| Ollama | `eval_duration / 1e6` (API server — diretto) |
| OpenAI-compat | `max(0, elapsed_s - ttft_s) * 1000` (calcolato) |

### M6. `power_watts` — Potenza GPU

**Definizione**: Potenza media GPU durante l'esecuzione di **questo specifico motore**, in watt.

**Ambito**: Un `PowerMonitor` per motore. Avviato prima del primo prompt, fermato dopo
l'ultima esecuzione. Ogni motore ottiene la sua misurazione — nessuna media a livello di sessione.

Sorgente: `sudo powermetrics` (macOS).

### M7. `tok_per_sec_per_watt` — Efficienza energetica

```
tok_per_sec_per_watt = tok_per_sec / power_watts
```

Usa i tok/s corretti (M1) e la potenza per motore (M6).

### M8. `std_dev_tok_s` — Varianza (combinata)

**Definizione**: Deviazione standard combinata intra-prompt — cattura il rumore tra esecuzioni
**senza** mescolare la varianza tra prompt.

```
For each prompt_type p with runs [v1, v2, ..., vn]:
    var_p = sum((vi - mean_p)^2) / n    (population variance)

pooled_variance = mean(var_p for all p with n >= 2)
std_dev_tok_s   = sqrt(pooled_variance)
```

**Classificazione di stabilità** (invariata):
- CV < 5% → `stable`
- CV < 10% → `variable`
- CV >= 10% → `unstable`

Dove CV = `(std_dev_tok_s / avg_tok_s) * 100`.

## Mappa di implementazione

| Metrica | `base.py` | `ollama.py` | `openai_compat.py` | `runner.py` | `reporter.py` |
|--------|-----------|-------------|--------------------|-----------  |----------------|
| M1 tok/s | field | server API | client (excl. TTFT) | passthrough | avg |
| M2 ttft_ms | field | server API | client streaming | passthrough | avg |
| M3 total_duration_ms | field | server API | client wall-clock | passthrough | avg |
| M4 tokens_generated | field | server API | server or `len//4` | passthrough | avg |
| M5 generation_duration_ms | field | server API | computed | stored in dict | — |
| M6 power_watts | — | — | — | per-engine monitor | passthrough |
| M7 tok/s/W | — | — | — | computed | passthrough |
| M8 std_dev | — | — | — | — | pooled intra-prompt |

## Protocollo di benchmark

1. **Warmup**: 1 generazione non cronometrata per motore (`"Hello"`, max_tokens=1) per preparare le cache.
2. **Esecuzioni misurate**: Di default 3 esecuzioni per prompt per motore (configurabile con `--runs`).
3. **Campionamento**: `temperature=0` (greedy) su tutti i motori per output deterministico.
4. **Report**: Mediana tok/s come metrica primaria (standard SPEC), media +/- deviazione standard come secondaria.
5. **Throttling**: Avvertimento emesso se `thermal_speed_limit < 100%` durante qualsiasi esecuzione.
6. **Metadati**: engine_version, model_format, model_quantization, hw_chip, os_version
   salvati per risultato per la riproducibilità.

Vedi [benchmark-best-practices.md](benchmark-best-practices.md) per l'audit completo della metodologia.
