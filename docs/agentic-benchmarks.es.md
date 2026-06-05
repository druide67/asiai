---
description: Resultados de benchmark en modo agéntico sobre Apple Silicon — Qwen3.6 y Qwopus3.6 (27B denso vs 35B-A3B MoE), con y sin decodificación especulativa MTP, en llama.cpp y la familia de motores MLX. Decode, TTFT, energía, RAM, validez. Una página de resultados viva.
---

# Resultados de benchmark agéntico

Esta página reporta resultados reales de `asiai bench --agentic-mode` sobre Apple Silicon. El
protocolo agéntico ejecuta una conversación de 8 fases consciente de la prefix-cache (`--runs 5` para
varianza), que ejercita la forma en que un agente usa realmente un modelo — multiturno,
prefijo de sistema largo, fase de contexto largo de 50K tokens — en lugar de una única
generación de un solo paso.

**Por qué el modo agéntico — ¿para quién es?** Los frameworks de agentes no manejan
un modelo como un chatbot: reutilizan un gran prefijo de sistema a lo largo de muchos
turnos, emiten llamadas a herramientas y arrastran contexto largo. Una cifra de
throughput de un solo paso ignora todo eso — y el ranking puede incluso invertirse (un
motor con un decode bruto excelente pero con un TTFT de varios segundos o una
prefix-cache rota es inutilizable para un agente). El modo agéntico mide el modelo tal
como es realmente manejado por **orquestadores de agentes y asistentes de código** —
p. ej. [Hermes Agent](https://github.com/nousresearch/hermes-agent),
[OpenClaw](https://github.com/openclaw/openclaw),
[opencode](https://github.com/sst/opencode), Aider, Cline o Continue — de modo que el
resultado refleja cargas de trabajo reales de agentes, no un artefacto de benchmark.

> **Documento vivo.** Estas cifras se actualizan a medida que mejoran las versiones de los motores, las
> revisiones de los modelos y la instrumentación (p. ej. la captura de RAM pico). Cada fila lleva
> la versión exacta del motor y el archivo del modelo, de modo que un resultado siempre es reproducible.

**Campaña 2026-06-03.** Modelos: Qwen3.6 y el finetune Qwopus3.6, en dos
arquitecturas — **27B denso** y **35B-A3B MoE** (Mixture-of-Experts, ~3B parámetros
activos por token). Motores: llama.cpp (b9430) y la familia MLX (mlx-lm,
mlx_vlm, omlx, rapid-mlx, vllm-mlx). MTP = la cabeza de Multi-Token
Prediction integrada del modelo, usada para decodificación especulativa (`--spec-type draft-mtp`).
Hardware: **MacBook Pro M5 Max (128 GB)** y **Mac mini M4 Pro (64 GB)**, ambos en
High Power Mode.

## Cómo leer la tabla

Veredicto primero. Las filas se agrupan por un resultado de gate determinista, no solo se ordenan:

- **★** mejor throughput validado del bloque · **✓** viable · **⚠** reserva
  (pasa los gates duros pero con latencia mediocre) · **✗** eliminado (falló un gate).
- Gates: `valid ≥ 80%` · `TTFT ≤ 1500 ms` (fallo duro > 3000) · `prefix-cache reuse > 0`.
- **dec** = decode sostenido en caliente (tok/s) · **50K** = decode a 50K de contexto ·
  **TTFT** = time-to-first-token (ms) · **t/s/W** = tokens por segundo por vatio de SoC
  (eficiencia, más alto es mejor) · **RAMpk** = RSS pico del motor (GB, la cifra que
  gobierna el ajuste de memoria) · `—` = no medido (nunca 0).
- ★ ordena por *throughput únicamente*. Elegir un modelo para trabajo real también pondera la
  calidad de salida (ver la evaluación dev/code), que el throughput no captura.

> El M4 Pro y el M5 Max **no** son comparables en términos absolutos aquí — quant distinto
> (Q5_K_XL vs Q4_K_S). Compara dentro de un mismo bloque de máquina.

## MacBook Pro M5 Max 128 GB · Q4

| | model · engine · MTP | dec t/s | peak | 50K | TTFT ms | reuse | t/s/W | RAMpk GB | valid% |
|:--|---|--:|--:|--:|--:|--:|--:|--:|--:|
| **★ Nivel 1 — ganador + rápido** |||||||||| |
| ★ | Qwopus-35B · llamacpp b9430 ▲MTP | 123.3 | 127.5 | 83.8 | 67 | 0.8 | 1.590 | — | 100 |
| ✓ | Qwen-35B · llamacpp b9430 ▲MTP | 118.3 | 123.5 | 82.9 | 62 | 0.8 | 1.513 | — | 100 |
| ✓ | Qwopus-35B · llamacpp b9430 | 105.7 | 108.3 | 76.1 | 63 | 0.8 | 1.507 | — | 100 |
| ✓ | Qwen-35B · llamacpp b9430 | 85.5 | 90.8 | 66.7 | 59 | 0.8 | 1.403 | — | 100 |
| **✓ Nivel 2 — viable (más lento)** |||||||||| |
| ✓ | Qwen-27B · llamacpp b9430 ▲MTP | 28.0 | 29.5 | 22.9 | 118 | 0.8 | 0.378 | 32.2 | 100 |
| ✓ | Qwopus-27B · llamacpp b9430 ▲MTP | 26.7 | 29.8 | 22.0 | 118 | 0.8 | 0.367 | 31.5 | 100 |
| ✓ | Qwopus-27B · llamacpp b9430 | 25.9 | 27.1 | 20.8 | 110 | 0.8 | 0.342 | 28.4 | 100 |
| ✓ | Qwen-27B · llamacpp b9430 | 23.8 | 24.0 | 19.2 | 111 | 0.8 | 0.340 | 28.9 | 100 |
| **⚠ Nivel 3 — reserva (latencia pobre)** |||||||||| |
| ⚠ | Qwopus-27B · mlx-lm 0.31.3 | 29.2 | 29.3 | 24.3 | 600 | 1.0 | 0.461 | 26.4 | 100 |
| ⚠ | Qwen-27B · rapid-mlx 0.6.71 | 20.6 | 20.7 | 17.9 | 798 | — | 0.357 | — | 85 |
| ⚠ | Qwen-27B · omlx 0.4.0 | 20.0 | 20.2 | 17.5 | 2150 | 0.82 | 0.346 | 26.7 | 100 |
| **✗ Nivel 4 — eliminado** |||||||||| |
| ✗ | ~~Qwen-27B · mlx_vlm 0.6.0 ▲MTP~~ | ~~41.0~~ | — | — | ~~10879~~ | 0.0 | — | — | 75 |
| ✗ | ~~Qwen-27B · mlx_vlm 0.6.0~~ | ~~31.9~~ | — | 26.0 | ~~9578~~ | 0.0 | — | — | 100 |
| ✗ | ~~Qwen-27B · vllm-mlx 0.3.0~~ | ~~20.5~~ | — | 18.1 | ~~9578~~ | — | — | 24.3 | 100 |

Eliminaciones: mlx_vlm+MTP falla la validez (75%) y rompe el contexto largo; tanto las
ejecuciones de mlx_vlm como vllm-mlx tienen ~9.6 s de TTFT (inutilizable por turno de agente).

## Mac mini M4 Pro 64 GB · Q5

| | model · engine · MTP | dec t/s | peak | 50K | TTFT ms | reuse | t/s/W | RAMpk GB | valid% |
|:--|---|--:|--:|--:|--:|--:|--:|--:|--:|
| **★ Nivel 1** |||||||||| |
| ★ | Qwen-35B · llamacpp b9430 ▲MTP | 44.6 | 50.7 | 32.6 | 143 | 0.8 | 1.557 | 33.0 | 100 |
| ✓ | Qwen-35B · llamacpp b9430 | 36.3 | 45.6 | 29.6 | 133 | 0.8 | 1.553 | 30.8 | 100 |
| **✓ Nivel 2** |||||||||| |
| ✓ | Qwen-27B · llamacpp b9430 | 10.4 | 10.4 | 7.2 | 397 | 0.8 | 0.279 | 31.9 | 100 |
| ✓ | Qwen-27B · llamacpp b9430 ▲MTP | 9.7 | 9.8 | 7.5 | 409 | 0.8 | 0.272 | 35.4 | 100 |

## Hallazgos clave

- **El MoE 35B-A3B supera al denso 27B en todos los ejes de throughput** en ambas
  máquinas — activa solo ~3B parámetros por token, así que decodifica ~4× más rápido
  que el denso 27B y es ~3.5× más eficiente energéticamente (1.5 vs ~0.4 tok/s/W).
  Sin embargo, throughput no es calidad — ver la advertencia más abajo.
- **La ganancia de MTP depende de arquitectura × hardware.** Mejora de decode medida:
  MoE +38% (M5) / +23% (M4); denso +16% (M5) pero **−7% (M4)** — en la GPU más lenta del M4
  el overhead del draft denso no se amortiza. Así que MTP es una medición por modelo y por
  máquina, no una victoria universal.
- **La familia de servidores MLX aquí es solo-throughput**: mlx-lm tiene el mejor decode MLX
  pero un piso de TTFT de 600 ms; mlx_vlm, vllm-mlx y omlx quedan fuera por TTFT
  (2–11 s) y/o prefix-cache rota. llama.cpp domina la latencia del primer token
  (~60–120 ms).
- **RAM pico vs en régimen.** El RSS de mlx-lm se mantiene en ~14.5 GB en régimen pero **alcanza un
  pico de 26.4 GB** (asignación perezosa de KV + pesos MLX-4bit compactos); llama.cpp preasigna
  por adelantado todo el KV del contexto (~29 GB plano). En el pico son comparables — usa
  **RAMpk** para las decisiones de ajuste de memoria, no el valor en régimen.

## Metodología y advertencias

- `asiai bench --agentic-mode --runs 5`, thinking desactivado
  (`chat_template_kwargs.enable_thinking=false`), contexto de servidor ≥ 65536.
- Un solo motor residente a la vez (SOLO); la page cache se purga entre ejecuciones de GGUF que
  comparten un archivo.
- **El quant difiere según la máquina** (M5 Q4_K_S/Q4_K_XL, M4 Q5_K_XL) → las cifras absolutas
  no son comparables entre máquinas, solo dentro de un bloque.
- **High Power Mode** es obligatorio en el portátil M5 (de lo contrario la GPU sostenida se ve
  throttleada ~40%); el escritorio mini M4 es aproximadamente neutral a ello.
- **Carencias conocidas de instrumentación** (en proceso de corrección): la RAM pico falta (`—`) en algunos
  servidores llama.cpp lanzados manualmente; la versión del motor todavía no se sella por ejecución
  (mostrada aquí a partir de un mapa de versiones); el `reuse` de la prefix-cache es una fracción
  gruesa a la espera de una verdadera tasa de aciertos.

Véase también: [Metodología de benchmark](methodology.md) · [Especificación de métricas](metrics-spec.md)
· [Leaderboard comunitario](leaderboard.md).
