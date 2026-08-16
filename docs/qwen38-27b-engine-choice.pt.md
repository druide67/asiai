---
title: "Qual motor para Qwen3.8-27B no Apple Silicon"
description: "Oito motores de inferência medidos em um único M5 Max com o mesmo modelo. Dois motores que leem o mesmo arquivo de pesos diferem em 50%, e o flag que rende 20% vem desligado por padrão em quase todos eles."
type: article
date: 2026-08-16
updated: 2026-08-16
---

<!-- STALE: rewritten 2026-08-16 after adversarial audit; retranslate from the English before publishing -->

# Qual motor para Qwen3.8-27B no Apple Silicon

A questão do modelo está resolvida: o Qwen3.8-27B roda em um laptop e sustenta 262.144
tokens de contexto. A questão do motor não está, e custa mais do que se imagina.

Medimos oito motores em um único M5 Max. Os dois resultados mais interessantes não têm
nada a ver com velocidade — são dois motores lendo o *mesmo arquivo* e divergindo em
50%, e um flag que ninguém liga.

## Condições, antes dos números

M5 Max 128 GB, na tomada, High Power Mode, um motor residente por vez. Raciocínio
desativado em todos os motores para que possam ser comparados entre si. Throttling
térmico a 50% em 1-2 minutos em todas as células — **estes são pisos, não máximos**.
Validade da saída de 100% em todas as linhas. Prompts de 7.530 tokens (fases curtas) e
55.839 (longas), saída limitada a 400 e 200 tokens.

**Não afirmamos que estas são as velocidades que você vai obter.** Afirmamos que são as
diferenças entre motores sob um mesmo protocolo.

## A tabela

| Motor | Pesos | n | A quente | Aos 56k | Primeiro token | Memória | Ctx declarado |
|---|---|---|---|---|---|---|---|
| **MTPLX** Bare-Speed | MTPLX 4-bit g64 | 3 | **56,0** | **46,5** | 101 ms | 22,0 GB | padrão do motor |
| **MTPLX** Optimized-Speed | MTPLX 4-bit g32 | **5** | **44,4** | 37,5 | 99 ms | 27,0 GB | padrão do motor |
| **mlx-vlm** + drafter MTP | MLX 4-bit ⁽¹⁾ | 3 | **43,3** | 28,9 | **9.982 ms** | 15,5 GB | padrão do motor |
| **MTPLX** Optimized-Quality | MTPLX 8-bit g64 | 3 | 40,8 | 30,3 | 118 ms | 32,9 GB | padrão do motor |
| Ollama 0.32.13 | GGUF (não declarado) | 3 | 32,8 | 21,7 | 240 ms | 30,3 GB | 65.536 |
| llama.cpp b10434 + MTP | GGUF Q5_K_XL ⁽²⁾ | 3 | 31,8 | 22,7 | **125 ms** | 36,8 GB | 131.072 |
| rapid-mlx 0.12.11 | MLX 4-bit ⁽¹⁾ | 3 | 30,2 | 24,7 | **33.195 ms** | 15,0 GB | padrão do motor |
| oMLX 0.6.0-dev | oQ4e-mtp (de terceiros) | 3 | 29,8 | 24,6 | 1.968 ms | 16,7 GB | padrão do motor |
| mlx-lm 0.31.3 | MLX 4-bit ⁽¹⁾ | 3 | 28,8 | 24,0 | 432 ms | **14,6 GB** | padrão do motor |
| LM Studio 0.4.21 **+ MTP** | GGUF Q5_K_XL ⁽²⁾ | 3 | 27,8 | 23,4 | 419 ms | 36,3 GB | 65.536 |
| LM Studio 0.4.21 padrão | GGUF Q5_K_XL ⁽²⁾ | 3 | 23,1 | 18,7 | 359 ms | 35,2 GB | 65.536 |

⁽¹⁾ e ⁽²⁾ marcam linhas que compartilham um **arquivo de pesos idêntico byte a byte**.
Cada linha é uma célula, uma exportação — nenhum valor misturado entre execuções.

⚠️ **A memória não é comparável entre famílias.** llama.cpp e Ollama fazem mmap do seu
GGUF: o resident set é respaldado por arquivo e descartável (llama.cpp: 36,8 GB de RSS,
mas 19,8 GB de footprint físico). Os motores MLX alocam. Leia a coluna dentro de uma
família, não entre famílias.

⚠️ **O contexto declarado difere.** Três motores receberam uma janela explícita; os
demais rodaram com seu padrão. Só isso já proíbe ordenar globalmente a coluna de memória.

## Dois motores, um arquivo, 50% de diferença ⁽¹⁾

mlx-vlm, mlx-lm e rapid-mlx serviram todos `lmstudio-community/Qwen3.8-27B-MLX-4bit`,
snapshot `6067b15c` — o mesmo arquivo em disco.

| Motor | A quente | Primeiro token | Memória |
|---|---|---|---|
| mlx-vlm + drafter MTP | **43,3** | 9.982 ms | 15,5 GB |
| rapid-mlx | 30,2 | 33.195 ms | 15,0 GB |
| mlx-lm | 28,8 | **432 ms** | 14,6 GB |

**+50% do mlx-lm para o mlx-vlm, sem nada alterado além do servidor.** É a comparação
mais limpa da campanha: nenhuma diferença de quantização para discutir.

E ela se inverte de imediato: a vantagem de 50% do mlx-vlm custa um **tempo até o
primeiro token 23× pior**, porque ele não tem cache de prefixo nenhum. Para uma geração
one-shot, ele vence. Para um agente, é inutilizável — e a razão está na próxima seção.

## O flag que rende 20%, e por que ele vem desligado ⁽²⁾

O Qwen3.8 traz uma **cabeça de predição multi-token dentro dos pesos**. O modelo propõe
vários tokens à frente, e o motor os verifica em um único forward pass. Motores que
implementam a regra de aceitação por razão de probabilidades preservam exatamente a
distribuição de saída; nós mesmos não verificamos essa propriedade, e você não deveria
tomá-la como fé a partir de um benchmark — leia a implementação do seu motor.

Quase todos os motores a entregam **desligada**.

| Motor | Flag | Ligado por padrão? |
|---|---|---|
| vmlx | `--native-mtp-depth` | **sim** |
| MTPLX | `--mtp --depth 3` | sim |
| vllm-mlx | `--enable-mtp` | não |
| llama.cpp | `--spec-type draft-mtp` | não |
| LM Studio | `--speculative-draft-mtp` | não |
| mlx-vlm | `--draft-kind mtp` + repositório de drafter separado | não |
| oMLX | não entrou em ação no Qwen3.8 nas nossas execuções | — |
| Ollama · mlx-lm · rapid-mlx | sem suporte | — |

Medimos o custo de não saber disso no mesmo arquivo de pesos, mesmo contexto de 65.536,
tudo igual exceto dois flags: **o LM Studio vai de 23,1 → 27,8 tok/s, +20%.** Nenhuma
GUI expõe isso.

Efeito de segunda ordem, e que importa mais: **comparar dois motores em seus padrões
compara dois regimes diferentes.** O vmlx faz drafting, o llama.cpp não.

## O primeiro token varia 350×. O prefill não explica isso.

De 99 ms a 33.195 ms ao longo da tabela. O que decide é a **granularidade do cache de
prefixo** — quanto de um prompt repetido sobrevive entre turnos. Medido na mesma fase (o
turno a quente, de onde se tira a latência do primeiro token):

| Motor | Reaproveita | Prefill refeito a cada turno | Primeiro token |
|---|---|---|---|
| llama.cpp | 7.526 / 7.530 — **nível de token** | 4 tokens | 125 ms |
| oMLX | 6.144 / 7.530 — **blocos de 1024 tokens** | 1.386 tokens | 1.944 ms |
| mlx-vlm | 0 / 7.530 | 7.530 tokens | 9.982 ms |

6.144 é seis vezes 1.024. O oMLX reaproveita blocos inteiros e refaz o prefill de tudo
que não preenche um bloco — 1.386 tokens, a cada turno, para sempre. É essa a diferença
inteira entre 125 ms e 2 segundos.

⚠️ **Não compare taxas de reaproveitamento agregadas por sessão entre motores.** Elas
têm tetos diferentes conforme a fração do prompt de teste que é cacheável, e compará-las
produz paradoxos que desaparecem quando se compara a mesma fase. Cometemos esse erro em
um rascunho anterior desta página.

**Não** estamos publicando uma coluna de throughput de prefill. A nossa veio de uma única
requisição a frio, não repetida, que para motores de carregamento preguiçoso inclui ler
20 GB do disco — o LM Studio mediu 216 tok/s nessa requisição e 938 na seguinte. Teria
sido um número fabricado.

## Tokens por segundo não é uma velocidade

Entre quantizações do mesmo modelo, tok/s mede em parte o tamanho das saídas, não a
rapidez com que elas chegam:

| Build | tok/s | chars/s |
|---|---|---|
| Bare-Speed | 56,0 | 200,8 |
| Optimized-Speed | 44,4 | **203,1** |
| Optimized-Quality | 40,8 | 165,7 |

O Bare-Speed lidera por 26% em tokens por segundo e fica **atrás** em caracteres por
segundo. Mesmo tokenizador nos três — o que muda é o que cada quantização escolheu
escrever. Publique a definição junto com o número.

## O que recomendamos

**Para um agente autônomo local: MTPLX com `Qwen3.8-27B-MTPLX-Optimized-Speed`, MTP com
profundidade 3.** Rápido, 99 ms até o primeiro token, reaproveitamento de prefixo em
nível de token, 27 GB.

Não Bare-Speed, embora lidere no papel. Os três builds diferem na divergência em relação
ao bf16, publicada pelo autor das quantizações: **0,00105** para Optimized-Quality,
**0,0220** para Optimized-Speed, **0,0376** para Bare-Speed. Medição dele, não nossa, não
reproduzida — mas é o único número de fidelidade que alguém tem, e Bare-Speed fica a uma
ordem de grandeza de Quality.

Optimized-Quality também não: custa **8,3 GB a mais** por uma vantagem que ninguém
demonstrou numa tarefa.

**Rode-o com o raciocínio ativo.** A Qwen recomenda o nível de esforço `xhigh` para trabalho
agêntico e afirma que, em tarefas agênticas multiturno, um esforço menor *«pode levar a
análise insuficiente, mais falhas e novas tentativas repetidas, o que pode aumentar a
latência total»*. A MTPLX 2.7.1 lista à parte o raciocínio desativado como problema
conhecido no Qwen3.8. Note: `high` não existe neste modelo — a Qwen expõe apenas `low`,
`medium` e `xhigh`, e `xhigh` é o padrão.

## O que não conseguimos medir

**vmlx e vllm-mlx foram tentados e estão ausentes.** Ambos suportam MTP nativo — o vmlx
o traz ligado por padrão — de modo que a ausência deles é uma lacuna real nesta
comparação, não um erro de arredondamento. O vllm-mlx morreu na inicialização por um erro
de aspas na linha de comando; o vmlx ainda estava rodando quando isto foi publicado.

**O raciocínio ficou desativado em todos os casos, para tornar os motores comparáveis.** É
uma decisão de medição e não de implantação — veja a recomendação acima. Não temos nenhum
número a oferecer sobre o que o raciocínio faz a estes motores, e não vamos extrapolar um.

**Ressalvas de versão.** As linhas do MTPLX rodaram na **2.6.0**, antes de o motor passar
a trazer uma família de modelos `qwen3_8` — ele serviu o Qwen3.8 sob os padrões do
Qwen3.6, incluindo um contrato de amostragem diferente. Isso não afeta o throughput; mas
afeta tudo o que diz respeito ao comportamento. A linha do oMLX veio de uma build de
desenvolvimento temporária cuja string de versão a exportação não capturou, então essa
linha não é reproduzível tal como publicada. E nossa exportação do mlx-vlm se
autoidentifica como `mlxlm 0.31.3_2` — só o log de inicialização prova que
`mlx_vlm.server` era o servidor.

**A ordenação do primeiro token entre as três builds do MTPLX está dentro do seu próprio
ruído** — coeficientes de variação de 0,33 a 0,66 nessa métrica. 99, 101 e 118 ms não são
separáveis. A coluna de throughput é bem mais estável (CV 0,01-0,04).

**A dispersão teste-reteste em reexecuções idênticas do mesmo comando chegou a 7,5%**
(37,97 / 40,82 / 39,35 tok/s em três execuções do Optimized-Quality), e a memória variou
5 GB entre reexecuções. Trate qualquer diferença abaixo de 8% como nada.

**O tuning não foi simétrico.** O llama.cpp recebeu flags explícitos de cache
(`--cache-reuse 256 --slot-prompt-similarity 0.5`, flash attention, 131k de KV) que os
motores MLX não receberam. O MTPLX rodou com `--profile turbo`, não com seu padrão. Esta
é uma comparação de configurações que colocaríamos em produção, não dos padrões de
fábrica.

## Reproduzir isto

Cada número vem de um card certificado produzido pelo [asiai](https://asiai.dev), por um
caminho scriptado único, com gates de solidão, provas de identidade do modelo servido e
amostragem térmica. Exportações brutas disponíveis.

Se você levar só uma coisa: **verifique se o seu motor tem predição multi-token, e se ela
está ligada.**
