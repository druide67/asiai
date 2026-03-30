---
description: "Controlla la versione di asiai, l'ambiente Python e lo stato di registrazione dell'agente con un singolo comando."
---

# asiai version

Mostra informazioni sulla versione e sul sistema.

## Uso

```bash
asiai version
asiai --version
```

## Output

Il sottocomando `version` mostra il contesto di sistema arricchito:

```
asiai 1.0.1
  Apple M4 Pro, 64 GB RAM
  Engines: ollama, lmstudio
  Daemon: monitor, web
```

Il flag `--version` mostra solo la stringa di versione:

```
asiai 1.0.1
```

## Casi d'uso

- Controllo rapido del sistema per issue e segnalazioni di bug
- Raccolta contesto dell'agente (chip, RAM, motori disponibili)
- Scripting: `VERSION=$(asiai version | head -1)`
