# Qwen-AgentWorld-35B on Apple Silicon: should it get a slot in your agent loop?

> An evaluation brief for people who run local models and build autonomous agents.
> **What it is**: a *language world-model* — it predicts what a terminal would
> output after an action, it does not act. **What runs**: MLX, or llama.cpp/Metal
> with a one-line metadata override (a plain GGUF won't load without it); no
> official MLX build. **Its one differentiator we measured**:
> it holds the simulator role across multi-step sequences where a generalist drifts.
> **Its cost**: heavy over-reasoning — cappable. Numbers are small-N and directional,
> each tagged with its sample size; author benchmark figures are flagged as claims.
>
> Measured with `asiai` on an M5 Max, MLX 4-bit, one engine at a time, 2026-06.
> Corrections welcome via [github.com/druide67/asiai](https://github.com/druide67/asiai/issues).

!!! tip "When to use it / when not"
    **Use it as** an environment simulator for cheap agent rollouts, a mock for
    tool/terminal output, or a trajectory verifier in place of an LLM-as-judge
    (*the verifier use case is untested here — see §6*). It also holds up as a
    plain 35B generalist if you prompt it as an assistant.

    **Don't use it as** your daily assistant: the authors ship no chat/code usage
    path and it carries a steep over-reasoning tax (cappable, see §5). And don't
    wait for the 397B variant that "beats GPT-5.4" — it is **not downloadable**
    (HF returns 401 despite the Apache-2.0 announcement).

## 1. Runnability & reproduction (read this first)

If it doesn't run on your machine, nothing else matters. Verdict, blunt:

- **Two paths work today; neither is turnkey.** There is **no official MLX build** —
  we used a community MLX conversion, and that is the path we measured on. The GGUF
  **also loads** on llama.cpp / Metal, but not out of the box: as-is it fails with
  `missing tensor 'blk.40.attn_norm.weight'` (build 9780, re-confirmed 2026-06-25).
  The cause is a converter off-by-one, **not missing weights** — the GGUF declares
  `block_count=41` (an extra MTP layer at index 40) while shipping only the 40 real
  layers 0–39, so llama.cpp asks for a layer that was never meant to exist. Override
  the metadata at load and it loads *and generates*:
  `--override-kv qwen35moe.block_count=int:40 --override-kv qwen35moe.nextn_predict_layers=int:0`.
  Ollama and LM Studio wrap llama.cpp but don't reliably expose `--override-kv`, so
  treat those two as untested. Official server deployment is vLLM / SGLang / Transformers.
- **A quant that loads is not proof it emits a correct long chain-of-thought** —
  validate generation, not just load.

Reproduction setup:

| | Repo (Hugging Face) | Size |
|---|---|---|
| AgentWorld (specialist) | `jedisct1/Qwen-AgentWorld-35B-A3B-oQ4-MLX` | ~20 GB |
| Qwen3.6 (generalist baseline) | `mlx-community/Qwen3.6-35B-A3B-4bit` | ~19 GB |

`mlx-lm` 0.31.3 · M5 Max 128 GB · sampling temp 0.6 / top-p 0.95 / top-k 20 · one model loaded at a time.

!!! warning "Token budget is a first-class setup variable"
    AgentWorld emits a very long reasoning trace. At `max_tokens=4096` its output
    is **truncated before the answer** and scores as a false failure. It needs
    **8192–12288** reasoning tokens to finish on some trivial cases. Anyone
    re-running at a low budget will get worse-looking numbers for AgentWorld that
    are harness artifacts, not model errors.

**RAM / context fit**: weights ~20 GB; peak ~27 GB at 64K context on a 128 GB Mac;
the KV cache grows only ~5 GB from 4K to 64K (a property of the shared hybrid
architecture). A 64 GB Mac runs it comfortably at reduced context; 36–48 GB is
tight but workable at 4K–32K.

## 2. What it is, and how the authors position it

A **language world-model**: given a state and an action (a typed command), it
predicts the next observation (what the terminal returns) via a long
chain-of-thought. Seven digital domains (MCP, Search, Terminal, SWE, Android, Web,
OS). It is trained to *be the environment*, not to act in it.

The authors ship it **as a world-model, not an assistant**: the system prompts are
simulation prompts, and there is no documented chat/code usage path. So a fair
worry is that, used as an assistant, it would simulate a console output instead of
answering. Our test nuances this (§4): with a standard assistant prompt it codes
and reasons on par with the generalist. **The behavior is decided by the prompt,
not by a lost capability.**

!!! note "On the word *world-model*"
    The most common community objection is terminological: this is an
    autoregressive LLM doing next-text-state prediction, not a non-autoregressive /
    energy-based world-model in the LeCun sense. Worth knowing before the name sets
    an expectation the model doesn't claim to meet.

Verified specs (HF model card, in-the-clear):

| | |
|---|---|
| Parameters | **34.66 B** total · ~3 B active (MoE) |
| Architecture | `qwen3_5_moe`, hybrid **Attention + Gated-DeltaNet** |
| Experts | 256 (8 routed + 1 shared) |
| Context | up to **256K** tokens |
| License | **Apache-2.0** (~65 GB in BF16) |

## 3. The differentiator: multi-step role fidelity

This is the one new, defensible result — and exactly what the authors' own
benchmark never measures (it is single-step only). The test: chain commands that
build state (create a dir, enter it, write a file, read it back) and, at each step,
have the model predict the exact terminal output.

Frame it as a **reliability** property — format/role discipline — **not** a
comprehension advantage. Qwen3.6 understands the terminal perfectly well (it tracks
the working directory, counts the right lines); the difference is that it sometimes
*leaves the role*.

| Test | AgentWorld | Qwen3.6 | Note |
|---|---|---|---|
| Plausible output (`ls`, `git`, `ps`) — N=3 | 9/9 | 9/9 | parity |
| Sequence A — 6 steps, anchored (4 runs) | 0 role-breaks / 24 steps | intermittent | role-hold |
| Sequence B — 8 steps, anchored (3 runs) | 0 role-breaks / 24 steps | intermittent | role-hold |
| Closed-loop (feeds itself) — N=2 | 6/6 ×2 | intermittent | role-hold |

**Honest reading**: AgentWorld broke role in **0 of 48 observed steps** across two
sequences and four runs. Qwen3.6 breaks role intermittently — its anchored runs
swung 0/6 → 6/6 across repeats (N=2), so this is **directional, not a rate**. When
it fails, it **regurgitates the action JSON** instead of simulating the output:

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

The correct answer is often present in Qwen3.6's output — it is a **format/role**
failure, not a misunderstanding. For a loop where each step must be machine-readable
by the next, a single role-break poisons the chain, which is what AgentWorld avoids.

!!! note "Measurement caveats (disclosed)"
    Byte-exact scoring on the command-echo line is strict, and our Sequence-D vs
    Sequence-E fixtures were inconsistent about whether a `cd` observation includes
    the echo — so the role-fidelity metric has a known wrinkle. The direction is
    robust across four files; the precise gap is not.

## 4. Generalist capability: the base is not degraded

The owner's question (did the world-model fine-tune break the base LLM?) gets one
sober section, not the headline. Short answer: no — N=3, directional.

| Task | AgentWorld | Qwen3.6 | |
|---|---|---|---|
| Reasoning (5 verifiable puzzles incl. the strawberry-'r' trap) | 15/15 | 15/15 | parity |
| Code generation (4 functions, **executed against unit tests**) | 12/12 | 12/12 | parity |

Run with an assistant prompt (not the simulator prompt), AgentWorld writes correct
code and reasons correctly, at parity with the generalist. It does not "derail" — it
is a competent generalist that happens to over-reason.

## 5. The cost: an over-reasoning tax — and the remedy

Promote this from a footnote to an adoption gate, because for a per-step verifier it
is the deciding number — but it has a fix.

Measured on deterministic terminal cases (N=2 per case):

| Mode | AgentWorld | Qwen3.6 |
|---|---|---|
| Reasoning **on** (default simulator mode) | median **1140 tok/pred**, max 2558 · ~14 s · 8/8 exact | 504 tok · ~4.5 s · 8/8 |
| Reasoning **off** (`enable_thinking=false`) | **45 tok/pred · ~0.5 s · 8/8 exact** | 45 tok · ~0.4 s · 8/8 |

AgentWorld emits ~2.3× more tokens than the generalist and on a trivial `cd ; pwd`
its reasoning ran **past 8192 tokens in 2 of 3 runs**. The final answer is correct —
this is a latency/compute tax per step, not a correctness defect.

!!! tip "The remedy: cap it"
    Turning reasoning **off** for the simulator role cuts tokens ~25× and latency
    ~28× **with no loss of byte-exact fidelity** on deterministic cases (still 8/8).
    For a per-step verifier or mock, run it with `enable_thinking=false` and a
    `max_tokens` ceiling. **Caveat**: this is tested on deterministic cases only —
    on outputs where the reasoning genuinely helps (ambiguous state, complex
    content), reasoning-off may cost fidelity. Untested here.

## 6. Performance (single-run, indicative ★)

Same family, same architecture, so the profiles are close. Read these as trends.

| Measure | AgentWorld | Qwen3.6 | Reading |
|---|---|---|---|
| Time to first token ★ | ~360 ms | ~510 ms | AW ahead |
| Decode throughput ★ | ~110 t/s | ~117 t/s | ~7% slower |
| Decode at 64K context | ~132 t/s | ~160 t/s | ~73% retained |
| Memory 4K → 64K | +5 GB | +5 GB | hybrid arch, not AW-specific |
| Context cache (13K-token prefix reuse) | ~×21 | ~×23 | **MLX property**, not the model |

The ~7% decode gap is most likely the 4-bit recipe (AgentWorld protects its
linear-attention projection in 6-bit; Qwen3.6 protects the MoE gate in 8-bit), on
unequal output lengths — a confound, not a model disadvantage. Prompt caching is an
mlx-lm feature identical on both models; its ~20× gain scales with the cached prefix
length, it is not a property of AgentWorld.

**Untested but high-value (the community's #2 use case)**: using next-state
prediction as a *trajectory verifier* — when the real environment diverges from the
prediction, that signals an off-path agent. We did not measure its false-positive /
false-negative behavior. Open question.

## 7. What the authors claim

!!! quote "Author benchmark — a claim, not a measurement"
    On their own benchmark (AgentWorldBench), AgentWorld-35B scores **56.4**, level
    with Claude Sonnet 4.6 (56.0). The gains they attribute to specialization, by
    ablation against the **base Qwen3.5** (self-reported, not a head-to-head vs
    Qwen3.6): **+21.9** tool-use (MCP), **+18.1** software engineering, **+10.2**
    terminal. Thesis: *world-model specialization beats generational improvement* —
    the generalist Qwen3.6 scores **below** the base (42.9 vs 47.7) on simulation
    fidelity, because it is tuned to *act*, not to *predict state*.

    These figures come from a single-source, in-house benchmark graded by an LLM
    judge, on a model less than 48 h old at publication — **no third-party
    replication**. The top of their table sits within ~2 points under one judge, so
    near-the-top ordering is within noise; the 397B "beats GPT-5.4" margin is +0.46
    (noise), and that variant is non-public (HF 401) despite the Apache-2.0
    announcement.

Our multi-step result (§3) is on a *different, non-replicated metric* than their
single-step bench; it points the same direction (Qwen3.6 weaker at simulation), but
that is thesis convergence, not confirmation.

## 8. How I'd wire it in

- **Prompt**: use the official terminal **simulation** system prompt to run it as an
  environment; use a plain assistant prompt only if you want generalist output. The
  two modes are different jobs.
- **Cost control**: `enable_thinking=false` + a `max_tokens` ceiling for the
  simulator role (§5). With reasoning on, budget ~1000–2500 tokens/step.
- **Closed loop**: feed back the model's own predictions, but anchor on the real
  environment when you have it; expect format strictness to matter (the echo line).
- **Footprint**: ~20 GB weights, ~27 GB peak at 64K.
- **The build-vs-adopt question**: is "never leaves role" intrinsic to the
  world-model training, or could a generalist + grammar-constrained decoding close
  most of the gap? We did not test the constrained-generalist alternative — weigh it
  before adopting a dedicated model.

## Limits of this bench

- **Small samples** (N=1–5, no standard deviation). Every numeric gap is a trend,
  not a statistical result.
- **One domain** for the two key results (terminal sequences). Role-hold "in a loop"
  remains to be confirmed elsewhere.
- **Quantization not isolated**: the two 4-bit recipes differ slightly; the decode
  gap is likely tied to that but it is not proven here.
- **Not yet tested**: random/complex scenarios, a second domain, a three-way against
  the base Qwen3.5 to isolate the fine-tune's exact effect, and the trajectory-verifier
  use case.
- **Only the 35B is public.** The 397B variant is not downloadable.

---

*Sources: arXiv 2606.24597 · [Qwen-AgentWorld-35B-A3B](https://huggingface.co/Qwen/Qwen-AgentWorld-35B-A3B) (Apache-2.0). Results internally cross-reviewed for bias before publication. ★ = single, indicative measurement.*
