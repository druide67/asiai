# Panel d'inférence agentique sur Apple Silicon

> Panel de benchmark comparatif entre moteurs d'inférence (llama.cpp, mlx-lm,
> LM Studio, Rapid-MLX, vLLM-MLX, oMLX, vMLX, Ollama) exécutant les modèles de la
> famille Qwen 3.6 sur Apple Silicon série M, mesurés avec
> `asiai bench --agentic-mode` et `asiai bench --burst-mode`.
>
> **Charge cible** : classe agent-orchestrateur — ~60-80 appels d'outils par tour,
> prompt système identique d'environ 7 Ko, message utilisateur changeant à chaque
> appel. C'est le pire cas pour un caching de préfixe naïf : une vraie réutilisation
> de cache cross-USER est nécessaire, pas seulement un cache-on-the-same-prompt.
>
> **Lecture des chiffres de débit** : les taux de decode de la Section 1 utilisent
> le template de chat par défaut de Qwen3 (thinking ON), donc ils incluent les
> tokens de raisonnement — le débit agentique effectif sur un modèle thinking est
> plus faible. Le thinking est un arbitrage par tâche (caveat 1), pas un on/off
> global.
>
> Publié le 2026-06 · contributions et corrections bienvenues via
> [github.com/druide67/asiai](https://github.com/druide67/asiai/issues).

## ⚠️ Caveats connus avant d'aller plus loin

1. **Le mode thinking est un arbitrage par tâche.** Avec le template par défaut de
   Qwen3 (thinking ON), Qwen 3.6 / Qwopus émettent ~6-7× plus de tokens, donc les
   chiffres de decode de la Section 1 **incluent les tokens de raisonnement** et le
   débit agentique effectif est plus faible. Le thinking ON est **requis** pour les
   livrables rédigés multi-sections (un modèle thinking-OFF saute le livrable) mais
   **coûte** la propreté atomique des appels d'outils (asiai mesure ~100 % d'appels
   d'outils propres avec thinking OFF vs ~77,8 % avec thinking ON + `preserve_thinking`
   ON, déterministe d'un run à l'autre ; `enable_thinking=on` + `preserve_thinking=off`
   est inutilisable — un HTTP 500 déterministe dès que le raisonnement s'accumule dans
   le contexte). Régler le thinking **par dimension de tâche**, pas comme un flag
   global unique.
2. **Rapid-MLX et vLLM-MLX partagent un moteur.** Rapid-MLX est un fork communautaire
   de `waybarrios/vllm-mlx` ; ils apparaissent en lignes séparées ci-dessous parce
   qu'ils ont divergé en version et en fonctionnalités, mais le mécanisme de snapshot
   de cache de préfixe est de la même lignée.
3. **MTP : Qwen 3.6 a un vrai head ; le backend importe.** Le `config.json` officiel
   de Qwen 3.6 porte `mtp_num_hidden_layers=1` (nommage Qwen — **et non** la clé
   DeepSeek `num_nextn_predict_layers`, donc une vérification `nextn`-only conclut à
   tort « pas de head »). Certains artefacts GGUF/MLX re-quantifiés laissent tomber
   les tenseurs MTP tout en gardant le flag de config — vérifier les tenseurs dans
   l'index des poids, pas seulement le flag. Le MTP natif de llama.cpp
   (`--spec-type draft-mtp`) **requiert un `-MTP-GGUF`** qui embarque le head ; un
   GGUF simple ne peut pas drafter. Le mlx-lm publié n'exécute pas le head en
   speculative decoding natif (la PR
   [ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990) l'ajoute).
   LM Studio route le GGUF via son backend dérivé de llama.cpp et le MLX via
   `mlx-engine`.
4. **Mesures à une passe, pas de report de variance** — les chiffres des Sections
   1 / 2 sont des observations uniques. Le report de variance (médiane + min + max
   sur N passes) est supporté depuis `--burst-runs N` mais le re-bench est en attente.

| Section | Sujet | Statut |
|---------|-------|--------|
| 1 | Performance en appel unique | 🟡 8 cellules, mode thinking ON (decode inclut les tokens de raisonnement) |
| 2 | Burst concurrent (30/60/80 appels parallèles) | 🟡 cellule smoke + 2 points concurrents partiels ; pas de panel normalisé 30/60/80 |
| 3 | Caches & optimisations | ✅ 8 moteurs couverts |
| 4 | Mémoire & ressources | ✅ idle + swap sous charge (+0) + footprint mesuré |
| 5 | Qualité des modèles (leaderboards publics) | 🟡 chiffres vendor/auto-déclarés (llm-stats) |
| — | **mesures directes asiai** | ✅ dev-quality, ablation thinking, MTP, suivi d'instructions |
| 6 | Opérationnel (licence, endpoints, maintenance) | ✅ 8 moteurs couverts |
| 7 | Pondération des benchmarks qualité | 🟡 pondération par défaut, override via `--weights` prévu |
| 8 | Éval custom long-horizon (proposition) | 🟡 cadrée, pas encore construite |

---

## Section 1 — Performance en appel unique

> 🟠 **Snapshot de mai 2026 — indicatif, ce ne sont pas les chiffres de référence.**
> Cette table a été capturée en mai (mode thinking ON, une seule passe) et ses
> fixtures sources n'ont pas été re-vérifiées. Pour un **débit de decode actuel et
> reproductible**, utiliser la section *mesures directes asiai* ci-dessous (juin,
> llama.cpp b9430, déterministe). Ce pour quoi cette table reste fiable, c'est
> l'histoire **relative TTFT / cache de préfixe** (réutilisation cross-USER), pas les
> t/s absolus. Noter en particulier que les 123.9 t/s de la ligne 5 (LM Studio
> GGUF+MTP) côtoient les **llama.cpp Qwopus+MTP 123.3 t/s** de juin — le chemin GGUF
> de LM Studio est un backend dérivé de llama.cpp, donc les deux mesurent
> essentiellement le même moteur.

> ⚠️ **À lire avec le caveat 1 ci-dessus** : chaque chiffre de cette table inclut les
> tokens du mode thinking par défaut de Qwen3 (reasoning_content). Le débit agentique
> effectif nécessite de relancer avec
> `chat_template_kwargs={"enable_thinking": false}`. La colonne est intitulée
> « decode (t/s) » et non « débit effectif ».
>
> La colonne « estimation borne basse » est `60 × (TTFT + max_tokens/decode)`, en
> supposant un dispatch séquentiel (que le single-slot de Rapid-MLX impose). Ce
> n'est **pas** une prédiction de tick de production — voir la
> [Section 7](#section-7) pour le caveat méthodologique.
>
> 📌 **Versions testées (mai 2026)** : Rapid-MLX 0.6.66, LM Studio 0.4.14,
> llama.cpp b9270. Les versions de moteurs bougent chaque semaine sur Apple Silicon —
> traiter chaque chiffre comme daté, pas comme actuel. (La section mesures-asiai
> utilise llama.cpp b9430.)

| # | Moteur | Modèle | Format | Warm decode (t/s) ¹ | TTFT warm (ms) | TTFT prefix-test médian (ms) | TTFT cold (ms) | Estimation borne basse (60 appels × appel unique, optimiste) | Fixture source |
|---|--------|-------|--------|--------------------:|---------------:|----------------------------:|---------------:|----------------------------------------------------------:|----------------|
| 1 | Rapid-MLX 0.6.66 (fork of vllm-mlx) | Qwopus 3.6-35B-A3B-v1 (zaydiscold MLX-4bit) | MLX-4bit | **109.1** ¹ | 139 | **131** | 2074 | ~3.6 min | `cell-rapidmlx-qwopus35b.json` |
| 2 | Rapid-MLX 0.6.66 | Qwen 3.6-35B-A3B-UD (MLX-4bit) | MLX-4bit | 106.9 ¹ | 321 | 319 | 2095 | ~4 min | `cell-rapidmlx-35b-a3b.json` |
| 3 | Rapid-MLX 0.6.66 | Qwopus 3.6-27B-v2 (Jackrong MLX-4bit) | MLX-4bit | 31.8 ¹ | 323 | 323 | 8647 | ~13 min | `cell-rapidmlx-qwopus.json` |
| 4 | Rapid-MLX 0.6.66 | Qwen 3.6-27B-UD (MLX-4bit) | MLX-4bit | 20.5 ¹ | 527 | 527 | 8954 | ~23 min | `cell-rapidmlx-full-27bud.json` |
| 5 | LM Studio 0.4.14 (GGUF backend) ² | Qwen 3.6-35B-A3B-MTP (Unsloth GGUF) | GGUF Q4 + MTP | **123.9** ¹ ² | 309 | 5965 | 6063 | ~3.5 min warm / ~9.2 min prefix-changing | `cell-lmstudio-mtp-qwen35b.json` |
| 6 | LM Studio 0.4.14 (GGUF backend) ² | Qwopus 3.6-35B-A3B-v1 (Jackrong GGUF) | GGUF Q4_K_S | 105.6 ¹ | 292 | 5785 | 5624 | ~3.5 min warm / ~9.6 min prefix-changing | `cell-lmstudio-qwopus35b.json` |
| 7 | llama.cpp b9270 | Qwen 3.6-35B-A3B (UD Q5_K_XL) | GGUF Q5_K_XL | 80.9 ¹ | 3000 | 3000 | n/a | ~8 min | (baseline reference) |
| 8 | llama.cpp b9270 | Qwopus 3.6-27B-v2 (Jackrong GGUF Q4) | GGUF Q4 | 25.3 ¹ | 13000 | 13000 | n/a | ~30 min | (baseline reference) |

¹ **Caveat mode thinking** : chiffres capturés avec le template de chat par défaut
(thinking ON). Le débit effectif réel sur les charges d'appels d'outils est
typiquement de 4-12 t/s sur les finetunes Qwopus/Qwen3.6 quand les tokens de
raisonnement gonflent la sortie de 6-7×. Pour reproduire ces chiffres de decode,
passer `chat_template_kwargs={"enable_thinking": false}` dans le payload de la requête.

² **Backend LM Studio** : les lignes 5-6 ont utilisé un fichier GGUF, qui route via
le backend dérivé de llama.cpp de LM Studio (PAS le runtime MLX `mlx-engine`). Le
claim MTP de la ligne 5 reflète l'implémentation de ce backend, pas le speculative
decoding de mlx-engine. Le mlx-lm publié n'exécute pas le head MTP en speculative
decoding natif (son `sanitize()` laissait historiquement tomber les poids MTP pendant
la conversion ; le support natif est dans la PR
[ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990)), donc un
hypothétique modèle MTP au format MLX n'en bénéficierait pas non plus sur le
mlx-engine publié.

### Observations clés

- Sur le pattern agent réaliste (système identique + prompts utilisateur changeants),
  **Rapid-MLX + Qwopus 35B-A3B-v1** délivre 131 ms de TTFT prefix-test médian
  vs 5965 ms pour le backend GGUF de LM Studio (**~44× plus rapide**). L'avantage
  vient du mécanisme de snapshot de cache de préfixe de vllm-mlx (voir Section 3
  pour la désambiguïsation du code source).
- Sur le débit de decode pur (chemin warm), le **backend GGUF de LM Studio avec
  Unsloth MTP** enregistre 123.9 t/s vs Rapid-MLX 109.1 t/s (+13.5%). Ce delta
  reflète le speculative decoding du backend dérivé de llama.cpp de LM Studio sur un
  GGUF portant le head MTP, pas un gain Apple-MLX (le mlx-engine publié n'exécute pas
  le head — voir note de bas de page 2). Sur le chemin natif llama.cpp, le MTP est
  net-positif sur le MoE 35B-A3B — voir Section 3.
- Toutes les configurations de la `famille Qwen 3.6` (hybride DeltaNet + full-attention)
  échouent au cache de préfixe cross-USER **sauf Rapid-MLX**, qui conserve un snapshot
  d'état RNN. Sur llama.cpp / LM Studio GGUF `llama_memory_can_shift=false` ; sur
  mlx-lm / oMLX l'état récurrent/SSM ne peut pas être scindé à une frontière de token
  arbitraire. Le fix amont de llama.cpp pour cette architecture n'est pas mergé
  ([#23121](https://github.com/ggml-org/llama.cpp/pull/23121) fermée ;
  `preserve_thinking` ne le résout pas,
  [#22615](https://github.com/ggml-org/llama.cpp/issues/22615)).
- **Sérialisation single-slot confirmée** : le test smoke burst (Section 2) montre
  que Rapid-MLX 0.6.66 sérialise les appels concurrents en FIFO (p50 ≈ p95 ≈ max sur
  burst=5). Pour 60-80 appels/tour, le wall-time total scale linéairement avec la
  taille du burst sur ce moteur. Un moteur multi-slot (ex. llama.cpp `--parallel N`)
  se comporterait différemment, mais `--parallel N` sur l'hybride Qwen3.6 désactive le
  cache de préfixe par slot (limitation architecturale).

---

## Section 2 — Burst concurrent (30/60/80 appels parallèles)

> Pattern : 30 à 80 appels `POST /v1/chat/completions` concurrents tirés dans une
> fenêtre d'environ 200 ms. Simule une boucle d'agent dispatchant plusieurs appels
> MCP/outils en parallèle. Mesuré nativement via `asiai bench --burst-mode`.
>
> 🟡 **Statut** : 1 cellule smoke mesurée (Rapid-MLX burst-5). Panel complet en attente.

### Cellule smoke (Rapid-MLX 0.6.66 + Qwopus 35B-A3B-v1, burst=5)

| burst N | wall-time (s) | p50 latency (ms) | p95 latency (ms) | max latency (ms) | agg throughput (t/s) |
|--------:|--------------:|-----------------:|-----------------:|-----------------:|---------------------:|
| 5 | 2.8 | 2615 | 2792 | 2812 | 88.8 |

**Constat smoke** : `p50 ≈ p95 ≈ max` indique que les 5 appels ont été **sérialisés
côté serveur** (moteur single-slot). Rapid-MLX 0.6.66 **ne semble pas** supporter
l'ordonnancement de requêtes concurrentes — les appels font la queue en FIFO en
interne. À valider à l'échelle de 60/80 appels.

### Panel concurrent complet — pas encore mesuré

Un panel normalisé 30/60/80-concurrent n'a pas été exécuté (les mesures ici sont en
agentic-mode séquentiel, pas en burst concurrent). Les deux points de données
concurrents partiels qui existent ailleurs :

- **TurboQuant** (K=`q8_0` V=`turbo2`, Qwen3-4B, M4 Pro) : **+9% en agrégé à
  4-parallel** (68.5 → 74.7 t/s) alors même que le single-stream est à −8% — la
  compression KV rachète la marge parallèle.
- **oMLX** continuous batching (mlx-lm `BatchGenerator`) : **×1.8 en agrégé à
  burst-8** (12.8 → 22.9 t/s), mais il **s'effondre à burst-30** (17.3 t/s) dès qu'un
  27B-dense sature la RAM en swap — 0 crash.

Un panel burst-mode dédié à travers tous les moteurs est différé.

---

## Section 3 — Caches & optimisations

| # | Couple | Réutilisation cache cross-USER | Snapshot persiste cross-restart | Support MTP | Taux d'acceptation MTP | Compat TurboQuant | Types KV cache natifs | Slots parallèles natifs |
|---|--------|---|---|---|---|---|---|---|
| 1 | Rapid-MLX + Qwopus 35B-A3B-v1 | ✅ YES (RNN-state snapshot, see ³ below) | ✅ persistent in `~/.cache/vllm-mlx/` | ❌ released MLX runtime doesn't run the MTP head as speculative decode (mlx-lm PR #990 pending) | n/a | ❌ MLX only | MLX native (no quant flag exposed) | ⚠️ single slot (smoke burst confirms FIFO serialization) |
| 2 | Rapid-MLX + Qwen 35B-A3B-UD | ✅ YES ³ | ✅ persistent | ❌ | n/a | ❌ | MLX native | ⚠️ single slot |
| 3 | LM Studio + Qwen 35B-A3B-MTP | ❌ NO (architectural hybrid limitation) | n/a | ✅ via mlx-engine v1.8.1 | **82.1 %** (on coding task) | ❌ | mlx-engine v1.8.1 (4bit MLX) | configurable via GUI |
| 4 | LM Studio + Qwopus 35B-A3B-v1 | ❌ NO | n/a | ❌ no heads | n/a | ❌ | mlx-engine v1.8.1 (Q4_K_S GGUF) | configurable via GUI |
| 5 | llama.cpp + Qwen 3.6-35B-A3B | ❌ NO (architectural hybrid limitation) | n/a | ✅ `--spec-type draft-mtp` on a `-MTP-GGUF` (a plain GGUF cannot draft). Net-positive on the MoE 35B-A3B — asiai measures **+38%** decode (base) / **+17%** (Qwopus) on M5 Max (see § asiai measurements) | benefit = intra-session decode delta (no acceptance rate logged) | ✅ turbo2/3/4 V cache | `fp16`, `q8_0`, `q5_0`, `turbo2/3/4` | ⚠️ `--parallel N` works mechanically but **disables prefix cache per slot on hybrid arch** (each slot owns its KV, the `--cache-reuse N` flag is already silently disabled here). Use with caution. |
| 6 | mlx-lm | ❌ NO (PRs #923, #188, #192 pending upstream) | n/a | ❌ broken on hybrid arch | n/a | ❌ | MLX native | ❌ (single slot) |
| 7 | oMLX | ❌ NO (tool calling lost post-cache-hit, issue #825) | partial | ❌ | n/a | ❌ | MLX native + tiered SSD cache | ❌ |
| 8 | vLLM-MLX (`waybarrios`, upstream of Rapid-MLX) | ⚠️ trie prefix-cache, no documented hybrid/DeltaNet support (Rapid-MLX rows 1-2 add the RNN-state snapshot on top) | n/a | ⚠️ MTP added in prerelease 0.4.0rc1 | n/a | ❌ | MLX + paged-attention | ✅ |

³ **Cache de préfixe Rapid-MLX** : le cache stocke des slabs KV d'attention hybride +
des snapshots d'état RNN, indexés par `<repo>--<sys_prompt_hash>` et persistés sous
`~/.cache/vllm-mlx/`. Le TTFT prefix-test observé d'environ 131 ms est un
réattachement de slab KV en RAM plus la passe forward de l'utilisateur changé, pas un
rechargement depuis le disque.

**Cache grand-contexte oMLX.** Le cache KV SSD paginé 2-tiers d'oMLX fait passer un
prefill de 55K tokens d'environ 115 s à environ **3,5 s** de TTFT sur un cache-hit
même-prompt (×33 ; 55 296 / 55 837 tokens cachés). Sur les petits prompts (~7,5K) il
n'y a pas d'avantage (~2-5 s, = mlx-lm) et le decode est à ~19 t/s (pas de gain en
vitesse brute). C'est une réutilisation même-prompt, pas cross-USER (qu'oMLX ne fait
pas) ; la persistance cross-restart est documentée mais pas encore testée en A/B.

**Compression KV TurboQuant** (llama.cpp). K=`q8_0` V=`turbo2` réduit la RAM KV
d'environ **28%** (22.9 → 16.4 GB sur un modèle 4B, M4 Pro) avec une validité d'appel
d'outils inchangée (10/10), et gagne **+9% en agrégé à 4-parallel** malgré −8% en
single-stream. Le symétrique K=`turbo3` V=`turbo3` atteint ~−56% de RAM mais dégrade
la qualité (early-stop, répétition) — l'asymétrique `q8_0`/`turbo2` est la config
utilisable.

---

## Section 4 — Mémoire & ressources (Apple Silicon M5 Max 128 GB)

| # | Couple | RAM working-set (GB) | Footprint disque (GB) | Swap Δ idle | Swap Δ sous charge | SOLO requis ? | Cohabitation sûre ? |
|---|--------|---|---|---|---|---|---|
| 1 | Rapid-MLX + Qwopus 35B-A3B-v1 | ~22 | 19.9 (MLX-4bit) | +0 | **+0 MB** | ⚠️ SOLO (cohabit thrash to 0.4 t/s) | ❌ |
| 2 | Rapid-MLX + Qwen 35B-A3B-UD | ~24 | 20.0 (MLX-4bit) | +0 | **+0 MB** | ⚠️ SOLO | ❌ |
| 3 | LM Studio + Qwen 35B-A3B-MTP | 21.6 | 23.2 (Q4 + MTP heads) | +0 | **+0 MB** | not tested | not tested |
| 4 | LM Studio + Qwopus 35B-A3B-v1 | 18.5 | 19.9 (Q4_K_S) | +0 | **+0 MB** | not tested | not tested |
| 5 | llama.cpp + Qwen 3.6-35B-A3B (reference) | ~16 | ~16 (Q5_K_XL) | +0 | **+0 MB** | ❌ | ✅ with `--parallel 2/3` |

> **« Sous charge »** = le bench agentique 8 phases incluant un prefill de 50K
> tokens (le stress mémoire *séquentiel* le plus lourd mesuré), M5 Max 128 GB, SOLO :
> delta de swap **0 MB / 0 swapouts pour chaque moteur** — modèle + KV tiennent dans
> la mémoire free/inactive avec >100 GB de marge. C'est de la mémoire en charge
> séquentielle, **pas** de la mémoire en 60-concurrent (voir Section 2). La RAM
> working-set est une estimation ; le RSS mesuré inclut le GGUF mmap'd / les pages MLX
> wired, donc le vrai footprint incrémental est plus bas (le head MTP ajoute ~+3 GB).

### Observations

- **Rapid-MLX requiert une opération SOLO sur le GPU** : la cohabitation avec un autre
  moteur en train de décoder activement déclenche un delta de swap de 5.4 → 14.2 GB et
  un effondrement du decode à 0.4 t/s. Ne pas démarrer un second moteur sur le même
  GPU Apple Silicon.
- **Le footprint disque de LM Studio MTP** est de +13 % vs Q4_K_S sans heads MTP, à
  cause des blocs de poids MTP. Coût négligeable par rapport au gain de decode de +17 %.
- Sur les 128 GB de mémoire unifiée du M5 Max : chaque configuration 35B-A3B testée
  laisse plus de 100 GB de marge après chargement — la RAM n'est pas le facteur
  limitant.
- Sur M4 Pro 64 GB : `Q5_K_XL` **ne** tient **pas** aux côtés des modèles auxiliaires
  (swap thrash observé en production). `Q4_K_S` tient.

---

## Section 5 — Qualité des modèles

> Les chiffres de benchmarks publics ici sont **vendor / auto-déclarés** et agrégés
> par des leaderboards (llm-stats), non vérifiés indépendamment. Recouper sur
> [llm-stats](https://llm-stats.com) · [LiveBench](https://livebench.ai) ·
> [SWE-bench](https://swebench.com) avant de s'y fier. Les propres mesures directes
> d'asiai sur Apple Silicon sont dans la section suivante.
>
> Les claims auteur-uniquement (Jackrong/Qwopus, auto-éval Unsloth) sont signalés
> séparément et tenus hors des colonnes de leaderboard public.
>
> 🔴 **Constat critique** : le benchmark « Hessling agentic » cité sur plusieurs model
> cards communautaires **n'est pas reproductible indépendamment** — 16 prompts,
> curateur unique, pas d'intégration neutre à un leaderboard. Les trois conseillers
> recommandent de le traiter comme un simple smoke test.

### Modèles de base open-weight Qwen 3.6

> Chiffres de leaderboard public (llm-stats), auto-déclarés. Le 27B-dense surpasse le
> MoE 35B-A3B sur SWE-bench — cohérent avec le propre constat dev-quality d'asiai
> ci-dessous (la base MoE est celle qui rencontre le bug d'objet vide en appel
> d'outils). Les heads MTP sont une fonctionnalité de vitesse de decode et ne
> changent pas les scores de qualité d'un modèle.

| Modèle | Architecture | SWE-bench Verified | GPQA Diamond | MMLU-Pro | Terminal-Bench 2.0 | BFCL |
|-------|--------------|-------------------:|-------------:|---------:|-------------------:|------|
| Qwen 3.6-35B-A3B-Instruct | MoE 35B / 3B active | 73.4% | 86.0% | 85.2% | 24.6% | absent from board |
| Qwen 3.6-27B-Dense Instruct | Dense 27B hybrid | 77.2% | 87.8% | 86.2% | 59.3% (vendor) | absent from board |

> Terminal-Bench **2.0** est bien plus difficile que l'ancien Terminal-Bench v1 (les
> model cards communautaires citent ~51.5% pour le 35B-A3B sur v1) ; les 24.6% ici sont
> la génération 2.0.

### Famille Qwopus 3.6 — auteur-déclaré uniquement, **non vérifié indépendamment**

Les finetunes Qwopus 3.6 publiés par Jackrong sur HuggingFace revendiquent des gains
substantiels par rapport à la base Qwen. En mai 2026, ces claims n'ont **pas été
reproduits indépendamment** sur des leaderboards neutres. À traiter comme expérimental
jusqu'à ce que des re-runs BFCL / SWE-bench par un tiers soient disponibles.

| Modèle (claims auteur) | MMLU-Pro | SWE-bench Verified | Hessling agentic (16 prompts) |
|-----------------------|---------:|-------------------:|------------------------------:|
| Qwopus 3.6-35B-A3B-v1 (Jackrong) | claimed 88+ | claimed 75+ | claimed 88.6 ⚠ non-reproducible |
| Qwopus 3.6-27B-v2 (Jackrong) | claimed 87.43 | claimed 75.25 | n/a |

⚠ Le benchmark « Hessling agentic » cité sur les model cards de Jackrong semble être
une évaluation de 16 prompts spécifique à un curateur, sans intégration neutre à un
leaderboard. Les trois conseils interrogés (Grok-4, GPT-5, Gemini Advanced)
recommandent de le traiter comme un simple smoke test.

### Ancrages frontier (mi-2026)

> Tous les chiffres sont **vendor / auto-déclarés**, agrégés par llm-stats — aucun
> n'y est vérifié indépendamment. **Terminal-Bench 2.0** est l'exception (l'équipe
> tbench rejoue les soumissions ; les lignes sont les scores de pointe agent×modèle).
> Les GPQA sont des chiffres « Diamond » vendor et le set est quasi-saturé — à traiter
> comme approximatifs.

| Modèle | SWE-bench Verified | GPQA Diamond | MMLU-Pro | Terminal-Bench 2.0 | Source |
|-------|-------------------:|-------------:|---------:|-------------------:|--------|
| Claude Opus 4.8 | 88.6% | 93.6% | n/a | — (no TB submission) | llm-stats / Anthropic |
| Claude Opus 4.7 | 87.6% | 94.2% | n/a | **90.2%** | llm-stats / tbench |
| Claude Sonnet 4.6 | 79.6% | 89.9% | n/a | 53.4% | llm-stats / tbench |
| GPT-5.5 | n/a\* (SWE-Pro 58.6%) | 93.6% | n/a | 84.7% | OpenAI / tbench |
| GPT-5 (base) | 74.9% | 85.7% | n/a | 49.6% | llm-stats / tbench |
| Gemini 3.1 Pro | 80.6% | ~94.4% | n/a | 80.2% | llm-stats / tbench |
| DeepSeek-V4-Pro-Max | 80.6% | 90.1% | 87.5% | n/a | vendor (DeepSeek) |
| Llama-3.3-70B-Instruct | n/a | n/a | 68.9% | n/a | Meta (baseline) |

\* GPT-5.5 n'a pas de score SWE-bench *Verified* public (OpenAI rapporte SWE-bench Pro
Public 58.6%) ; le chiffre « 88.7% SWE-bench » qui circule n'est sur aucune source
primaire. Note : **Qwen 3.6 n'a pas de 235B-A22B** — la famille ouverte est le
27B-dense et le 35B-A3B (ci-dessous) ; le 235B-A22B est la génération Qwen3 précédente.

### Baselines open-weights de même classe

| Modèle | MMLU-Pro | SWE-bench Verified | Notes |
|-------|---------:|-------------------:|-------|
| Llama-3.3-70B-Instruct | ~75-80 | ~40-50 | Older but well-characterized baseline |
| Mistral Codestral 25.05 / Devstral | high (coding-specialized) | medium-high | Strong editor-style completion fidelity, weaker on reasoning |
| GLM-4.6-Coder (Zhipu) | vendor claims very high | disputed | Significant skepticism around evaluation methodology (consensus) |

### Benchmarks qualité dépréciés pour cette décision

- **HumanEval / HumanEval+** — saturés en 2026, tous les modèles frontier au-dessus de
  90 %, plus de signal.
- **GSM8K** — saturé, pas de signal pour les agents de code.
- **MMLU (original)** — remplacé par MMLU-Pro.
- **« Hessling agentic » 16 prompts auteur-déclaré** — non reproductible, à traiter
  comme simple smoke test.

### Questions de qualité ouvertes (lacunes de recherche)

1. **Benchmark qualité-par-GB-RAM** : aucun standard n'existe. Formule proxy proposée :
   `AgentScorePerGB = (0.5·SWE + 0.3·BFCL + 0.2·TerminalBench) / RAM_resident`.
2. **Stabilité long-horizon (60+ appels d'outils)** : les benchmarks existants les
   plus proches sont τ-bench, PencilPuzzleBench (>1000 tours), MultiAgentBench, TRAIL.
   Aucun d'eux ne mesure spécifiquement « la correction de schéma et la cohérence
   stratégique sur 60-80 appels d'outils séquentiels » — cette lacune de benchmark est
   reconnue par les trois conseillers.
3. **Évaluation conversion-aware (MLX-4bit vs GGUF Q4_K_M vs Q5_K_XL)** : pas de
   leaderboard standardisé. Les rapports communautaires divergent — certains
   prétendent que le MLX-4bit préserve moins bien la stabilité d'appel d'outils que le
   GGUF Q5_K_M, d'autres disent l'inverse. **Conseil pratique** : exécuter votre propre
   charge de production contre chaque quant avant de vous engager.
4. **Validation qualité de la famille Qwopus 3.6** : nécessite des re-runs BFCL +
   SWE-bench par un tiers. Les claims auteur ne devraient pas piloter les décisions de
   production.

---

## Mesures directes asiai — Apple Silicon, mi-2026

> Ce que les leaderboards publics ci-dessus ne montrent pas : des mesures qu'asiai a
> exécutées directement sur Apple Silicon (M5 Max 128 GB en High Power Mode, M4 Pro
> 64 GB), llama.cpp b9430, déterministe (temp 0), sur la famille publique Qwen 3.6 et
> le finetune **Qwopus** distillé d'Opus. Caveat : le débit absolu cross-session sur
> le laptop M5 est à ±15% (thermique/charge) ; seuls les **deltas ±MTP back-to-back
> intra-session** sont serrés, et les absolus M5↔M4 ne sont pas comparables (quants
> différents).

### Dev-quality / appel d'outils (`asiai bench --code`)

- La **base Qwen 3.6-35B-A3B (MoE)** réduit `edit_file.edits` à un objet vide au tour
  deep-context — **3/3 runs, à la fois en Q4_K_S et Q5_K_XL**, même template de chat.
  Tool-call clean **87.5%**, edit-turns clean **66.7%**. C'est le comportement de
  génération d'appel d'outils de la base MoE, pas le quant ni le template.
- Le **dense 27B** (Q5_K_XL) et **Qwopus-35B-A3B** (Q4_K_S) scorent tous deux **100%
  clean / 0 bug** — Qwopus atteint la fiabilité d'appel d'outils du dense-27B au taux
  de decode ~4× du MoE.
- Sous une suite de stress d'appel d'outils plus difficile, Qwopus reste **100% / 0**
  tandis que le dense 27B tombe à **88.9% / 3 bugs** (le même échec d'objet vide). Mais
  sur un piège d'évaluateur d'expression (précédence de `**` vs moins unaire) le **dense
  27B est correct et Qwopus se trompe** — ils se séparent. (Le taux de récupération est
  sensible aux poids et bruité — pas un titre principal.)

### Ablation thinking (`asiai bench --thinking-ablation`, Qwopus-35B-A3B, 3 runs déterministes)

| Config | Tool-call clean | Note |
|--------|----------------:|------|
| `enable_thinking=off` | **100%** | the only fully-clean config |
| `enable_thinking=on` + `preserve_thinking=on` | 77.8% | 2/9 turns dirty |
| `enable_thinking=on` + `preserve_thinking=off` | 11.1% | turns 2-8 → HTTP 500 (context corruption); avoid |

### Débit MTP (`--spec-type draft-mtp`, warm decode, ±MTP intra-session)

| Modèle / matériel | MTP off | MTP on | Δ |
|------------------|--------:|-------:|--:|
| 35B-A3B base · M5 Max | 85.5 t/s | **118.4 t/s** | **+38%** |
| Qwopus 35B-A3B · M5 Max | 105.7 t/s | 123.3 t/s | +17% |
| 27B-dense · M5 Max | 23.8 t/s | 28.0 t/s | +18% |
| Qwopus 27B · M5 Max | 25.9 t/s | 26.7 t/s | +3% |
| 35B-A3B MoE · M4 Pro | 36.3 t/s | 44.6 t/s | +23% |
| 27B-dense · M4 Pro | 10.4 t/s | 9.7 t/s | **−6%** |

Le gain MTP scale comme **(MoE > dense) × (M5 > M4)** — fortement positif sur le MoE,
marginal-à-négatif sur le chemin dense lent (le surcoût de draft n'est pas amorti). Le
head MTP du finetune Qwopus est aussi plus faible que celui du modèle de base (Qwopus
27B +3% / 35B +17%, contre base 27B-dense +18% / 35B-A3B +38%) — le finetuning érode le
head de draft. Le
MTP côté MLX (mlx_vlm) est disqualifié : il casse le long contexte (sortie vide, 75%
valide). Titre principal : le MoE 35B-A3B + MTP sur llama.cpp soutient **~118 t/s** de
decode sur M5 Max (~44 t/s sur M4 Pro), ~4× le 27B-dense, à ~1,5 tok/s/W, TTFT ~62 ms,
100% de validité de sortie.

### Suivi d'instructions (`asiai bench --instruct`, research-brief)

L'arbitrage thinking a du mordant sur les livrables multi-étapes : avec
`enable_thinking=false`, Qwopus-35B fait le travail d'outils mais délivre le brief
multi-sections demandé **0%** du temps (il s'arrête à l'étape secondaire) ; avec le
thinking on, le modèle de base le délivre **100%** (5/5 sections). Cela tire dans le
sens opposé du résultat d'appel d'outils ci-dessus — thinking-off est le plus propre
pour les appels d'outils atomiques mais supprime les livrables rédigés — c'est pourquoi
asiai règle le thinking **par dimension de tâche**, pas comme un interrupteur global
unique.

### Boucle de recherche perfectionniste (`asiai bench --instruct loop-search`)

L'IFEval single-turn et le research-brief saturent à 100% sur ces modèles, donc
aucun des deux ne fait remonter la *boucle de recherche perfectionniste* : un modèle
qui refuse d'accepter un résultat de recherche ambigu et impossible à confirmer et
réémet des requêtes sémantiquement équivalentes jusqu'à ce qu'un garde-fou de
non-progression l'arrête, sans jamais délivrer. Un balayage `loop-search` (9 configs,
M5, b9430, thinking on/off, deux modes d'ambiguïté) l'isole :

- Le **MoE 35B-A3B boucle jusqu'au plafond** — pour **la base comme pour le finetune
  Qwopus, en Q4 comme en Q8**. Le quant plus haut ne le corrige pas, donc la boucle
  est **architecturale au MoE A3B**, pas un artefact de quant.
- Le **dense 27B ne boucle jamais** (Q4 / Q5 / Q8) : il accepte le résultat ambigu
  et rédige le briefing.

Le leader du throughput (le MoE, ~118-123 t/s) et le leader de l'aptitude agentique
(le dense 27B, ~25 t/s) sont donc des modèles *différents*. Pour un harnais tel que
le Hermes Agent de NousResearch, la résistance à la boucle peut l'emporter sur le
decode brut — le modèle le plus rapide n'est pas toujours le bon agent. (C'est
l'inverse du résultat d'appel d'outils, où le finetune MoE était l'agent le plus
robuste : **l'aptitude se mesure par mode d'échec, donc en mesurer plusieurs.**)

---

## Section 6 — Opérationnel

> 📌 Snapshot des capacités (mi-2026). Les versions de moteurs bougent chaque semaine
> sur Apple Silicon — ces cellules sont à un instant T, pas une garantie épinglée à une
> version.

| # | Moteur | Licence | Stream OAI-compat | `/v1/models` | `/health` | `/metrics` (Prometheus) | Tool calling | Auto-DL HF | Cache de préfixe persisté | Activité mainteneur |
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

## Section 7 — Pondération des benchmarks qualité pour les charges agentic-coding

> Ceci est la **pondération par défaut d'asiai** pour une charge de classe
> orchestrateur (60-80 appels d'outils séquentiels par tour, sortie validée par
> schéma, prompts système long-contexte). Elle est informée par trois avis de LLM
> frontier (Grok-4, GPT-5, Gemini Advanced) interrogés en mai 2026, mais **n'est pas
> un consensus communautaire** — à traiter comme un point de départ, pas comme une
> autorité. Override via un futur flag `--weights` (prévu).

| Benchmark | Ce qu'il mesure | Pourquoi ça importe ici | Poids consensus |
|-----------|------------------|---------------------|-----------------:|
| **SWE-bench Verified** | Real GitHub repo navigation + patch + test repair | Best proxy for code-editing fidelity inside an agent loop | **35 %** |
| **BFCL v3** (Berkeley Function Calling Leaderboard) | Multi-turn function-call accuracy, argument fidelity, schema adherence | Direct predictor of orchestrator stability across many tool calls | **25 %** |
| **TerminalBench 2.0 / MCP-Atlas** | CLI and MCP task execution autonomy | "Does the agent survive 40+ actions without derailing" | **20 %** |
| **LiveBench Coding** | Contamination-resistant coding tasks (refreshed monthly) | Catches train-test leakage that inflates HumanEval-class scores | **10 %** |
| **Custom long-horizon stability eval** | 60-80 sequential tool calls with cumulative context growth, malformed JSON recovery | The benchmark that does not exist yet in public form — see Section 8 | **10 %** |

### Benchmarks consciemment écartés de la pondération

- MMLU-Pro, GPQA Diamond, HumanEval+ — utiles comme signal de capacité générale, mais
  **faiblement corrélés** avec la fiabilité en boucle d'agent selon les preuves de
  2026. Les confirmations de labs frontier indiquent que les scores de raisonnement
  single-shot ne prédisent plus le succès d'agent autonome à une granularité suffisante.
- Agrégats auteur-déclarés sans re-runs tiers (Jackrong Hessling, auto-éval Unsloth,
  claims vendor GLM-4.6-Coder).

---

## Section 8 — Proposition de benchmark « endurance » custom (opportunité de recherche)

Les trois conseillers convergent sur la même lacune : **le benchmark qui
caractériserait le mieux une charge d'orchestrateur n'existe pas encore publiquement**.
En construire un est le seul moyen d'obtenir le signal manquant.

### Périmètre proposé

- **80 appels d'outils séquentiels** par trajectoire
- **Validation de schéma à chaque tour** (JSON strict / sortie structurée)
- **Croissance cumulative du contexte** (10K → 50K tokens à travers la trajectoire)
- **Tests d'interruption / récupération** (annulation mi-trajectoire + reprise)
- **Récupération de XML/JSON malformé** (l'agent s'auto-corrige-t-il ?)
- **Persistance des éditions de repo** (les éditions faites au tour N tiennent-elles
  encore au tour 60 ?)

C'est sur la roadmap asiai (un mode endurance long-horizon, après le burst-mode). S'il
est construit, ce serait le premier benchmark public dans cette niche spécifique.

---

## Méthodologie

- **Matériel** : MacBook Pro M5 Max 128 GB mémoire unifiée, macOS 26.4.1.
- **Charge** : classe orchestrateur — prompt système ~7 Ko, prompt utilisateur
  ~150-200 tokens, 60-80 appels par tour.
- **Phases mesurées** (appel unique, agentic-mode v1.6.0) :
  - `cold` : premier appel après un démarrage frais
  - `warm` : exactement le même prompt que cold (cache chaud)
  - `prefix-test-1/2/3` : système identique, utilisateur changeant — mesure la
    réutilisation de cache cross-USER
  - `cold-prefix` : système identique, après redémarrage — mesure le cache persistant
- **Verdict réutilisation cache de préfixe** : `YES` si `median(prefix-test) / cold < 0.2`,
  sinon `NO`.
- **Mesures anti-biais** : mode SOLO (pas de moteurs cohabitants), baseline thermique
  idle, phase de warm-up mmap.
- **Quality gates** (auto-suivies par asiai bench) :
  - `early_stop` : au moins 2 runs avec une complétion médiane `<0.5×`
  - `memory_pressure` : delta de swap `>500 MB` OU delta de swapouts `>1000`
  - `duplicate_processes` : plusieurs processus moteur détectés pendant le bench

Le protocole complet est l'instrumentation `asiai bench --agentic-mode` /
`--burst-mode` (power/thermal, footprint moteur, occupation KV, phases de cache de
préfixe) — voir la doc CLI d'asiai.

---

## Questions ouvertes

1. **MTP sur vLLM-MLX/Rapid-MLX — répondu (partiellement).** vLLM-MLX a ajouté le MTP
   en prerelease **0.4.0rc1** (2026-05-21) ; le combo théorique « MLX + Qwopus 35B-A3B
   équipé MTP + snapshot cross-USER » pourrait gagner à la fois sur le decode et le
   TTFT une fois que le fork Rapid-MLX suit la 0.4.x. Surveiller quand Rapid-MLX
   récupère le chemin MTP.
2. **MTP sur le runtime MLX — état actuel.** Le mlx-lm publié n'exécute pas le head MTP
   en speculative decoding natif (`sanitize()` laisse tomber les poids MTP pendant la
   conversion ; le support natif est dans la PR non-mergée
   [ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990)). Le
   `mlx-engine` de LM Studio enveloppe mlx-lm, donc il en hérite — le gain de decode de
   +13.5% de la ligne 5 de la Section 1 vient du **backend dérivé de llama.cpp** de
   LM Studio (le fichier est en GGUF), pas du speculative decoding de mlx-engine.
3. **Comportement burst sur Rapid-MLX/vllm-mlx à l'échelle de 60-80 appels** : le test
   smoke confirme un FIFO single-slot à burst=5. Panel complet en attente (Section 2).
   La question amont pertinente est de savoir si vllm-mlx prévoit du continuous-batching
   / ordonnancement multi-slot pour les modèles d'arch hybride.
4. **`llama_memory_can_shift=false` sur l'hybride Qwen 3.6** — toujours cassé en amont.
   [#18497](https://github.com/ggml-org/llama.cpp/issues/18497) est fermée (documente le
   re-processing complet) ; [#22384](https://github.com/ggml-org/llama.cpp/issues/22384)
   est une *issue* (closed-as-completed), **pas** un fix mergé ; la vraie PR de fix
   [#23121](https://github.com/ggml-org/llama.cpp/pull/23121) a été **fermée sans merge**
   (les patches ne vivent que sur des forks). Le workaround « juste activer
   `preserve_thinking` » est réfuté par l'issue ouverte
   [#22615](https://github.com/ggml-org/llama.cpp/issues/22615) (speedup de 0.67× = le
   cache reste inerte). Les couches DeltaNet hybrides n'exposent pas un état de cache
   décalable par construction.
5. **Reproduction indépendante de la qualité Qwopus 3.6** : nécessite des re-runs BFCL /
   SWE-bench par un tiers. Les chiffres publiés par l'auteur ne devraient pas piloter
   les décisions de production tant qu'ils ne sont pas recoupés.
6. **Lignée vllm-mlx vs Rapid-MLX — répondu.** Rapid-MLX est un **hard fork**
   communautaire de `waybarrios/vllm-mlx`, pas un wrapper mince : il embarque le moteur
   en-tree (package toujours nommé `vllm_mlx`), ne dépend pas en pip du package amont, et
   a divergé substantiellement (Rapid-MLX 0.6.74 vs amont 0.3.0). Le nom de package
   `vllm_mlx` partagé et le répertoire `~/.cache/vllm-mlx/` sont une source fréquente de
   confusion d'attribution (voir Section 3, caveat 2).

---

*Ce panel est un document vivant. Contributions, corrections, et cellules de bench
additionnelles bienvenues via
[github.com/druide67/asiai](https://github.com/druide67/asiai/issues).*
