---
description: Resultados de benchmark de calidad-dev y retención multilingüe sobre Apple Silicon — fiabilidad de llamadas a herramientas (el bug de truncamiento de argumentos JSON / objeto vacío), recuperación de errores agéntica, disciplina de thinking y retención de idioma. Determinista, sin necesidad de juez LLM para la señal central. Una página de resultados viva.
---

# Benchmarks de calidad-dev e idioma

El throughput no es calidad. Un modelo puede decodificar rápido y aun así ser inutilizable
para coding agéntico — trunca los argumentos de las llamadas a herramientas, entra en bucle
ante los errores, o su finetune rompió silenciosamente otro idioma. Esta página reporta
resultados reales de `asiai bench --code` y `asiai bench --language`: señales
**deterministas** (sin necesidad de juez LLM para el núcleo) que miden si un modelo
realmente funciona, no qué tan rápido emite tokens.

> **Documento vivo.** Las cifras se actualizan a medida que cambian las revisiones de los
> modelos, los motores y las plantillas. Cada bloque nombra el archivo exacto del modelo y la
> configuración de servicio, de modo que un resultado es reproducible.

## Qué se mide

`asiai bench --code` (determinista, sin juez):

- **tool-call** — una sesión agéntica de edición de archivos de 8 turnos bajo contexto
  acumulativo. Puntúa la emisión de la llamada a herramienta, la validez del JSON, la
  no-truncación, la herramienta correcta, la conformidad con el esquema y el **bug de objeto
  vacío**: el truncamiento de la plantilla `|items` que colapsa un array `edit_file.edits` a
  `{}` / `[]`.
- **tool-call-stress** — lo mismo, más difícil: contexto más profundo, arrays de edición de
  8–10 elementos, presión de escapado JSON (saltos de línea, comillas, barras invertidas,
  unicode). Se usa para distinguir entre modelos que clavan la línea base.
- **recovery** — inyecta un error de herramienta sintético a mitad de la sesión; puntúa una
  acción correctiva frente a un bucle atascado (reemitir la llamada que falla).
- **thinking** — disciplina del modo thinking: sin fuga de `<think>` al contenido, salida no
  vacía con un presupuesto corto, y `enable_thinking=false` respetado.
- **coding** / **coding-hard** *(juez opcional)* — tareas de coding multiturno calificadas de
  1 a 5 por un juez LLM en `--judge-url` (cualquier endpoint compatible con OpenAI).

`asiai bench --instruct` (seguimiento de instrucciones determinista):

- **verifiable** — prompts de un solo turno estilo IFEval con instrucciones
  verificables programáticamente (recuentos de palabras/frases/secciones, palabras clave,
  solo-JSON, mayúsculas/minúsculas, sin comas, frase final, título en `<<>>`, idioma…). Se
  reporta como exactitud estricta/laxa a nivel de prompt y a nivel de instrucción — el formato
  del leaderboard público. Reimplementación nativa de asiai del paradigma IFEval (Zhou et al.
  2023); no se incluye código ni datos de IFEval.
- **research-brief** — una tarea agéntica: investigar varios temas mediante herramientas, luego
  redactar un briefing multi-sección, y luego una acción de herramienta secundaria (guardar)
  **al final**. ¿Produce el modelo el briefing primario, o hace el trabajo de herramienta y
  devuelve solo la confirmación del paso secundario? Un modelo puede clavar la fiabilidad de
  llamadas a herramientas y aun así saltarse el entregable principal — puntuado de forma
  determinista comprobando que las secciones requeridas aparecen tras los turnos de herramienta.
  **order-control** invierte el orden (primero el secundario) como diagnóstico.

`asiai bench --language <code>` (determinista, 8 idiomas):

- **adherence** — ¿se mantiene el modelo en el idioma objetivo? (ratio de palabras funcionales
  objetivo vs. inglés para escrituras latinas; ratio de caracteres en la escritura objetivo
  para ja/ko/zh).
- **diacritics** — prompts trampa cuya respuesta correcta debe contener tokens acentuados
  específicos (`café`, `préféré`); una respuesta despojada de su ASCII falla.

Los tres modos son solo-JSON y comparan entre modelos haciendo diff de la salida.

## Ejemplo trabajado — Qwen3.6-35B-A3B vs Qwopus3.6-35B-A3B vs Qwen3.6-27B denso

Un finetune (`Qwopus3.6`, un finetune destilado de Opus del MoE `Qwen3.6-35B-A3B`) frente a su
base, frente a un modelo denso de la mitad de su tamaño. El mismo llama.cpp, **la misma
plantilla de chat mantenida constante** (solo se intercambió el archivo del modelo), thinking
desactivado, 3 repeticiones. Apple Silicon M5 Max, High Power Mode.

### Fiabilidad de llamadas a herramientas

| model · quant | tool-call clean | empty-object bug | under stress |
|---|--:|--:|--:|
| Qwen3.6-35B-A3B base · Q4 / Q5 | 87.5% | **3** | 87.5% · **3 bugs** |
| **Qwopus3.6-35B-A3B · Q4** | **100%** | **0** | **100% · 0** |
| Qwen3.6-27B dense · Q5 | 100% | 0 | 88.9% · **3 bugs** |

- **El MoE 35B base tiene un defecto residual de llamadas a herramientas que el arreglo de la
  plantilla no cierra del todo.** Colapsa `edit_file.edits` al bug de objeto vacío 3/3 en un
  turno de contexto profundo — en **ambos** quants Q4 y Q5 (así que es un comportamiento de
  generación, no de cuantización). La plantilla comunitaria `froggeric`, que arregla el bug de
  `|items` en llamadas simples, no salva al MoE base en lo profundo del contexto.
- **El finetune destilado de Opus lo repara por completo** — 0 bugs, 100% limpio — y a un quant
  *más bajo* (Q4 vs Q5), lo que refuerza la victoria.
- **Bajo estrés, el finetune es el agente más robusto que el denso 27B**: el 27B se quiebra
  (3 bugs de objeto vacío en la suite más difícil) mientras que el finetune se queda en 0.
  Empatan en la línea base; la suite de estrés los separa.

### Corrección de código (tareas difíciles juzgadas por LLM)

En dos tareas de coding multiturno más espinosas se **reparten**: en un rate limiter de ventana
deslizante ambos manejan los casos límite de frontera/desalojo; en un evaluador de expresiones
el **denso 27B acierta la precedencia de operadores** (`-2**2 == -4`, el menos unario como un
operador propiamente dicho) mientras que el **finetune no** (pliega el menos unario dentro del
número → `4.0`). La robustez de las llamadas a herramientas y la corrección algorítmica son ejes
*diferentes* — mide ambos.

### Retención de idioma

Ejecutando `--language fr` sobre el finetune y su base, mismo quant:

| model | adherence | diacritic traps | ASCII-stripped |
|---|--:|--:|--:|
| Qwen3.6-35B-A3B base | 100% | 4/4 | 0 |
| **Qwopus3.6-35B-A3B** | 100% | 4/4 | 0 |

**Cero regresión del francés.** El finetune orientado a coding mantuvo intacto el francés del
modelo base (adherence, diacríticos, sin despojo de ASCII) — un finetune específico de tarea
*no* costó otro idioma, algo que vale la pena verificar en lugar de asumir.

## Cómo leer esto

- **Veredicto primero, no velocidad primero.** Estas son señales de corrección/fiabilidad. Para
  el throughput, ver los [Benchmarks agénticos](agentic-benchmarks.md).
- **Núcleo determinista, juez opcional.** tool-call / recovery / thinking / adherence /
  diacritics no necesitan juez LLM — son reproducibles. Las calificaciones `coding`/`fluency`
  son juzgadas por LLM (subjetivas, opcionales).
- **Compara dentro de un cambio controlado.** El ejemplo mantiene la plantilla constante y varía
  solo el modelo, de modo que una diferencia es del modelo, no del harness.

## Metodología y advertencias

- `asiai bench --code` / `--language`, thinking desactivado
  (`chat_template_kwargs.enable_thinking=false`), un solo motor residente a la vez.
- **El quant difiere en el ejemplo** (el finetune Q4 vs los modelos Qwen Q5): el bug de objeto
  vacío de cabecera está impulsado por plantilla/generación y se confirmó en **ambos** quants
  para la base, así que el quant no explica la brecha — y el finetune gana desde el quant más
  bajo.
- **El juez de calidad de código no es estrictamente ciego** aquí (un modelo frontera leyó las
  transcripciones por sus méritos); las cifras deterministas de tool-call/stress son objetivas.
- **La recuperación es sensible a los pesos**, no es una señal limpia entre modelos — la
  cabecera es la fiabilidad de tool-call/objeto-vacío, que es estable entre repeticiones.

Véase también: [Benchmarks agénticos](agentic-benchmarks.md) ·
[Metodología de benchmark](methodology.md) · [Especificación de métricas](metrics-spec.md).
