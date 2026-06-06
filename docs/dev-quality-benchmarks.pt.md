---
description: Resultados de benchmark de qualidade de dev e de retenção multilíngue no Apple Silicon — confiabilidade de tool call (o bug de truncamento de argumento JSON / objeto vazio), recuperação de erro agêntica, disciplina de thinking e retenção de língua. Determinístico, sem necessidade de juiz LLM para o sinal central. Uma página de resultados viva.
---

# Benchmarks de Qualidade de Dev e de Língua

Throughput não é qualidade. Um modelo pode fazer decode rápido e ainda assim ser inutilizável para
coding agêntico — ele trunca argumentos de tool call, entra em loop em erros ou seu
finetune quebrou silenciosamente outra língua. Esta página reporta resultados reais de
`asiai bench --code` e `asiai bench --language`: sinais **determinísticos**
(sem necessidade de juiz LLM para o núcleo) que medem se um modelo realmente
funciona, não quão rápido ele emite tokens.

> **Documento vivo.** Os números são atualizados à medida que revisões de modelo, engines e
> templates mudam. Cada bloco nomeia o arquivo exato do modelo e a configuração de serving, de modo que um
> resultado seja reproduzível.

## O que é medido

`asiai bench --code` (determinístico, sem juiz):

- **tool-call** — uma sessão agêntica de edição de arquivo de 8 turnos sob contexto
  acumulado. Pontua a emissão de tool call, a validade JSON, a não-truncação, a ferramenta
  correta, a conformidade com o schema e o **bug de objeto vazio**: o truncamento do template
  `|items` que colapsa um array `edit_file.edits` para `{}` / `[]`.
- **tool-call-stress** — o mesmo, mais difícil: contexto mais profundo, arrays de edição com 8–10
  elementos, pressão de escaping de JSON (quebras de linha, aspas, contrabarras, unicode). Usado
  para distinguir os modelos que gabaritam a baseline.
- **recovery** — injeta um erro de ferramenta sintético no meio da sessão; pontua uma ação
  corretiva vs. um loop travado (reemitir a chamada que falha).
- **thinking** — disciplina de thinking-mode: nenhum vazamento de `<think>` no conteúdo,
  saída não-vazia com um budget curto e `enable_thinking=false` respeitado.
- **coding** / **coding-hard** *(juiz opcional)* — tarefas de coding multi-turno
  avaliadas de 1 a 5 por um juiz LLM em `--judge-url` (qualquer endpoint compatível com OpenAI).

`asiai bench --instruct` (seguimento de instruções determinístico):

- **verifiable** — prompts de turno único no estilo IFEval com instruções verificáveis
  programaticamente (contagens de palavras/frases/seções, keywords, somente JSON, caixa, sem
  vírgulas, frase final, título em `<<>>`, língua…). Reportado como acurácia strict/loose
  no nível de prompt e no nível de instrução — o formato do leaderboard público.
  Reimplementação asiai-nativa do paradigma IFEval (Zhou et al. 2023); nenhum
  código ou dado do IFEval é incorporado.
- **research-brief** — uma tarefa agêntica: pesquisar vários tópicos via ferramentas, então
  escrever um briefing de várias seções, e então uma ação de ferramenta secundária (salvar) **por último**.
  O modelo produz o briefing primário, ou ele faz o trabalho de ferramenta e retorna apenas
  a confirmação do passo secundário? Um modelo pode gabaritar a confiabilidade de tool call e ainda
  pular o entregável principal — pontuado deterministicamente verificando que as seções exigidas
  aparecem após os turnos de ferramenta. **order-control** inverte a ordem
  (secundário primeiro) como diagnóstico.
- **loop-search** — uma armadilha de busca ambígua: um warmup profundo sobre tópicos
  claros, depois um fato-alvo que o `web_search` nunca consegue confirmar
  (reformulações semânticas da consulta colapsam em uma única resposta). Pontua se o
  modelo aceita a ambiguidade e entrega (sóbrio) ou reemite consultas equivalentes até
  um teto de ausência-de-progresso o deter (perfeccionista), além de um sinal de
  colapso de tokens de saída. Dois modos (`short`, resultado sub-1KB / `unconfirmable`,
  fato plausível-mas-ausente). Este é o modo de falha que o IFEval de turno único e o
  research-brief não revelam.

`asiai bench --language <code>` (determinístico, 8 línguas):

- **adherence** — o modelo permanece na língua-alvo? (razão de palavras funcionais
  alvo vs. inglês para escritas latinas; razão de caracteres da escrita-alvo para
  ja/ko/zh).
- **diacritics** — prompts-armadilha cuja resposta correta deve conter tokens
  acentuados específicos (`café`, `préféré`); uma resposta com ASCII removido falha.

Todos os três modos são somente JSON e comparam entre modelos fazendo o diff da saída.

## Exemplo trabalhado — Qwen3.6-35B-A3B vs Qwopus3.6-35B-A3B vs Qwen3.6-27B denso

Um finetune (`Qwopus3.6`, um finetune destilado de Opus do MoE `Qwen3.6-35B-A3B`)
vs. sua base, vs. um modelo denso com metade do tamanho. Mesmo llama.cpp, **mesmo chat
template mantido constante** (só o arquivo do modelo trocado), thinking desativado, 3
repetições. Apple Silicon M5 Max, High Power Mode.

### Confiabilidade de tool call

| model · quant | tool-call clean | empty-object bug | under stress |
|---|--:|--:|--:|
| Qwen3.6-35B-A3B base · Q4 / Q5 | 87.5% | **3** | 87.5% · **3 bugs** |
| **Qwopus3.6-35B-A3B · Q4** | **100%** | **0** | **100% · 0** |
| Qwen3.6-27B dense · Q5 | 100% | 0 | 88.9% · **3 bugs** |

- **O MoE 35B base tem um defeito residual de tool call que o fix de template não
  fecha completamente.** Ele colapsa `edit_file.edits` no bug de objeto vazio 3/3 em um
  turno de contexto profundo — em **ambos os quants Q4 e Q5** (portanto é um comportamento de
  geração, não de quantização). O template da comunidade `froggeric`, que corrige
  o bug `|items` em chamadas simples, não salva o MoE base no fundo do contexto.
- **O finetune destilado de Opus o repara completamente** — 0 bugs, 100% clean —
  e em um quant *mais baixo* (Q4 vs Q5), o que torna a vitória mais forte.
- **Sob stress, o finetune é o agente mais robusto que o denso 27B**:
  o 27B racha (3 bugs de objeto vazio na suíte mais difícil) enquanto o finetune
  fica em 0. Eles empatam na baseline; a suíte de stress os separa.

### Correção de código (tarefas difíceis avaliadas por LLM)

Em duas tarefas de coding multi-turno mais complicadas eles **se dividem**: em um rate
limiter de janela deslizante ambos tratam os edge cases de fronteira/eviction; em um avaliador de
expressões o **denso 27B acerta a precedência de operadores** (`-2**2 == -4`, menos unário como
um operador apropriado) enquanto o **finetune não** (ele incorpora o menos unário no
número → `4.0`). Robustez de tool call e correção algorítmica são eixos
*diferentes* — meça ambos.

### Retenção de língua

Rodando `--language fr` no finetune e em sua base, mesmo quant:

| model | adherence | diacritic traps | ASCII-stripped |
|---|--:|--:|--:|
| Qwen3.6-35B-A3B base | 100% | 4/4 | 0 |
| **Qwopus3.6-35B-A3B** | 100% | 4/4 | 0 |

**Zero regressão de francês.** O finetune orientado a coding manteve o francês do modelo base
intacto (adherence, diacríticos, sem remoção de ASCII) — um finetune específico de tarefa
*não* custou outra língua, o que vale a pena verificar em vez de
presumir.

### Loop de pesquisa perfeccionista (loop-search)

O `research-brief` satura em 100% para todos os modelos aqui, então ele não
discrimina o *loop perfeccionista* que quebra agentes reais. O cenário `loop-search`
sim. Ao longo de uma varredura de configs dense 27B e MoE 35B-A3B (M5, llama.cpp
b9430, thinking on/off, ambos os modos de ambiguidade):

- O **MoE 35B-A3B entra em loop** — ele reemite buscas semanticamente equivalentes
  sobre um fato não-confirmável até que uma guardrail de ausência-de-progresso o
  detenha, em vez de aceitar a incerteza e entregar. Ele faz isso em **ambos Q4 e Q8**
  (arquitetural, não um artefato de quant), tanto para a base quanto para o finetune
  destilado de Opus.
- O **27B denso nunca entra em loop** (Q4 / Q5 / Q8): ele aceita o resultado ambíguo e
  escreve o briefing.

Para um harness agêntico como o Hermes Agent da NousResearch, este é o sinal decisivo:
o modelo denso resistente a loop é o main mais seguro mesmo quando existe um MoE mais
rápido — o throughput não compra nada se o agente despencar em uma única etapa ambígua.
É também a lição inversa do resultado de tool call acima (onde o finetune MoE era o
agente *mais* robusto): **a aptidão é por modo-de-falha, então meça vários.**

## Como ler isto

- **Veredito primeiro, não velocidade primeiro.** Estes são sinais de correção/confiabilidade.
  Para throughput, ver os [Benchmarks em Modo Agêntico](agentic-benchmarks.md).
- **Núcleo determinístico, juiz opcional.** tool-call / recovery / thinking /
  adherence / diacritics não precisam de juiz LLM — são reproduzíveis. As
  notas de `coding`/`fluency` são avaliadas por LLM (subjetivas, opcionais).
- **Compare dentro de uma mudança controlada.** O exemplo mantém o template constante
  e varia apenas o modelo, de modo que uma diferença seja do modelo, não do harness.

## Metodologia e ressalvas

- `asiai bench --code` / `--language`, thinking desativado
  (`chat_template_kwargs.enable_thinking=false`), um engine residente por vez.
- **A quant difere ao longo do exemplo** (o finetune Q4 vs os modelos Qwen Q5):
  o bug de objeto vazio em destaque é dirigido por template/geração e foi confirmado
  em **ambos** os quants para a base, então o quant não explica a diferença — e o
  finetune vence a partir do quant mais baixo.
- **O juiz de qualidade de código não é estritamente cego** aqui (um modelo de fronteira leu
  os transcripts pelo mérito); os números determinísticos de tool-call/stress são
  objetivos.
- **Recovery é sensível aos pesos**, não um sinal cross-model limpo — o destaque
  é a confiabilidade de tool-call/objeto-vazio, que é estável ao longo das repetições.

Veja também: [Benchmarks em Modo Agêntico](agentic-benchmarks.md) ·
[Metodologia de benchmark](methodology.md) · [Especificação de métricas](metrics-spec.md).
