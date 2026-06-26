# Qwen-AgentWorld-35B en Apple Silicon: ¿merece un lugar en tu bucle de agentes?

> Un informe de evaluación para quienes ejecutan modelos locales y construyen agentes autónomos.
> **Qué es**: un *modelo de mundo lingüístico* — predice lo que una terminal
> devolvería tras una acción, no actúa. **Qué se ejecuta**: MLX, o llama.cpp/Metal
> con una anulación de metadatos de una línea (un GGUF plano no carga sin ella); no
> hay build MLX oficial. **El único diferenciador que medimos**:
> mantiene el rol de simulador a lo largo de secuencias de varios pasos donde un generalista se desvía.
> **Su coste**: un sobre-razonamiento pesado — limitable. Las cifras son de N pequeño y direccionales,
> cada una etiquetada con su tamaño de muestra; las cifras de benchmark del autor se señalan como afirmaciones.
>
> Medido con `asiai` en un M5 Max, MLX 4-bit, un motor a la vez, 2026-06.
> Correcciones bienvenidas vía [github.com/druide67/asiai](https://github.com/druide67/asiai/issues).

!!! tip "Cuándo usarlo / cuándo no"
    **Úsalo como** simulador de entorno para rollouts de agente baratos, un mock para
    salida de herramienta/terminal, o un verificador de trayectorias en lugar de un
    LLM-como-juez (*el caso de uso del verificador no está probado aquí — ver §6*). También
    se sostiene como un generalista 35B plano si lo prompteas como asistente.

    **No lo uses como** tu asistente diario: los autores no entregan ninguna vía de uso
    chat/código y arrastra un fuerte impuesto de sobre-razonamiento (limitable, ver §5). Y no
    esperes a la variante 397B que "le gana a GPT-5.4" — **no es descargable**
    (HF devuelve 401 a pesar del anuncio Apache-2.0).

## 1. Ejecutabilidad y reproducción (lee esto primero)

Si no se ejecuta en tu máquina, nada más importa. Veredicto, sin rodeos:

- **Hoy funcionan dos vías; ninguna es llave en mano.** **No hay build MLX oficial** —
  usamos una conversión MLX comunitaria, y esa es la vía sobre la que medimos. El GGUF
  **también carga** en llama.cpp / Metal, pero no de fábrica: tal cual falla con
  `missing tensor 'blk.40.attn_norm.weight'` (build 9780, reconfirmado 2026-06-25).
  La causa es un error off-by-one del conversor, **no pesos faltantes** — el GGUF declara
  `block_count=41` (una capa MTP extra en el índice 40) mientras solo entrega las 40 capas
  reales 0–39, así que llama.cpp pide una capa que nunca debió existir. Anula
  los metadatos en la carga y carga *y genera*:
  `--override-kv qwen35moe.block_count=int:40 --override-kv qwen35moe.nextn_predict_layers=int:0`.
  Ollama y LM Studio envuelven llama.cpp pero no exponen `--override-kv` de forma fiable, así que
  trata esos dos como no probados. El despliegue de servidor oficial es vLLM / SGLang / Transformers.
- **Un quant que carga no es prueba de que emita una cadena-de-pensamiento larga correcta** —
  valida la generación, no solo la carga.

Configuración de reproducción:

| | Repo (Hugging Face) | Tamaño |
|---|---|---|
| AgentWorld (especialista) | `jedisct1/Qwen-AgentWorld-35B-A3B-oQ4-MLX` | ~20 GB |
| Qwen3.6 (baseline generalista) | `mlx-community/Qwen3.6-35B-A3B-4bit` | ~19 GB |

`mlx-lm` 0.31.3 · M5 Max 128 GB · muestreo temp 0.6 / top-p 0.95 / top-k 20 · un modelo cargado a la vez.

!!! warning "El presupuesto de tokens es una variable de configuración de primer orden"
    AgentWorld emite una traza de razonamiento muy larga. Con `max_tokens=4096` su salida
    queda **truncada antes de la respuesta** y puntúa como un falso fallo. Necesita
    **8192–12288** tokens de razonamiento para terminar en algunos casos triviales. Cualquiera
    que reejecute con un presupuesto bajo obtendrá números de peor aspecto para AgentWorld que
    son artefactos del harness, no errores del modelo.

**Encaje de RAM / contexto**: pesos ~20 GB; pico ~27 GB con contexto de 64K en un Mac de 128 GB;
la caché KV crece solo ~5 GB de 4K a 64K (una propiedad de la arquitectura híbrida
compartida). Un Mac de 64 GB lo ejecuta cómodamente con contexto reducido; 36–48 GB es
ajustado pero viable de 4K a 32K.

## 2. Qué es, y cómo lo posicionan los autores

Un **modelo de mundo lingüístico**: dado un estado y una acción (un comando tipado),
predice la siguiente observación (lo que la terminal devuelve) vía una larga
cadena-de-pensamiento. Siete dominios digitales (MCP, Search, Terminal, SWE, Android, Web,
OS). Está entrenado para *ser el entorno*, no para actuar en él.

Los autores lo entregan **como un modelo de mundo, no como un asistente**: los system prompts son
prompts de simulación, y no hay ninguna vía documentada de uso chat/código. Así que una
preocupación legítima es que, usado como asistente, simularía la salida de una consola en lugar de
responder. Nuestra prueba matiza esto (§4): con un prompt de asistente estándar codifica
y razona a la par con el generalista. **El comportamiento lo decide el prompt,
no una capacidad perdida.**

!!! note "Sobre la palabra *modelo de mundo*"
    La objeción comunitaria más común es terminológica: esto es un
    LLM autorregresivo haciendo predicción del siguiente estado-texto, no un modelo de mundo
    no-autorregresivo / basado en energía en el sentido de LeCun. Conviene saberlo antes de que el nombre
    fije una expectativa que el modelo no afirma cumplir.

Specs verificadas (tarjeta del modelo en HF, a la vista):

| | |
|---|---|
| Parámetros | **34.66 B** total · ~3 B activos (MoE) |
| Arquitectura | `qwen3_5_moe`, híbrida **Attention + Gated-DeltaNet** |
| Expertos | 256 (8 enrutados + 1 compartido) |
| Contexto | hasta **256K** tokens |
| Licencia | **Apache-2.0** (~65 GB en BF16) |

## 3. El diferenciador: fidelidad de rol en varios pasos

Este es el único resultado nuevo y defendible — y exactamente lo que el propio benchmark
de los autores nunca mide (es solo de un único paso). La prueba: encadenar comandos que
construyen estado (crear un dir, entrar en él, escribir un archivo, releerlo) y, en cada paso,
hacer que el modelo prediga la salida exacta de la terminal.

Enmárcalo como una propiedad de **fiabilidad** — disciplina de formato/rol — **no** como una
ventaja de comprensión. Qwen3.6 entiende la terminal perfectamente (rastrea
el directorio de trabajo, cuenta las líneas correctas); la diferencia es que a veces
*abandona el rol*.

| Prueba | AgentWorld | Qwen3.6 | Nota |
|---|---|---|---|
| Salida plausible (`ls`, `git`, `ps`) — N=3 | 9/9 | 9/9 | paridad |
| Secuencia A — 6 pasos, anclada (4 ejecuciones) | 0 rupturas de rol / 24 pasos | intermitente | mantiene rol |
| Secuencia B — 8 pasos, anclada (3 ejecuciones) | 0 rupturas de rol / 24 pasos | intermitente | mantiene rol |
| Bucle cerrado (se alimenta a sí mismo) — N=2 | 6/6 ×2 | intermitente | mantiene rol |

**Lectura honesta**: AgentWorld rompió el rol en **0 de 48 pasos observados** a lo largo de dos
secuencias y cuatro ejecuciones. Qwen3.6 rompe el rol de forma intermitente — sus ejecuciones ancladas
oscilaron 0/6 → 6/6 entre repeticiones (N=2), así que esto es **direccional, no una tasa**. Cuando
falla, **regurgita el JSON de la acción** en lugar de simular la salida:

```text
$ cat log.txt              # log.txt was just deleted → env must return an error

AgentWorld (in role):
  root@host:/home/user# cat log.txt
  cat: log.txt: No such file or directory
  root@host:/home/user#

Qwen3.6 (out of role, ~1 run in 2 here):
  [{"keystrokes": "cat log.txt\n", "duration": 0.1}]    # echoes the input command
                                                        # instead of the output
```

La respuesta correcta suele estar presente en la salida de Qwen3.6 — es un fallo de
**formato/rol**, no un malentendido. Para un bucle donde cada paso debe ser legible por máquina
para el siguiente, una sola ruptura de rol envenena la cadena, que es lo que AgentWorld evita.

!!! note "Salvedades de medición (declaradas)"
    El scoring byte-exacto en la línea de eco del comando es estricto, y nuestros fixtures de
    Secuencia-D vs Secuencia-E eran inconsistentes sobre si una observación de `cd` incluye
    el eco — así que la métrica de fidelidad de rol tiene una arruga conocida. La dirección es
    robusta a lo largo de cuatro archivos; la brecha precisa no lo es.

## 4. Capacidad generalista: la base no está degradada

La pregunta del dueño (¿el fine-tune del modelo de mundo rompió el LLM base?) recibe una
sección sobria, no el titular. Respuesta corta: no — N=3, direccional.

| Tarea | AgentWorld | Qwen3.6 | |
|---|---|---|---|
| Razonamiento (5 puzles verificables incl. la trampa de las 'r' de strawberry) | 15/15 | 15/15 | paridad |
| Generación de código (4 funciones, **ejecutadas contra tests unitarios**) | 12/12 | 12/12 | paridad |

Ejecutado con un prompt de asistente (no el prompt de simulador), AgentWorld escribe código
correcto y razona correctamente, a la par con el generalista. No "descarrila" — es
un generalista competente que resulta sobre-razonar.

## 5. El coste: un impuesto de sobre-razonamiento — y el remedio

Promovemos esto de nota al pie a una puerta de adopción, porque para un verificador por-paso
es la cifra decisiva — pero tiene solución.

Medido en casos de terminal deterministas (N=2 por caso):

| Modo | AgentWorld | Qwen3.6 |
|---|---|---|
| Razonamiento **activado** (modo simulador por defecto) | mediana **1140 tok/pred**, máx 2558 · ~14 s · 8/8 exacto | 504 tok · ~4.5 s · 8/8 |
| Razonamiento **desactivado** (`enable_thinking=false`) | **45 tok/pred · ~0.5 s · 8/8 exacto** | 45 tok · ~0.4 s · 8/8 |

AgentWorld emite ~2.3× más tokens que el generalista y en un trivial `cd ; pwd` su
razonamiento se pasó de los **8192 tokens en 2 de 3 ejecuciones**. La respuesta final es correcta —
esto es un impuesto de latencia/cómputo por paso, no un defecto de corrección.

!!! tip "El remedio: limítalo"
    Desactivar el razonamiento para el rol de simulador recorta tokens ~25× y latencia
    ~28× **sin pérdida de fidelidad byte-exacta** en casos deterministas (sigue siendo 8/8).
    Para un verificador por-paso o un mock, ejecútalo con `enable_thinking=false` y un
    techo de `max_tokens`. **Salvedad**: esto está probado solo en casos deterministas —
    en salidas donde el razonamiento ayuda genuinamente (estado ambiguo, contenido
    complejo), desactivar el razonamiento puede costar fidelidad. No probado aquí.

## 6. Rendimiento (ejecución única, indicativo ★)

Misma familia, misma arquitectura, así que los perfiles son cercanos. Léelos como tendencias.

| Medida | AgentWorld | Qwen3.6 | Lectura |
|---|---|---|---|
| Tiempo al primer token ★ | ~360 ms | ~510 ms | AW por delante |
| Rendimiento de decode ★ | ~110 t/s | ~117 t/s | ~7% más lento |
| Decode con contexto de 64K | ~132 t/s | ~160 t/s | ~73% retenido |
| Memoria 4K → 64K | +5 GB | +5 GB | arq. híbrida, no específica de AW |
| Caché de contexto (reutilización de prefijo de 13K tokens) | ~×21 | ~×23 | **propiedad de MLX**, no del modelo |

La brecha de decode del ~7% es muy probablemente la receta 4-bit (AgentWorld protege su
proyección de atención lineal en 6-bit; Qwen3.6 protege la compuerta MoE en 8-bit), sobre
longitudes de salida desiguales — un confundidor, no una desventaja del modelo. El caching de prompt es una
característica de mlx-lm idéntica en ambos modelos; su ganancia de ~20× escala con la longitud del prefijo
cacheado, no es una propiedad de AgentWorld.

**No probado pero de alto valor (el caso de uso #2 de la comunidad)**: usar la predicción
del siguiente estado como un *verificador de trayectorias* — cuando el entorno real diverge de la
predicción, eso señala un agente fuera de ruta. No medimos su comportamiento de
falsos-positivos / falsos-negativos. Pregunta abierta.

## 7. Lo que afirman los autores

!!! quote "Benchmark del autor — una afirmación, no una medición"
    En su propio benchmark (AgentWorldBench), AgentWorld-35B puntúa **56.4**, al nivel
    de Claude Sonnet 4.6 (56.0). Las ganancias las atribuyen a la especialización, por
    ablación contra el **Qwen3.5 base** (auto-reportado, no un mano-a-mano vs
    Qwen3.6): **+21.9** uso de herramientas (MCP), **+18.1** ingeniería de software, **+10.2**
    terminal. Tesis: *la especialización de modelo de mundo supera la mejora
    generacional* — el generalista Qwen3.6 puntúa **por debajo** de la base (42.9 vs 47.7) en
    fidelidad de simulación, porque está ajustado para *actuar*, no para *predecir estado*.

    Estas cifras provienen de un benchmark interno de fuente única, calificado por un juez
    LLM, sobre un modelo con menos de 48 h de vida en la publicación — **sin réplica de
    terceros**. La cima de su tabla cabe en ~2 puntos bajo un único juez, así que
    el orden cerca de la cima está dentro del ruido; el margen del 397B que "le gana a GPT-5.4" es +0.46
    (ruido), y esa variante es no pública (HF 401) a pesar del anuncio Apache-2.0.

Nuestro resultado de varios pasos (§3) es sobre una *métrica distinta, no replicada* respecto a su
bench de un único paso; apunta en la misma dirección (Qwen3.6 más débil en simulación), pero
eso es convergencia de tesis, no confirmación.

## 8. Cómo lo conectaría yo

- **Prompt**: usa el system prompt oficial de **simulación** de terminal para ejecutarlo como un
  entorno; usa un prompt de asistente plano solo si quieres salida generalista. Los
  dos modos son trabajos distintos.
- **Control de coste**: `enable_thinking=false` + un techo de `max_tokens` para el
  rol de simulador (§5). Con el razonamiento activado, presupuesta ~1000–2500 tokens/paso.
- **Bucle cerrado**: realimenta las propias predicciones del modelo, pero ancla en el entorno
  real cuando lo tengas; espera que la estrictez de formato importe (la línea de eco).
- **Huella**: ~20 GB de pesos, ~27 GB de pico a 64K.
- **La pregunta de construir-vs-adoptar**: ¿es "nunca abandona el rol" intrínseco al
  entrenamiento del modelo de mundo, o podría un generalista + decodificación restringida por gramática cerrar
  la mayor parte de la brecha? No probamos la alternativa del generalista-restringido — sopésala
  antes de adoptar un modelo dedicado.

## Límites de este bench

- **Muestras pequeñas** (N=1–5, sin desviación estándar). Cada brecha numérica es una tendencia,
  no un resultado estadístico.
- **Un solo dominio** para los dos resultados clave (secuencias de terminal). El mantener-rol "en un bucle"
  queda por confirmar en otros lugares.
- **Cuantización no aislada**: las dos recetas 4-bit difieren ligeramente; la brecha de
  decode está probablemente ligada a eso pero no se prueba aquí.
- **Aún no probado**: escenarios aleatorios/complejos, un segundo dominio, un triple contra
  el Qwen3.5 base para aislar el efecto exacto del fine-tune, y el caso de uso del verificador-de-trayectorias.
- **Solo el 35B es público.** La variante 397B no es descargable.

---

*Fuentes: arXiv 2606.24597 · [Qwen-AgentWorld-35B-A3B](https://huggingface.co/Qwen/Qwen-AgentWorld-35B-A3B) (Apache-2.0). Resultados revisados internamente de forma cruzada por sesgo antes de la publicación. ★ = medición única, indicativa.*
