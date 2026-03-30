---
description: Genera schede benchmark condivisibili con i tuoi risultati. SVG o PNG, con modello, motore, hardware e dati di prestazione.
---

# Scheda benchmark

Condividi i tuoi risultati di benchmark come un'immagine bella e brandizzata. Un comando genera una scheda che puoi postare su Reddit, X, Discord o qualsiasi piattaforma social.

## Avvio rapido

```bash
asiai bench --quick --card --share    # Bench + scheda + condivisione in ~15 secondi
asiai bench --card --share            # Bench completo + scheda + condivisione
asiai bench --card                    # SVG + PNG salvati localmente
```

## Esempio

![Esempio di scheda benchmark](assets/benchmark-card-example.png)

## Cosa ottieni

Una **scheda 1200x630 a tema scuro** (formato immagine OG, ottimizzata per i social media) contenente:

- **Badge hardware** — il tuo chip Apple Silicon in evidenza (in alto a destra)
- **Nome del modello** — quale modello è stato valutato
- **Confronto motori** — grafico a barre stile terminale che mostra tok/s per motore
- **Evidenziazione del vincitore** — quale motore è più veloce e di quanto
- **Chip metriche** — tok/s, TTFT, rating di stabilità, utilizzo VRAM
- **Branding asiai** — logo mark + badge "asiai.dev"

Il formato è progettato per massima leggibilità quando condiviso come miniatura su Reddit, X o Discord.

## Come funziona

```
asiai bench --card --share
        │
        ▼
  ┌──────────┐     ┌──────────────┐     ┌──────────────┐
  │ Benchmark │────▶│ Genera SVG   │────▶│  Salva locale │
  │  (normal) │     │  (zero-dep)  │     │ ~/.local/     │
  └──────────┘     └──────┬───────┘     │ share/asiai/  │
                          │             │ cards/         │
                          ▼             └──────────────┘
                   ┌──────────────┐
                   │ --share ?    │
                   │ Invia bench  │
                   │ + ottieni PNG│
                   └──────┬───────┘
                          │
                          ▼
                   ┌──────────────┐
                   │ URL          │
                   │ condivisibile│
                   │ + PNG        │
                   └──────────────┘
```

### Modalità locale (predefinita)

SVG generato localmente con **zero dipendenze** — niente Pillow, niente Cairo, niente ImageMagick. Puro templating di stringhe Python. Funziona offline.

Le schede sono salvate in `~/.local/share/asiai/cards/`. L'SVG è perfetto per l'anteprima locale, ma **Reddit, X e Discord richiedono PNG** — aggiungi `--share` per ottenere un PNG e un URL condivisibile.

### Modalità condivisione

Quando combinato con `--share`, il benchmark viene inviato all'API comunitaria, che genera una versione PNG lato server. Ottieni:

- Un **file PNG** scaricato localmente
- Un **URL condivisibile** su `asiai.dev/card/{submission_id}`

## Casi d'uso

### Reddit / r/LocalLLaMA

> "Ho appena testato Qwen 3.5 sul mio M4 Pro — LM Studio 2.4x più veloce di Ollama"
> *[allega immagine della scheda]*

I post di benchmark con immagini ottengono **5-10x più coinvolgimento** rispetto ai post di solo testo.

### X / Twitter

Il formato 1200x630 è esattamente la dimensione immagine OG — si visualizza perfettamente come anteprima scheda nei tweet.

### Discord / Slack

Lascia il PNG in qualsiasi canale. Il tema scuro assicura leggibilità su piattaforme in dark mode.

### README GitHub

Mostra i tuoi risultati di benchmark personali nel README del tuo profilo GitHub:

```markdown
![I miei benchmark LLM](asiai-card.png)
```

## Combina con --quick

Per condivisione rapida:

```bash
asiai bench -Q --card --share
```

Esegue un singolo prompt (~15 secondi), genera la scheda e condivide — perfetto per confronti rapidi dopo l'installazione di un nuovo modello o l'aggiornamento di un motore.

## Filosofia di design

Ogni scheda condivisa include il branding asiai. Questo crea un **loop virale**:

1. L'utente fa il benchmark del suo Mac
2. L'utente condivide la scheda sui social media
3. Chi guarda vede la scheda brandizzata
4. Chi guarda scopre asiai
5. I nuovi utenti fanno il benchmark e condividono le proprie schede

Questo è il [modello Speedtest.net](https://www.speedtest.net) adattato per l'inferenza LLM locale.
