---
title: "Qué motor para Qwen3.8-27B en Apple Silicon"
description: "Ocho motores de inferencia medidos en un solo M5 Max con el mismo modelo. Dos motores que leen el mismo archivo de pesos difieren en un 50%, y la opción que aporta un 20% viene desactivada por defecto en casi todos."
type: article
date: 2026-08-16
updated: 2026-08-16
---

# Qué motor para Qwen3.8-27B en Apple Silicon

La cuestión del modelo está zanjada: Qwen3.8-27B funciona en un portátil y sostiene
262 144 tokens de contexto. La del motor no lo está, y cuesta más de lo que se cree.

Medimos ocho motores en un solo M5 Max. Los dos resultados más interesantes no van de
velocidad: van de dos motores que leen el *mismo archivo* y discrepan en un 50%, y de una
opción que nadie activa.

## Condiciones, antes de las cifras

M5 Max 128 GB, alimentación de red, High Power Mode, un solo motor residente a la vez.
Razonamiento desactivado en todos los motores para poder compararlos entre sí. Limitación
térmica al 50% en 1-2 minutos en todas las celdas: **son suelos, no máximos**. Validez de
salida del 100% en todas las filas. Tamaños de prompt de 7 530 tokens (fases cortas) y
55 839 (largas), salida limitada a 400 y 200 tokens.

**No afirmamos que estas sean las velocidades que vas a obtener.** Afirmamos que son las
diferencias entre motores bajo un mismo protocolo.

## La tabla

| Motor | Pesos | n | En caliente | A 56k | Primer token | Memoria | Ctx declarado |
|---|---|---|---|---|---|---|---|
| **MTPLX** Bare-Speed | MTPLX 4-bit g64 | 3 | **56,0** | **46,5** | 101 ms | 22,0 GB | por defecto del motor |
| **MTPLX** Optimized-Speed | MTPLX 4-bit g32 | **5** | **44,4** | 37,5 | 99 ms | 27,0 GB | por defecto del motor |
| **mlx-vlm** + drafter MTP | MLX 4-bit ⁽¹⁾ | 3 | **43,3** | 28,9 | **9 982 ms** | 15,5 GB | por defecto del motor |
| **MTPLX** Optimized-Quality | MTPLX 8-bit g64 | 3 | 40,8 | 30,3 | 118 ms | 32,9 GB | por defecto del motor |
| Ollama 0.32.13 | GGUF (sin declarar) | 3 | 32,8 | 21,7 | 240 ms | 30,3 GB | 65 536 |
| llama.cpp b10434 + MTP | GGUF Q5_K_XL ⁽²⁾ | 3 | 31,8 | 22,7 | **125 ms** | 36,8 GB | 131 072 |
| rapid-mlx 0.12.11 | MLX 4-bit ⁽¹⁾ | 3 | 30,2 | 24,7 | **33 195 ms** | 15,0 GB | por defecto del motor |
| oMLX 0.6.0-dev | oQ4e-mtp (de terceros) | 3 | 29,8 | 24,6 | 1 968 ms | 16,7 GB | por defecto del motor |
| mlx-lm 0.31.3 | MLX 4-bit ⁽¹⁾ | 3 | 28,8 | 24,0 | 432 ms | **14,6 GB** | por defecto del motor |
| LM Studio 0.4.21 **+ MTP** | GGUF Q5_K_XL ⁽²⁾ | 3 | 27,8 | 23,4 | 419 ms | 36,3 GB | 65 536 |
| LM Studio 0.4.21 por defecto | GGUF Q5_K_XL ⁽²⁾ | 3 | 23,1 | 18,7 | 359 ms | 35,2 GB | 65 536 |

⁽¹⁾ y ⁽²⁾ marcan las filas que comparten un **archivo de pesos idéntico byte a byte**.
Cada fila es una celda, una exportación: ningún valor se mezcla entre ejecuciones.

⚠️ **La memoria no es comparable entre familias.** llama.cpp y Ollama hacen mmap de su
GGUF: su conjunto residente está respaldado por archivo y es expulsable (llama.cpp:
36,8 GB de RSS pero 19,8 GB de huella física). Los motores MLX reservan memoria. Lee la
columna dentro de una familia, no entre familias.

⚠️ **El contexto declarado difiere.** A tres motores se les dio una ventana explícita; los
demás funcionaron con la suya por defecto. Solo eso ya prohíbe ordenar globalmente la
columna de memoria.

## Dos motores, un archivo, 50% de diferencia ⁽¹⁾

mlx-vlm, mlx-lm y rapid-mlx sirvieron todos `lmstudio-community/Qwen3.8-27B-MLX-4bit`,
snapshot `6067b15c`: el mismo archivo en disco.

| Motor | En caliente | Primer token | Memoria |
|---|---|---|---|
| mlx-vlm + drafter MTP | **43,3** | 9 982 ms | 15,5 GB |
| rapid-mlx | 30,2 | 33 195 ms | 15,0 GB |
| mlx-lm | 28,8 | **432 ms** | 14,6 GB |

**+50% de mlx-lm a mlx-vlm, sin cambiar nada más que el servidor.** Es la comparación más
limpia de la campaña: no hay diferencia de cuantización que discutir.

Y se invierte de inmediato: la ventaja del 50% de mlx-vlm cuesta un **tiempo hasta el
primer token 23× peor**, porque no tiene ninguna caché de prefijo. Para una generación
única, gana. Para un agente, es inutilizable, y el motivo está en la sección siguiente.

## La opción que aporta un 20%, y por qué está desactivada ⁽²⁾

Qwen3.8 incorpora una **cabeza de predicción multi-token dentro de los pesos**. El modelo
propone varios tokens por adelantado y el motor los verifica en una sola pasada hacia
delante. Los motores que implementan la regla de aceptación por cociente de
probabilidades preservan exactamente la distribución de salida; nosotros no verificamos
esa propiedad, y no deberías darla por buena porque lo diga un benchmark: lee la
implementación de tu motor.

Casi todos los motores la traen **desactivada**.

| Motor | Opción | ¿Activada por defecto? |
|---|---|---|
| vmlx | `--native-mtp-depth` | **sí** |
| MTPLX | `--mtp --depth 3` | sí |
| vllm-mlx | `--enable-mtp` | no |
| llama.cpp | `--spec-type draft-mtp` | no |
| LM Studio | `--speculative-draft-mtp` | no |
| mlx-vlm | `--draft-kind mtp` + repositorio de drafter aparte | no |
| oMLX | no se activó con Qwen3.8 en nuestras ejecuciones | — |
| Ollama · mlx-lm · rapid-mlx | sin soporte | — |

Medimos el coste de no saberlo sobre el mismo archivo de pesos, el mismo contexto de
65 536, todo igual salvo dos opciones: **LM Studio pasa de 23,1 → 27,8 tok/s, +20%.**
Ninguna interfaz gráfica lo muestra.

Efecto de segundo orden, y pesa más: **comparar dos motores con sus valores por defecto
es comparar dos regímenes distintos.** vmlx hace drafting, llama.cpp no.

## El primer token abarca 350×. El prefill no lo explica.

De 99 ms a 33 195 ms a lo largo de la tabla. Lo que decide es la **granularidad de la
caché de prefijo**: cuánto sobrevive de un prompt repetido entre turnos. Medido sobre la
misma fase (el turno en caliente, donde se toma la latencia hasta el primer token):

| Motor | Reutiliza | Re-prefill en cada turno | Primer token |
|---|---|---|---|
| llama.cpp | 7 526 / 7 530 — **a nivel de token** | 4 tokens | 125 ms |
| oMLX | 6 144 / 7 530 — **bloques de 1024 tokens** | 1 386 tokens | 1 944 ms |
| mlx-vlm | 0 / 7 530 | 7 530 tokens | 9 982 ms |

6 144 es seis veces 1 024. oMLX reutiliza bloques enteros y vuelve a hacer prefill de todo
lo que no llena uno: 1 386 tokens, en cada turno, para siempre. Ahí está toda la
diferencia entre 125 ms y 2 segundos.

⚠️ **No compares entre motores los ratios de reutilización agregados por sesión.** Tienen
techos distintos según qué parte del prompt de prueba sea cacheable, y compararlos produce
paradojas que se desvanecen cuando comparas la misma fase. Cometimos ese error en un
borrador anterior de esta página.

**No** publicamos una columna de rendimiento de prefill. El nuestro venía de una única
petición en frío sin repetir, que en motores de carga perezosa incluye leer 20 GB de
disco: LM Studio midió 216 tok/s en esa petición y 938 en la siguiente. Habría sido una
cifra fabricada.

## Tokens por segundo no es una velocidad

Entre cuantizaciones del mismo modelo, los tok/s miden en parte lo largas que son las
salidas, no lo rápido que llegan:

| Build | tok/s | chars/s |
|---|---|---|
| Bare-Speed | 56,0 | 200,8 |
| Optimized-Speed | 44,4 | **203,1** |
| Optimized-Quality | 40,8 | 165,7 |

Bare-Speed lidera por un 26% en tokens por segundo y va **por detrás** en caracteres por
segundo. El mismo tokenizador en las tres: lo que cambia es lo que las cuantizaciones
eligieron escribir. Publica la definición junto con la cifra.

## Lo que recomendamos

**Para un agente autónomo local: MTPLX con `Qwen3.8-27B-MTPLX-Optimized-Speed`, MTP a
profundidad 3.** Rápido, 99 ms hasta el primer token, reutilización de prefijo a nivel de
token, 27 GB.

Bare-Speed no, aunque lidere sobre el papel. Suites de tool-calling, mismo protocolo en
las tres:

| Build | tool-call (24 turnos) | stress (33 turnos) | turnos de edición (9) |
|---|---|---|---|
| Optimized-Quality | **83,3%** | 81,8% | **55,6%** |
| Optimized-Speed | 79,2% | **81,8%** | 44,4% |
| Bare-Speed | 62,5% | 72,7% | 22,2% |

⚠️ **Léelas con honestidad.** En la suite de stress, más grande, Optimized-Speed y
Optimized-Quality **empatan exactamente**. Y el test exacto de Fisher sobre la suite de
24 turnos da **p = 0,34** para Bare-Speed frente a Optimized-Speed y **p = 1,00** para
Quality frente a Speed: ninguna de las dos diferencias es estadísticamente significativa
con este tamaño de muestra. Los 24 turnos son 3 repeticiones de 8 tareas, así que la n
efectiva es aún menor.

Lo que sí tenemos es una **dirección consistente a lo largo de tres suites y dos métodos
independientes**: nuestros resultados de tool-calling ordenan las tres builds igual que
las cifras de divergencia respecto a bf16 publicadas por el autor de la cuantización
(0,00105 / 0,0220 / 0,0376 — su medición, no la nuestra, no reproducida). La coincidencia
entre métodos sin relación entre sí vale más que cualquiera de los dos p-valores. Por eso
desaconsejamos Bare-Speed, y es una evidencia más débil de lo que aparenta una tabla de
porcentajes.

Optimized-Quality tampoco: cuesta **8,3 GB más** por una ventaja que no podemos demostrar.

## Lo que no pudimos medir

**vmlx y vllm-mlx se intentaron y faltan.** Ambos admiten MTP nativo — vmlx lo trae
activado por defecto —, así que su ausencia es un hueco real en esta comparación, no un
error de redondeo. vllm-mlx murió al arrancar por un error de comillas en la línea de
comandos; vmlx seguía ejecutándose cuando esto se publicó.

**El razonamiento estaba desactivado, y no es así como deberías ejecutar este modelo.**
Qwen afirma que, en tareas agénticas multiturno, un menor esfuerzo de razonamiento *"can
lead to insufficient analysis, more failures, and repeated retries, which may increase
total latency"* (puede llevar a un análisis insuficiente, más fallos y reintentos
repetidos, lo que puede aumentar la latencia total). MTPLX 2.7.1 recoge el razonamiento
desactivado como problema conocido para Qwen3.8. Lo desactivamos para hacer comparables
los motores: una decisión de medición, no de despliegue.

**Salvedades de versión.** Las filas de MTPLX se ejecutaron en **2.6.0**, antes de que el
motor incorporara una familia de modelos `qwen3_8`: servía Qwen3.8 con los valores por
defecto de Qwen3.6, incluido un contrato de muestreo distinto. Esto no afecta al
rendimiento; sí afecta a todo lo relativo al comportamiento. La fila de oMLX salió de una
build de desarrollo temporal cuya cadena de versión la exportación no capturó, así que esa
fila no es reproducible tal como se publica. Y nuestra exportación de mlx-vlm se
autoidentifica como `mlxlm 0.31.3_2`: solo el log de arranque prueba que el servidor era
`mlx_vlm.server`.

**El orden del primer token entre las tres builds de MTPLX está dentro de su propio
ruido**: coeficientes de variación de 0,33 a 0,66 en esa métrica. 99, 101 y 118 ms no son
separables. La columna de rendimiento es mucho más estable (CV 0,01-0,04).

**La dispersión test-retest en reejecuciones idénticas del mismo comando llegó al 7,5%**
(37,97 / 40,82 / 39,35 tok/s en tres ejecuciones de Optimized-Quality), y la memoria varió
5 GB entre reejecuciones. Trata como nada cualquier diferencia por debajo del 8%.

**El ajuste no fue simétrico.** llama.cpp recibió opciones explícitas de caché
(`--cache-reuse 256 --slot-prompt-similarity 0.5`, flash attention, KV de 131k) que los
motores MLX no recibieron. MTPLX se ejecutó con `--profile turbo`, no con su valor por
defecto. Esta es una comparación de configuraciones que desplegaríamos, no de valores por
defecto listos para usar.

## Cómo reproducir esto

Todas las cifras proceden de una tarjeta certificada producida por
[asiai](https://asiai.dev), a través de una única ruta programada con gates de soledad,
pruebas de identidad del modelo servido y muestreo térmico. Exportaciones en bruto
disponibles.

Si te quedas con una sola cosa: **comprueba si tu motor tiene predicción multi-token, y si
está activada.**
