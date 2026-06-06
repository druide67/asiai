# Panel de inferencia agéntica en Apple Silicon

> Panel comparativo de benchmarks entre motores de inferencia (llama.cpp, mlx-lm,
> LM Studio, Rapid-MLX, vLLM-MLX, oMLX, vMLX, Ollama) ejecutando modelos de la
> familia Qwen 3.6 en Apple Silicon serie M, medidos con
> `asiai bench --agentic-mode` y `asiai bench --burst-mode`.
>
> **Carga de trabajo objetivo**: clase agente-orquestador — ~60-80 llamadas a
> herramientas por turno, prompt de sistema idéntico de ~7 KB, mensaje de usuario
> que cambia en cada llamada. Es el peor caso para el caché de prefijos ingenuo:
> se requiere una verdadera reutilización de caché entre USUARIOS distintos, no
> solo caché sobre el mismo prompt.
>
> **Cómo leer las cifras de rendimiento**: las tasas de decodificación de la
> Sección 1 usan la plantilla de chat por defecto de Qwen3 (thinking ON), por lo
> que incluyen tokens de razonamiento — el rendimiento agéntico efectivo en un
> modelo con thinking es menor. El thinking es un compromiso por tarea (advertencia
> 1), no un interruptor global on/off.
>
> Publicado 2026-06 · contribuciones y correcciones bienvenidas vía
> [github.com/druide67/asiai](https://github.com/druide67/asiai/issues).

## ⚠️ Advertencias conocidas antes de seguir leyendo

1. **El modo thinking es un compromiso por tarea.** Con la plantilla por defecto
   de Qwen3 (thinking ON), Qwen 3.6 / Qwopus emiten ~6-7× más tokens, por lo que
   las cifras de decodificación de la Sección 1 **incluyen tokens de razonamiento**
   y el rendimiento agéntico efectivo es menor. El thinking ON es **necesario**
   para entregables escritos de varias secciones (un modelo con thinking OFF
   omite el entregable) pero **cuesta** limpieza en las llamadas a herramientas
   atómicas (asiai mide ~100% de llamadas a herramientas limpias con thinking OFF
   frente a ~77.8% con thinking ON + `preserve_thinking` ON, determinista entre
   ejecuciones; `enable_thinking=on` + `preserve_thinking=off` es inutilizable —
   un HTTP 500 determinista en cuanto el razonamiento se acumula en el contexto).
   Configura el thinking **por dimensión de tarea**, no como un único flag global.
2. **Rapid-MLX y vLLM-MLX comparten motor.** Rapid-MLX es un fork comunitario de
   `waybarrios/vllm-mlx`; aparecen como filas separadas más abajo porque han
   divergido en versión y características, pero el mecanismo de snapshot del caché
   de prefijos es del mismo linaje.
3. **MTP: Qwen 3.6 tiene una cabeza real; el backend importa.** El `config.json`
   oficial de Qwen 3.6 lleva `mtp_num_hidden_layers=1` (nomenclatura de Qwen —
   **no** la clave `num_nextn_predict_layers` de DeepSeek, así que una comprobación
   basada solo en `nextn` concluye erróneamente "no hay cabeza"). Algunos
   artefactos GGUF/MLX recuantizados eliminan los tensores MTP manteniendo el flag
   en la config — verifica los tensores en el índice de pesos, no solo el flag. El
   MTP nativo de llama.cpp (`--spec-type draft-mtp`) **requiere un `-MTP-GGUF`** que
   incruste la cabeza; un GGUF normal no puede draftear. El mlx-lm publicado no
   ejecuta la cabeza como decodificación especulativa nativa (el PR
   [ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990) lo añade).
   LM Studio enruta GGUF por su backend derivado de llama.cpp y MLX por
   `mlx-engine`.
4. **Mediciones de una sola pasada, sin reporte de varianza** — las cifras de las
   Secciones 1 / 2 son observaciones únicas. El reporte de varianza (mediana + min
   + max sobre N pasadas) está soportado a partir de `--burst-runs N` pero el
   re-benchmark está pendiente.

| Sección | Tema | Estado |
|---------|-------|--------|
| 1 | Rendimiento de llamada única | 🟡 8 celdas, modo thinking ON (la decodificación incluye tokens de razonamiento) |
| 2 | Ráfaga concurrente (30/60/80 llamadas paralelas) | 🟡 celda de prueba + 2 puntos concurrentes parciales; sin panel 30/60/80 normalizado |
| 3 | Cachés y optimizaciones | ✅ 8 motores cubiertos |
| 4 | Memoria y recursos | ✅ idle + swap bajo carga (+0) + footprint medido |
| 5 | Calidad del modelo (leaderboards públicos) | 🟡 cifras del fabricante/autorreportadas (llm-stats) |
| — | **mediciones directas de asiai** | ✅ calidad dev, ablación de thinking, MTP, seguimiento de instrucciones |
| 6 | Operativo (licencia, endpoints, mantenimiento) | ✅ 8 motores cubiertos |
| 7 | Ponderación de benchmarks de calidad | 🟡 ponderación por defecto, override vía `--weights` planeado |
| 8 | Eval personalizada de horizonte largo (propuesta) | 🟡 acotada, aún no construida |

---

## Sección 1 — Rendimiento de llamada única

> 🟠 **Instantánea de mayo 2026 — indicativa, no son las cifras de referencia.**
> Esta tabla se capturó en mayo (modo thinking ON, una sola pasada) y sus fixtures
> de origen no se han re-verificado. Para **rendimiento de decodificación actual y
> reproducible**, usa la sección *mediciones directas de asiai* más abajo (junio,
> llama.cpp b9430, determinista). Para lo que esta tabla sí es fiable es para el
> relato **relativo de TTFT / caché de prefijos** (reutilización entre USUARIOS),
> no para los t/s absolutos. Nota en particular que los 123.9 t/s de la fila 5
> (LM Studio GGUF+MTP) quedan justo al lado de los **123.3 t/s de llama.cpp
> Qwopus+MTP** de junio — el camino GGUF de LM Studio es un backend derivado de
> llama.cpp, así que ambos miden esencialmente el mismo motor.

> ⚠️ **Lee junto con la advertencia 1 de arriba**: cada cifra de esta tabla incluye
> los tokens del modo thinking por defecto de Qwen3 (reasoning_content). El
> rendimiento agéntico efectivo requiere re-ejecutar con
> `chat_template_kwargs={"enable_thinking": false}`. La columna está etiquetada
> "decode (t/s)", no "rendimiento efectivo".
>
> La columna "estimación de cota inferior" es `60 × (TTFT + max_tokens/decode)`,
> asumiendo despacho secuencial (que Rapid-MLX impone con su slot único). **No** es
> una predicción de tick de producción — ver la [Sección 7](#section-7) para la
> advertencia metodológica.
>
> 📌 **Versiones probadas (mayo 2026)**: Rapid-MLX 0.6.66, LM Studio 0.4.14,
> llama.cpp b9270. Las versiones de los motores cambian semanalmente en Apple
> Silicon — trata cada cifra como datada, no actual. (La sección de mediciones de
> asiai usa llama.cpp b9430.)

| # | Motor | Modelo | Formato | Warm decode (t/s) ¹ | TTFT warm (ms) | TTFT prefix-test mediana (ms) | TTFT cold (ms) | Estimación de cota inferior (60 llamadas × llamada única, optimista) | Fixture de origen |
|---|--------|-------|--------|--------------------:|---------------:|----------------------------:|---------------:|----------------------------------------------------------:|----------------|
| 1 | Rapid-MLX 0.6.66 (fork of vllm-mlx) | Qwopus 3.6-35B-A3B-v1 (zaydiscold MLX-4bit) | MLX-4bit | **109.1** ¹ | 139 | **131** | 2074 | ~3.6 min | `cell-rapidmlx-qwopus35b.json` |
| 2 | Rapid-MLX 0.6.66 | Qwen 3.6-35B-A3B-UD (MLX-4bit) | MLX-4bit | 106.9 ¹ | 321 | 319 | 2095 | ~4 min | `cell-rapidmlx-35b-a3b.json` |
| 3 | Rapid-MLX 0.6.66 | Qwopus 3.6-27B-v2 (Jackrong MLX-4bit) | MLX-4bit | 31.8 ¹ | 323 | 323 | 8647 | ~13 min | `cell-rapidmlx-qwopus.json` |
| 4 | Rapid-MLX 0.6.66 | Qwen 3.6-27B-UD (MLX-4bit) | MLX-4bit | 20.5 ¹ | 527 | 527 | 8954 | ~23 min | `cell-rapidmlx-full-27bud.json` |
| 5 | LM Studio 0.4.14 (GGUF backend) ² | Qwen 3.6-35B-A3B-MTP (Unsloth GGUF) | GGUF Q4 + MTP | **123.9** ¹ ² | 309 | 5965 | 6063 | ~3.5 min warm / ~9.2 min prefix-changing | `cell-lmstudio-mtp-qwen35b.json` |
| 6 | LM Studio 0.4.14 (GGUF backend) ² | Qwopus 3.6-35B-A3B-v1 (Jackrong GGUF) | GGUF Q4_K_S | 105.6 ¹ | 292 | 5785 | 5624 | ~3.5 min warm / ~9.6 min prefix-changing | `cell-lmstudio-qwopus35b.json` |
| 7 | llama.cpp b9270 | Qwen 3.6-35B-A3B (UD Q5_K_XL) | GGUF Q5_K_XL | 80.9 ¹ | 3000 | 3000 | n/a | ~8 min | (baseline reference) |
| 8 | llama.cpp b9270 | Qwopus 3.6-27B-v2 (Jackrong GGUF Q4) | GGUF Q4 | 25.3 ¹ | 13000 | 13000 | n/a | ~30 min | (baseline reference) |

¹ **Advertencia del modo thinking**: cifras capturadas con la plantilla de chat
por defecto (thinking ON). El rendimiento efectivo real en cargas de llamadas a
herramientas es típicamente de 4-12 t/s en finetunes Qwopus/Qwen3.6 cuando los
tokens de razonamiento inflan la salida 6-7×. Para reproducir estas cifras de
decodificación, pasa `chat_template_kwargs={"enable_thinking": false}` en el
payload de la petición.

² **Backend de LM Studio**: las filas 5-6 usaron un archivo GGUF, que se enruta por
el backend de LM Studio derivado de llama.cpp (NO por el runtime MLX `mlx-engine`).
La afirmación de MTP en la fila 5 refleja la implementación de este backend, no la
decodificación especulativa de mlx-engine. El mlx-lm publicado no ejecuta la cabeza
MTP como decodificación especulativa nativa (su `sanitize()` históricamente
eliminaba los pesos MTP durante la conversión; el soporte nativo está en el PR
[ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990)), así que un
hipotético modelo MTP en formato MLX tampoco se beneficiaría en el mlx-engine
publicado.

### Observaciones clave

- En el patrón agéntico realista (sistema idéntico + prompts de usuario
  cambiantes), **Rapid-MLX + Qwopus 35B-A3B-v1** entrega 131 ms de TTFT mediano en
  prefix-test frente a 5965 ms del backend GGUF de LM Studio (**~44× más rápido**).
  La ventaja proviene del mecanismo de snapshot del caché de prefijos de vllm-mlx
  (ver la Sección 3 para la desambiguación a nivel de código fuente).
- En rendimiento de decodificación puro (camino warm), el **backend GGUF de LM
  Studio con MTP de Unsloth** registra 123.9 t/s frente a los 109.1 t/s de
  Rapid-MLX (+13.5%). Este delta refleja la decodificación especulativa del backend
  de LM Studio derivado de llama.cpp sobre un GGUF que lleva la cabeza MTP, no una
  ganancia de Apple-MLX (el mlx-engine publicado no ejecuta la cabeza — ver la nota
  al pie 2). En el camino nativo de llama.cpp, el MTP es netamente positivo en el
  MoE 35B-A3B — ver la Sección 3.
- Todas las configuraciones de la `Qwen 3.6 family` (DeltaNet híbrido +
  atención completa) fallan el caché de prefijos entre USUARIOS **excepto
  Rapid-MLX**, que mantiene un snapshot del estado RNN. En llama.cpp / LM Studio
  GGUF `llama_memory_can_shift=false`; en mlx-lm / oMLX el estado recurrente/SSM no
  puede dividirse en un límite de token arbitrario. La corrección upstream de
  llama.cpp para esta arquitectura no está mergeada
  ([#23121](https://github.com/ggml-org/llama.cpp/pull/23121) cerrada;
  `preserve_thinking` no lo resuelve,
  [#22615](https://github.com/ggml-org/llama.cpp/issues/22615)).
- **Serialización de slot único confirmada**: la prueba de ráfaga (Sección 2)
  muestra que Rapid-MLX 0.6.66 serializa las llamadas concurrentes en FIFO
  (p50 ≈ p95 ≈ max en burst=5). Para 60-80 llamadas/turno, el tiempo total de
  reloj escala linealmente con el tamaño de la ráfaga en este motor. Un motor
  multi-slot (p. ej. llama.cpp `--parallel N`) se comportaría de forma distinta,
  pero `--parallel N` en el híbrido Qwen3.6 deshabilita el caché de prefijos por
  slot (limitación arquitectónica).

---

## Sección 2 — Ráfaga concurrente (30/60/80 llamadas paralelas)

> Patrón: de 30 a 80 llamadas concurrentes `POST /v1/chat/completions` lanzadas
> dentro de una ventana de ~200 ms. Simula un bucle de agente despachando
> múltiples llamadas MCP/herramienta en paralelo. Medido nativamente vía
> `asiai bench --burst-mode`.
>
> 🟡 **Estado**: 1 celda de prueba medida (Rapid-MLX burst-5). Panel completo
> pendiente.

### Celda de prueba (Rapid-MLX 0.6.66 + Qwopus 35B-A3B-v1, burst=5)

| burst N | wall-time (s) | p50 latencia (ms) | p95 latencia (ms) | max latencia (ms) | rendimiento agreg. (t/s) |
|--------:|--------------:|-----------------:|-----------------:|-----------------:|---------------------:|
| 5 | 2.8 | 2615 | 2792 | 2812 | 88.8 |

**Hallazgo de la prueba**: `p50 ≈ p95 ≈ max` indica que las 5 llamadas se
**serializaron del lado del servidor** (motor de slot único). Rapid-MLX 0.6.66 **no**
parece soportar la planificación de peticiones concurrentes — las llamadas se
encolan en FIFO internamente. Pendiente validar a escala de 60/80 llamadas.

### Panel concurrente completo — aún no medido

Un panel concurrente 30/60/80 normalizado no se ha ejecutado (las mediciones aquí
son agentic-mode secuencial, no ráfaga concurrente). Los dos puntos de datos
concurrentes parciales que existen en otros lugares:

- **TurboQuant** (K=`q8_0` V=`turbo2`, Qwen3-4B, M4 Pro): **+9% agregado a
  4-paralelo** (68.5 → 74.7 t/s) aunque el flujo único sea −8% — la compresión KV
  recupera el margen paralelo.
- **oMLX** continuous batching (mlx-lm `BatchGenerator`): **×1.8 agregado a
  burst-8** (12.8 → 22.9 t/s), pero **colapsa a burst-30** (17.3 t/s) cuando un
  27B-denso satura la RAM hacia el swap — 0 crashes.

Un panel dedicado de burst-mode entre todos los motores queda aplazado.

---

## Sección 3 — Cachés y optimizaciones

| # | Pareja | Reutilización caché entre USUARIOS | Snapshot persiste entre reinicios | Soporte MTP | Tasa de aceptación MTP | Compat. TurboQuant | Tipos nativos de caché KV | Slots paralelos nativos |
|---|--------|---|---|---|---|---|---|---|
| 1 | Rapid-MLX + Qwopus 35B-A3B-v1 | ✅ SÍ (snapshot de estado RNN, ver ³ abajo) | ✅ persistente en `~/.cache/vllm-mlx/` | ❌ el runtime MLX publicado no ejecuta la cabeza MTP como decodificación especulativa (PR mlx-lm #990 pendiente) | n/a | ❌ solo MLX | MLX nativo (sin flag de quant expuesto) | ⚠️ slot único (la prueba de ráfaga confirma serialización FIFO) |
| 2 | Rapid-MLX + Qwen 35B-A3B-UD | ✅ SÍ ³ | ✅ persistente | ❌ | n/a | ❌ | MLX nativo | ⚠️ slot único |
| 3 | LM Studio + Qwen 35B-A3B-MTP | ❌ NO (limitación arquitectónica del híbrido) | n/a | ✅ vía mlx-engine v1.8.1 | **82.1 %** (en tarea de coding) | ❌ | mlx-engine v1.8.1 (4bit MLX) | configurable vía GUI |
| 4 | LM Studio + Qwopus 35B-A3B-v1 | ❌ NO | n/a | ❌ sin cabezas | n/a | ❌ | mlx-engine v1.8.1 (Q4_K_S GGUF) | configurable vía GUI |
| 5 | llama.cpp + Qwen 3.6-35B-A3B | ❌ NO (limitación arquitectónica del híbrido) | n/a | ✅ `--spec-type draft-mtp` sobre un `-MTP-GGUF` (un GGUF normal no puede draftear). Netamente positivo en el MoE 35B-A3B — asiai mide **+38%** decode (base) / **+17%** (Qwopus) en M5 Max (ver § mediciones de asiai) | beneficio = delta de decode intra-sesión (sin tasa de aceptación registrada) | ✅ caché V turbo2/3/4 | `fp16`, `q8_0`, `q5_0`, `turbo2/3/4` | ⚠️ `--parallel N` funciona mecánicamente pero **deshabilita el caché de prefijos por slot en arquitectura híbrida** (cada slot posee su KV, el flag `--cache-reuse N` ya está silenciosamente deshabilitado aquí). Usar con precaución. |
| 6 | mlx-lm | ❌ NO (PRs #923, #188, #192 pendientes upstream) | n/a | ❌ roto en arquitectura híbrida | n/a | ❌ | MLX nativo | ❌ (slot único) |
| 7 | oMLX | ❌ NO (tool calling perdido tras cache-hit, issue #825) | parcial | ❌ | n/a | ❌ | MLX nativo + caché SSD por niveles | ❌ |
| 8 | vLLM-MLX (`waybarrios`, upstream de Rapid-MLX) | ⚠️ caché de prefijos por trie, sin soporte híbrido/DeltaNet documentado (las filas 1-2 de Rapid-MLX añaden el snapshot de estado RNN encima) | n/a | ⚠️ MTP añadido en prerelease 0.4.0rc1 | n/a | ❌ | MLX + paged-attention | ✅ |

³ **Caché de prefijos de Rapid-MLX**: el caché almacena bloques de KV de atención
híbrida + snapshots de estado RNN, indexados por `<repo>--<sys_prompt_hash>` y
persistidos bajo `~/.cache/vllm-mlx/`. Los ~131 ms de TTFT observados en
prefix-test son una reasociación de bloque KV en RAM más la pasada forward del
usuario cambiado, no una recarga desde disco.

**Caché de contexto largo de oMLX.** El caché KV SSD paginado de 2 niveles de oMLX
convierte un prefill de 55K tokens de ~115 s a ~**3.5 s** de TTFT en un cache-hit
de mismo prompt (×33; 55,296 / 55,837 tokens cacheados). En prompts pequeños
(~7.5K) no hay ventaja (~2-5 s, = mlx-lm) y la decodificación es de ~19 t/s (sin
ganancia de velocidad bruta). Es reutilización de mismo prompt, no entre USUARIOS
(que oMLX no hace); la persistencia entre reinicios está documentada pero aún no
probada A/B.

**Compresión KV de TurboQuant** (llama.cpp). K=`q8_0` V=`turbo2` recorta la RAM de
KV ~**28%** (22.9 → 16.4 GB en un modelo 4B, M4 Pro) con la validez de llamadas a
herramientas inalterada (10/10), y gana **+9% agregado a 4-paralelo** pese al −8%
de flujo único. La simétrica K=`turbo3` V=`turbo3` alcanza ~−56% de RAM pero degrada
la calidad (early-stop, repetición) — la asimétrica `q8_0`/`turbo2` es la
configuración usable.

---

## Sección 4 — Memoria y recursos (Apple Silicon M5 Max 128 GB)

| # | Pareja | RAM working-set (GB) | Footprint en disco (GB) | Swap Δ idle | Swap Δ bajo carga | ¿SOLO requerido? | ¿Cohabitación segura? |
|---|--------|---|---|---|---|---|---|
| 1 | Rapid-MLX + Qwopus 35B-A3B-v1 | ~22 | 19.9 (MLX-4bit) | +0 | **+0 MB** | ⚠️ SOLO (cohabit thrash to 0.4 t/s) | ❌ |
| 2 | Rapid-MLX + Qwen 35B-A3B-UD | ~24 | 20.0 (MLX-4bit) | +0 | **+0 MB** | ⚠️ SOLO | ❌ |
| 3 | LM Studio + Qwen 35B-A3B-MTP | 21.6 | 23.2 (Q4 + MTP heads) | +0 | **+0 MB** | not tested | not tested |
| 4 | LM Studio + Qwopus 35B-A3B-v1 | 18.5 | 19.9 (Q4_K_S) | +0 | **+0 MB** | not tested | not tested |
| 5 | llama.cpp + Qwen 3.6-35B-A3B (reference) | ~16 | ~16 (Q5_K_XL) | +0 | **+0 MB** | ❌ | ✅ con `--parallel 2/3` |

> **"Bajo carga"** = el bench agéntico de 8 fases incluyendo un prefill de 50K
> tokens (el estrés de memoria *secuencial* más pesado medido), M5 Max 128 GB,
> SOLO: delta de swap **0 MB / 0 swapouts para todos los motores** — modelo + KV
> caben en memoria libre/inactiva con >100 GB de margen. Esto es memoria de carga
> secuencial, **no** memoria de 60-concurrente (ver la Sección 2). La RAM
> working-set es una estimación; el RSS medido incluye GGUF mmap'd / páginas MLX
> wired, así que el footprint incremental real es menor (la cabeza MTP añade
> ~+3 GB).

### Observaciones

- **Rapid-MLX requiere operación SOLO en la GPU**: la cohabitación con otro motor
  decodificando activamente dispara un delta de swap de 5.4 → 14.2 GB y un colapso
  de decodificación a 0.4 t/s. No arranques un segundo motor en la misma GPU de
  Apple Silicon.
- El footprint en disco de **LM Studio MTP** es +13 % vs Q4_K_S sin cabezas MTP,
  debido a los bloques de pesos MTP. Coste despreciable frente a la ganancia de
  decode del +17 %.
- En memoria unificada M5 Max 128 GB: toda configuración 35B-A3B probada deja más
  de 100 GB de margen tras la carga — la RAM no es el factor limitante.
- En M4 Pro 64 GB: `Q5_K_XL` **no** cabe junto a los modelos auxiliares (swap
  thrash observado en producción). `Q4_K_S` sí cabe.

---

## Sección 5 — Calidad del modelo

> Las cifras de benchmarks públicos aquí son **del fabricante / autorreportadas** y
> agregadas por leaderboards (llm-stats), no verificadas de forma independiente.
> Contrasta en [llm-stats](https://llm-stats.com) · [LiveBench](https://livebench.ai) ·
> [SWE-bench](https://swebench.com) antes de confiar en ellas. Las propias
> mediciones directas de asiai en Apple Silicon están en la siguiente sección.
>
> Las afirmaciones solo del autor (Jackrong/Qwopus, autoevaluación de Unsloth) se
> señalan por separado y se mantienen fuera de las columnas de leaderboard público.
>
> 🔴 **Hallazgo crítico**: el benchmark "Hessling agentic" citado en varias model
> cards comunitarias **no es reproducible de forma independiente** — 16 prompts, un
> único curador, sin integración en leaderboard neutral. Los tres asesores
> recomiendan tratarlo solo como una smoke test.

### Modelos base open-weight Qwen 3.6

> Cifras de leaderboard público (llm-stats), autorreportadas. El 27B-denso supera
> al MoE 35B-A3B en SWE-bench — consistente con el propio hallazgo de calidad dev
> de asiai más abajo (el MoE base es el que cae en el bug del objeto vacío en
> llamadas a herramientas). Las cabezas MTP son una característica de velocidad de
> decodificación y no cambian las puntuaciones de calidad de un modelo.

| Modelo | Arquitectura | SWE-bench Verified | GPQA Diamond | MMLU-Pro | Terminal-Bench 2.0 | BFCL |
|-------|--------------|-------------------:|-------------:|---------:|-------------------:|------|
| Qwen 3.6-35B-A3B-Instruct | MoE 35B / 3B active | 73.4% | 86.0% | 85.2% | 24.6% | absent from board |
| Qwen 3.6-27B-Dense Instruct | Dense 27B hybrid | 77.2% | 87.8% | 86.2% | 59.3% (vendor) | absent from board |

> Terminal-Bench **2.0** es mucho más difícil que el antiguo Terminal-Bench v1 (las
> cards comunitarias citan ~51.5% para el 35B-A3B en v1); el 24.6% aquí es la
> generación 2.0.

### Familia Qwopus 3.6 — solo reportado por el autor, **no verificado de forma independiente**

Los finetunes Qwopus 3.6 publicados por Jackrong en HuggingFace afirman ganancias
sustanciales sobre la base Qwen. A fecha de mayo 2026 estas afirmaciones **no se
han reproducido de forma independiente** en leaderboards neutrales. Trátalas como
experimentales hasta que haya re-ejecuciones de BFCL / SWE-bench por un tercero.

| Modelo (afirmaciones del autor) | MMLU-Pro | SWE-bench Verified | Hessling agentic (16 prompts) |
|-----------------------|---------:|-------------------:|------------------------------:|
| Qwopus 3.6-35B-A3B-v1 (Jackrong) | claimed 88+ | claimed 75+ | claimed 88.6 ⚠ non-reproducible |
| Qwopus 3.6-27B-v2 (Jackrong) | claimed 87.43 | claimed 75.25 | n/a |

⚠ El benchmark "Hessling agentic" citado en las model cards de Jackrong parece ser
una evaluación específica de un curador con 16 prompts y sin integración en
leaderboard neutral. Los tres asesores consultados (Grok-4, GPT-5, Gemini Advanced)
recomiendan tratarlo solo como smoke test.

### Anclas de frontera (mediados de 2026)

> Todas las cifras son **del fabricante / autorreportadas**, agregadas por
> llm-stats — ninguna verificada de forma independiente allí. **Terminal-Bench 2.0**
> es la excepción (el equipo de tbench re-ejecuta los envíos; las filas son las
> puntuaciones pico agente×modelo). Los GPQA son cifras "Diamond" del fabricante y
> el conjunto está casi saturado — trátalos como aproximados.

| Modelo | SWE-bench Verified | GPQA Diamond | MMLU-Pro | Terminal-Bench 2.0 | Fuente |
|-------|-------------------:|-------------:|---------:|-------------------:|--------|
| Claude Opus 4.8 | 88.6% | 93.6% | n/a | — (no TB submission) | llm-stats / Anthropic |
| Claude Opus 4.7 | 87.6% | 94.2% | n/a | **90.2%** | llm-stats / tbench |
| Claude Sonnet 4.6 | 79.6% | 89.9% | n/a | 53.4% | llm-stats / tbench |
| GPT-5.5 | n/a\* (SWE-Pro 58.6%) | 93.6% | n/a | 84.7% | OpenAI / tbench |
| GPT-5 (base) | 74.9% | 85.7% | n/a | 49.6% | llm-stats / tbench |
| Gemini 3.1 Pro | 80.6% | ~94.4% | n/a | 80.2% | llm-stats / tbench |
| DeepSeek-V4-Pro-Max | 80.6% | 90.1% | 87.5% | n/a | vendor (DeepSeek) |
| Llama-3.3-70B-Instruct | n/a | n/a | 68.9% | n/a | Meta (baseline) |

\* GPT-5.5 no tiene puntuación pública de SWE-bench *Verified* (OpenAI reporta
SWE-bench Pro Public 58.6%); la cifra "88.7% SWE-bench" que circula no está en
ninguna fuente primaria. Nota: **Qwen 3.6 no tiene un 235B-A22B** — la familia
abierta es el 27B-denso y el 35B-A3B (abajo); el 235B-A22B es la generación
anterior de Qwen3.

### Baselines open-weights de la misma clase

| Modelo | MMLU-Pro | SWE-bench Verified | Notas |
|-------|---------:|-------------------:|-------|
| Llama-3.3-70B-Instruct | ~75-80 | ~40-50 | Baseline más antiguo pero bien caracterizado |
| Mistral Codestral 25.05 / Devstral | high (coding-specialized) | medium-high | Fuerte fidelidad de completado estilo editor, más débil en razonamiento |
| GLM-4.6-Coder (Zhipu) | vendor claims very high | disputed | Escepticismo significativo en torno a la metodología de evaluación (consenso) |

### Benchmarks de calidad descartados para esta decisión

- **HumanEval / HumanEval+** — saturado en 2026, todos los modelos de frontera por encima del 90 %, sin señal restante.
- **GSM8K** — saturado, sin señal para agentes de coding.
- **MMLU (original)** — superado por MMLU-Pro.
- **"Hessling agentic" de 16 prompts reportado por el autor** — no reproducible, tratar solo como smoke test.

### Preguntas abiertas de calidad (lagunas de investigación)

1. **Benchmark de calidad-por-GB-RAM**: no existe ninguno estándar. Fórmula proxy
   propuesta: `AgentScorePerGB = (0.5·SWE + 0.3·BFCL + 0.2·TerminalBench) / RAM_resident`.
2. **Estabilidad de horizonte largo (60+ llamadas a herramientas)**: los
   benchmarks existentes más cercanos son τ-bench, PencilPuzzleBench (>1000 turnos),
   MultiAgentBench, TRAIL. Ninguno de ellos mide específicamente "corrección de
   esquema y coherencia estratégica a lo largo de 60-80 llamadas secuenciales a
   herramientas" — esa laguna de benchmark la reconocen los tres asesores.
3. **Evaluación consciente de la conversión (MLX-4bit vs GGUF Q4_K_M vs Q5_K_XL)**:
   no hay leaderboard estandarizado. Los reportes comunitarios divergen — algunos
   afirman que MLX-4bit preserva peor la estabilidad de tool-calling que GGUF
   Q5_K_M, otros dicen lo contrario. **Consejo práctico**: ejecuta tu propia carga
   de producción contra cada quant antes de comprometerte.
4. **Validación de calidad de la familia Qwopus 3.6**: necesita re-ejecuciones de
   BFCL + SWE-bench por terceros. Las afirmaciones del autor no deberían dirigir
   las decisiones de producción.

---

## Mediciones directas de asiai — Apple Silicon, mediados de 2026

> Lo que los leaderboards públicos de arriba no muestran: mediciones que asiai
> ejecutó directamente en Apple Silicon (M5 Max 128 GB en High Power Mode, M4 Pro
> 64 GB), llama.cpp b9430, determinista (temp 0), sobre la familia pública Qwen 3.6
> y el finetune **Qwopus** destilado de Opus. Advertencia: el rendimiento absoluto
> entre sesiones en el portátil M5 es ±15% (térmico/carga); solo los **deltas ±MTP
> back-to-back intra-sesión** son ajustados, y los absolutos M5↔M4 no son
> comparables (quants distintos).

### Calidad dev / tool-call (`asiai bench --code`)

- El **Qwen 3.6-35B-A3B base (MoE)** colapsa `edit_file.edits` a un objeto vacío en
  el turno de contexto profundo — **3/3 runs, tanto en Q4_K_S como en Q5_K_XL**,
  misma plantilla de chat. Tool-call clean **87.5%**, edit-turns clean **66.7%**. Es
  el comportamiento de generación de tool-call del MoE base, no el quant ni la
  plantilla.
- El **27B denso** (Q5_K_XL) y el **Qwopus-35B-A3B** (Q4_K_S) puntúan ambos **100%
  clean / 0 bugs** — Qwopus alcanza la fiabilidad de tool-call del 27B denso a la
  tasa de decodificación ~4× del MoE.
- Bajo una suite de estrés de tool-call más dura, Qwopus se mantiene en **100% / 0**
  mientras que el 27B denso baja a **88.9% / 3 bugs** (el mismo fallo del objeto
  vacío). Pero en una trampa de evaluador de expresiones (precedencia de `**` vs
  menos unario) el **27B denso es correcto y Qwopus se equivoca** — se separan. (La
  tasa de recuperación es sensible a los pesos y ruidosa — no es un titular.)

### Ablación de thinking (`asiai bench --thinking-ablation`, Qwopus-35B-A3B, 3 runs deterministas)

| Config | Tool-call clean | Nota |
|--------|----------------:|------|
| `enable_thinking=off` | **100%** | la única config completamente limpia |
| `enable_thinking=on` + `preserve_thinking=on` | 77.8% | 2/9 turnos sucios |
| `enable_thinking=on` + `preserve_thinking=off` | 11.1% | turnos 2-8 → HTTP 500 (corrupción de contexto); evitar |

### Rendimiento MTP (`--spec-type draft-mtp`, warm decode, ±MTP intra-sesión)

| Modelo / hardware | MTP off | MTP on | Δ |
|------------------|--------:|-------:|--:|
| 35B-A3B base · M5 Max | 85.5 t/s | **118.4 t/s** | **+38%** |
| Qwopus 35B-A3B · M5 Max | 105.7 t/s | 123.3 t/s | +17% |
| 27B-dense · M5 Max | 23.8 t/s | 28.0 t/s | +18% |
| Qwopus 27B · M5 Max | 25.9 t/s | 26.7 t/s | +3% |
| 35B-A3B MoE · M4 Pro | 36.3 t/s | 44.6 t/s | +23% |
| 27B-dense · M4 Pro | 10.4 t/s | 9.7 t/s | **−6%** |

La ganancia de MTP escala como **(MoE > denso) × (M5 > M4)** — fuertemente positiva
en el MoE, marginal-a-negativa en el camino denso lento (el overhead de drafting no
se amortiza). El MTP del lado MLX (mlx_vlm) queda descalificado: rompe el contexto
largo (salida vacía, 75% válido). Titular: el MoE 35B-A3B + MTP en llama.cpp
sostiene **~118 t/s** de decodificación en M5 Max (~44 t/s en M4 Pro), ~4× el 27B
denso, a ~1.5 tok/s/W, TTFT ~62 ms, 100% de validez de salida. La cabeza MTP del
finetune Qwopus también es más débil que la base (Qwopus 27B +3% / 35B +17%, frente
a base 27B-dense +18% / 35B-A3B +38%) — el finetuning erosiona la cabeza de drafting.

### Seguimiento de instrucciones (`asiai bench --instruct`, research-brief)

El compromiso del thinking tiene mordiente en los entregables multi-paso: con
`enable_thinking=false`, Qwopus-35B hace el trabajo de herramientas pero entrega el
brief multi-sección solicitado el **0%** de las veces (se detiene en el paso
secundario); con thinking on, el modelo base lo entrega el **100%** (5/5 secciones).
Esto tira en sentido opuesto al resultado de tool-call de arriba — thinking-off es
lo más limpio para llamadas a herramientas atómicas pero suprime los entregables
escritos — razón por la que asiai configura el thinking **por dimensión de tarea**,
no como un único interruptor global.

### Bucle de investigación perfeccionista (`asiai bench --instruct loop-search`)

IFEval de un solo turno y research-brief se saturan al 100% en estos modelos, así que
ninguno saca a la luz el *bucle de investigación perfeccionista*: un modelo que no acepta
un resultado de búsqueda ambiguo e inconfirmable y reemite consultas semánticamente
equivalentes hasta que una salvaguarda de no-progreso lo detiene, sin entregar nunca. Un
barrido `loop-search` (9 configs, M5, b9430, thinking on/off, dos modos de ambigüedad) lo
aísla:

- El **MoE 35B-A3B entra en bucle hasta el tope** — tanto para **la base como para el
  finetune Qwopus, en Q4 y Q8 por igual**. El quant más alto no lo arregla, así que el
  bucle es **arquitectónico del MoE A3B**, no un artefacto del quant.
- El **denso 27B nunca entra en bucle** (Q4 / Q5 / Q8): acepta el resultado ambiguo y
  redacta el briefing.

Así que el líder en throughput (el MoE, ~118-123 t/s) y el líder en aptitud agéntica (el
denso 27B, ~25 t/s) son *modelos distintos*. Para un harness como el Hermes Agent de
NousResearch, la resistencia al bucle puede pesar más que el decode bruto — el modelo más
rápido no siempre es el agente adecuado. (Esto es el inverso del resultado de tool-call,
donde el finetune MoE era el agente más robusto: **la aptitud es por modo de fallo, así
que mide varios.**)

---

## Sección 6 — Operativo

> 📌 Instantánea de capacidades (mediados de 2026). Las versiones de los motores
> cambian semanalmente en Apple Silicon — estas celdas son de un momento puntual,
> no una garantía fijada a una versión.

| # | Motor | Licencia | Stream OAI-compat | `/v1/models` | `/health` | `/metrics` (Prometheus) | Tool calling | Auto-DL HF | Caché de prefijos persistido | Actividad del mantenedor |
|---|--------|---------|---|---|---|---|---|---|---|---|
| 1 | Rapid-MLX 0.6.66 | Apache-2.0 | ✅ | ✅ | ✅ (HTML page) | ❌ (logs only) | ✅ | ✅ HF Hub auto-DL on serve | ✅ `~/.cache/vllm-mlx/prefix_cache/` | community (raullenchai) |
| 2 | LM Studio 0.4.14 | proprietary | ✅ | ✅ | partial (websocket) | ❌ | ✅ | ✅ via `lms get` CLI | ❌ | Element Labs |
| 3 | llama.cpp b9270 | MIT | ✅ | ✅ | ✅ | ✅ `--metrics` | ✅ | manual (GGUF on disk) | ❌ (`--cache-reuse N` arch-disabled on hybrid) | ggerganov very active |
| 4 | mlx-lm | MIT | ✅ | ✅ | ✅ | ❌ | partial | ✅ HF auto | ❌ | Apple ml-explore active |
| 5 | oMLX | MIT | ✅ | ✅ | ✅ | ❌ | ✅ (caveat: post-cache-hit bug) | ✅ | partial (tiered SSD) | jundot active |
| 6 | vLLM-MLX | Apache-2.0 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ paged-attention | vllm-project active |
| 7 | vMLX (Mamba/SSM) | Apache-2.0 | ✅ | ✅ | ✅ | partial | untested | partial | untested | community |
| 8 | Ollama | MIT | ✅ | partial | ✅ `/api/version` | ❌ | partial | ✅ `ollama pull` | ❌ | Ollama Inc. very active |

---

## Sección 7 — Ponderación de benchmarks de calidad para cargas de coding agéntico

> Esta es la **ponderación por defecto de asiai** para una carga de clase
> orquestador (60-80 llamadas secuenciales a herramientas por turno, salida
> validada por esquema, prompts de sistema de contexto largo). Está informada por
> tres asesorías de LLM de frontera (Grok-4, GPT-5, Gemini Advanced) consultadas en
> mayo 2026, pero **no es un consenso comunitario** — trátala como un punto de
> partida, no como autoritativa. Override vía un futuro flag `--weights` (planeado).

| Benchmark | Qué mide | Por qué importa aquí | Peso de consenso |
|-----------|------------------|---------------------|-----------------:|
| **SWE-bench Verified** | Navegación real de repo GitHub + patch + reparación de tests | Mejor proxy de la fidelidad de edición de código dentro de un bucle de agente | **35 %** |
| **BFCL v3** (Berkeley Function Calling Leaderboard) | Precisión de llamada de función multi-turno, fidelidad de argumentos, adherencia al esquema | Predictor directo de la estabilidad del orquestador a lo largo de muchas llamadas a herramientas | **25 %** |
| **TerminalBench 2.0 / MCP-Atlas** | Autonomía de ejecución de tareas CLI y MCP | "¿Sobrevive el agente a 40+ acciones sin descarrilar?" | **20 %** |
| **LiveBench Coding** | Tareas de coding resistentes a la contaminación (refrescadas mensualmente) | Detecta fugas train-test que inflan las puntuaciones tipo HumanEval | **10 %** |
| **Eval personalizada de estabilidad de horizonte largo** | 60-80 llamadas secuenciales a herramientas con crecimiento acumulativo del contexto, recuperación de JSON malformado | El benchmark que aún no existe en forma pública — ver la Sección 8 | **10 %** |

### Benchmarks descartados conscientemente de la ponderación

- MMLU-Pro, GPQA Diamond, HumanEval+ — útiles como señal general de capacidad,
  pero **débilmente correlacionados** con la fiabilidad del bucle de agente según
  la evidencia de 2026. Las confirmaciones de laboratorios de frontera indican que
  las puntuaciones de razonamiento de un solo disparo ya no predicen el éxito del
  agente autónomo con suficiente granularidad.
- Agregados reportados por el autor sin re-ejecuciones de terceros (Jackrong
  Hessling, autoevaluación de Unsloth, afirmaciones del fabricante de GLM-4.6-Coder).

---

## Sección 8 — Propuesta de benchmark personalizado de "resistencia" (oportunidad de investigación)

Los tres asesores convergen en la misma laguna: **el benchmark que mejor
caracterizaría una carga de orquestador aún no existe públicamente**. Construir uno
es la única forma de obtener la señal que falta.

### Alcance propuesto

- **80 llamadas secuenciales a herramientas** por trayectoria
- **Validación de esquema en cada turno** (JSON estricto / salida estructurada)
- **Crecimiento acumulativo del contexto** (10K → 50K tokens a lo largo de la trayectoria)
- **Pruebas de interrupción / recuperación** (cancelar a mitad de trayectoria + reanudar)
- **Recuperación de XML/JSON malformado** (¿se autocorrige el agente?)
- **Persistencia de ediciones del repo** (¿las ediciones hechas en el turno N siguen vigentes en el turno 60?)

Esto está en la roadmap de asiai (un modo de resistencia de horizonte largo,
después del burst-mode). Si se construye, sería el primer benchmark público en este
nicho específico.

---

## Metodología

- **Hardware**: MacBook Pro M5 Max 128 GB de memoria unificada, macOS 26.4.1.
- **Carga de trabajo**: clase orquestador — prompt de sistema ~7 KB, prompt de
  usuario ~150-200 tokens, 60-80 llamadas por turno.
- **Fases medidas** (llamada única, agentic-mode v1.6.0):
  - `cold`: primera llamada tras un arranque en frío
  - `warm`: el mismo prompt exacto que cold (caché caliente)
  - `prefix-test-1/2/3`: sistema idéntico, usuario cambiante — mide la reutilización de caché entre USUARIOS
  - `cold-prefix`: sistema idéntico, tras reinicio — mide el caché persistente
- **Veredicto de reutilización del caché de prefijos**: `YES` si `median(prefix-test) / cold < 0.2`,
  si no `NO`.
- **Medidas anti-sesgo**: modo SOLO (sin motores cohabitando), baseline térmico
  idle, fase de calentamiento de mmap.
- **Quality gates** (auto-rastreados por asiai bench):
  - `early_stop`: al menos 2 runs con `<0.5×` la mediana de completado
  - `memory_pressure`: delta de swap `>500 MB` O delta de swapouts `>1000`
  - `duplicate_processes`: múltiples procesos del motor detectados durante el bench

El protocolo completo es la instrumentación `asiai bench --agentic-mode` /
`--burst-mode` (power/thermal, footprint del motor, ocupación de KV, fases del
caché de prefijos) — ver la documentación del CLI de asiai.

---

## Preguntas abiertas

1. **MTP en vLLM-MLX/Rapid-MLX — respondida (en parte).** vLLM-MLX añadió MTP en
   la prerelease **0.4.0rc1** (2026-05-21); el combo teórico "MLX + Qwopus 35B-A3B
   equipado con MTP + snapshot entre USUARIOS" podría ganar tanto en decode como en
   TTFT una vez que el fork Rapid-MLX siga la 0.4.x. Vigilar cuándo Rapid-MLX adopta
   el camino MTP.
2. **MTP en el runtime MLX — estado actual.** El mlx-lm publicado no ejecuta la
   cabeza MTP como decodificación especulativa nativa (`sanitize()` elimina los
   pesos MTP durante la conversión; el soporte nativo está en el PR sin mergear
   [ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990)). El
   `mlx-engine` de LM Studio envuelve a mlx-lm, así que lo hereda — la ganancia de
   decode del +13.5% en la fila 5 de la Sección 1 proviene del **backend de LM
   Studio derivado de llama.cpp** (el archivo es GGUF), no de la decodificación
   especulativa de mlx-engine.
3. **Comportamiento de ráfaga en Rapid-MLX/vllm-mlx a escala de 60-80 llamadas**:
   la prueba confirma FIFO de slot único a burst=5. Panel completo pendiente
   (Sección 2). El issue upstream relevante es si vllm-mlx planea planificación
   continuous-batching / multi-slot para modelos de arquitectura híbrida.
4. **`llama_memory_can_shift=false` en el híbrido Qwen 3.6** — sigue roto upstream.
   [#18497](https://github.com/ggml-org/llama.cpp/issues/18497) está cerrada
   (documenta el reprocesamiento completo); [#22384](https://github.com/ggml-org/llama.cpp/issues/22384)
   es un *issue* (cerrado-como-completado), **no** una corrección mergeada; el PR de
   corrección real [#23121](https://github.com/ggml-org/llama.cpp/pull/23121) se
   **cerró sin mergear** (los parches viven solo en forks). El workaround de "solo
   activa `preserve_thinking`" queda refutado por el issue abierto
   [#22615](https://github.com/ggml-org/llama.cpp/issues/22615) (speedup de 0.67× =
   el caché se queda inerte). Las capas DeltaNet híbridas no exponen un estado de
   caché desplazable por construcción.
5. **Reproducción independiente de la calidad de Qwopus 3.6**: necesita
   re-ejecuciones de BFCL / SWE-bench por terceros. Los números publicados por el
   autor no deberían dirigir las decisiones de producción hasta ser
   contra-verificados.
6. **Linaje vllm-mlx vs Rapid-MLX — respondida.** Rapid-MLX es un **hard fork**
   comunitario de `waybarrios/vllm-mlx`, no un wrapper fino: vendoriza el motor
   in-tree (el paquete sigue llamándose `vllm_mlx`), no depende vía pip del paquete
   upstream, y ha divergido sustancialmente (Rapid-MLX 0.6.74 vs upstream 0.3.0). El
   nombre de paquete compartido `vllm_mlx` y el directorio `~/.cache/vllm-mlx/` son
   una fuente frecuente de confusión de atribución (ver la Sección 3, advertencia 2).

---

*Este panel es un documento vivo. Contribuciones, correcciones y celdas de bench
adicionales son bienvenidas vía [github.com/druide67/asiai](https://github.com/druide67/asiai/issues).*
