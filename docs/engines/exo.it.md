---
description: "Inferenza LLM distribuita con Exo: benchmark di più Mac insieme, porta 52415, configurazione cluster e prestazioni."
---

# Exo

Exo consente l'inferenza LLM distribuita raggruppando la VRAM di più Mac Apple Silicon sulla rete locale, servendo sulla porta 52415. Permette di eseguire modelli da 70B+ parametri che non entrerebbero su una singola macchina, con scoperta automatica dei peer e un'API compatibile con OpenAI.

[Exo](https://github.com/exo-explore/exo) consente l'inferenza distribuita tra più dispositivi Apple Silicon. Esegui modelli grandi (70B+) raggruppando la VRAM di diversi Mac.

## Installazione

```bash
pip install exo-inference
exo
```

Oppure installa dal codice sorgente:

```bash
git clone https://github.com/exo-explore/exo.git
cd exo && pip install -e .
exo
```

## Dettagli

| Proprietà | Valore |
|----------|-------|
| Porta predefinita | 52415 |
| Tipo API | Compatibile con OpenAI |
| Report VRAM | Sì (aggregato tra i nodi del cluster) |
| Formato modello | GGUF / MLX |
| Rilevamento | Automatico via DEFAULT_URLS |

## Benchmarking

```bash
asiai bench --engines exo -m llama3.3:70b
```

Exo viene valutato come qualsiasi altro motore. asiai lo rileva automaticamente sulla porta 52415.

## Note

- Exo scopre i nodi peer automaticamente sulla rete locale.
- La VRAM mostrata in asiai riflette la memoria totale aggregata da tutti i nodi del cluster.
- I modelli grandi che non entrano su un singolo Mac possono funzionare senza problemi nel cluster.
- Avvia `exo` su ogni Mac del cluster prima di eseguire i benchmark.

## Vedi anche

Confronta motori con `asiai bench --engines exo` --- [scopri come](../benchmark-llm-mac.md)
