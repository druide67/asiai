---
description: Raccomandazioni modello consapevoli dell'hardware basate su RAM, core GPU e margine termico del tuo Mac.
---

# asiai recommend

Ottieni raccomandazioni sui motori per il tuo hardware e caso d'uso.

## Uso

```bash
asiai recommend [options]
```

## Opzioni

| Opzione | Descrizione |
|--------|-------------|
| `--model MODEL` | Modello per cui ottenere raccomandazioni |
| `--use-case USE_CASE` | Ottimizza per: `throughput`, `latency` o `efficiency` |
| `--community` | Includi dati benchmark della community nelle raccomandazioni |
| `--db PATH` | Percorso al database benchmark locale |

## Fonti dati

Le raccomandazioni sono costruite dai migliori dati disponibili, in ordine di priorità:

1. **Benchmark locali** — le tue esecuzioni sul tuo hardware
2. **Dati comunitari** — risultati aggregati da chip simili (con `--community`)
3. **Euristiche** — regole integrate quando non sono disponibili dati benchmark

## Livelli di confidenza

| Livello | Criterio |
|-------|----------|
| Alto | 5 o più esecuzioni benchmark locali |
| Medio | Da 1 a 4 esecuzioni locali, o dati comunitari disponibili |
| Basso | Basato su euristiche, nessun dato benchmark |

## Esempio

```bash
asiai recommend --model qwen3.5 --use-case throughput
```

```
  Recommendation: qwen3.5 — M4 Pro — throughput

  #   Engine       tok/s    Confidence   Source
  ── ────────── ──────── ──────────── ──────────
  1   lmstudio    72.6     high         local (5 runs)
  2   ollama      30.4     high         local (5 runs)
  3   exo         18.2     medium       community

  Tip: lmstudio is 2.4x faster than ollama for this model.
```

## Note

- Esegui `asiai bench` prima per le raccomandazioni più accurate.
- Usa `--community` per colmare le lacune quando non hai valutato un motore specifico localmente.
- Il caso d'uso `efficiency` tiene conto del consumo energetico (richiede dati `--power` da benchmark precedenti).
