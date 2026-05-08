# Bench-0 — Protocole méthodologique général

**Rôle** : Architect bench/LLM (BMAD asiai pile R&D bench, extension custom)
**Document** : constant transverse, supervise N campagnes Bench-X
**Version** : v1.0 (2026-05-08)
**Statut** : draft analyst, à valider PM (JMN) au Sprint Bench-1.5

> Ce document définit les invariants méthodologiques de toutes les campagnes
> bench asiai. Une campagne (Bench-1 → Bench-4) applique ce protocole sans
> le réécrire. Toute déviation par campagne doit être motivée et auditée
> par l'Architect bench/LLM en Sprint Bench-3.

## 0. Lexique

- **Run** : une exécution unique d'un prompt (1 prompt → 1 réponse complète)
- **Session** : un ensemble de runs sur un même tuple `(hardware, modèle, moteur, contexte, KV cache)`
- **Campagne** : un projet bench défini (ex: Bench M5 Phase 1, Bench thermal v0.5+)
- **Hardware** : un Mac Apple Silicon avec specs fixes (M4 Pro 64 GB, M5 Max 128 GB, etc.)
- **Endpoint** : un moteur d'inférence accessible via HTTP local (Ollama :11434, LM Studio :1234, etc.)

## 1. Objectifs & scope

### Ce que le protocole couvre
- Perf raw d'un moteur sur un modèle (tok/s, TTFT, mémoire)
- Parité cross-engine (Ollama vs LM Studio vs llama.cpp vs oMLX vs TurboQuant)
- Parité cross-version (Qwen 3.5 vs 3.6, Q4_K_M vs Q5_K_M vs MLX)
- Cas d'usage agent (tool-calling, streaming, contexte long, subagents parallèles)
- Cohabitation multi-moteurs sur un même hardware

### Ce que le protocole NE couvre PAS
- **Qualité de sortie LLM** (correctness des réponses) — domaine MLX-Benchmark, Open LLM Leaderboard, etc.
- Compatibilité fonctionnelle (templates, dataset training-time) — couvert par les criteria du consommateur (ex: Hermes, asiai bench)
- Sécurité du déploiement (cf. règles claude-config secrets-management)

## 2. Métriques retenues

### Métriques primaires
| Métrique | Définition | Unité | Outils |
|---|---|---|---|
| `tok_s` | Throughput tokens/s en régime établi (post-TTFT) | tokens/s | calcul = `tokens_generated / generation_duration_ms * 1000` |
| `ttft_ms` | Time to first token (premier byte de réponse) | ms | timing client HTTP |
| `total_duration_ms` | Durée totale request → fin de stream | ms | timing client HTTP |

### Métriques secondaires
| Métrique | Définition | Unité | Notes |
|---|---|---|---|
| `vram_bytes` | Pic mémoire wired GPU (compresseur inclus) | bytes | `vm_stat` parsé via aisai |
| `power_watts` | Puissance moyenne pendant la session | W | `powermetrics --samplers cpu_power,gpu_power` |
| `tok_s_per_watt` | Efficacité énergétique | tokens/s/W | dérivée |
| `error_rate` | Taux de runs qui produisent error/timeout/0 token | % | par session |
| `ttft_p50` / `ttft_p95` / `ttft_p99` | Distribution TTFT | ms | nécessite ≥10 runs |
| `tok_s_p50` / `tok_s_p95` | Distribution throughput | tok/s | idem |

### Métriques agent (Hermes-specific, criteria merlin 2026-05-08)
| Métrique | Définition | Unité | Source |
|---|---|---|---|
| `tool_call_json_success` | Ratio runs où le tool-call JSON parse correctement côté agent | % | tool-call test set dédié |
| `tool_call_round_trip_ms` | Latence end-to-end agent → tool-call → réponse parsée | ms | timing agent côté |
| `streaming_jitter_ms` | Écart-type des intervalles inter-token | ms | mesure stream client |
| `streaming_completeness` | Ratio sessions où le stream finit clean (vs interruption) | % | détection client |
| `cold_start_ms` | Temps premier token après load complet du modèle | ms | timing post-launch |
| `subagent_parallel_throughput` | tok/s agrégé quand N=2,3 sessions concurrentes | tok/s | requêtes simultanées |

## 3. Hardware envelope

### Hardware approuvé
- **M4 Pro Mini 64 GB** (`192.168.0.16`) — endpoint principal partagé Hermes-prod + asiai monitoring
- **M5 Max 128 GB** — burst dev/heavy + bench R&D
- **M1 Max 64 GB** — archive Phase H 60j, **bench legacy uniquement** (référence historique, pas nouvelle data)

### Conditions hardware obligatoires
- Mac sur secteur (pas batterie)
- Aucune autre application interactive lancée (pas de Chrome, pas d'IDE, pas de bench parallèle d'autre tool)
- macOS déterministe : pas de sleep/wake pendant la campagne
- Network LAN seulement (pas de bench via VPN ou WiFi instable)

### Caractéristiques à logger
- Chip (`sysctl machdep.cpu.brand_string`)
- RAM (`sysctl hw.memsize`)
- macOS version (`sw_vers`)
- Ambient temperature si possible (`sudo powermetrics --samplers smc`)
- Charge initiale système (`top -l 1` snapshot)

## 4. Modèles & moteurs

### Sélection modèle pour campagne

Une campagne définit la matrice modèles dans son brief Bench-1. Le protocole impose :
- **Configs identiques** entre moteurs (context, top_p, température, repeat_penalty, KV cache type)
- **Paire de quantizations** quand applicable : Q4_K_M (référence ggml standard) ET MLX qx64-hi pour LM Studio
- Si MLX-only (oMLX, mlx-lm) : noter que la comparaison cross-engine est asymétrique

### Modèles canoniques actuels (à mettre à jour quand pertinent)

| Famille | Variant | Source | Justification |
|---|---|---|---|
| **Qwen3.6-27B** | Q4_K_M / MLX qx64-hi | HF mlx-community + Ollama Library | Canonique Hermes (Nous Research AMA Reddit r/LocalLLaMA 1sz2y76, 2026-04-25) |
| Qwen3.6-35B-A3B | text-qx64-hi-mlx / NVFP4 | HF mlx-community + Ollama | Continuité ligne asiai 3.5 (parité bench 17 avril) |
| Qwen3.5-35B-A3B | qx64-hi-mlx | HF mlx-community | Référence prod swarm openclaw |
| Qwen3.5-9B / Qwen3.5-4B | Q4_K_M | Fallback bas-bout, RETEX Birdinhandandbush |
| Llama 3.3 70B | Q4_K_M | Test 70B M5 Max exclusive |
| Qwen3-coder 30B | Q4_K_M | Coder dev quotidien |

### Moteurs supportés v1.0

| Moteur | Port | Format | Native unload | aisrv driver |
|---|---|---|---|---|
| Ollama | 11434 | GGUF | ✓ keep_alive=0 | EngineDriver |
| LM Studio | 1234 | GGUF + MLX | ✓ lms unload | EngineDriver |
| oMLX | 8800 | MLX | ✗ | RestartOnlyDriver |
| TurboQuant | 8081 | GGUF llama.cpp KV turbo | ✗ | RestartOnlyDriver |

### Contexte minimum

- **64K minimum** pour scénarios agent (Hermes, multi-tool-calls)
- **128K idéal** (criteria merlin H2 2026-05-08)
- **Sur Ollama** : défaut 4K obligatoirement override via `OLLAMA_CONTEXT_LENGTH=131072` ou Modelfile `num_ctx 131072`
- Pour bench raw perf comparable, 8K suffit si on déclare le contexte explicitement dans la session metadata

## 5. Conditions d'exécution

### Warmup obligatoire

Tout run d'une session doit être **précédé** d'un warmup :
- 1 run "throwaway" avec un prompt court (~50 tokens output) pour amorcer mmap, KV cache et chemins MLX/Metal
- **Le résultat warmup est exclu de l'agrégat** (tagué `is_warmup: true`)
- Sans warmup, le premier run est typiquement 30-60 % plus lent que les suivants → biais observé sur tous les engines Apple Silicon

### Cool-down inter-runs

- 5 secondes minimum entre runs consécutifs (laisse le GPU thermal se stabiliser)
- 30 secondes entre sessions différentes (full reset thermal envelope)

### Thermal monitoring

- Logger `thermal_level` à chaque run (sample `pmset -g therm | grep CPU_Speed_Limit`)
- Si `CPU_Speed_Limit < 100`, le run est en throttling — flagué `thermal_throttled: true`
- Sur M5 Max sustained, ré-évaluer après 10 runs (sinon résultats post-throttling masqués)

### Reproductibilité

- Seed fixe pour génération (où supporté) : `seed=42`
- Greedy decoding pour benchs perf pure : `temperature=0, top_p=1.0`
- Pour benchs qualité : retain default model recommended params, mais logger explicitement

### Isolation

- Un seul moteur LLM actif à la fois (anti-pollution VRAM cross-engine)
- `aisctl engine purge` entre sessions cross-modèles ou cross-engines (mémoire `feedback-bench-discipline.md`)
- Si plusieurs moteurs doivent être chargés (test cohabitation Hermes), c'est un cas explicite de la matrice (ex: workload #5)

## 6. Prompts standards

### Set "perf-raw" (cross-engine, cross-modèle)
| ID | Prompt | Tokens output cible | Justification |
|---|---|---|---|
| `code-fib` | "Write a Python function that returns the n-th Fibonacci number. Include docstring and 3 unit tests." | ~250 | Code generation standard, déterministe, testable côté client |
| `prose-summary` | "Summarize in 5 bullet points: [paragraphe ~500 tokens d'un article tech]" | ~150 | Compréhension + génération brève |
| `chat-followup` | "Tell me about Apple Silicon. Now compare it to recent x86 chips." | ~400 | Multi-turn simulé |
| `long-ctx-recall` | "Read this 50K-token document. What was the value of X mentioned in section 7?" | ~50 | Test contexte long |

### Set "agent-tool-calling" (Hermes-specific, criteria merlin)
| ID | Prompt | Tools attendus | Critère qualité |
|---|---|---|---|
| `tool-search` | "Find the latest news about local LLM inference on Apple Silicon" | `web_search(query="...")` | JSON parse OK + tool-name correct |
| `tool-read` | "Read the file ~/projets/asiai/README.md and summarize" | `read_file(path="...")` | path correctement quoted |
| `tool-mem-add` | "Remember that JMN prefers French for replies" | `memory.add(content="...")` | structure attendue |
| `tool-delegate` | "Delegate the task 'audit the Sprint 0 BMAD findings' to a sub-agent" | `delegate_task(task="...", agent="...")` | sub-agent param valide |
| `tool-multi` | "Search the web for X, then add the result to memory" | `web_search` puis `memory.add` | order correct + chaining |

### Set "stress" (occasionnel, gros risques)
| ID | Prompt | Notes |
|---|---|---|
| `stress-128k` | Prompt 120K tokens + question simple | Test KV cache + OOM |
| `stress-stream-cancel` | Prompt long, kill stream à 50% | Test propre interruption |
| `stress-3-parallel` | 3 sessions concurrentes du même prompt | Test multi-tenant (subagents Hermes) |

## 7. Anti-biais détaillé

### Biais observés sur Apple Silicon (à neutraliser systématiquement)

1. **mmap cold** : premier run après reboot OU après `purge` est plus lent. → warmup obligatoire (cf. §5)
2. **Thermal drift sustained** : run 1-3 = full perf, run 5+ = throttling silencieux. → cool-down + thermal monitoring + flag `thermal_throttled`
3. **KV cache leak inter-runs** : sur Ollama avec `keep_alive` non zéro, le run 2 profite du KV cache du run 1 → réponse plus rapide artificielle. → forcer `keep_alive=0` entre runs OU explicitement déclarer "warm session" dans metadata
4. **Compresseur memory unifié** : `vm_stat` reporte une VRAM "active" trompeuse car les modèles MLX peuvent être en compressed/swap actif. → utiliser `total_active_bytes = active + wired + compressed pages` (déjà géré par aisai)
5. **Engine reporting incohérent** : Ollama reporte VRAM via `/api/ps`, LM Studio via `process` Métal, oMLX directement métriques. Pas de standardisation. → noter chaque moteur avec sa source de mesure, ne pas croiser sans correction
6. **Variance run-to-run élevée** : sur 10 runs, écart 5-15 % sur tok_s n'est pas anormal. → médiane > moyenne, p95 documenté, écart-type rapporté
7. **Bench tier-user "M5 Pro 48 GB" mystère** (cf. leaderboard 2026-05-07) : 1-3 samples seulement = pas de variance fiable → exiger ≥5 samples pour publier sur le leaderboard
8. **Network jitter LAN** : sur cascade multi-Mac via SSH, latence réseau ajoute du jitter au TTFT. → bench LOCAL d'abord (un Mac à la fois), cascade benchée séparément avec délai réseau noté
9. **Tokenizer-induced output length variance** : un même prompt peut produire 200 ou 400 tokens selon le tokenizer. → comparer tok_s sur un *régime* observé, pas sur durée totale, et logger tokens_generated par run
10. **JIT load LM Studio** : LM Studio charge le modèle à la première requête → premier run inclut le load. → forcer un load explicite via `lms load <model>` AVANT le warmup, ou attendre que `aisctl engine status` reporte `running` et que ce soit chaud (probe répété)

### Biais consommateur (Hermes-specific)

11. **CLI vs Telegram gateway tokens** (RETEX virtualuncle 30j, cité merlin) : 2-3x tokens en passant par gateway. → si on bench une cible Hermes-prod, simuler le gateway, pas l'API directe
12. **Tool-calling JSON failure undetected** (gotcha Artest113 Reddit) : Qwen3.5:4b et Gemma4E4B *ne savent pas tool-call* en local malgré un succès apparent (tokens générés OK, mais JSON malformé). → critère qualité = parse + schema validation, pas juste "tokens OK"
13. **Cascade fuite cloud** (RETEX my_name_isnt_clever AMA) : Hermes a poussé silencieusement vers Gemini quand Ollama saturait. → test sécurité config explicite (workload #8 merlin) avant publication

## 8. Critères qualité campagne

Une session Bench-X est **valide** ssi :
- ≥5 runs (non-warmup) collectés
- Variance tok_s ≤ 25 % (sinon flag `unstable` et investigate)
- Aucun run thermal-throttled (sinon écarter ou signaler)
- `error_rate` ≤ 20 % (au-delà, la session est compromise)
- Métadonnées hardware/OS/engine version logguées

Une **campagne** est valide ssi :
- ≥3 sessions valides par tuple `(hardware, modèle, moteur)`
- Audit méthode Bench-3 par Architect bench/LLM signe-off
- Audit identifie ≤2 biais résiduels acceptables (au-delà : retry)
- Données brutes archivées dans `~/projets/asiai/docs/research/bench-<campagne>/raw/`
- Rapport final Bench-4 disponible

## 9. Hooks campagne (template Bench-1)

Une campagne se définit dans `~/projets/asiai/docs/research/bench-<campagne>/brief.md` avec :
- Nom campagne (ex: "M5 Phase 1", "Thermal sustained 70B")
- Objectifs spécifiques
- Hypothèses testables (ex: "LM Studio MLX > Ollama Q4 sur M5 Max throughput, mais inverse sur TTFT")
- Matrice : modèles × moteurs × hardware × prompts
- Budget temps (heures)
- Out of scope explicite

## 10. Audit méthode (template Bench-3)

L'Architect bench/LLM produit en Bench-3 un fichier `audit.md` couvrant :
- Conformité protocole (warmup ? cool-down ? thermal monitoring ? isolation ?)
- Biais détectés (lesquels, mitigation appliquée ou non)
- Variance observée vs attendue
- Recommandations retry / publication / discard
- Sign-off explicite : "Méthode conforme, résultats publiables sur leaderboard" OU "Méthode non-conforme, recommander retry parce que X"

## 11. Évolutions du protocole

Toute évolution du protocole doit :
- Être motivée par un finding documenté (campagne précédente, retex, biais nouveau découvert)
- Bumper la version du document (semver : v1.0 → v1.1 patch, v2.0 breaking)
- Référencer la version dans les briefs Bench-1 ultérieurs ("appliquons protocole v1.1")

## Références

- Wiki transverse : [bmad-asiai.md](../../../../claude-shared-wiki/wiki/decisions/bmad-asiai.md)
- Sprint 0 Analyst : [findings.md](../../bmad/sprint-0-analyst/findings.md)
- Mémoire bench discipline : `~/.claude/projects/.../memory/feedback-bench-discipline.md`
- Mémoire bench rigor : `~/.claude/projects/.../memory/feedback-bench-rigor.md`
- Bench Qwen 3.6 référence 17 avril : `~/.claude/projects/.../memory/bench-qwen36-results.md`
- Whisper merlin Hermes criteria 2026-05-08 (cascade-inference thread) — Qwen3.6-27B canonique
- Bench officiel Nous Research M5 Max (`local-llm-on-mac.md` doc Hermes) — TTFT 67 ms llama.cpp vs 289 ms MLX

## Sign-off Bench-0

- **Auteur** : Architect bench/LLM (asiai instance, BMAD pile R&D)
- **Date** : 2026-05-08
- **Version** : v1.0
- **À valider** : PM (JMN) au Sprint Bench-1.5 avant exécution première campagne
- **Question(s) ouverte(s) PM** :
  1. Critère qualité ≥5 runs/session : trop strict pour une exploration rapide ? Acceptes-tu un mode "draft" avec ≥3 runs si flag `quality: draft` ?
  2. Tool-calling success rate côté agent : on a besoin d'un harness agent dédié pour mesurer (probablement code aisai bench --quality évoqué dans `idea-asiai-quality-suite.md`). Veux-tu qu'on intègre ça dans v0.5+ asiai bench OU on fait du sub-script bench-tool-calling.py ad-hoc pour Bench-1 ?
  3. Architect bench/LLM doit-il auditer aussi les bench non-asiai (ex: tier user M5 Pro 48 GB qwen3.6) qui apparaissent sur le leaderboard public ? À quel niveau de validation on les laisse passer ?
