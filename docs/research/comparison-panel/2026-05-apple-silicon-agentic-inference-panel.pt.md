# Painel de Inferência Agêntica em Apple Silicon

> Painel comparativo de benchmark entre motores de inferência (llama.cpp, mlx-lm,
> LM Studio, Rapid-MLX, vLLM-MLX, oMLX, vMLX, Ollama) executando modelos da
> família Qwen 3.6 em Apple Silicon série M, medidos com
> `asiai bench --agentic-mode` e `asiai bench --burst-mode`.
>
> **Alvo de carga de trabalho**: classe agente-orquestrador — ~60-80 chamadas de
> ferramenta por turno, prompt de sistema idêntico de ~7 KB, mensagem de usuário
> mudando a cada chamada. Este é o pior caso para cache de prefixo ingênuo: é
> necessário um verdadeiro reuso de cache entre USUÁRIOS, não apenas cache sobre
> o mesmo prompt.
>
> **Lendo os números de throughput**: as taxas de decode da Seção 1 usam o
> template de chat padrão do Qwen3 (thinking ON), portanto incluem tokens de
> raciocínio — o throughput efetivo do agente em um modelo com thinking é mais
> baixo. O thinking é um trade-off por tarefa (ressalva 1), não um liga/desliga
> global.
>
> Publicado em 2026-06 · contribuições e correções são bem-vindas via
> [github.com/druide67/asiai](https://github.com/druide67/asiai/issues).

## ⚠️ Ressalvas conhecidas antes de prosseguir na leitura

1. **O modo thinking é um trade-off por tarefa.** Com o template padrão do Qwen3
   (thinking ON), Qwen 3.6 / Qwopus emitem ~6-7× mais tokens, de modo que os
   números de decode da Seção 1 **incluem tokens de raciocínio** e o throughput
   efetivo do agente é mais baixo. Thinking ON é **necessário** para entregáveis
   escritos com múltiplas seções (um modelo com thinking OFF pula o entregável),
   mas **custa** a limpeza atômica das chamadas de ferramenta (o asiai mede ~100%
   de chamadas de ferramenta limpas com thinking OFF vs ~77.8% com thinking ON +
   `preserve_thinking` ON, determinístico entre execuções;
   `enable_thinking=on` + `preserve_thinking=off` é inutilizável — um HTTP 500
   determinístico assim que o raciocínio se acumula no contexto). Defina o
   thinking **por dimensão de tarefa**, não como uma única flag global.
2. **Rapid-MLX e vLLM-MLX compartilham um motor.** Rapid-MLX é um fork comunitário
   de `waybarrios/vllm-mlx`; eles aparecem como linhas separadas abaixo porque
   divergiram em versão e funcionalidades, mas o mecanismo de snapshot de cache de
   prefixo é da mesma linhagem.
3. **MTP: o Qwen 3.6 tem uma cabeça real; o backend importa.** O `config.json`
   oficial do Qwen 3.6 carrega `mtp_num_hidden_layers=1` (nomenclatura Qwen —
   **não** a chave `num_nextn_predict_layers` da DeepSeek, de modo que uma
   verificação apenas de `nextn` conclui erroneamente "sem cabeça"). Alguns
   artefatos GGUF/MLX re-quantizados descartam os tensores MTP mantendo a flag de
   config — verifique os tensores no índice de pesos, não apenas a flag. O MTP
   nativo do llama.cpp (`--spec-type draft-mtp`) **requer um `-MTP-GGUF`** que
   embuta a cabeça; um GGUF simples não consegue fazer draft. O mlx-lm lançado não
   executa a cabeça como decode especulativo nativo (o PR
   [ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990) o
   adiciona). O LM Studio roteia GGUF através do seu backend derivado do llama.cpp
   e MLX através do `mlx-engine`.
4. **Medições de passagem única, sem relato de variância** — os números das
   Seções 1 / 2 são observações únicas. O relato de variância (mediana + min + max
   ao longo de N passagens) é suportado a partir de `--burst-runs N`, mas o
   re-benchmark está pendente.

| Seção | Tópico | Status |
|---------|-------|--------|
| 1 | Performance de chamada única | 🟡 8 cells, thinking-mode ON (decode includes reasoning tokens) |
| 2 | Burst concorrente (30/60/80 chamadas paralelas) | 🟡 smoke cell + 2 partial concurrent points; no normalized 30/60/80 panel |
| 3 | Caches & otimizações | ✅ 8 engines covered |
| 4 | Memória & recursos | ✅ idle + under-load swap (+0) + footprint measured |
| 5 | Qualidade dos modelos (leaderboards públicos) | 🟡 vendor/self-reported figures (llm-stats) |
| — | **medições diretas do asiai** | ✅ dev-quality, thinking ablation, MTP, instruction-following |
| 6 | Operacional (licença, endpoints, manutenção) | ✅ 8 engines covered |
| 7 | Ponderação dos benchmarks de qualidade | 🟡 default weighting, override via `--weights` planned |
| 8 | Avaliação custom de horizonte longo (proposta) | 🟡 scoped, not yet built |

---

## Seção 1 — Performance de chamada única

> 🟠 **Snapshot de maio de 2026 — indicativo, não são os números de referência.**
> Esta tabela foi capturada em maio (thinking-mode ON, passagem única) e suas
> fixtures de origem não foram re-verificadas. Para **throughput de decode atual e
> reproduzível**, use a seção *medições diretas do asiai* abaixo (junho, llama.cpp
> b9430, determinístico). Aquilo para o que esta tabela é confiável é a história
> **relativa de TTFT / cache de prefixo** (reuso entre USUÁRIOS), não os t/s
> absolutos. Note em particular que os 123.9 t/s na linha 5 (LM Studio GGUF+MTP)
> ficam logo ao lado dos **llama.cpp Qwopus+MTP 123.3 t/s** de junho — o caminho
> GGUF do LM Studio é um backend derivado do llama.cpp, portanto os dois medem
> essencialmente o mesmo motor.

> ⚠️ **Leia com a ressalva 1 acima**: cada número nesta tabela inclui os tokens do
> modo thinking padrão do Qwen3 (reasoning_content). O throughput efetivo do
> agente requer re-execução com
> `chat_template_kwargs={"enable_thinking": false}`. A coluna é rotulada
> "decode (t/s)", não "throughput efetivo".
>
> A coluna "estimativa de limite inferior" é `60 × (TTFT + max_tokens/decode)`,
> assumindo despacho sequencial (que o single-slot do Rapid-MLX impõe). **Não** é
> uma previsão de tick de produção — veja a [Seção 7](#section-7) para a ressalva
> metodológica.
>
> 📌 **Versões testadas (maio de 2026)**: Rapid-MLX 0.6.66, LM Studio 0.4.14,
> llama.cpp b9270. As versões dos motores mudam semanalmente em Apple Silicon —
> trate cada número como datado, não atual. (A seção de medições do asiai usa
> llama.cpp b9430.)

| # | Motor | Modelo | Formato | Warm decode (t/s) ¹ | TTFT warm (ms) | TTFT prefix-test mediana (ms) | TTFT cold (ms) | Estimativa de limite inferior (60 chamadas × chamada única, otimista) | Fixture de origem |
|---|--------|-------|--------|--------------------:|---------------:|----------------------------:|---------------:|----------------------------------------------------------:|----------------|
| 1 | Rapid-MLX 0.6.66 (fork of vllm-mlx) | Qwopus 3.6-35B-A3B-v1 (zaydiscold MLX-4bit) | MLX-4bit | **109.1** ¹ | 139 | **131** | 2074 | ~3.6 min | `cell-rapidmlx-qwopus35b.json` |
| 2 | Rapid-MLX 0.6.66 | Qwen 3.6-35B-A3B-UD (MLX-4bit) | MLX-4bit | 106.9 ¹ | 321 | 319 | 2095 | ~4 min | `cell-rapidmlx-35b-a3b.json` |
| 3 | Rapid-MLX 0.6.66 | Qwopus 3.6-27B-v2 (Jackrong MLX-4bit) | MLX-4bit | 31.8 ¹ | 323 | 323 | 8647 | ~13 min | `cell-rapidmlx-qwopus.json` |
| 4 | Rapid-MLX 0.6.66 | Qwen 3.6-27B-UD (MLX-4bit) | MLX-4bit | 20.5 ¹ | 527 | 527 | 8954 | ~23 min | `cell-rapidmlx-full-27bud.json` |
| 5 | LM Studio 0.4.14 (GGUF backend) ² | Qwen 3.6-35B-A3B-MTP (Unsloth GGUF) | GGUF Q4 + MTP | **123.9** ¹ ² | 309 | 5965 | 6063 | ~3.5 min warm / ~9.2 min prefix-changing | `cell-lmstudio-mtp-qwen35b.json` |
| 6 | LM Studio 0.4.14 (GGUF backend) ² | Qwopus 3.6-35B-A3B-v1 (Jackrong GGUF) | GGUF Q4_K_S | 105.6 ¹ | 292 | 5785 | 5624 | ~3.5 min warm / ~9.6 min prefix-changing | `cell-lmstudio-qwopus35b.json` |
| 7 | llama.cpp b9270 | Qwen 3.6-35B-A3B (UD Q5_K_XL) | GGUF Q5_K_XL | 80.9 ¹ | 3000 | 3000 | n/a | ~8 min | (baseline reference) |
| 8 | llama.cpp b9270 | Qwopus 3.6-27B-v2 (Jackrong GGUF Q4) | GGUF Q4 | 25.3 ¹ | 13000 | 13000 | n/a | ~30 min | (baseline reference) |

¹ **Ressalva do modo thinking**: números capturados com o template de chat padrão
(thinking ON). O throughput efetivo no mundo real em cargas de chamada de
ferramenta é tipicamente 4-12 t/s em finetunes Qwopus/Qwen3.6 quando os tokens de
raciocínio inflam a saída em 6-7×. Para reproduzir esses números de decode, passe
`chat_template_kwargs={"enable_thinking": false}` no payload da requisição.

² **Backend do LM Studio**: as linhas 5-6 usaram um arquivo GGUF, que é roteado
através do backend derivado do llama.cpp do LM Studio (NÃO o runtime MLX
`mlx-engine`). A alegação de MTP na linha 5 reflete a implementação desse backend,
não o decode especulativo do mlx-engine. O mlx-lm lançado não executa a cabeça MTP
como decode especulativo nativo (seu `sanitize()` historicamente descartava os
pesos MTP durante a conversão; o suporte nativo está no PR
[ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990)), portanto
um modelo MTP hipotético em formato MLX também não se beneficiaria no mlx-engine
lançado.

### Observações-chave

- No padrão de agente realista (sistema idêntico + prompts de usuário variando),
  **Rapid-MLX + Qwopus 35B-A3B-v1** entrega 131 ms de TTFT prefix-test mediano vs
  5965 ms para o backend GGUF do LM Studio (**~44× mais rápido**). A vantagem vem
  do mecanismo de snapshot de cache de prefixo do vllm-mlx (veja a Seção 3 para a
  desambiguação no código-fonte).
- Em throughput de decode puro (caminho warm), o **backend GGUF do LM Studio com
  MTP da Unsloth** registra 123.9 t/s vs Rapid-MLX 109.1 t/s (+13.5%). Esse delta
  reflete o decode especulativo do backend derivado do llama.cpp do LM Studio em um
  GGUF carregando a cabeça MTP, não um ganho de Apple-MLX (o mlx-engine lançado não
  executa a cabeça — veja a nota de rodapé 2). No caminho nativo do llama.cpp, o
  MTP é net-positivo no MoE 35B-A3B — veja a Seção 3.
- Todas as configurações da `família Qwen 3.6` (híbrido DeltaNet + atenção
  completa) falham no cache de prefixo entre USUÁRIOS **exceto Rapid-MLX**, que
  mantém um snapshot de estado RNN. No llama.cpp / LM Studio GGUF
  `llama_memory_can_shift=false`; no mlx-lm / oMLX o estado recorrente/SSM não pode
  ser dividido em um limite de token arbitrário. A correção upstream do llama.cpp
  para essa arquitetura não está mergeada
  ([#23121](https://github.com/ggml-org/llama.cpp/pull/23121) fechado;
  `preserve_thinking` não resolve isso,
  [#22615](https://github.com/ggml-org/llama.cpp/issues/22615)).
- **Serialização single-slot confirmada**: o smoke burst test (Seção 2) mostra que
  o Rapid-MLX 0.6.66 serializa chamadas concorrentes em FIFO (p50 ≈ p95 ≈ max em
  burst=5). Para 60-80 chamadas/turno, o tempo total de parede escala linearmente
  com o tamanho do burst nesse motor. Um motor multi-slot (ex: llama.cpp
  `--parallel N`) se comportaria de forma diferente, mas `--parallel N` no híbrido
  Qwen3.6 desabilita o cache de prefixo por slot (limitação arquitetural).

---

## Seção 2 — Burst concorrente (30/60/80 chamadas paralelas)

> Padrão: 30 a 80 chamadas concorrentes `POST /v1/chat/completions` disparadas em
> uma janela de ~200 ms. Simula um loop de agente despachando múltiplas chamadas
> MCP/ferramenta em paralelo. Medido nativamente via `asiai bench --burst-mode`.
>
> 🟡 **Status**: 1 smoke cell medida (Rapid-MLX burst-5). Painel completo pendente.

### Smoke cell (Rapid-MLX 0.6.66 + Qwopus 35B-A3B-v1, burst=5)

| burst N | tempo de parede (s) | latência p50 (ms) | latência p95 (ms) | latência max (ms) | throughput agg (t/s) |
|--------:|--------------:|-----------------:|-----------------:|-----------------:|---------------------:|
| 5 | 2.8 | 2615 | 2792 | 2812 | 88.8 |

**Achado do smoke**: `p50 ≈ p95 ≈ max` indica que as 5 chamadas foram
**serializadas no lado do servidor** (motor single-slot). O Rapid-MLX 0.6.66 **não**
parece suportar escalonamento concorrente de requisições — as chamadas entram em
fila FIFO internamente. A validar na escala de 60/80 chamadas.

### Painel concorrente completo — ainda não medido

Um painel normalizado de 30/60/80 concorrentes não foi executado (as medições aqui
são agentic-mode sequencial, não burst concorrente). Os dois pontos parciais de
dados concorrentes que existem em outro lugar:

- **TurboQuant** (K=`q8_0` V=`turbo2`, Qwen3-4B, M4 Pro): **+9% agregado em
  4-parallel** (68.5 → 74.7 t/s) mesmo que single-stream seja −8% — a compressão de
  KV recompra a margem paralela.
- **oMLX** continuous batching (mlx-lm `BatchGenerator`): **×1.8 agregado em
  burst-8** (12.8 → 22.9 t/s), mas **colapsa em burst-30** (17.3 t/s) assim que um
  27B-dense satura a RAM em swap — 0 crashes.

Um painel burst-mode dedicado entre todos os motores está adiado.

---

## Seção 3 — Caches & otimizações

| # | Par | Reuso de cache entre USUÁRIOS | Snapshot persiste entre reinícios | Suporte a MTP | Taxa de aceitação MTP | Compat. TurboQuant | Tipos nativos de cache KV | Slots paralelos nativos |
|---|--------|---|---|---|---|---|---|---|
| 1 | Rapid-MLX + Qwopus 35B-A3B-v1 | ✅ YES (RNN-state snapshot, see ³ below) | ✅ persistent in `~/.cache/vllm-mlx/` | ❌ released MLX runtime doesn't run the MTP head as speculative decode (mlx-lm PR #990 pending) | n/a | ❌ MLX only | MLX native (no quant flag exposed) | ⚠️ single slot (smoke burst confirms FIFO serialization) |
| 2 | Rapid-MLX + Qwen 35B-A3B-UD | ✅ YES ³ | ✅ persistent | ❌ | n/a | ❌ | MLX native | ⚠️ single slot |
| 3 | LM Studio + Qwen 35B-A3B-MTP | ❌ NO (architectural hybrid limitation) | n/a | ✅ via mlx-engine v1.8.1 | **82.1 %** (on coding task) | ❌ | mlx-engine v1.8.1 (4bit MLX) | configurable via GUI |
| 4 | LM Studio + Qwopus 35B-A3B-v1 | ❌ NO | n/a | ❌ no heads | n/a | ❌ | mlx-engine v1.8.1 (Q4_K_S GGUF) | configurable via GUI |
| 5 | llama.cpp + Qwen 3.6-35B-A3B | ❌ NO (architectural hybrid limitation) | n/a | ✅ `--spec-type draft-mtp` on a `-MTP-GGUF` (a plain GGUF cannot draft). Net-positive on the MoE 35B-A3B — asiai measures **+38%** decode (base) / **+17%** (Qwopus) on M5 Max (see § asiai measurements) | benefit = intra-session decode delta (no acceptance rate logged) | ✅ turbo2/3/4 V cache | `fp16`, `q8_0`, `q5_0`, `turbo2/3/4` | ⚠️ `--parallel N` works mechanically but **disables prefix cache per slot on hybrid arch** (each slot owns its KV, the `--cache-reuse N` flag is already silently disabled here). Use with caution. |
| 6 | mlx-lm | ❌ NO (PRs #923, #188, #192 pending upstream) | n/a | ❌ broken on hybrid arch | n/a | ❌ | MLX native | ❌ (single slot) |
| 7 | oMLX | ❌ NO (tool calling lost post-cache-hit, issue #825) | partial | ❌ | n/a | ❌ | MLX native + tiered SSD cache | ❌ |
| 8 | vLLM-MLX (`waybarrios`, upstream of Rapid-MLX) | ⚠️ trie prefix-cache, no documented hybrid/DeltaNet support (Rapid-MLX rows 1-2 add the RNN-state snapshot on top) | n/a | ⚠️ MTP added in prerelease 0.4.0rc1 | n/a | ❌ | MLX + paged-attention | ✅ |

³ **Cache de prefixo do Rapid-MLX**: o cache armazena slabs de KV de atenção
híbrida + snapshots de estado RNN, indexados por `<repo>--<sys_prompt_hash>` e
persistidos em `~/.cache/vllm-mlx/`. O TTFT prefix-test de ~131 ms observado é um
re-anexo em RAM do slab de KV mais a passagem forward do usuário alterado, não um
recarregamento do disco.

**Cache de contexto longo do oMLX.** O cache KV SSD paginado de 2 níveis do oMLX
transforma um prefill de 55K tokens de ~115 s para ~**3.5 s** de TTFT em um
cache-hit do mesmo prompt (×33; 55,296 / 55,837 tokens em cache). Em prompts
pequenos (~7.5K) não há vantagem (~2-5 s, = mlx-lm) e o decode é ~19 t/s (sem ganho
de velocidade bruta). Isto é reuso do mesmo prompt, não entre USUÁRIOS (o que o oMLX
não faz); a persistência entre reinícios está documentada mas ainda não foi testada
em A/B.

**Compressão KV TurboQuant** (llama.cpp). K=`q8_0` V=`turbo2` corta a RAM de KV em
~**28%** (22.9 → 16.4 GB em um modelo de 4B, M4 Pro) com a validade da chamada de
ferramenta inalterada (10/10), e ganha **+9% agregado em 4-parallel** apesar do −8%
em single-stream. O simétrico K=`turbo3` V=`turbo3` chega a ~−56% de RAM mas degrada
a qualidade (early-stop, repetição) — o assimétrico `q8_0`/`turbo2` é a configuração
utilizável.

---

## Seção 4 — Memória & recursos (Apple Silicon M5 Max 128 GB)

| # | Par | RAM working-set (GB) | Footprint em disco (GB) | Swap Δ idle | Swap Δ under load | SOLO necessário? | Coabitação segura? |
|---|--------|---|---|---|---|---|---|
| 1 | Rapid-MLX + Qwopus 35B-A3B-v1 | ~22 | 19.9 (MLX-4bit) | +0 | **+0 MB** | ⚠️ SOLO (cohabit thrash to 0.4 t/s) | ❌ |
| 2 | Rapid-MLX + Qwen 35B-A3B-UD | ~24 | 20.0 (MLX-4bit) | +0 | **+0 MB** | ⚠️ SOLO | ❌ |
| 3 | LM Studio + Qwen 35B-A3B-MTP | 21.6 | 23.2 (Q4 + MTP heads) | +0 | **+0 MB** | not tested | not tested |
| 4 | LM Studio + Qwopus 35B-A3B-v1 | 18.5 | 19.9 (Q4_K_S) | +0 | **+0 MB** | not tested | not tested |
| 5 | llama.cpp + Qwen 3.6-35B-A3B (reference) | ~16 | ~16 (Q5_K_XL) | +0 | **+0 MB** | ❌ | ✅ with `--parallel 2/3` |

> **"Under load"** = o bench agêntico de 8 fases incluindo um prefill de 50K tokens
> (o estresse de memória *sequencial* mais pesado medido), M5 Max 128 GB, SOLO:
> delta de swap **0 MB / 0 swapouts para todos os motores** — modelo + KV cabem na
> memória livre/inativa com >100 GB de folga. Esta é memória de carga sequencial,
> **não** memória de 60-concorrentes (veja a Seção 2). A RAM working-set é uma
> estimativa; o RSS medido inclui o GGUF mapeado em mmap / páginas MLX fixadas
> (wired), portanto o footprint incremental real é mais baixo (a cabeça MTP
> acrescenta ~+3 GB).

### Observações

- **O Rapid-MLX requer operação SOLO na GPU**: a coabitação com outro motor que
  esteja decodificando ativamente dispara um delta de swap de 5.4 → 14.2 GB e um
  colapso de decode para 0.4 t/s. Não inicie um segundo motor na mesma GPU Apple
  Silicon.
- O footprint em disco do **MTP do LM Studio** é +13 % vs Q4_K_S sem as cabeças
  MTP, devido aos blocos de peso MTP. Custo negligível em relação ao ganho de
  decode de +17 %.
- Na memória unificada do M5 Max 128 GB: toda configuração 35B-A3B testada deixa
  mais de 100 GB de folga após a carga — a RAM não é o fator limitante.
- No M4 Pro 64 GB: `Q5_K_XL` **não** cabe ao lado de modelos auxiliares (swap
  thrash observado em produção). `Q4_K_S` cabe.

---

## Seção 5 — Qualidade dos modelos

> Os números de benchmark público aqui são **reportados pelo fornecedor / por si
> próprios** e agregados por leaderboards (llm-stats), não verificados de forma
> independente. Faça validação cruzada em
> [llm-stats](https://llm-stats.com) · [LiveBench](https://livebench.ai) ·
> [SWE-bench](https://swebench.com) antes de confiar neles. As próprias medições
> diretas do asiai em Apple Silicon estão na próxima seção.
>
> Alegações apenas do autor (Jackrong/Qwopus, autoavaliação da Unsloth) são
> sinalizadas separadamente e mantidas fora das colunas de leaderboard público.
>
> 🔴 **Achado crítico**: o benchmark "Hessling agentic" citado em vários cards de
> modelo comunitários **não é reprodutível de forma independente** — 16 prompts,
> curador único, sem integração a um leaderboard neutro. Todos os três
> consultores recomendam tratá-lo apenas como um smoke test.

### Modelos base open-weight Qwen 3.6

> Números de leaderboard público (llm-stats), reportados por si próprios. O
> 27B-dense supera o MoE 35B-A3B no SWE-bench — consistente com o próprio achado de
> dev-quality do asiai abaixo (o MoE base é o que atinge o bug de objeto vazio na
> chamada de ferramenta). As cabeças MTP são uma funcionalidade de velocidade de
> decode e não alteram os escores de qualidade de um modelo.

| Modelo | Arquitetura | SWE-bench Verified | GPQA Diamond | MMLU-Pro | Terminal-Bench 2.0 | BFCL |
|-------|--------------|-------------------:|-------------:|---------:|-------------------:|------|
| Qwen 3.6-35B-A3B-Instruct | MoE 35B / 3B active | 73.4% | 86.0% | 85.2% | 24.6% | absent from board |
| Qwen 3.6-27B-Dense Instruct | Dense 27B hybrid | 77.2% | 87.8% | 86.2% | 59.3% (vendor) | absent from board |

> O Terminal-Bench **2.0** é muito mais difícil que o antigo Terminal-Bench v1 (os
> cards comunitários citam ~51.5% para o 35B-A3B no v1); os 24.6% aqui são a geração
> 2.0.

### Família Qwopus 3.6 — reportado apenas pelo autor, **não verificado de forma independente**

Os finetunes Qwopus 3.6 publicados por Jackrong no HuggingFace alegam ganhos
substanciais sobre o Qwen base. Até maio de 2026 essas alegações **não foram
reproduzidas de forma independente** em leaderboards neutros. Trate como
experimental até que estejam disponíveis re-execuções de BFCL / SWE-bench por
terceiros.

| Modelo (alegações do autor) | MMLU-Pro | SWE-bench Verified | Hessling agentic (16 prompts) |
|-----------------------|---------:|-------------------:|------------------------------:|
| Qwopus 3.6-35B-A3B-v1 (Jackrong) | claimed 88+ | claimed 75+ | claimed 88.6 ⚠ non-reproducible |
| Qwopus 3.6-27B-v2 (Jackrong) | claimed 87.43 | claimed 75.25 | n/a |

⚠ O benchmark "Hessling agentic" citado nos cards de modelo da Jackrong parece ser
uma avaliação específica de curador com 16 prompts, sem integração a um leaderboard
neutro. Todas as três consultorias questionadas (Grok-4, GPT-5, Gemini Advanced)
recomendam tratá-lo apenas como smoke test.

### Âncoras de fronteira (meados de 2026)

> Todos os números são **reportados pelo fornecedor / por si próprios**, agregados
> pelo llm-stats — nenhum é verificado de forma independente lá. O **Terminal-Bench
> 2.0** é a exceção (o time do tbench re-executa as submissões; as linhas são
> escores de pico agente×modelo). Os GPQA são números "Diamond" do fornecedor e o
> conjunto está quase saturado — trate como aproximado.

| Modelo | SWE-bench Verified | GPQA Diamond | MMLU-Pro | Terminal-Bench 2.0 | Fonte |
|-------|-------------------:|-------------:|---------:|-------------------:|--------|
| Claude Opus 4.8 | 88.6% | 93.6% | n/a | — (no TB submission) | llm-stats / Anthropic |
| Claude Opus 4.7 | 87.6% | 94.2% | n/a | **90.2%** | llm-stats / tbench |
| Claude Sonnet 4.6 | 79.6% | 89.9% | n/a | 53.4% | llm-stats / tbench |
| GPT-5.5 | n/a\* (SWE-Pro 58.6%) | 93.6% | n/a | 84.7% | OpenAI / tbench |
| GPT-5 (base) | 74.9% | 85.7% | n/a | 49.6% | llm-stats / tbench |
| Gemini 3.1 Pro | 80.6% | ~94.4% | n/a | 80.2% | llm-stats / tbench |
| DeepSeek-V4-Pro-Max | 80.6% | 90.1% | 87.5% | n/a | vendor (DeepSeek) |
| Llama-3.3-70B-Instruct | n/a | n/a | 68.9% | n/a | Meta (baseline) |

\* O GPT-5.5 não tem um escore público de SWE-bench *Verified* (a OpenAI reporta
SWE-bench Pro Public 58.6%); o número "88.7% SWE-bench" em circulação não está em
nenhuma fonte primária. Nota: **o Qwen 3.6 não tem um 235B-A22B** — a família aberta
é o 27B-dense e o 35B-A3B (abaixo); o 235B-A22B é da geração Qwen3 anterior.

### Baselines open-weights da mesma classe

| Modelo | MMLU-Pro | SWE-bench Verified | Notas |
|-------|---------:|-------------------:|-------|
| Llama-3.3-70B-Instruct | ~75-80 | ~40-50 | Older but well-characterized baseline |
| Mistral Codestral 25.05 / Devstral | high (coding-specialized) | medium-high | Strong editor-style completion fidelity, weaker on reasoning |
| GLM-4.6-Coder (Zhipu) | vendor claims very high | disputed | Significant skepticism around evaluation methodology (consensus) |

### Benchmarks de qualidade descontinuados para esta decisão

- **HumanEval / HumanEval+** — saturados em 2026, todos os modelos de fronteira
  acima de 90 %, sem sinal restante.
- **GSM8K** — saturado, sem sinal para agentes de código.
- **MMLU (original)** — substituído pelo MMLU-Pro.
- **"Hessling agentic" de 16 prompts reportado pelo autor** — não reprodutível,
  tratar apenas como smoke test.

### Questões de qualidade em aberto (lacunas de pesquisa)

1. **Benchmark de qualidade-por-GB-de-RAM**: não existe um padrão. Fórmula proxy
   proposta:
   `AgentScorePerGB = (0.5·SWE + 0.3·BFCL + 0.2·TerminalBench) / RAM_resident`.
2. **Estabilidade de horizonte longo (60+ chamadas de ferramenta)**: os benchmarks
   existentes mais próximos são τ-bench, PencilPuzzleBench (>1000 turnos),
   MultiAgentBench, TRAIL. Nenhum deles mede especificamente "correção de schema e
   coerência estratégica ao longo de 60-80 chamadas de ferramenta sequenciais" —
   essa lacuna de benchmark é reconhecida por todos os três consultores.
3. **Avaliação consciente da conversão (MLX-4bit vs GGUF Q4_K_M vs Q5_K_XL)**: não
   há leaderboard padronizado. Os relatos da comunidade divergem — alguns alegam que
   o MLX-4bit preserva a estabilidade da chamada de ferramenta pior que o GGUF
   Q5_K_M, outros dizem o oposto. **Conselho prático**: execute sua própria carga de
   produção contra cada quant antes de se comprometer.
4. **Validação de qualidade da família Qwopus 3.6**: precisa de re-execuções de
   BFCL + SWE-bench por terceiros. As alegações do autor não devem guiar decisões de
   produção.

---

## medições diretas do asiai — Apple Silicon, meados de 2026

> O que os leaderboards públicos acima não mostram: medições que o asiai executou
> diretamente em Apple Silicon (M5 Max 128 GB em High Power Mode, M4 Pro 64 GB),
> llama.cpp b9430, determinístico (temp 0), na família pública Qwen 3.6 e no finetune
> destilado de Opus, **Qwopus**. Ressalva: o throughput absoluto entre sessões no
> laptop M5 é ±15% (térmico/carga); apenas os **deltas intra-sessão ±MTP
> back-to-back** são apertados, e os absolutos M5↔M4 não são comparáveis (quants
> diferentes).

### Dev-quality / chamada de ferramenta (`asiai bench --code`)

- O **Qwen 3.6-35B-A3B base (MoE)** colapsa `edit_file.edits` em um objeto vazio no
  turno de contexto profundo — **3/3 execuções, tanto em Q4_K_S quanto em Q5_K_XL**,
  mesmo template de chat. Chamada de ferramenta limpa **87.5%**, turnos de edição
  limpos **66.7%**. É o comportamento de geração de chamada de ferramenta do MoE
  base, não o quant e não o template.
- O **27B dense** (Q5_K_XL) e o **Qwopus-35B-A3B** (Q4_K_S) ambos pontuam **100%
  limpo / 0 bugs** — o Qwopus alcança a confiabilidade de chamada de ferramenta do
  dense-27B na taxa de decode ~4× do MoE.
- Sob uma suíte de estresse de chamada de ferramenta mais difícil, o Qwopus
  permanece **100% / 0** enquanto o 27B dense cai para **88.9% / 3 bugs** (a mesma
  falha de objeto vazio). Mas em uma armadilha de avaliador de expressões
  (precedência de `**` vs menos unário) o **27B dense está correto e o Qwopus está
  errado** — eles divergem. (A taxa de recuperação é sensível aos pesos e ruidosa —
  não é uma manchete.)

### Ablação de thinking (`asiai bench --thinking-ablation`, Qwopus-35B-A3B, 3 execuções determinísticas)

| Configuração | Chamada de ferramenta limpa | Nota |
|--------|----------------:|------|
| `enable_thinking=off` | **100%** | the only fully-clean config |
| `enable_thinking=on` + `preserve_thinking=on` | 77.8% | 2/9 turns dirty |
| `enable_thinking=on` + `preserve_thinking=off` | 11.1% | turns 2-8 → HTTP 500 (context corruption); avoid |

### Throughput MTP (`--spec-type draft-mtp`, warm decode, intra-sessão ±MTP)

| Modelo / hardware | MTP off | MTP on | Δ |
|------------------|--------:|-------:|--:|
| 35B-A3B base · M5 Max | 85.5 t/s | **118.4 t/s** | **+38%** |
| Qwopus 35B-A3B · M5 Max | 105.7 t/s | 123.3 t/s | +17% |
| 27B-dense · M5 Max | 23.8 t/s | 28.0 t/s | +18% |
| Qwopus 27B · M5 Max | 25.9 t/s | 26.7 t/s | +3% |
| 35B-A3B MoE · M4 Pro | 36.3 t/s | 44.6 t/s | +23% |
| 27B-dense · M4 Pro | 10.4 t/s | 9.7 t/s | **−6%** |

O ganho de MTP escala como **(MoE > dense) × (M5 > M4)** — fortemente positivo no
MoE, marginal-a-negativo no caminho dense lento (o overhead do draft não é
amortizado). O MTP do lado MLX (mlx_vlm) está desqualificado: ele quebra o contexto
longo (saída vazia, 75% válido). Manchete: o MoE 35B-A3B + MTP no llama.cpp sustenta
**~118 t/s** de decode no M5 Max (~44 t/s no M4 Pro), ~4× o 27B-dense, a ~1.5
tok/s/W, TTFT ~62 ms, 100% de validade de saída. O head de MTP do finetune Qwopus
também é mais fraco que o da base (Qwopus 27B +3% / 35B +17%, vs base 27B-dense +18%
/ 35B-A3B +38%) — o finetuning erode o draft head.

### Seguimento de instruções (`asiai bench --instruct`, research-brief)

O trade-off do thinking tem dentes em entregáveis multi-etapa: com
`enable_thinking=false`, o Qwopus-35B faz o trabalho de ferramenta mas entrega o
brief multi-seção solicitado **0%** das vezes (ele para na etapa secundária); com o
thinking ativado, o modelo base o entrega **100%** (5/5 seções). Isto puxa na
direção oposta do resultado de chamada de ferramenta acima — thinking-off é o mais
limpo para chamadas de ferramenta atômicas mas suprime os entregáveis escritos — e é
por isso que o asiai define o thinking **por dimensão de tarefa**, não como um único
interruptor global.

---

## Seção 6 — Operacional

> 📌 Snapshot de capacidades (meados de 2026). As versões dos motores mudam
> semanalmente em Apple Silicon — estas cells são de um ponto no tempo, não uma
> garantia fixada por versão.

| # | Motor | Licença | Stream OAI-compat | `/v1/models` | `/health` | `/metrics` (Prometheus) | Chamada de ferramenta | Auto-DL HF | Cache de prefixo persistido | Atividade do mantenedor |
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

## Seção 7 — Ponderação dos benchmarks de qualidade para cargas de codificação agêntica

> Esta é a **ponderação padrão do asiai** para uma carga de classe orquestrador
> (60-80 chamadas de ferramenta sequenciais por turno, saída validada por schema,
> prompts de sistema de contexto longo). Ela é informada por três consultorias de
> LLMs de fronteira (Grok-4, GPT-5, Gemini Advanced) questionadas em maio de 2026,
> mas **não é um consenso da comunidade** — trate como um ponto de partida, não como
> autoritativa. Sobrescreva via uma futura flag `--weights` (planejada).

| Benchmark | O que mede | Por que importa aqui | Peso de consenso |
|-----------|------------------|---------------------|-----------------:|
| **SWE-bench Verified** | Real GitHub repo navigation + patch + test repair | Best proxy for code-editing fidelity inside an agent loop | **35 %** |
| **BFCL v3** (Berkeley Function Calling Leaderboard) | Multi-turn function-call accuracy, argument fidelity, schema adherence | Direct predictor of orchestrator stability across many tool calls | **25 %** |
| **TerminalBench 2.0 / MCP-Atlas** | CLI and MCP task execution autonomy | "Does the agent survive 40+ actions without derailing" | **20 %** |
| **LiveBench Coding** | Contamination-resistant coding tasks (refreshed monthly) | Catches train-test leakage that inflates HumanEval-class scores | **10 %** |
| **Custom long-horizon stability eval** | 60-80 sequential tool calls with cumulative context growth, malformed JSON recovery | The benchmark that does not exist yet in public form — see Section 8 | **10 %** |

### Benchmarks conscientemente removidos da ponderação

- MMLU-Pro, GPQA Diamond, HumanEval+ — úteis como sinal geral de capacidade, mas
  **fracamente correlacionados** com a confiabilidade do loop de agente segundo a
  evidência de 2026. Confirmações de laboratórios de fronteira indicam que escores
  de raciocínio single-shot já não predizem o sucesso de agentes autônomos com
  granularidade suficiente.
- Agregados reportados pelo autor sem re-execuções por terceiros (Jackrong Hessling,
  autoavaliação da Unsloth, alegações do fornecedor GLM-4.6-Coder).

---

## Seção 8 — Proposta de benchmark custom de "resistência" (oportunidade de pesquisa)

Todos os três consultores convergem para a mesma lacuna: **o benchmark que melhor
caracterizaria uma carga de orquestrador ainda não existe publicamente**. Construir
um é a única forma de obter o sinal que falta.

### Escopo proposto

- **80 chamadas de ferramenta sequenciais** por trajetória
- **Validação de schema a cada turno** (JSON estrito / saída estruturada)
- **Crescimento cumulativo de contexto** (10K → 50K tokens ao longo da trajetória)
- **Testes de interrupção / recuperação** (cancelamento + retomada no meio da
  trajetória)
- **Recuperação de XML/JSON malformado** (o agente se autocorrige ?)
- **Persistência de edição de repositório** (as edições feitas no turno N ainda se
  mantêm no turno 60 ?)

Isto está no roadmap do asiai (um modo de resistência de horizonte longo, depois do
burst-mode). Se construído, seria o primeiro benchmark público neste nicho
específico.

---

## Metodologia

- **Hardware**: MacBook Pro M5 Max 128 GB de memória unificada, macOS 26.4.1.
- **Carga de trabalho**: classe orquestrador — prompt de sistema ~7 KB, prompt de
  usuário ~150-200 tokens, 60-80 chamadas por turno.
- **Fases medidas** (chamada única, agentic-mode v1.6.0):
  - `cold`: primeira chamada após início limpo
  - `warm`: mesmo prompt exato do cold (cache warm)
  - `prefix-test-1/2/3`: sistema idêntico, usuário mudando — mede o reuso de cache
    entre USUÁRIOS
  - `cold-prefix`: sistema idêntico, após reinício — mede o cache persistente
- **Veredito de reuso de cache de prefixo**: `YES` se `median(prefix-test) / cold < 0.2`,
  senão `NO`.
- **Medidas anti-viés**: modo SOLO (sem motores coabitando), baseline térmico em
  idle, fase de aquecimento de mmap.
- **Quality gates** (auto-rastreados pelo asiai bench):
  - `early_stop`: pelo menos 2 execuções com `<0.5×` da mediana de conclusão
  - `memory_pressure`: delta de swap `>500 MB` OU delta de swapouts `>1000`
  - `duplicate_processes`: múltiplos processos de motor detectados durante o bench

O protocolo completo é a instrumentação `asiai bench --agentic-mode` /
`--burst-mode` (power/thermal, footprint do motor, ocupação de KV, fases de cache de
prefixo) — veja a documentação do CLI do asiai.

---

## Questões em aberto

1. **MTP no vLLM-MLX/Rapid-MLX — respondida (em parte).** O vLLM-MLX adicionou MTP
   no prerelease **0.4.0rc1** (2026-05-21); o combo teórico "MLX + Qwopus 35B-A3B
   equipado com MTP + snapshot entre USUÁRIOS" poderia vencer tanto em decode quanto
   em TTFT assim que o fork Rapid-MLX acompanhar o 0.4.x. Acompanhe quando o
   Rapid-MLX incorporar o caminho MTP.
2. **MTP no runtime MLX — estado atual.** O mlx-lm lançado não executa a cabeça MTP
   como decode especulativo nativo (`sanitize()` descarta os pesos MTP durante a
   conversão; o suporte nativo está no PR não-mergeado
   [ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990)). O
   `mlx-engine` do LM Studio embrulha o mlx-lm, então herda isso — o ganho de decode
   de +13.5% na linha 5 da Seção 1 vem do **backend derivado do llama.cpp** do LM
   Studio (o arquivo é GGUF), não do decode especulativo do mlx-engine.
3. **Comportamento de burst no Rapid-MLX/vllm-mlx na escala de 60-80 chamadas**: o
   smoke test confirma FIFO single-slot em burst=5. Painel completo pendente (Seção
   2). A questão upstream relevante é se o vllm-mlx planeja escalonamento
   continuous-batching / multi-slot para modelos de arquitetura híbrida.
4. **`llama_memory_can_shift=false` no híbrido Qwen 3.6** — ainda quebrado upstream.
   O [#18497](https://github.com/ggml-org/llama.cpp/issues/18497) está fechado
   (documenta o reprocessamento completo); o
   [#22384](https://github.com/ggml-org/llama.cpp/issues/22384) é uma *issue*
   (fechada-como-concluída), **não** uma correção mergeada; o PR de correção real
   [#23121](https://github.com/ggml-org/llama.cpp/pull/23121) foi **fechado sem
   merge** (os patches vivem apenas em forks). A solução alternativa de "apenas
   habilite `preserve_thinking`" é refutada pela issue aberta
   [#22615](https://github.com/ggml-org/llama.cpp/issues/22615) (speedup de 0.67× =
   o cache permanece inerte). As camadas híbridas DeltaNet não expõem um estado de
   cache deslocável por construção.
5. **Reprodução independente da qualidade do Qwopus 3.6**: precisa de re-execuções
   de BFCL / SWE-bench por terceiros. Os números publicados pelo autor não devem
   guiar decisões de produção até serem verificados de forma cruzada.
6. **Linhagem vllm-mlx vs Rapid-MLX — respondida.** O Rapid-MLX é um **hard fork**
   comunitário de `waybarrios/vllm-mlx`, não um wrapper fino: ele vendora o motor
   in-tree (o pacote ainda é chamado `vllm_mlx`), não depende via pip do pacote
   upstream, e divergiu substancialmente (Rapid-MLX 0.6.74 vs upstream 0.3.0). O
   nome de pacote compartilhado `vllm_mlx` e o diretório `~/.cache/vllm-mlx/` são uma
   fonte frequente de confusão de atribuição (veja a Seção 3, ressalva 2).

---

*Este painel é um documento vivo. Contribuições, correções e cells de bench
adicionais são bem-vindas via
[github.com/druide67/asiai](https://github.com/druide67/asiai/issues).*
