# Qwen-AgentWorld-35B sur Apple Silicon : faut-il lui donner une place dans votre boucle d'agent ?

> Un brief d'évaluation pour qui fait tourner des modèles en local et construit des agents.
> **Ce que c'est** : un *world-model langagier* — il prédit ce qu'un terminal
> afficherait après une action, il n'agit pas. **Ce qui tourne** : MLX, ou
> llama.cpp/Metal avec un override de métadonnée en une ligne (un GGUF brut ne
> charge pas sans ça) ; pas de build MLX officiel non plus. **Son seul
> différenciateur que nous avons mesuré** : il tient le rôle de simulateur sur des
> séquences multi-pas là où un généraliste dérive. **Son coût** : une sur-réflexion
> lourde — mais maîtrisable. Les chiffres sont à petit N et directionnels, chacun
> porte sa taille d'échantillon ; les chiffres du benchmark des auteurs sont signalés
> comme des revendications.
>
> Mesuré avec `asiai` sur un M5 Max, MLX 4-bit, un seul moteur à la fois, 2026-06.
> Corrections bienvenues via [github.com/druide67/asiai](https://github.com/druide67/asiai/issues).

!!! tip "Quand l'utiliser / quand pas"
    **À utiliser comme** simulateur d'environnement pour des rollouts d'agent pas
    chers, comme mock de sortie d'outil/terminal, ou comme vérificateur de
    trajectoire à la place d'un LLM-juge (*ce dernier usage n'est pas testé ici —
    voir §6*). Il tient aussi la route comme simple généraliste 35B si on le prompte
    en assistant.

    **À ne pas utiliser comme** assistant quotidien : les auteurs ne documentent
    aucun usage chat/code, et il porte une lourde taxe de sur-réflexion (maîtrisable,
    voir §5). Et n'attendez pas la variante 397B qui « bat GPT-5.4 » : elle n'est
    **pas téléchargeable** (HF renvoie 401 malgré l'annonce Apache-2.0).

## 1. Runnabilité & reproduction (à lire en premier)

Si ça ne tourne pas sur votre machine, le reste importe peu. Verdict, cash :

- **Deux chemins marchent aujourd'hui ; aucun n'est clé en main.** Il n'y a **pas de
  build MLX officiel** — on a utilisé une conversion MLX communautaire, et c'est le
  chemin sur lequel on a mesuré. Le GGUF **charge aussi** sur llama.cpp / Metal, mais
  pas tel quel : en l'état il échoue sur `missing tensor 'blk.40.attn_norm.weight'`
  (build 9780, re-confirmé le 2026-06-25). La cause est un off-by-one du
  convertisseur, **pas des poids absents** — le GGUF déclare `block_count=41` (une
  couche MTP surnuméraire à l'index 40) alors qu'il ne livre que les 40 couches
  réelles 0–39, si bien que llama.cpp réclame une couche qui n'aurait jamais dû
  exister. On override la métadonnée au chargement et il charge *et génère* :
  `--override-kv qwen35moe.block_count=int:40 --override-kv qwen35moe.nextn_predict_layers=int:0`.
  Ollama et LM Studio wrappent llama.cpp mais n'exposent pas de façon fiable
  `--override-kv` : à considérer comme non testés. Le déploiement serveur officiel se
  fait via vLLM / SGLang / Transformers.
- **Un quant qui charge n'est pas une preuve qu'il produit un long raisonnement
  correct** — validez la génération, pas seulement le chargement.

Configuration de reproduction :

| | Dépôt (Hugging Face) | Taille |
|---|---|---|
| AgentWorld (spécialiste) | `jedisct1/Qwen-AgentWorld-35B-A3B-oQ4-MLX` | ~20 Go |
| Qwen3.6 (généraliste, référence) | `mlx-community/Qwen3.6-35B-A3B-4bit` | ~19 Go |

`mlx-lm` 0.31.3 · M5 Max 128 Go · échantillonnage temp 0.6 / top-p 0.95 / top-k 20 · un seul modèle chargé à la fois.

!!! warning "Le budget de tokens est un paramètre de premier ordre"
    AgentWorld émet une très longue trace de raisonnement. À `max_tokens=4096`, sa
    sortie est **tronquée avant la réponse** et compte comme un faux échec. Il lui
    faut **8192 à 12288** tokens de raisonnement pour finir sur certains cas pourtant
    triviaux. Quiconque rejoue à budget faible obtiendra de plus mauvais chiffres
    pour AgentWorld — des artefacts de mesure, pas des erreurs du modèle.

**RAM / contexte** : poids ~20 Go ; pic ~27 Go à 64K de contexte sur un Mac 128 Go ;
le cache KV ne grossit que d'environ 5 Go de 4K à 64K (une propriété de
l'architecture hybride partagée). Un Mac 64 Go le fait tourner confortablement à
contexte réduit ; 36–48 Go est tendu mais jouable à 4K–32K.

## 2. Ce que c'est, et comment les auteurs le positionnent

Un **world-model langagier** : à partir d'un état et d'une action (une commande
tapée), il prédit l'observation suivante (ce que le terminal renvoie) via un long
raisonnement. Sept domaines numériques (MCP, Search, Terminal, SWE, Android, Web,
OS). Il est entraîné à *être l'environnement*, pas à agir dedans.

Les auteurs le publient **comme un world-model, pas comme un assistant** : les
prompts système sont des prompts de simulation, et aucun usage chat/code n'est
documenté. On pouvait donc craindre qu'utilisé comme assistant, il simule une sortie
de console au lieu de répondre. Notre test nuance (§4) : avec un prompt d'assistant
standard, il code et raisonne à parité avec le généraliste. **C'est le prompt qui
décide du comportement, pas une capacité perdue.**

!!! note "Sur le mot *world-model*"
    L'objection la plus fréquente de la communauté est terminologique : c'est un LLM
    autorégressif qui fait de la prédiction du prochain état textuel, pas un
    world-model non-autorégressif / à base d'énergie au sens de LeCun. Bon à savoir
    avant que le nom ne crée une attente que le modèle ne prétend pas tenir.

Specs vérifiées (model card HF, en clair) :

| | |
|---|---|
| Paramètres | **34,66 Md** au total · ~3 Md actifs (MoE) |
| Architecture | `qwen3_5_moe`, hybride **Attention + Gated-DeltaNet** |
| Experts | 256 (8 routés + 1 partagé) |
| Contexte | jusqu'à **256K** tokens |
| Licence | **Apache-2.0** (~65 Go en BF16) |

## 3. Le différenciateur : la fidélité de rôle multi-pas

C'est le seul résultat neuf et défendable — et précisément ce que le benchmark des
auteurs ne mesure jamais (il est single-step). Le test : enchaîner des commandes qui
construisent un état (créer un dossier, y entrer, écrire un fichier, le relire) et,
à chaque pas, faire prédire au modèle la sortie exacte du terminal.

À cadrer comme une propriété de **fiabilité** — la discipline de format/rôle — et
**non** comme un avantage de compréhension. Qwen3.6 comprend parfaitement le terminal
(il suit le bon répertoire, compte les bonnes lignes) ; la différence, c'est qu'il
*sort parfois du rôle*.

| Test | AgentWorld | Qwen3.6 | Note |
|---|---|---|---|
| Sorties plausibles (`ls`, `git`, `ps`) — N=3 | 9/9 | 9/9 | parité |
| Séquence A — 6 pas, ancrée (4 essais) | 0 sortie de rôle / 24 pas | instable | tient le rôle |
| Séquence B — 8 pas, ancrée (3 essais) | 0 sortie de rôle / 24 pas | instable | tient le rôle |
| Boucle fermée (se relit lui-même) — N=2 | 6/6 ×2 | instable | tient le rôle |

**Lecture honnête** : AgentWorld n'est pas sorti du rôle sur **0 des 48 pas
observés**, à travers deux séquences et quatre essais. Qwen3.6 sort du rôle par
intermittence — ses essais ancrés ont oscillé de 0/6 à 6/6 d'une répétition à l'autre
(N=2), donc c'est **directionnel, pas un taux**. Quand il échoue, il **régurgite le
bloc d'action JSON** au lieu de simuler la sortie :

```text
$ cat log.txt              # log.txt vient d'être supprimé → l'env doit renvoyer une erreur

AgentWorld (dans le rôle) :
  root@host:/home/user# cat log.txt
  cat: log.txt: No such file or directory
  root@host:/home/user#

Qwen3.6 (hors du rôle, ~1 essai sur 2 ici) :
  [{"keystrokes": "cat log.txt\n", "duration": 0.1}]    # répète la commande d'entrée
                                                        # au lieu de la sortie
```

La bonne réponse est souvent présente dans la sortie de Qwen3.6 — c'est un échec de
**format/rôle**, pas une incompréhension. Pour une boucle où chaque pas doit être
lisible par le suivant, une seule sortie de rôle empoisonne la chaîne — et c'est
exactement ce qu'AgentWorld évite.

!!! note "Limites de mesure (divulguées)"
    Le scoring byte-exact sur la ligne d'écho de commande est strict, et nos fixtures
    de séquence D vs E étaient incohérentes sur l'inclusion ou non de l'écho après un
    `cd` — la métrique de fidélité de rôle a donc une imperfection connue. La
    direction est robuste sur quatre fichiers ; l'amplitude précise ne l'est pas.

## 4. Capacités généralistes : la base n'est pas dégradée

La question du propriétaire (le fine-tuning world-model a-t-il cassé le LLM de base ?)
a droit à une section sobre, pas au titre. Réponse courte : non — N=3, directionnel.

| Tâche | AgentWorld | Qwen3.6 | |
|---|---|---|---|
| Raisonnement (5 énigmes vérifiables, dont le piège des « r » de *strawberry*) | 15/15 | 15/15 | parité |
| Génération de code (4 fonctions, **exécutées contre des tests unitaires**) | 12/12 | 12/12 | parité |

Avec un prompt d'assistant (pas le prompt de simulation), AgentWorld écrit du code
correct et raisonne juste, à parité avec le généraliste. Il ne « déraille » pas —
c'est un généraliste compétent qui, simplement, sur-réfléchit.

## 5. Le coût : une taxe de sur-réflexion — et son remède

À promouvoir de note de bas de page à gate d'adoption, parce que pour un vérificateur
par pas c'est le chiffre qui décide — mais il a une parade.

Mesuré sur des cas terminal déterministes (N=2 par cas) :

| Mode | AgentWorld | Qwen3.6 |
|---|---|---|
| Raisonnement **activé** (mode simulateur par défaut) | médiane **1140 tok/préd.**, max 2558 · ~14 s · 8/8 exact | 504 tok · ~4,5 s · 8/8 |
| Raisonnement **désactivé** (`enable_thinking=false`) | **45 tok/préd. · ~0,5 s · 8/8 exact** | 45 tok · ~0,4 s · 8/8 |

AgentWorld émet ~2,3× plus de tokens que le généraliste, et sur un trivial `cd ; pwd`
son raisonnement a dépassé **8192 tokens dans 2 essais sur 3**. La réponse finale est
correcte — c'est une taxe de latence/calcul par pas, pas un défaut de justesse.

!!! tip "Le remède : plafonner"
    Désactiver le raisonnement pour le rôle de simulateur divise les tokens par ~25
    et la latence par ~28 **sans perte de fidélité byte-exact** sur les cas
    déterministes (toujours 8/8). Pour un vérificateur ou un mock par pas, faites-le
    tourner avec `enable_thinking=false` et un plafond `max_tokens`. **Réserve** :
    testé sur les seuls cas déterministes — sur des sorties où le raisonnement aide
    vraiment (état ambigu, contenu complexe), le sans-raisonnement pourrait coûter en
    fidélité. Non testé ici.

## 6. Performance (mesure unique, indicative ★)

Même famille, même architecture, donc des profils proches. À lire comme des
tendances.

| Mesure | AgentWorld | Qwen3.6 | Lecture |
|---|---|---|---|
| Temps au 1ᵉʳ token ★ | ~360 ms | ~510 ms | AW devant |
| Débit de génération ★ | ~110 t/s | ~117 t/s | ~7% plus lent |
| Débit à 64K de contexte | ~132 t/s | ~160 t/s | ~73% conservé |
| Mémoire de 4K → 64K | +5 Go | +5 Go | arch hybride, pas propre à AW |
| Cache de contexte (réutilisation préfixe 13K) | ~×21 | ~×23 | **propriété MLX**, pas du modèle |

L'écart de débit de ~7% est très probablement la recette 4-bit (AgentWorld protège
sa projection d'attention linéaire en 6-bit ; Qwen3.6 protège la porte du MoE en
8-bit), sur des longueurs de sortie inégales — un confond, pas un désavantage du
modèle. Le cache de prompt est une fonction de mlx-lm identique sur les deux ; son
gain de ~×20 dépend de la taille du préfixe réutilisé, ce n'est pas une propriété
d'AgentWorld.

**Non testé mais à forte valeur (l'usage n°2 de la communauté)** : utiliser la
prédiction du prochain état comme *vérificateur de trajectoire* — quand
l'environnement réel diverge de la prédiction, c'est le signal d'un agent qui sort du
chemin. Nous n'avons pas mesuré son comportement faux-positifs / faux-négatifs.
Question ouverte.

## 7. Ce que revendiquent les auteurs

!!! quote "Benchmark des auteurs — une revendication, pas une mesure"
    Sur leur propre benchmark (AgentWorldBench), AgentWorld-35B marque **56,4**, au
    niveau de Claude Sonnet 4.6 (56,0). Les gains qu'ils attribuent à la
    spécialisation, par ablation contre la **base Qwen3.5** (auto-reportés, pas un
    face-à-face avec Qwen3.6) : **+21,9** pilotage d'outils (MCP), **+18,1** ingénierie
    logicielle, **+10,2** terminal. Thèse : *la spécialisation world-model prime sur
    l'amélioration générationnelle* — le généraliste Qwen3.6 score **sous** la base
    (42,9 vs 47,7) sur la fidélité de simulation, parce qu'il est optimisé pour
    *agir*, pas pour *prédire l'état*.

    Ces chiffres viennent d'un benchmark maison mono-source, jugé par un LLM, sur un
    modèle de moins de 48 h à la publication — **aucune réplication tierce**. Le haut
    de leur tableau tient dans ~2 points sous un seul juge, donc l'ordre près du
    sommet est dans le bruit ; la marge du 397B sur GPT-5.4 est de +0,46 (bruit), et
    cette variante est non publique (HF 401) malgré l'annonce Apache-2.0.

Notre résultat multi-pas (§3) porte sur une *métrique différente et non répliquée*
de leur bench single-step ; il pointe dans la même direction (Qwen3.6 plus faible en
simulation), mais c'est une convergence de thèse, pas une confirmation.

## 8. Comment je le câblerais

- **Prompt** : utilisez le prompt système de **simulation** terminal officiel pour
  le faire tourner comme environnement ; n'utilisez un prompt d'assistant que si vous
  voulez une sortie généraliste. Les deux modes sont deux métiers différents.
- **Maîtrise du coût** : `enable_thinking=false` + un plafond `max_tokens` pour le
  rôle de simulateur (§5). Avec le raisonnement activé, budgétez ~1000–2500
  tokens/pas.
- **Boucle fermée** : réinjectez les propres prédictions du modèle, mais ancrez sur
  l'environnement réel quand vous l'avez ; attendez-vous à ce que la rigueur de
  format compte (la ligne d'écho).
- **Empreinte** : ~20 Go de poids, ~27 Go de pic à 64K.
- **La question build-vs-adopt** : « ne sort jamais du rôle » est-il intrinsèque à
  l'entraînement world-model, ou un généraliste + un décodage contraint par grammaire
  comblerait-il l'essentiel de l'écart ? Nous n'avons pas testé l'alternative du
  généraliste contraint — à peser avant d'adopter un modèle dédié.

## Limites de ce bench

- **Échantillons petits** (N=1–5, aucun écart-type). Tout écart chiffré est une
  tendance, pas un résultat statistique.
- **Un seul domaine** pour les deux résultats clés (séquences de terminal). La tenue
  du rôle « en boucle » reste à confirmer ailleurs.
- **Quantification non isolée** : les deux recettes 4-bit diffèrent un peu ; l'écart
  de débit y est probablement lié, mais ce n'est pas démontré ici.
- **Pas encore testé** : scénarios aléatoires/complexes, un second domaine, une
  comparaison à trois avec la base Qwen3.5 pour isoler l'effet exact du fine-tuning,
  et l'usage de vérificateur de trajectoire.
- **Seul le 35B est public.** La variante 397B n'est pas téléchargeable.

---

*Sources : arXiv 2606.24597 · [Qwen-AgentWorld-35B-A3B](https://huggingface.co/Qwen/Qwen-AgentWorld-35B-A3B) (Apache-2.0). Résultats relus en interne contre les biais avant publication. ★ = mesure unique, indicative.*
