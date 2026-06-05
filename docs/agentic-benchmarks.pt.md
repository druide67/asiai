---
description: Resultados de benchmark em modo agêntico no Apple Silicon — Qwen3.6 e Qwopus3.6 (27B denso vs 35B-A3B MoE), com e sem speculative decoding via MTP, nas famílias llama.cpp e MLX. Decode, TTFT, energia, RAM, validade. Uma página de resultados viva.
---

# Resultados de Benchmark em Modo Agêntico

Esta página reporta resultados reais de `asiai bench --agentic-mode` no Apple Silicon. O
protocolo agêntico executa uma conversa de 8 fases, consciente de prefix-cache (`--runs 5` para
variância), que exercita a forma como um agente realmente usa um modelo — multi-turno,
prefixo de sistema longo, fase de contexto longo de 50K tokens — em vez de uma única geração
one-shot.

**Por que o modo agêntico — para quem é isto?** Frameworks de agente não dirigem um modelo como um
chatbot: eles reutilizam um grande prefixo de sistema ao longo de muitos turnos, emitem tool calls e
carregam contexto longo. Um número de throughput one-shot ignora tudo isso — e o
ranking pode até inverter (um engine com ótimo decode bruto, mas com TTFT de vários segundos ou
um prefix-cache quebrado, é inutilizável para um agente). O modo agêntico mede o modelo da
forma como ele é realmente dirigido por **orquestradores de agentes e assistentes de código** — por exemplo
[Hermes Agent](https://github.com/nousresearch/hermes-agent),
[OpenClaw](https://github.com/openclaw/openclaw),
[opencode](https://github.com/sst/opencode), Aider, Cline ou Continue — de modo que o
resultado reflete cargas de trabalho reais de agente, não um artefato de benchmark.

> **Documento vivo.** Estes números são atualizados à medida que as versões dos engines, as revisões
> dos modelos e a instrumentação evoluem (por exemplo, captura de RAM de pico). Cada linha carrega
> a versão exata do engine e o arquivo do modelo, de modo que um resultado seja sempre reproduzível.

**Campanha 2026-06-03.** Modelos: Qwen3.6 e o finetune Qwopus3.6, em duas
arquiteturas — **27B denso** e **35B-A3B MoE** (Mixture-of-Experts, ~3B parâmetros ativos
por token). Engines: llama.cpp (b9430) e a família MLX (mlx-lm,
mlx_vlm, omlx, rapid-mlx, vllm-mlx). MTP = a head de Multi-Token
Prediction embutida no modelo, usada para speculative decoding (`--spec-type draft-mtp`).
Hardware: **MacBook Pro M5 Max (128 GB)** e **Mac mini M4 Pro (64 GB)**, ambos em
High Power Mode.

## Como ler a tabela

Veredito primeiro. As linhas são agrupadas por um resultado de gate determinístico, não apenas ordenadas:

- **★** melhor throughput validado no bloco · **✓** viável · **⚠** reserva
  (passa nos gates rígidos, mas tem latência medíocre) · **✗** eliminado (falhou em um gate).
- Gates: `valid ≥ 80%` · `TTFT ≤ 1500 ms` (falha rígida > 3000) · `prefix-cache reuse > 0`.
- **dec** = decode quente sustentado (tok/s) · **50K** = decode em contexto de 50K ·
  **TTFT** = time-to-first-token (ms) · **t/s/W** = tokens por segundo por watt de SoC
  (eficiência, quanto maior melhor) · **RAMpk** = RSS de pico do engine (GB, o valor que
  governa o cabimento em memória) · `—` = não medido (nunca 0).
- ★ classifica apenas por *throughput*. Escolher um modelo para trabalho real também pesa a qualidade
  da saída (ver a avaliação dev/code), que o throughput não captura.

> M4 Pro e M5 Max **não** são comparáveis em termos absolutos aqui — quant diferente
> (Q5_K_XL vs Q4_K_S). Compare dentro de um bloco de máquina.

## MacBook Pro M5 Max 128 GB · Q4

| | model · engine · MTP | dec t/s | peak | 50K | TTFT ms | reuse | t/s/W | RAMpk GB | valid% |
|:--|---|--:|--:|--:|--:|--:|--:|--:|--:|
| **★ Tier 1 — vencedor + rápido** |||||||||| |
| ★ | Qwopus-35B · llamacpp b9430 ▲MTP | 123.3 | 127.5 | 83.8 | 67 | 0.8 | 1.590 | — | 100 |
| ✓ | Qwen-35B · llamacpp b9430 ▲MTP | 118.3 | 123.5 | 82.9 | 62 | 0.8 | 1.513 | — | 100 |
| ✓ | Qwopus-35B · llamacpp b9430 | 105.7 | 108.3 | 76.1 | 63 | 0.8 | 1.507 | — | 100 |
| ✓ | Qwen-35B · llamacpp b9430 | 85.5 | 90.8 | 66.7 | 59 | 0.8 | 1.403 | — | 100 |
| **✓ Tier 2 — viável (mais lento)** |||||||||| |
| ✓ | Qwen-27B · llamacpp b9430 ▲MTP | 28.0 | 29.5 | 22.9 | 118 | 0.8 | 0.378 | 32.2 | 100 |
| ✓ | Qwopus-27B · llamacpp b9430 ▲MTP | 26.7 | 29.8 | 22.0 | 118 | 0.8 | 0.367 | 31.5 | 100 |
| ✓ | Qwopus-27B · llamacpp b9430 | 25.9 | 27.1 | 20.8 | 110 | 0.8 | 0.342 | 28.4 | 100 |
| ✓ | Qwen-27B · llamacpp b9430 | 23.8 | 24.0 | 19.2 | 111 | 0.8 | 0.340 | 28.9 | 100 |
| **⚠ Tier 3 — reserva (latência ruim)** |||||||||| |
| ⚠ | Qwopus-27B · mlx-lm 0.31.3 | 29.2 | 29.3 | 24.3 | 600 | 1.0 | 0.461 | 26.4 | 100 |
| ⚠ | Qwen-27B · rapid-mlx 0.6.71 | 20.6 | 20.7 | 17.9 | 798 | — | 0.357 | — | 85 |
| ⚠ | Qwen-27B · omlx 0.4.0 | 20.0 | 20.2 | 17.5 | 2150 | 0.82 | 0.346 | 26.7 | 100 |
| **✗ Tier 4 — eliminado** |||||||||| |
| ✗ | ~~Qwen-27B · mlx_vlm 0.6.0 ▲MTP~~ | ~~41.0~~ | — | — | ~~10879~~ | 0.0 | — | — | 75 |
| ✗ | ~~Qwen-27B · mlx_vlm 0.6.0~~ | ~~31.9~~ | — | 26.0 | ~~9578~~ | 0.0 | — | — | 100 |
| ✗ | ~~Qwen-27B · vllm-mlx 0.3.0~~ | ~~20.5~~ | — | 18.1 | ~~9578~~ | — | — | 24.3 | 100 |

Eliminações: mlx_vlm+MTP falha na validade (75%) e quebra o contexto longo; tanto as
execuções de mlx_vlm quanto a de vllm-mlx têm TTFT de ~9.6 s (inutilizável por turno de agente).

## Mac mini M4 Pro 64 GB · Q5

| | model · engine · MTP | dec t/s | peak | 50K | TTFT ms | reuse | t/s/W | RAMpk GB | valid% |
|:--|---|--:|--:|--:|--:|--:|--:|--:|--:|
| **★ Tier 1** |||||||||| |
| ★ | Qwen-35B · llamacpp b9430 ▲MTP | 44.6 | 50.7 | 32.6 | 143 | 0.8 | 1.557 | 33.0 | 100 |
| ✓ | Qwen-35B · llamacpp b9430 | 36.3 | 45.6 | 29.6 | 133 | 0.8 | 1.553 | 30.8 | 100 |
| **✓ Tier 2** |||||||||| |
| ✓ | Qwen-27B · llamacpp b9430 | 10.4 | 10.4 | 7.2 | 397 | 0.8 | 0.279 | 31.9 | 100 |
| ✓ | Qwen-27B · llamacpp b9430 ▲MTP | 9.7 | 9.8 | 7.5 | 409 | 0.8 | 0.272 | 35.4 | 100 |

## Principais conclusões

- **O MoE 35B-A3B supera o 27B denso em todos os eixos de throughput** em ambas as
  máquinas — ele ativa apenas ~3B parâmetros por token, então faz decode ~4× mais rápido
  que o denso 27B e é ~3.5× mais eficiente em energia (1.5 vs ~0.4 tok/s/W).
  Throughput não é qualidade, no entanto — ver a ressalva abaixo.
- **O ganho de MTP depende de arquitetura × hardware.** Uplift de decode medido:
  MoE +38% (M5) / +23% (M4); denso +16% (M5), mas **−7% (M4)** — na GPU mais lenta do M4
  o overhead do draft no modelo denso não é amortizado. Portanto, MTP é uma medição por modelo
  e por máquina, não um ganho universal.
- **A família de servidores MLX é só throughput aqui**: o mlx-lm tem o melhor decode MLX,
  mas um piso de TTFT de 600 ms; mlx_vlm, vllm-mlx e omlx são eliminados pelo TTFT
  (2–11 s) e/ou pelo prefix-cache quebrado. O llama.cpp domina a latência de primeiro token
  (~60–120 ms).
- **RAM de pico vs estável.** O RSS do mlx-lm fica em ~14.5 GB estável, mas **atinge pico de
  26.4 GB** (alocação lazy de KV + pesos compactos MLX-4bit); o llama.cpp pré-aloca
  o KV de contexto completo já no início (~29 GB plano). No pico eles são comparáveis — use
  **RAMpk** para decisões de cabimento em memória, não o valor estável.

## Metodologia e ressalvas

- `asiai bench --agentic-mode --runs 5`, thinking desativado
  (`chat_template_kwargs.enable_thinking=false`), contexto do servidor ≥ 65536.
- Um engine residente por vez (SOLO); page cache purgado entre execuções de GGUF que
  compartilham um arquivo.
- **A quant difere por máquina** (M5 Q4_K_S/Q4_K_XL, M4 Q5_K_XL) → os números absolutos
  não são comparáveis entre máquinas, apenas dentro de um bloco.
- **High Power Mode** é obrigatório no laptop M5 (caso contrário a GPU sustentada sofre
  throttle de ~40%); o desktop mini M4 é mais ou menos neutro a isso.
- **Lacunas conhecidas de instrumentação** (em correção): a RAM de pico está ausente (`—`) em alguns
  servidores llama.cpp lançados manualmente; a versão do engine ainda não é carimbada por execução
  (mostrada aqui a partir de um mapa de versões); o `reuse` de prefix-cache é uma fração grosseira
  pendente de uma taxa de hit real.

Veja também: [Metodologia de benchmark](methodology.md) · [Especificação de métricas](metrics-spec.md)
· [Leaderboard da comunidade](leaderboard.md).
