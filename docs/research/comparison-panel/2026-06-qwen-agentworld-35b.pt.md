# Qwen-AgentWorld-35B em Apple Silicon: deve ganhar um lugar no teu agent loop?

> Um relatório de avaliação para quem corre modelos locais e constrói agentes autónomos.
> **O que é**: um *modelo de mundo linguístico* — prevê o que um terminal
> devolveria após uma ação, não age. **O que corre**: MLX, ou llama.cpp/Metal
> com uma substituição de metadados de uma linha (um GGUF simples não carrega sem ela); não há
> build oficial MLX. **O único diferenciador que medimos**:
> mantém o papel de simulador ao longo de sequências multi-passo onde um generalista deriva.
> **O seu custo**: sobre-raciocínio pesado — limitável. Os números são de N pequeno e indicativos,
> cada um etiquetado com o seu tamanho de amostra; os valores de benchmark do autor são assinalados como afirmações.
>
> Medido com `asiai` num M5 Max, MLX 4-bit, um motor de cada vez, 2026-06.
> Correções bem-vindas via [github.com/druide67/asiai](https://github.com/druide67/asiai/issues).

!!! tip "Quando usar / quando não"
    **Usa-o como** simulador de ambiente para rollouts de agentes baratos, um mock para
    saída de ferramenta/terminal, ou um verificador de trajetória em vez de um LLM-as-judge
    (*o caso de uso do verificador não é testado aqui — ver §6*). Também aguenta como
    um simples generalista 35B se o instruíres como assistente.

    **Não o uses como** o teu assistente do dia a dia: os autores não fornecem nenhum caminho de uso
    chat/código e ele carrega um imposto de sobre-raciocínio acentuado (limitável, ver §5). E não
    esperes pela variante 397B que "bate o GPT-5.4" — **não é descarregável**
    (a HF devolve 401 apesar do anúncio Apache-2.0).

## 1. Funcionamento e reprodução (lê isto primeiro)

Se não corre na tua máquina, nada mais importa. Veredicto, sem rodeios:

- **Dois caminhos funcionam hoje; nenhum é chave-na-mão.** Não há **build oficial MLX** —
  usámos uma conversão MLX da comunidade, e foi nesse caminho que medimos. O GGUF
  **também carrega** em llama.cpp / Metal, mas não de imediato: tal como está, falha com
  `missing tensor 'blk.40.attn_norm.weight'` (build 9780, reconfirmado 2026-06-25).
  A causa é um off-by-one do conversor, **não pesos em falta** — o GGUF declara
  `block_count=41` (uma camada MTP extra no índice 40) embora forneça apenas as 40 camadas reais
  0–39, por isso o llama.cpp pede uma camada que nunca foi suposta existir. Substitui
  os metadados ao carregar e ele carrega *e gera*:
  `--override-kv qwen35moe.block_count=int:40 --override-kv qwen35moe.nextn_predict_layers=int:0`.
  Ollama e LM Studio embrulham o llama.cpp mas não expõem de forma fiável `--override-kv`, por isso
  trata esses dois como não testados. A implantação oficial de servidor é vLLM / SGLang / Transformers.
- **Um quant que carrega não é prova de que emite uma cadeia-de-raciocínio longa correta** —
  valida a geração, não apenas o carregamento.

Configuração de reprodução:

| | Repo (Hugging Face) | Tamanho |
|---|---|---|
| AgentWorld (especialista) | `jedisct1/Qwen-AgentWorld-35B-A3B-oQ4-MLX` | ~20 GB |
| Qwen3.6 (baseline generalista) | `mlx-community/Qwen3.6-35B-A3B-4bit` | ~19 GB |

`mlx-lm` 0.31.3 · M5 Max 128 GB · sampling temp 0.6 / top-p 0.95 / top-k 20 · um modelo carregado de cada vez.

!!! warning "O orçamento de tokens é uma variável de configuração de primeira classe"
    O AgentWorld emite um rasto de raciocínio muito longo. Com `max_tokens=4096` a sua saída
    é **truncada antes da resposta** e pontua como uma falha falsa. Precisa de
    **8192–12288** tokens de raciocínio para terminar em alguns casos triviais. Quem
    re-correr com um orçamento baixo obterá números de pior aspeto para o AgentWorld que
    são artefactos do harness, não erros do modelo.

**Encaixe de RAM / contexto**: pesos ~20 GB; pico ~27 GB a 64K de contexto num Mac de 128 GB;
a cache KV cresce apenas ~5 GB de 4K a 64K (uma propriedade da arquitetura híbrida
partilhada). Um Mac de 64 GB corre-o confortavelmente com contexto reduzido; 36–48 GB é
apertado mas viável a 4K–32K.

## 2. O que é, e como os autores o posicionam

Um **modelo de mundo linguístico**: dado um estado e uma ação (um comando tipado), ele
prevê a próxima observação (o que o terminal devolve) através de uma longa
cadeia-de-raciocínio. Sete domínios digitais (MCP, Search, Terminal, SWE, Android, Web,
OS). É treinado para *ser o ambiente*, não para agir nele.

Os autores fornecem-no **como um modelo de mundo, não um assistente**: os system prompts são
prompts de simulação, e não há nenhum caminho de uso chat/código documentado. Por isso uma
preocupação justa é que, usado como assistente, ele simularia uma saída de consola em vez de
responder. O nosso teste matiza isto (§4): com um prompt de assistente padrão ele programa
e raciocina ao nível do generalista. **O comportamento é decidido pelo prompt,
não por uma capacidade perdida.**

!!! note "Sobre a palavra *modelo de mundo*"
    A objeção mais comum da comunidade é terminológica: isto é um
    LLM autorregressivo a fazer previsão de próximo-estado-de-texto, não um modelo de mundo
    não-autorregressivo / baseado em energia no sentido de LeCun. Vale a pena saber antes que o nome estabeleça
    uma expectativa que o modelo não afirma cumprir.

Especificações verificadas (model card da HF, em claro):

| | |
|---|---|
| Parâmetros | **34,66 B** total · ~3 B ativos (MoE) |
| Arquitetura | `qwen3_5_moe`, híbrida **Attention + Gated-DeltaNet** |
| Especialistas | 256 (8 roteados + 1 partilhado) |
| Contexto | até **256K** tokens |
| Licença | **Apache-2.0** (~65 GB em BF16) |

## 3. O diferenciador: fidelidade de papel multi-passo

Este é o único resultado novo e defensável — e exatamente aquilo que o próprio
benchmark dos autores nunca mede (é apenas single-step). O teste: encadear comandos que
constroem estado (criar uma diretoria, entrar nela, escrever um ficheiro, lê-lo de volta) e, em cada passo,
fazer o modelo prever a saída exata do terminal.

Enquadra-o como uma propriedade de **fiabilidade** — disciplina de formato/papel — **não** uma
vantagem de compreensão. O Qwen3.6 percebe perfeitamente o terminal (acompanha o
diretório de trabalho, conta as linhas certas); a diferença é que ele por vezes
*sai do papel*.

| Teste | AgentWorld | Qwen3.6 | Nota |
|---|---|---|---|
| Saída plausível (`ls`, `git`, `ps`) — N=3 | 9/9 | 9/9 | paridade |
| Sequência A — 6 passos, ancorada (4 runs) | 0 quebras-de-papel / 24 passos | intermitente | manutenção-de-papel |
| Sequência B — 8 passos, ancorada (3 runs) | 0 quebras-de-papel / 24 passos | intermitente | manutenção-de-papel |
| Ciclo fechado (alimenta-se a si próprio) — N=2 | 6/6 ×2 | intermitente | manutenção-de-papel |

**Leitura honesta**: o AgentWorld quebrou o papel em **0 de 48 passos observados** ao longo de duas
sequências e quatro runs. O Qwen3.6 quebra o papel intermitentemente — os seus runs ancorados
oscilaram 0/6 → 6/6 entre repetições (N=2), por isso isto é **indicativo, não uma taxa**. Quando
falha, ele **regurgita o JSON da ação** em vez de simular a saída:

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

A resposta correta está muitas vezes presente na saída do Qwen3.6 — é uma falha de
**formato/papel**, não um mal-entendido. Para um loop onde cada passo tem de ser legível por máquina
pelo seguinte, uma única quebra-de-papel envenena a cadeia, que é o que o AgentWorld evita.

!!! note "Ressalvas de medição (divulgadas)"
    A pontuação byte-exata na linha de eco do comando é estrita, e os nossos fixtures Sequência-D vs
    Sequência-E foram inconsistentes quanto a se uma observação de `cd` inclui
    o eco — pelo que a métrica de fidelidade-de-papel tem uma falha conhecida. A direção é
    robusta ao longo de quatro ficheiros; o gap preciso não é.

## 4. Capacidade generalista: a base não está degradada

A pergunta do dono (terá o fine-tune do modelo de mundo partido o LLM base?) recebe uma
secção sóbria, não o destaque. Resposta curta: não — N=3, indicativo.

| Tarefa | AgentWorld | Qwen3.6 | |
|---|---|---|---|
| Raciocínio (5 puzzles verificáveis incl. a armadilha do 'r' em strawberry) | 15/15 | 15/15 | paridade |
| Geração de código (4 funções, **executadas contra testes unitários**) | 12/12 | 12/12 | paridade |

Corrido com um prompt de assistente (não o prompt de simulador), o AgentWorld escreve código correto
e raciocina corretamente, ao nível do generalista. Não "descarrila" — é
um generalista competente que por acaso sobre-raciocina.

## 5. O custo: um imposto de sobre-raciocínio — e o remédio

Promove isto de nota de rodapé a porta de adoção, porque para um verificador por passo é
o número decisivo — mas tem uma solução.

Medido em casos de terminal determinísticos (N=2 por caso):

| Modo | AgentWorld | Qwen3.6 |
|---|---|---|
| Raciocínio **ligado** (modo simulador por defeito) | mediana **1140 tok/pred**, máx 2558 · ~14 s · 8/8 exato | 504 tok · ~4,5 s · 8/8 |
| Raciocínio **desligado** (`enable_thinking=false`) | **45 tok/pred · ~0,5 s · 8/8 exato** | 45 tok · ~0,4 s · 8/8 |

O AgentWorld emite ~2,3× mais tokens do que o generalista e num trivial `cd ; pwd` o
seu raciocínio passou **dos 8192 tokens em 2 de 3 runs**. A resposta final está correta —
isto é um imposto de latência/computação por passo, não um defeito de correção.

!!! tip "O remédio: limita-o"
    Desligar o raciocínio para o papel de simulador corta tokens ~25× e latência
    ~28× **sem perda de fidelidade byte-exata** em casos determinísticos (ainda 8/8).
    Para um verificador por passo ou mock, corre-o com `enable_thinking=false` e um
    teto de `max_tokens`. **Ressalva**: isto é testado apenas em casos determinísticos —
    em saídas onde o raciocínio genuinamente ajuda (estado ambíguo, conteúdo
    complexo), raciocínio-desligado pode custar fidelidade. Não testado aqui.

## 6. Desempenho (single-run, indicativo ★)

Mesma família, mesma arquitetura, por isso os perfis são próximos. Lê-os como tendências.

| Medida | AgentWorld | Qwen3.6 | Leitura |
|---|---|---|---|
| Tempo até ao primeiro token ★ | ~360 ms | ~510 ms | AW à frente |
| Débito de decode ★ | ~110 t/s | ~117 t/s | ~7% mais lento |
| Decode a 64K de contexto | ~132 t/s | ~160 t/s | ~73% retido |
| Memória 4K → 64K | +5 GB | +5 GB | arq. híbrida, não específica do AW |
| Cache de contexto (reuso de prefixo de 13K tokens) | ~×21 | ~×23 | **propriedade do MLX**, não do modelo |

O gap de decode de ~7% deve-se muito provavelmente à receita 4-bit (o AgentWorld protege a sua
projeção de linear-attention em 6-bit; o Qwen3.6 protege o gate MoE em 8-bit), em
comprimentos de saída desiguais — um confound, não uma desvantagem do modelo. O prompt caching é uma
funcionalidade do mlx-lm idêntica em ambos os modelos; o seu ganho de ~20× escala com o comprimento do
prefixo em cache, não é uma propriedade do AgentWorld.

**Não testado mas de alto valor (o caso de uso nº 2 da comunidade)**: usar a previsão de
próximo-estado como um *verificador de trajetória* — quando o ambiente real diverge da
previsão, isso sinaliza um agente fora-do-caminho. Não medimos o seu comportamento de falsos-positivos /
falsos-negativos. Questão em aberto.

## 7. O que os autores afirmam

!!! quote "Benchmark do autor — uma afirmação, não uma medição"
    No seu próprio benchmark (AgentWorldBench), o AgentWorld-35B pontua **56.4**, ao nível
    do Claude Sonnet 4.6 (56.0). Os ganhos que atribuem à especialização, por
    ablação contra a **base Qwen3.5** (auto-reportado, não um head-to-head vs
    Qwen3.6): **+21.9** uso-de-ferramentas (MCP), **+18.1** engenharia de software, **+10.2**
    terminal. Tese: *a especialização em modelo de mundo bate a melhoria geracional* —
    o generalista Qwen3.6 pontua **abaixo** da base (42.9 vs 47.7) em fidelidade
    de simulação, porque está afinado para *agir*, não para *prever estado*.

    Estes valores vêm de um benchmark interno, de fonte única, avaliado por um
    juiz LLM, num modelo com menos de 48 h na publicação — **sem replicação
    de terceiros**. O topo da tabela situa-se dentro de ~2 pontos sob um único juiz, por isso
    a ordenação perto do topo está dentro do ruído; a margem de +0,46 (ruído) do 397B "bate o GPT-5.4",
    e essa variante é não-pública (HF 401) apesar do anúncio Apache-2.0.

O nosso resultado multi-passo (§3) é sobre uma *métrica diferente, não replicada* face ao seu
bench single-step; aponta na mesma direção (Qwen3.6 mais fraco em simulação), mas
isso é convergência de tese, não confirmação.

## 8. Como eu o ligaria

- **Prompt**: usa o system prompt oficial de **simulação** de terminal para o correr como um
  ambiente; usa um prompt de assistente simples apenas se quiseres saída generalista. Os
  dois modos são trabalhos diferentes.
- **Controlo de custo**: `enable_thinking=false` + um teto de `max_tokens` para o
  papel de simulador (§5). Com raciocínio ligado, orça ~1000–2500 tokens/passo.
- **Ciclo fechado**: realimenta as próprias previsões do modelo, mas ancora no ambiente
  real quando o tiveres; espera que a estritude de formato importe (a linha de eco).
- **Footprint**: ~20 GB de pesos, ~27 GB de pico a 64K.
- **A questão construir-vs-adotar**: "nunca sai do papel" é intrínseco ao
  treino do modelo de mundo, ou poderia um generalista + decodificação restrita por gramática fechar
  a maior parte do gap? Não testámos a alternativa generalista-restrito — pesa-a
  antes de adotar um modelo dedicado.

## Limites deste bench

- **Amostras pequenas** (N=1–5, sem desvio-padrão). Cada gap numérico é uma tendência,
  não um resultado estatístico.
- **Um domínio** para os dois resultados-chave (sequências de terminal). A manutenção-de-papel "num loop"
  fica por confirmar noutros lugares.
- **Quantização não isolada**: as duas receitas 4-bit diferem ligeiramente; o gap de decode
  está provavelmente ligado a isso mas não está provado aqui.
- **Ainda não testado**: cenários aleatórios/complexos, um segundo domínio, um three-way contra
  a base Qwen3.5 para isolar o efeito exato do fine-tune, e o caso de uso do verificador-de-trajetória.
- **Apenas o 35B é público.** A variante 397B não é descarregável.

---

*Fontes: arXiv 2606.24597 · [Qwen-AgentWorld-35B-A3B](https://huggingface.co/Qwen/Qwen-AgentWorld-35B-A3B) (Apache-2.0). Resultados revistos internamente em cruzado quanto a viés antes da publicação. ★ = medição única, indicativa.*
