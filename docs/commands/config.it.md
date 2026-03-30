---
description: "Come configurare asiai: gestire URL dei motori, porte e impostazioni persistenti per il tuo ambiente di benchmark LLM su Mac."
---

# asiai config

Gestisci la configurazione persistente dei motori. I motori scoperti da `asiai detect` vengono salvati automaticamente in `~/.config/asiai/engines.json` per un rilevamento successivo più rapido.

## Uso

```bash
asiai config show              # Mostra motori conosciuti
asiai config add <engine> <url> [--label NAME]  # Aggiungi motore manualmente
asiai config remove <url>      # Rimuovi un motore
asiai config reset             # Cancella tutta la configurazione
```

## Sottocomandi

### show

Mostra tutti i motori conosciuti con URL, versione, origine (auto/manuale) e ultimo timestamp.

```
$ asiai config show
Known engines (3):
  ollama v0.17.7 at http://localhost:11434  (auto)  last seen 2m ago
  lmstudio v0.4.6 at http://localhost:1234  (auto)  last seen 2m ago
  omlx v0.9.2 at http://localhost:8800 [mac-mini]  (manual)  last seen 5m ago
```

### add

Registra manualmente un motore su una porta non standard. I motori manuali non vengono mai eliminati automaticamente.

```bash
asiai config add omlx http://localhost:8800 --label mac-mini
asiai config add ollama http://192.168.0.16:11434 --label mini
```

### remove

Rimuovi un'entry motore per URL.

```bash
asiai config remove http://localhost:8800
```

### reset

Elimina l'intero file di configurazione. Il prossimo `asiai detect` riscoprirà i motori da zero.

## Come funziona

Il file di configurazione memorizza i motori scoperti durante il rilevamento:

- **Entry automatiche** (`source: auto`): create automaticamente quando `asiai detect` trova un nuovo motore. Eliminate dopo 7 giorni di inattività.
- **Entry manuali** (`source: manual`): create tramite `asiai config add`. Mai eliminate automaticamente.

La cascata di rilevamento a 3 livelli di `asiai detect` usa questa configurazione come Livello 1 (il più veloce), seguito dalla scansione porte (Livello 2) e dal rilevamento processi (Livello 3). Vedi [detect](detect.md) per i dettagli.

## Posizione del file di configurazione

```
~/.config/asiai/engines.json
```
