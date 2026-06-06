---
description: Résultats de benchmark de qualité dev et de rétention multilingue sur Apple Silicon — fiabilité des appels d'outils (le bug de troncature d'arguments JSON / objet vide), récupération d'erreur agentique, discipline de thinking et rétention de langue. Déterministe, aucun juge LLM nécessaire pour le signal principal. Une page de résultats vivante.
---

# Benchmarks de qualité dev & de langue

Le throughput n'est pas la qualité. Un modèle peut décoder vite et rester
inutilisable pour du coding agentique — il tronque les arguments d'appels
d'outils, boucle sur les erreurs, ou son finetune a discrètement cassé une autre
langue. Cette page présente de vrais résultats `asiai bench --code` et
`asiai bench --language` : des signaux **déterministes** (aucun juge LLM
nécessaire pour le cœur) qui mesurent si un modèle fonctionne réellement, pas à
quelle vitesse il émet des tokens.

> **Document vivant.** Ces chiffres sont rafraîchis à mesure que les révisions de
> modèles, les moteurs et les templates changent. Chaque bloc nomme le fichier de
> modèle exact et la config de service, de sorte qu'un résultat reste reproductible.

## Ce qui est mesuré

`asiai bench --code` (déterministe, sans juge) :

- **tool-call** — une session agentique d'édition de fichiers en 8 tours sous
  contexte qui s'accumule. Note l'émission d'appels d'outils, la validité JSON, la
  non-troncature, le bon outil, la conformité au schéma, et le **bug de l'objet
  vide** : la troncature du template `|items` qui réduit un tableau
  `edit_file.edits` à `{}` / `[]`.
- **tool-call-stress** — la même chose, en plus dur : contexte plus profond,
  tableaux d'édition de 8 à 10 éléments, pression d'échappement JSON (sauts de
  ligne, guillemets, antislashes, unicode). Sert à départager les modèles qui
  réussissent la baseline.
- **recovery** — injecte une erreur d'outil synthétique en milieu de session ;
  note une action corrective vs. une boucle bloquée (réémission de l'appel en
  échec).
- **thinking** — discipline du mode thinking : pas de fuite `<think>` dans le
  contenu, sortie non vide à budget court, et `enable_thinking=false` respecté.
- **coding** / **coding-hard** *(juge optionnel)* — tâches de coding multi-tours
  notées de 1 à 5 par un juge LLM à `--judge-url` (n'importe quel endpoint
  compatible OpenAI).

`asiai bench --instruct` (suivi d'instructions déterministe) :

- **verifiable** — prompts single-turn de type IFEval avec des instructions
  vérifiables programmatiquement (compte de mots/phrases/sections, mots-clés,
  JSON-only, casse, sans virgules, phrase de fin, titre en `<<>>`, langue…).
  Rapporté en exactitude strict/loose au niveau prompt et au niveau instruction —
  le format des leaderboards publics. Réimplémentation asiai-native du paradigme
  IFEval (Zhou et al. 2023) ; aucun code ni donnée IFEval n'est embarqué.
- **research-brief** — une tâche agentique : rechercher plusieurs sujets via des
  outils, puis rédiger un briefing multi-sections, puis une action d'outil
  secondaire (sauvegarde) **en dernier**. Le modèle produit-il le briefing
  principal, ou fait-il le travail d'outils et ne renvoie-t-il que la confirmation
  de l'étape secondaire ? Un modèle peut exceller en fiabilité d'appels d'outils et
  malgré tout sauter le livrable principal — noté de façon déterministe en
  vérifiant que les sections requises apparaissent après les tours d'outils.
  **order-control** inverse l'ordre (secondaire en premier) comme diagnostic.
- **loop-search** — un piège de recherche ambiguë : un warmup approfondi sur des
  sujets clairs, puis un fait cible que `web_search` ne peut jamais confirmer (les
  reformulations sémantiques de la requête se ramènent à une seule réponse). Note si
  le modèle accepte l'ambiguïté et délivre (sobre) ou réémet des requêtes
  équivalentes jusqu'à ce qu'un plafond de non-progression l'arrête
  (perfectionniste), plus un signal d'effondrement des tokens de sortie. Deux modes
  (`short` résultat sous 1 Ko / `unconfirmable` fait plausible mais manquant). C'est
  le mode d'échec que l'IFEval single-turn et le research-brief ne font pas
  remonter.

`asiai bench --language <code>` (déterministe, 8 langues) :

- **adherence** — le modèle reste-t-il dans la langue cible ? (ratio de mots-outils
  cible vs anglais pour les écritures latines ; ratio de caractères de l'écriture
  cible pour ja/ko/zh).
- **diacritics** — prompts pièges dont la bonne réponse doit contenir des tokens
  accentués spécifiques (`café`, `préféré`) ; une réponse dépouillée en ASCII
  échoue.

Les trois modes sont JSON-only et comparent les modèles entre eux en diffant la
sortie.

## Exemple traité — Qwen3.6-35B-A3B vs Qwopus3.6-35B-A3B vs Qwen3.6-27B dense

Un finetune (`Qwopus3.6`, un finetune d'`Qwen3.6-35B-A3B` MoE distillé d'Opus) vs.
sa base, vs. un modèle dense deux fois plus petit. Même llama.cpp, **même chat
template maintenu constant** (seul le fichier de modèle change), thinking
désactivé, 3 répétitions. Apple Silicon M5 Max, High Power Mode.

### Fiabilité des appels d'outils

| model · quant | tool-call clean | empty-object bug | under stress |
|---|--:|--:|--:|
| Qwen3.6-35B-A3B base · Q4 / Q5 | 87.5% | **3** | 87.5% · **3 bugs** |
| **Qwopus3.6-35B-A3B · Q4** | **100%** | **0** | **100% · 0** |
| Qwen3.6-27B dense · Q5 | 100% | 0 | 88.9% · **3 bugs** |

- **Le MoE 35B de base a un défaut d'appel d'outils résiduel que le correctif de
  template ne referme pas entièrement.** Il réduit `edit_file.edits` au bug de
  l'objet vide 3/3 sur un tour à contexte profond — aux **deux quants Q4 et Q5**
  (c'est donc un comportement de génération, pas de quantisation). Le template
  communautaire `froggeric`, qui corrige le bug `|items` sur les appels simples, ne
  sauve pas le MoE de base profondément dans le contexte.
- **Le finetune distillé d'Opus le répare complètement** — 0 bug, 100% clean — et à
  un quant *plus bas* (Q4 vs Q5), ce qui rend la victoire plus forte.
- **Sous stress, le finetune est l'agent plus robuste que le dense 27B** : le 27B
  craque (3 bugs d'objet vide sur la suite plus dure) tandis que le finetune reste à
  0. Ils sont à égalité sur la baseline ; la suite de stress les sépare.

### Justesse du code (tâches difficiles jugées par LLM)

Sur deux tâches de coding multi-tours plus délicates, ils se **divisent** : sur un
rate limiter à fenêtre glissante, les deux gèrent les cas limites
frontière/éviction ; sur un évaluateur d'expressions, le **dense 27B gère
correctement la priorité des opérateurs** (`-2**2 == -4`, moins unaire comme un
opérateur à part entière) tandis que le **finetune échoue** (il intègre le moins
unaire dans le nombre → `4.0`). La robustesse des appels d'outils et la justesse
algorithmique sont des axes *différents* — mesurer les deux.

### Rétention de langue

En lançant `--language fr` sur le finetune et sa base, même quant :

| model | adherence | diacritic traps | ASCII-stripped |
|---|--:|--:|--:|
| Qwen3.6-35B-A3B base | 100% | 4/4 | 0 |
| **Qwopus3.6-35B-A3B** | 100% | 4/4 | 0 |

**Zéro régression en français.** Le finetune orienté coding a conservé intact le
français du modèle de base (adherence, diacritiques, pas de dépouillement ASCII) —
un finetune spécifique à une tâche n'a *pas* coûté une autre langue, ce qui vaut la
peine d'être vérifié plutôt que supposé.

### Boucle de recherche perfectionniste (loop-search)

`research-brief` sature à 100% pour chaque modèle ici, donc il ne discrimine pas la
*boucle perfectionniste* qui casse les vrais agents. Le scénario `loop-search`, lui,
le fait. Sur un balayage de configs dense 27B et MoE 35B-A3B (M5, llama.cpp b9430,
thinking on/off, les deux modes d'ambiguïté) :

- Le **MoE 35B-A3B boucle** — il réémet des recherches sémantiquement équivalentes
  sur un fait impossible à confirmer jusqu'à ce qu'un garde-fou de non-progression
  l'arrête, au lieu d'accepter l'incertitude et de délivrer. Il le fait en **Q4
  comme en Q8** (c'est architectural, pas un artefact de quant), pour la base comme
  pour le finetune distillé d'Opus.
- Le **dense 27B ne boucle jamais** (Q4 / Q5 / Q8) : il accepte le résultat ambigu
  et rédige le briefing.

Pour un harnais agentique tel que le Hermes Agent de NousResearch, c'est le signal
décisif : le modèle dense résistant à la boucle est le main plus sûr même quand un
MoE plus rapide existe — le throughput n'achète rien si l'agent part en vrille sur
une seule étape ambiguë. C'est aussi la leçon inverse du résultat d'appel d'outils
ci-dessus (où le finetune MoE était l'agent *le plus* robuste) : **l'aptitude se
mesure par mode d'échec, donc en mesurer plusieurs.**

## Comment lire cette page

- **Verdict d'abord, pas vitesse d'abord.** Ce sont des signaux de
  justesse/fiabilité. Pour le throughput, voir les
  [Benchmarks agentiques](agentic-benchmarks.md).
- **Cœur déterministe, juge optionnel.** tool-call / recovery / thinking /
  adherence / diacritics ne nécessitent aucun juge LLM — ils sont reproductibles.
  Les notes `coding`/`fluency` sont jugées par LLM (subjectives, optionnelles).
- **Comparer à l'intérieur d'un changement contrôlé.** L'exemple maintient le
  template constant et ne fait varier que le modèle, de sorte qu'une différence est
  celle du modèle, pas du harnais.

## Méthodologie & caveats

- `asiai bench --code` / `--language`, thinking désactivé
  (`chat_template_kwargs.enable_thinking=false`), un seul moteur résident à la fois.
- **Le quant diffère dans l'exemple** (le finetune en Q4 vs les modèles Qwen en
  Q5) : le bug d'objet vide en tête d'affiche est piloté par le template/la
  génération et a été confirmé aux **deux** quants pour la base, donc le quant
  n'explique pas l'écart — et le finetune gagne depuis le quant plus bas.
- **Le juge de qualité de code n'est pas strictement aveugle** ici (un modèle de
  frontière a lu les transcripts sur le fond) ; les chiffres déterministes
  tool-call/stress sont objectifs.
- **La recovery est sensible aux poids**, ce n'est pas un signal cross-modèle
  propre — l'élément en tête d'affiche est la fiabilité tool-call/objet vide, qui
  est stable d'une répétition à l'autre.

Voir aussi : [Benchmarks agentiques](agentic-benchmarks.md) ·
[Méthodologie de benchmark](methodology.md) · [Spécification des métriques](metrics-spec.md).
