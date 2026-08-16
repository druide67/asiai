---
title: "Quel moteur pour Qwen3.8-27B sur Apple Silicon"
description: "Onze configurations sur huit moteurs d'inférence, une seule machine M5 Max. Changer de serveur ne fait presque rien ; activer la prédiction multi-token change tout — et c'est éteint par défaut chez presque tous."
type: article
date: 2026-08-16
updated: 2026-08-16
---

# Quel moteur pour Qwen3.8-27B sur Apple Silicon

La question du modèle est réglée : Qwen3.8-27B tourne sur un portable et tient 262 144
tokens de contexte. Celle du moteur ne l'est pas, et elle coûte plus cher qu'on ne le
croit.

Nous avons mesuré onze configurations sur huit moteurs, sur une seule machine M5 Max. Le
résultat qui nous a surpris est un résultat négatif : **changer de serveur, à fichier de
poids identique au bit près, rapporte moins de 5 %.** Ce qui rapporte 50 %, c'est un
drapeau de décodage que la plupart des moteurs livrent éteint.

## Les conditions, avant les chiffres

M5 Max 128 Go, sur secteur, High Power Mode, un seul moteur résident à la fois.
Raisonnement désactivé sur tous les moteurs pour qu'ils soient comparables entre eux —
c'est une décision de mesure, pas de déploiement ; voir *Ce que nous recommandons*.
Bridage thermique à 50 % au bout de 70 à 131 secondes sur chaque cellule — **ce sont des
planchers, pas des maximums**. Tailles de prompt : 7 530 tokens (phases courtes) et
55 839 (longues).

⚠️ **La sortie était plafonnée à 400 tokens (200 sur les phases longues) et chaque
exécution a atteint ce plafond.** Rien ici n'a mené une tâche à son terme : ceci mesure un
débit de flux sur une continuation tronquée. « Validité de sortie 100 % » signifie qu'un
texte non vide et bien formé est sorti avant le plafond, pas que le modèle ait terminé
quoi que ce soit. Comme le nombre de tokens est fixe, le tok/s de cette page est l'inverse
exact du temps mural, ce qui en fait le chiffre le *plus propre* d'ici — voir *Ce que vaut
un token* pour celui qui ne l'est pas.

**Nous ne prétendons pas que ce sont les vitesses que vous obtiendrez.** Nous prétendons
que ce sont les écarts entre moteurs sous un même protocole.

## Le tableau

« À chaud » et « à 56k » sont des tok/s. Le premier jeton est mesuré sur le tour à chaud ;
*premier jeton @56k* sur le premier passage d'un prompt de 55 839 tokens.

| Moteur | Poids | n | À chaud | À 56k | Premier jeton | @56k | Mémoire |
|---|---|---|---|---|---|---|---|
| MTPLX Bare-Speed | MTPLX 4 bits g64 | 3 | **56,0** | **46,5** | 101 ms | 322 ms | 22,0 Go |
| MTPLX Optimized-Speed | MTPLX 4 bits g32 | 5 | 44,4 | 37,5 | **99 ms** | **301 ms** | 27,0 Go |
| mlx-vlm + drafter MTP | MLX 4 bits ⁽¹⁾ | 3 | 43,3 | 28,9 | 9 982 ms | 100 733 ms | 15,5 Go |
| MTPLX Optimized-Quality | MTPLX 8 bits g64 | 3 | 40,8 | 30,3 | 118 ms | 100 243 ms | 32,9 Go |
| Ollama 0.32.13 | GGUF (non déclaré) | 3 | 32,8 | 21,7 | 240 ms | 574 ms | 30,3 Go |
| llama.cpp b10434 + MTP | GGUF Q5_K_XL ⁽²⁾ | 3 | 31,8 | 22,7 | 125 ms | 365 ms | 36,8 Go |
| rapid-mlx 0.12.11 | MLX 4 bits ⁽¹⁾ | 3 | 30,2 | 24,7 | 33 195 ms | 287 548 ms | 15,0 Go |
| oMLX 0.6.0-dev | oQ4e-mtp (tiers) | 3 | 29,8 | 24,6 | 1 968 ms | 1 991 ms | 16,7 Go |
| mlx-lm 0.31.3 | MLX 4 bits ⁽¹⁾ | 3 | 28,8 | 24,0 | 432 ms | 799 ms | 14,6 Go |
| LM Studio 0.4.21 **+ MTP** | GGUF Q5_K_XL ⁽²⁾ | 3 | 27,8 | 23,4 | 419 ms | 825 ms | 36,3 Go |
| LM Studio 0.4.21 par défaut | GGUF Q5_K_XL ⁽²⁾ | 3 | 23,1 | 18,7 | 359 ms | 865 ms | 35,2 Go |

⁽¹⁾ et ⁽²⁾ marquent les lignes qui partagent un **fichier de poids identique au bit
près**. Chaque ligne est une cellule, un export — aucune valeur mélangée entre exécutions.

⚠️ **L'écart entre deux relances identiques atteint 7,5 %, et la mémoire bouge de 5 Go.**
Traitez tout écart de débit inférieur à 8 % comme nul. Cela dissout le milieu de ce
tableau : Ollama, llama.cpp, rapid-mlx, oMLX, mlx-lm et LM Studio+MTP (de 32,8 à 27,8) ne
sont pas classés par ces chiffres, ils sont à égalité.

⚠️ **Les deux entrées à 100 secondes ne sont pas une vitesse de moteur.**
Optimized-Quality atteint son premier jeton en 118 ms à chaud et en 100 secondes sur un
prompt 56k froid — même moteur, même version que la ligne à 301 ms. Cette colonne mesure
l'état du cache, et sur les lignes MTPLX ce cache est dimensionné par
`MTPLX_MEMORY_BUDGET=60GB`, un réglage d'opérateur et non une propriété du moteur. Sur le
tour 56k répété, le même build revient à 498 ms.

⚠️ **La mémoire n'est pas comparable entre familles.** llama.cpp et Ollama mappent leur
GGUF : leur empreinte résidente est adossée au fichier et évinçable (llama.cpp : 36,8 Go
de RSS mais 19,4 Go d'empreinte physique). Les moteurs MLX allouent. Lisez cette colonne
au sein d'une famille, pas au travers — et notez que les lignes MLX portent un cache KV
dimensionné sur la RAM libre au lancement. Trois moteurs ont reçu une fenêtre de contexte
explicite, les autres ont tourné sur leur défaut, ce qui interdit tout classement global
de cette colonne.

## Trois serveurs, un fichier : le serveur n'est pas ce qui compte ⁽¹⁾

mlx-vlm, mlx-lm et rapid-mlx ont tous servi `lmstudio-community/Qwen3.8-27B-MLX-4bit`,
snapshot `6067b15c` — le même fichier sur le disque, octet pour octet.

| Serveur | Décodage spéculatif | À chaud | Premier jeton |
|---|---|---|---|
| mlx-vlm | **drafter MTP** ⁽³⁾ | 43,3 | 9 982 ms |
| rapid-mlx | aucun | 30,2 | 33 195 ms |
| mlx-lm | aucun | 28,8 | 432 ms |

⁽³⁾ mlx-vlm tournait avec un **second modèle chargé** : `--draft-model
mlx-community/Qwen3.8-27B-MTP-4bit --draft-kind mtp --draft-block-size 4`. Les deux autres
servaient le modèle cible seul.

**Comparez les deux lignes réellement comparables — rapid-mlx et mlx-lm, même fichier,
aucune spéculation d'un côté ni de l'autre : 30,2 contre 28,8, moins de 5 %.** C'est
sous notre propre plancher de bruit. Changer de serveur MLX, en soi, ne rapporte rien.

Les +50 % de mlx-vlm viennent du drafter, pas du serveur. C'est le même effet, mesuré en
conditions contrôlées dans la section suivante, et le lire comme un résultat de moteur —
ce que faisait une version antérieure de cette page — revient à le compter deux fois.

C'est sur le premier jeton que ces trois-là diffèrent réellement, d'un facteur 77. Cet
écart relève du cache de préfixe, mesuré plus bas.

## Le drapeau qui rapporte 20 %, et pourquoi il est éteint ⁽²⁾

Qwen3.8 embarque une **tête de prédiction multi-token dans ses poids**. Le modèle propose
plusieurs tokens d'avance, le moteur les vérifie en une seule passe. Les moteurs qui
implémentent la règle d'acceptation par ratio de probabilités préservent exactement la
distribution de sortie ; nous n'avons pas vérifié cette propriété nous-mêmes, et vous ne
devriez pas la croire sur parole depuis un banc d'essai — lisez l'implémentation de votre
moteur.

Presque tous les moteurs le livrent **éteint**.

| Moteur | Drapeau | Activé d'origine ? |
|---|---|---|
| MTPLX ⁽ᵐ⁾ | `--mtp --depth 3` | oui |
| llama.cpp ⁽ᵐ⁾ | `--spec-type draft-mtp` | non |
| LM Studio ⁽ᵐ⁾ | `--speculative-draft-mtp` | non |
| mlx-vlm ⁽ᵐ⁾ | `--draft-kind mtp` + dépôt drafter séparé | non |
| vmlx ⁽ᵈ⁾ | `--native-mtp-depth` | oui |
| vllm-mlx ⁽ᵈ⁾ | `--enable-mtp` | non |
| oMLX | ne s'est pas engagé sur Qwen3.8 dans nos runs | — |
| Ollama · mlx-lm · rapid-mlx ⁽ᵈ⁾ | pas de support | — |

⁽ᵐ⁾ attesté par nos propres lignes de lancement et les journaux du moteur. ⁽ᵈ⁾ d'après la
documentation du projet uniquement — nous n'avons pas exécuté ces chemins.

Nous avons mesuré le coût de l'ignorance en conditions contrôlées : même fichier de poids,
même contexte de 65 536, même séquence thermique, tout identique sauf deux drapeaux.
**LM Studio passe de 23,1 à 27,8 tok/s, soit +19,9 %.** Aucune interface graphique ne le
montre. C'est la comparaison la mieux contrôlée de cette page, et c'est aussi d'où
viennent les +50 % observés sur mlx-vlm.

Effet de second ordre, et il compte davantage : **comparer deux moteurs à leurs réglages
d'origine, c'est comparer deux régimes différents.** MTPLX drafte d'emblée ; Ollama ne
sait pas drafter du tout.

## Le premier jeton s'étale sur 335×. Le prefill ne l'explique pas.

De 99 ms à 33 195 ms d'un bout à l'autre du tableau. Une partie de la réponse tient à la
**granularité du cache de préfixe** — combien d'un prompt répété survit d'un tour à
l'autre. Mesuré sur la même phase (le tour à chaud, celui d'où vient la latence du premier
jeton) :

| Moteur | Réutilise | Recalculé à chaque tour | Premier jeton |
|---|---|---|---|
| llama.cpp | 7 526 / 7 530 — **au token près** | 4 tokens | 125 ms |
| oMLX | 6 144 / 7 530 — **blocs de 1024** | 1 386 tokens | 1 968 ms |
| mlx-vlm | 0 / 7 530 | 7 530 tokens | 9 982 ms |

6 144, c'est six fois 1 024. oMLX réutilise des blocs entiers et recalcule tout ce qui n'en
remplit pas un — 1 386 tokens, à chaque tour, indéfiniment. **Cela explique l'essentiel de
l'écart entre 125 ms et 2 secondes**, et c'est la seule affirmation causale que ces trois
lignes autorisent.

⚠️ **La granularité n'explique pas tout l'étalement de 335×.** Quatre moteurs déclarent
zéro réutilisation sur cette phase et vont pourtant de 240 ms (Ollama) à 33 195 ms
(rapid-mlx) — un facteur 138 à réutilisation identique. Autre chose domine là, et nous ne
l'avons pas isolé.

⚠️ **Ne comparez pas les taux de réutilisation agrégés par session entre moteurs.** Leurs
plafonds diffèrent selon la part du prompt de test qui est cachable, et les comparer
produit des paradoxes qui s'évanouissent dès qu'on compare la même phase. Nous avons
commis cette erreur dans une version antérieure de cette page.

Nous ne publions **pas** de colonne de débit de prefill. La nôtre venait d'une unique
requête froide non répétée, ce qui inclut, pour les moteurs à chargement paresseux, la
lecture de 20 Go sur le disque — LM Studio a mesuré 216 tok/s sur cette requête et 938 sur
la suivante. Ç'aurait été un chiffre fabriqué.

## Ce que vaut un token

Parce que chaque exécution s'est arrêtée au même plafond de 400 tokens, le tok/s est ici
exact : Bare-Speed a livré ses 400 tokens en 7,2 s, Optimized-Speed en 9,1 s. L'écart de
26 % est du temps mural réel, pas un artefact.

Ce qui n'est **pas** comparable d'un build à l'autre, c'est ce que ces tokens contiennent :

| Build | tok/s | car./token | car./s |
|---|---|---|---|
| Bare-Speed | 56,0 | 3,58 | 200,8 |
| Optimized-Speed | 44,4 | 4,62 | 205,5 |
| Optimized-Quality | 40,8 | 4,06 | 165,7 |

Même tokeniseur, même prompt, 29 % d'écart de densité — Bare-Speed a répondu en LaTeX
dense, Optimized-Speed en prose. Il est 26 % plus rapide en tokens et délivre légèrement
*moins* de caractères par seconde. Aucun des deux chiffres n'est faux ; ils répondent à
des questions différentes. Si vous en publiez un, dites lequel.

## Ce que nous recommandons

**Pour un agent autonome local : MTPLX avec `Qwen3.8-27B-MTPLX-Optimized-Speed`, MTP
profondeur 3.** 99 ms au premier jeton, 301 ms sur un prompt 56k froid, réutilisation de
préfixe au token près (7 530 / 7 530), 27 Go.

⚠️ **Ce que nous recommandons n'est pas ce que nous avons mesuré**, et l'écart porte sur
trois axes à la fois. Mesuré : raisonnement **coupé**, MTPLX **2.6.0** servant Qwen3.8 sous
les défauts de la famille Qwen3.6, `--profile turbo`. Recommandé : raisonnement `xhigh`,
**2.7.1**, profondeur 3.

Nous avons exécuté la 2.7.1 une fois, raisonnement actif, et **cette cellule a échoué à
notre propre contrôle de validité de sortie** : 75 % de sorties valides, six phases longues
vides, parce qu'un budget de 400 tokens ne peut pas contenir une trace de raisonnement et
une réponse. Ses chiffres — 51,2 tok/s, 158 ms au premier jeton — sont donc *indicatifs
seulement*, et nous ne les mettons pas dans le tableau. Ce qu'ils établissent, en revanche,
c'est que le régime recommandé n'est pas mesurable sous ce protocole. Le choix du moteur
repose sur le tableau ; le réglage du raisonnement repose sur les recommandations de Qwen
et sur rien de nous.

Pas Bare-Speed, bien qu'il mène sur le papier. Les trois builds diffèrent par leur
divergence par rapport à bf16, publiée par l'auteur des quantifications : **0,00105** pour
Optimized-Quality, **0,0220** pour Optimized-Speed, **0,0376** pour Bare-Speed. Sa mesure,
pas la nôtre, non reproduite — mais c'est le seul chiffre de fidélité dont quiconque
dispose, et Bare-Speed est **36× plus loin de bf16** que Quality.

Pas Optimized-Quality non plus : **5,9 Go de plus** pour un avantage que personne n'a
démontré sur une tâche, et un premier jeton à 100 secondes sur un 56k froid contre 301 ms.

⚠️ **Nous recommandons le moteur dont lui seul sait lire le format de quantification, avec
notre propre outil de mesure, sur notre propre site.** Les lignes MTPLX sont les seules où
le moteur et le format de poids ne peuvent pas être séparés. Pesez la recommandation en
conséquence ; le tableau des drapeaux par moteur, plus haut, est la partie de cette page
qu'il ne nous coûte rien d'avoir juste.

**Faites-le tourner avec le raisonnement actif.** Qwen recommande le niveau d'effort
`xhigh` pour le travail agentique, et indique que dans les tâches agentiques multi-tours un
effort plus faible *« peut conduire à une analyse insuffisante, à davantage d'échecs et à
des reprises répétées, ce qui peut augmenter la latence totale »*. MTPLX 2.7.1 signale par
ailleurs le raisonnement désactivé comme un problème connu sur Qwen3.8. À noter : `high`
n'existe pas sur ce modèle — Qwen n'expose que `low`, `medium` et `xhigh`, et `xhigh` est
la valeur par défaut.

## Ce que nous n'avons pas pu mesurer

**vmlx et vllm-mlx manquent, et tous deux supportent le MTP natif** — vmlx l'a activé par
défaut — donc leur absence est un vrai trou, pas une erreur d'arrondi. vllm-mlx est mort au
démarrage sur une erreur de quoting en ligne de commande. vmlx a exécuté 24 runs complets
et produit une carte, puis la cellule a été **refusée par notre propre gate** : asiai
résout `-e vmlx` vers la famille ollama et a vu le serveur vmlx comme un intrus. Son export
montre par ailleurs 2,3 Go résidents pour un modèle de 20 Go — il servait depuis le disque
— et un delta de swap de 9,8 Go. Le refus avait raison pour la mauvaise raison, et les
chiffres ne sont de toute façon pas publiables.

**Le raisonnement était désactivé partout, pour rendre les moteurs comparables.** C'est une
décision de mesure et non de déploiement — voir la recommandation ci-dessus. Nous n'avons
aucun chiffre à proposer sur ce que le raisonnement fait à ces moteurs, et nous n'allons
pas en extrapoler un.

**Réserves de version.** Les lignes MTPLX ont tourné sur la **2.6.0**, avant que le moteur
n'embarque une famille de modèle `qwen3_8` — il servait Qwen3.8 sous les défauts de
Qwen3.6, contrat d'échantillonnage compris. Cela n'affecte pas le débit ; cela affecte tout
ce qui touche au comportement. La ligne oMLX vient d'un build de développement temporaire
dont l'export n'a pas capturé la version, cette ligne n'est donc pas reproductible telle
que publiée. Et notre export mlx-vlm s'auto-identifie comme `mlxlm 0.31.3_2` — seul le
journal de lancement prouve que le serveur était bien `mlx_vlm.server`.

**Le classement du premier jeton entre les trois builds MTPLX est dans son propre bruit** —
coefficients de variation de 0,33 à 0,66 sur cette métrique. 99, 101 et 118 ms ne sont pas
séparables. Le débit est bien plus stable (CV 0,006-0,07).

**L'écart entre deux relances a atteint 7,5 %** entre deux cellules de trois runs
d'Optimized-Quality (37,97 et 40,82 tok/s), et la mémoire a bougé de 5 Go entre elles.
Traitez tout écart inférieur à 8 % comme nul.

**Les réglages n'étaient pas symétriques, et le bridage thermique non plus.** llama.cpp a
reçu des drapeaux de cache explicites (`--cache-reuse 256 --slot-prompt-similarity 0.5`,
flash attention, KV 131k) que les moteurs MLX n'ont pas eus ; MTPLX a tourné sur
`--profile turbo`, pas sur son défaut ; Ollama a gardé ses tailles de lot d'origine face au
`--batch-size 4096` de llama.cpp. Les paramètres d'échantillonnage n'ont pas été égalisés
non plus — rapid-mlx charge temp 1,0 / top_p 0,95 depuis le `generation_config.json` du
dépôt, MTPLX 2.6.0 tournait sous le contrat d'échantillonnage de Qwen3.6. Et les moteurs
n'étaient pas au même plafond thermique : la limite de vitesse moyenne par cellule va de
80,8 (mlx-lm) à 54,6 (llama.cpp, Ollama), parce que les moteurs rapides chauffent
davantage la machine. Chaque médiane publiée mélange un run non bridé et deux runs bridés.
« Des planchers, pas des maximums » vaut par ligne ; cela ne préserve pas les écarts entre
lignes.

**Nous n'avons pas publié l'énergie, et elle change l'ordre.** Les exports la portent :
mlx-vlm 0,744 tok/s/W, MTPLX Bare-Speed 0,694, MTPLX Optimized-Speed 0,623, rapid-mlx
0,544, oMLX 0,512, mlx-lm 0,472, Ollama 0,451, LM Studio+MTP 0,422, llama.cpp+MTP 0,395.
Pour un agent qui tourne toute la journée sur batterie, c'est la colonne qui décide, et
notre moteur recommandé n'est que troisième.

## Reproduire ceci

Chaque chiffre vient d'une carte certifiée produite par [asiai](https://asiai.dev), via un
chemin unique et scripté, avec gates de solitude, preuves d'identité du modèle servi et
échantillonnage thermique. Ce que cette page ne vous donne pas encore, et devrait : les
fichiers d'export bruts, la ligne de lancement complète de chaque ligne, le texte des
prompts et les graines. Demandez-les et nous les publierons — d'ici là, considérez chaque
chiffre d'ici comme non vérifié par vous.

Si vous ne retenez qu'une chose : **vérifiez si votre moteur dispose de la prédiction
multi-token, et si elle est activée.**
