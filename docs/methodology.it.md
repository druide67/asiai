---
description: Come asiai misura tok/s, TTFT e potenza. Warmup, metodologia statistica e perché i risultati sono riproducibili.
---

# Metodologia di benchmark

asiai segue standard di benchmarking consolidati ([MLPerf](https://mlcommons.org/benchmarks/inference-server/), [SPEC CPU 2017](https://www.spec.org/cpu2017/), [NVIDIA GenAI-Perf](https://docs.nvidia.com/deeplearning/nemo/user-guide/docs/en/stable/benchmarking/genai_perf.html)) per produrre risultati affidabili, riproducibili e confrontabili.

## Protocollo

1. **Verifica preliminare**: Rifiuta di avviarsi se la pressione di memoria è critica o il sistema è fortemente limitato (<80%)
2. **Warmup**: 1 generazione non cronometrata per motore per preparare compilatori JIT e cache
3. **Esecuzioni misurate**: Di default 3 esecuzioni per prompt per motore (configurabile con `--runs`)
4. **Campionamento**: `temperature=0` (greedy) per output deterministico
5. **Scaricamento modello**: Dopo il benchmark di ogni motore, il modello viene scaricato per liberare memoria unificata prima dell'avvio del motore successivo. Questo previene l'accumulo di memoria e lo swapping quando si confrontano più motori con modelli grandi
6. **Raffreddamento adattativo**: Dopo lo scaricamento, asiai attende che la pressione di memoria di macOS torni a "normal" (max 30s), poi aggiunge un minimo di 5s di raffreddamento termico
7. **Controlli di coerenza**: I risultati con tok/s ≤ 0 vengono scartati. TTFT > 60s o tok/s > 500 generano avvertimenti (probabile swapping o errori di misurazione)
8. **Report**: Mediana tok/s come metrica primaria (standard SPEC), media ± deviazione standard come secondaria
9. **Throttling**: Avvertimento emesso se `thermal_speed_limit < 100%` durante qualsiasi esecuzione. La deriva termica (diminuzione monotona dei tok/s tra le esecuzioni, calo ≥5%) viene rilevata e segnalata
10. **Metadati**: Versione motore, formato modello, quantizzazione, chip hardware, versione macOS salvati per risultato

## Metriche

### tok/s — Velocità di generazione

Token al secondo di **tempo di generazione**, escludendo l'elaborazione del prompt (TTFT).

```
generation_s = total_duration_s - ttft_s
tok_per_sec  = tokens_generated / generation_s
```

Con dimensioni di contesto grandi (es. 64k token), il TTFT può dominare la durata totale. Escluderlo dai tok/s evita che generatori veloci appaiano lenti.

### TTFT — Tempo al primo token

Tempo tra l'invio della richiesta e la ricezione del primo token di output, in millisecondi. Misurato lato server (Ollama) o lato client al primo chunk SSE con contenuto (motori compatibili con OpenAI).

### Power — Watt GPU

Potenza media GPU durante l'esecuzione di ciascun motore specifico, misurata tramite `sudo powermetrics`. Un `PowerMonitor` per motore — nessuna media a livello di sessione.

### tok/s/W — Efficienza energetica

```
tok_per_sec_per_watt = tok_per_sec / power_watts
```

### Varianza — Deviazione standard combinata

Deviazione standard combinata intra-prompt che cattura il rumore tra esecuzioni **senza** mescolare la varianza tra prompt.

Classificazione di stabilità:

- CV < 5% → `stable`
- CV < 10% → `variable`
- CV >= 10% → `unstable`

Dove CV = `(std_dev / mean) * 100`.

## Conformità

| Pratica | Stato |
|----------|--------|
| Verifica preliminare (pressione memoria + termica) | Implementato |
| TTFT separato da tok/s | Implementato |
| Campionamento deterministico (temperature=0) | Implementato |
| Conteggio token da API server (non chunk SSE) | Implementato |
| Monitoraggio energetico per motore (IOReport, senza sudo) | Implementato |
| 1 generazione di warmup per motore | Implementato |
| 3 esecuzioni di default (minimo SPEC) | Implementato |
| Mediana come metrica primaria (standard SPEC) | Implementato |
| Deviazione standard combinata intra-prompt | Implementato |
| Scaricamento modello tra motori | Implementato |
| Raffreddamento adattativo (sensibile a pressione memoria) | Implementato |
| Controlli di coerenza (tok/s, limiti TTFT) | Implementato |
| Rilevamento throttling termico + avvertimento | Implementato |
| Rilevamento deriva termica (diminuzione monotona) | Implementato |
| Versione motore + metadati modello salvati | Implementato |
| VRAM universale tramite ri_phys_footprint | Implementato |
| Rilevamento regressione storica | Implementato |

## Considerazioni su Apple Silicon

### Memoria unificata

Apple Silicon condivide la memoria tra CPU e GPU. asiai esegue i motori **in sequenza** e **scarica i modelli tra motori** per evitare contesa di memoria e swapping. La VRAM è riportata nativamente da Ollama e LM Studio; per gli altri motori, asiai stima l'utilizzo di memoria tramite `ri_phys_footprint` (la metrica di impronta fisica di macOS, come Monitor Attività). I valori stimati sono etichettati "(est.)" nell'interfaccia.

### Throttling termico

- **MacBook Air** (senza ventola): throttling severo sotto carico sostenuto
- **MacBook Pro** (con ventola): throttling lieve
- **Mac Mini/Studio/Pro**: raffreddamento attivo, throttling minimo

asiai registra `thermal_speed_limit` per risultato e avvisa se viene rilevato throttling.

### Cache KV

Dimensioni di contesto grandi (32k+) possono causare instabilità nei motori che pre-allocano la cache KV. Imposta la lunghezza del contesto del motore in modo che corrisponda alla dimensione effettiva del test per risultati equi.

## Misurazione della potenza

asiai misura il consumo energetico di GPU, CPU, ANE e DRAM tramite il framework Apple IOReport Energy Model — **senza necessità di sudo**. La potenza viene misurata automaticamente in ogni benchmark e in ogni snapshot di monitoraggio.

IOReport legge gli stessi contatori energetici hardware di `sudo powermetrics`, ma attraverso un'API user-space (`libIOReport.dylib` via ctypes). Questo elimina la necessità di configurazione sudo senza password.

### Validazione

Abbiamo validato IOReport contro `sudo powermetrics` sotto carico di inferenza LLM su M4 Pro 64GB, usando 10 campioni accoppiati per motore a intervalli di 2 secondi:

| Motore | Media IOReport | Media powermetrics | Delta medio | Delta massimo |
|--------|-------------|-----------------|------------|-----------|
| LM Studio (MLX) | 12,6 W | 12,6 W | 0,9% | 2,1% |
| Ollama (llama.cpp) | 15,6 W | 15,4 W | 1,3% | 4,1% |

Entrambi i motori hanno confermato un delta medio <1,5% con 10/10 campioni accoppiati. La potenza ANE era 0,000W su tutti i 20 campioni, confermando che nessun motore LLM utilizza attualmente il Neural Engine.

Il flag `--power` abilita la validazione incrociata aggiuntiva eseguendo simultaneamente IOReport e `sudo powermetrics`, salvando entrambe le letture per il confronto.

### Efficienza energetica

L'efficienza energetica (tok/s per watt) è calcolata come `tok_per_sec / gpu_watts` per ogni risultato di benchmark. Questa metrica consente il confronto del costo di inferenza tra motori e hardware.

## Metadati

Ogni risultato di benchmark salva: engine, engine_version, model, model_format, model_quantization, hw_chip, os_version, thermal_level, thermal_speed_limit, power_watts, power_source, metrics_version. Questo consente un confronto di regressione equo e benchmark tra macchine.
