---
description: Résultats de benchmark en mode agentique sur Apple Silicon — Qwen3.6 et Qwopus3.6 (27B dense vs 35B-A3B MoE), avec et sans speculative decoding MTP, à travers llama.cpp et la famille de moteurs MLX. Decode, TTFT, énergie, RAM, validité. Une page de résultats vivante.
---

# Résultats de benchmark agentique

Cette page présente de vrais résultats `asiai bench --agentic-mode` sur Apple
Silicon. Le protocole agentique exécute une conversation en 8 phases tenant compte
du prefix-cache (`--runs 5` pour la variance), qui sollicite la façon dont un agent
utilise réellement un modèle — multi-tours, long préfixe système, phase de
long-contexte à 50K tokens — plutôt qu'une génération unique en one-shot.

**Pourquoi le mode agentique — à qui s'adresse-t-il ?** Les frameworks d'agents ne
pilotent pas un modèle comme un chatbot : ils réutilisent un large préfixe système
sur de nombreux tours, émettent des appels d'outils et portent un long contexte. Un
chiffre de throughput one-shot passe à côté de tout cela — et le classement peut
même s'inverser (un moteur au decode brut excellent mais avec un TTFT de plusieurs
secondes ou un prefix-cache cassé est inutilisable pour un agent). Le mode agentique
mesure le modèle de la façon dont il est réellement piloté par les **orchestrateurs
d'agents et les assistants de code** — par ex.
[Hermes Agent](https://github.com/nousresearch/hermes-agent),
[OpenClaw](https://github.com/openclaw/openclaw),
[opencode](https://github.com/sst/opencode), Aider, Cline ou Continue — de sorte que
le résultat reflète des charges d'agent réelles, pas un artefact de benchmark.

> **Document vivant.** Ces chiffres sont rafraîchis à mesure que les versions de
> moteurs, les révisions de modèles et l'instrumentation s'améliorent (par ex. la
> capture de la RAM crête). Chaque ligne porte la version exacte du moteur et le
> fichier du modèle, de sorte qu'un résultat reste toujours reproductible.

**Campagne 2026-06-03.** Modèles : Qwen3.6 et le finetune Qwopus3.6, en deux
architectures — **27B dense** et **35B-A3B MoE** (Mixture-of-Experts, ~3B
paramètres actifs par token). Moteurs : llama.cpp (b9430) et la famille MLX (mlx-lm,
mlx_vlm, omlx, rapid-mlx, vllm-mlx). MTP = la tête Multi-Token Prediction intégrée
au modèle, utilisée pour le speculative decoding (`--spec-type draft-mtp`).
Matériel : **MacBook Pro M5 Max (128 GB)** et **Mac mini M4 Pro (64 GB)**, tous
deux en High Power Mode.

## Comment lire le tableau

Verdict d'abord. Les lignes sont groupées par un résultat de gate déterministe, et
pas seulement triées :

- **★** meilleur throughput validé dans le bloc · **✓** viable · **⚠** réserve
  (passe les hard gates mais latence médiocre) · **✗** éliminé (a échoué à un gate).
- Gates : `valid ≥ 80%` · `TTFT ≤ 1500 ms` (hard fail > 3000) · `prefix-cache reuse > 0`.
- **dec** = decode warm soutenu (tok/s) · **50K** = decode à 50K de contexte ·
  **TTFT** = time-to-first-token (ms) · **t/s/W** = tokens par seconde par watt SoC
  (efficacité, plus c'est haut, mieux c'est) · **RAMpk** = RSS moteur crête (GB, le
  chiffre qui gouverne le memory fit) · `—` = non mesuré (jamais 0).
- ★ classe selon le *throughput seul*. Choisir un modèle pour du travail réel pèse
  aussi la qualité de sortie (voir l'évaluation dev/code), que le throughput ne
  capture pas.

> Le M4 Pro et le M5 Max ne sont **pas** comparables en termes absolus ici — quant
> différent (Q5_K_XL vs Q4_K_S). Comparer à l'intérieur d'un bloc machine.

## MacBook Pro M5 Max 128 GB · Q4

| | model · engine · MTP | dec t/s | peak | 50K | TTFT ms | reuse | t/s/W | RAMpk GB | valid% |
|:--|---|--:|--:|--:|--:|--:|--:|--:|--:|
| **★ Tier 1 — gagnant + rapide** |||||||||| |
| ★ | Qwopus-35B · llamacpp b9430 ▲MTP | 123.3 | 127.5 | 83.8 | 67 | 0.8 | 1.590 | — | 100 |
| ✓ | Qwen-35B · llamacpp b9430 ▲MTP | 118.3 | 123.5 | 82.9 | 62 | 0.8 | 1.513 | — | 100 |
| ✓ | Qwopus-35B · llamacpp b9430 | 105.7 | 108.3 | 76.1 | 63 | 0.8 | 1.507 | — | 100 |
| ✓ | Qwen-35B · llamacpp b9430 | 85.5 | 90.8 | 66.7 | 59 | 0.8 | 1.403 | — | 100 |
| **✓ Tier 2 — viable (plus lent)** |||||||||| |
| ✓ | Qwen-27B · llamacpp b9430 ▲MTP | 28.0 | 29.5 | 22.9 | 118 | 0.8 | 0.378 | 32.2 | 100 |
| ✓ | Qwopus-27B · llamacpp b9430 ▲MTP | 26.7 | 29.8 | 22.0 | 118 | 0.8 | 0.367 | 31.5 | 100 |
| ✓ | Qwopus-27B · llamacpp b9430 | 25.9 | 27.1 | 20.8 | 110 | 0.8 | 0.342 | 28.4 | 100 |
| ✓ | Qwen-27B · llamacpp b9430 | 23.8 | 24.0 | 19.2 | 111 | 0.8 | 0.340 | 28.9 | 100 |
| **⚠ Tier 3 — réserve (latence médiocre)** |||||||||| |
| ⚠ | Qwopus-27B · mlx-lm 0.31.3 | 29.2 | 29.3 | 24.3 | 600 | 1.0 | 0.461 | 26.4 | 100 |
| ⚠ | Qwen-27B · rapid-mlx 0.6.71 | 20.6 | 20.7 | 17.9 | 798 | — | 0.357 | — | 85 |
| ⚠ | Qwen-27B · omlx 0.4.0 | 20.0 | 20.2 | 17.5 | 2150 | 0.82 | 0.346 | 26.7 | 100 |
| **✗ Tier 4 — éliminé** |||||||||| |
| ✗ | ~~Qwen-27B · mlx_vlm 0.6.0 ▲MTP~~ | ~~41.0~~ | — | — | ~~10879~~ | 0.0 | — | — | 75 |
| ✗ | ~~Qwen-27B · mlx_vlm 0.6.0~~ | ~~31.9~~ | — | 26.0 | ~~9578~~ | 0.0 | — | — | 100 |
| ✗ | ~~Qwen-27B · vllm-mlx 0.3.0~~ | ~~20.5~~ | — | 18.1 | ~~9578~~ | — | — | 24.3 | 100 |

Éliminations : mlx_vlm+MTP échoue à la validité (75%) et casse le long-contexte ;
les deux runs mlx_vlm et vllm-mlx ont un TTFT de ~9,6 s (inutilisable par tour
d'agent).

## Mac mini M4 Pro 64 GB · Q5

| | model · engine · MTP | dec t/s | peak | 50K | TTFT ms | reuse | t/s/W | RAMpk GB | valid% |
|:--|---|--:|--:|--:|--:|--:|--:|--:|--:|
| **★ Tier 1** |||||||||| |
| ★ | Qwen-35B · llamacpp b9430 ▲MTP | 44.6 | 50.7 | 32.6 | 143 | 0.8 | 1.557 | 33.0 | 100 |
| ✓ | Qwen-35B · llamacpp b9430 | 36.3 | 45.6 | 29.6 | 133 | 0.8 | 1.553 | 30.8 | 100 |
| **✓ Tier 2** |||||||||| |
| ✓ | Qwen-27B · llamacpp b9430 | 10.4 | 10.4 | 7.2 | 397 | 0.8 | 0.279 | 31.9 | 100 |
| ✓ | Qwen-27B · llamacpp b9430 ▲MTP | 9.7 | 9.8 | 7.5 | 409 | 0.8 | 0.272 | 35.4 | 100 |

## Principaux enseignements

- **Le MoE 35B-A3B bat le dense 27B sur chaque axe de throughput** sur les deux
  machines — il n'active que ~3B paramètres par token, donc il décode ~4× plus vite
  que le dense 27B et est ~3,5× plus efficace énergétiquement (1.5 vs ~0.4 tok/s/W).
  Le throughput n'est cependant pas la qualité — voir le caveat ci-dessous.
- **Le gain MTP dépend de l'architecture × le matériel.** Uplift de decode mesuré :
  MoE +38% (M5) / +23% (M4) ; dense +16% (M5) mais **−7% (M4)** — sur le GPU M4
  plus lent, le surcoût du draft dense n'est pas amorti. Le MTP est donc une mesure
  par modèle et par machine, pas un gain universel.
- **La famille de serveurs MLX n'est ici que throughput-only** : mlx-lm a le
  meilleur decode MLX mais un plancher de TTFT à 600 ms ; mlx_vlm, vllm-mlx et omlx
  sont disqualifiés par le TTFT (2–11 s) et/ou un prefix-cache cassé. llama.cpp
  domine la latence du premier token (~60–120 ms).
- **RAM crête vs RAM stable.** Le RSS de mlx-lm se situe à ~14,5 GB en régime
  stable mais **culmine à 26,4 GB** (allocation KV paresseuse + poids MLX-4bit
  compacts) ; llama.cpp pré-alloue d'emblée tout le KV du contexte (~29 GB à plat).
  En crête ils sont comparables — utiliser **RAMpk** pour les décisions de memory
  fit, pas la valeur stable.

## Méthodologie & caveats

- `asiai bench --agentic-mode --runs 5`, thinking désactivé
  (`chat_template_kwargs.enable_thinking=false`), contexte serveur ≥ 65536.
- Un seul moteur résident à la fois (SOLO) ; cache de pages purgé entre les runs
  GGUF qui partagent un même fichier.
- **Le quant diffère selon la machine** (M5 Q4_K_S/Q4_K_XL, M4 Q5_K_XL) → les
  chiffres absolus ne sont pas comparables d'une machine à l'autre, seulement à
  l'intérieur d'un bloc.
- **Le High Power Mode** est requis sur le laptop M5 (sinon le GPU soutenu est
  throttlé ~40%) ; le mini desktop M4 y est à peu près neutre.
- **Lacunes d'instrumentation connues** (en cours de correction) : la RAM crête est
  manquante (`—`) sur certains serveurs llama.cpp lancés manuellement ; la version
  du moteur n'est pas encore estampillée par run (montrée ici depuis une table de
  versions) ; la `reuse` du prefix-cache est une fraction grossière en attendant un
  vrai hit-rate.

Voir aussi : [Méthodologie de benchmark](methodology.md) · [Spécification des métriques](metrics-spec.md)
· [Leaderboard communautaire](leaderboard.md).
