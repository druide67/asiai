---
title: "Quel moteur pour Qwen3.8-27B sur Apple Silicon"
description: "Huit moteurs d'inférence mesurés sur un seul M5 Max avec le même modèle. Deux moteurs qui lisent le même fichier de poids divergent de 50 %, et le drapeau qui rapporte 20 % est désactivé par défaut sur presque tous."
type: article
date: 2026-08-16
updated: 2026-08-16
---

<!-- STALE: rewritten 2026-08-16 after adversarial audit; retranslate from the English before publishing -->

# Quel moteur pour Qwen3.8-27B sur Apple Silicon

La question du modèle est tranchée : Qwen3.8-27B tourne sur un portable et tient
262 144 tokens de contexte. Celle du moteur ne l'est pas, et elle coûte plus cher qu'on
ne le croit.

Nous avons mesuré huit moteurs sur un seul M5 Max. Les deux résultats les plus
intéressants ne portent pas du tout sur la vitesse — ils portent sur deux moteurs qui
lisent le *même fichier* et divergent de 50 %, et sur un drapeau que personne n'active.

## Les conditions, avant les chiffres

M5 Max 128 GB, sur secteur, High Power Mode, un seul moteur résident à la fois.
Raisonnement désactivé sur chaque moteur pour qu'ils soient comparables entre eux.
Throttling thermique à 50 % en 1-2 minutes sur chaque cellule — **ce sont des planchers,
pas des maxima**. Validité des sorties à 100 % sur chaque ligne. Tailles de prompt
7 530 tokens (phases courtes) et 55 839 (longues), sortie plafonnée à 400 et 200 tokens.

**Nous n'affirmons pas que ce sont les vitesses que vous obtiendrez.** Nous affirmons que
ce sont les écarts entre moteurs sous un protocole unique.

## Le tableau

| Moteur | Poids | n | À chaud | À 56k | Premier token | Mémoire | Ctx déclaré |
|---|---|---|---|---|---|---|---|
| **MTPLX** Bare-Speed | MTPLX 4-bit g64 | 3 | **56,0** | **46,5** | 101 ms | 22,0 GB | défaut du moteur |
| **MTPLX** Optimized-Speed | MTPLX 4-bit g32 | **5** | **44,4** | 37,5 | 99 ms | 27,0 GB | défaut du moteur |
| **mlx-vlm** + drafter MTP | MLX 4-bit ⁽¹⁾ | 3 | **43,3** | 28,9 | **9 982 ms** | 15,5 GB | défaut du moteur |
| **MTPLX** Optimized-Quality | MTPLX 8-bit g64 | 3 | 40,8 | 30,3 | 118 ms | 32,9 GB | défaut du moteur |
| Ollama 0.32.13 | GGUF (non déclaré) | 3 | 32,8 | 21,7 | 240 ms | 30,3 GB | 65 536 |
| llama.cpp b10434 + MTP | GGUF Q5_K_XL ⁽²⁾ | 3 | 31,8 | 22,7 | **125 ms** | 36,8 GB | 131 072 |
| rapid-mlx 0.12.11 | MLX 4-bit ⁽¹⁾ | 3 | 30,2 | 24,7 | **33 195 ms** | 15,0 GB | défaut du moteur |
| oMLX 0.6.0-dev | oQ4e-mtp (tiers) | 3 | 29,8 | 24,6 | 1 968 ms | 16,7 GB | défaut du moteur |
| mlx-lm 0.31.3 | MLX 4-bit ⁽¹⁾ | 3 | 28,8 | 24,0 | 432 ms | **14,6 GB** | défaut du moteur |
| LM Studio 0.4.21 **+ MTP** | GGUF Q5_K_XL ⁽²⁾ | 3 | 27,8 | 23,4 | 419 ms | 36,3 GB | 65 536 |
| LM Studio 0.4.21 par défaut | GGUF Q5_K_XL ⁽²⁾ | 3 | 23,1 | 18,7 | 359 ms | 35,2 GB | 65 536 |

⁽¹⁾ et ⁽²⁾ signalent les lignes qui partagent un **fichier de poids identique octet pour
octet**. Chaque ligne est une cellule, un export — aucune valeur mélangée entre des runs.

⚠️ **La mémoire n'est pas comparable d'une famille à l'autre.** llama.cpp et Ollama
mmappent leur GGUF : leur resident set est adossé au fichier et évinçable (llama.cpp :
36,8 GB de RSS mais 19,8 GB d'empreinte physique). Les moteurs MLX allouent. Lisez cette
colonne à l'intérieur d'une famille, pas d'une famille à l'autre.

⚠️ **Le contexte déclaré diffère.** Trois moteurs ont reçu une fenêtre explicite ; les
autres ont tourné sur leur valeur par défaut. Cela seul interdit tout classement global de
la colonne mémoire.

## Deux moteurs, un fichier, 50 % d'écart ⁽¹⁾

mlx-vlm, mlx-lm et rapid-mlx ont tous servi `lmstudio-community/Qwen3.8-27B-MLX-4bit`,
snapshot `6067b15c` — le même fichier sur disque.

| Moteur | À chaud | Premier token | Mémoire |
|---|---|---|---|
| mlx-vlm + drafter MTP | **43,3** | 9 982 ms | 15,5 GB |
| rapid-mlx | 30,2 | 33 195 ms | 15,0 GB |
| mlx-lm | 28,8 | **432 ms** | 14,6 GB |

**+50 % de mlx-lm à mlx-vlm, sans rien changer d'autre que le serveur.** C'est la
comparaison la plus propre de la campagne : aucune différence de quantification à
discuter.

Et cela s'inverse aussitôt : les 50 % d'avance de mlx-vlm coûtent un **temps jusqu'au
premier token 23× pire**, parce qu'il n'a aucun cache de préfixe. Pour une génération
one-shot, il gagne. Pour un agent, il est inutilisable — et la raison est dans la section
suivante.

## Le drapeau qui rapporte 20 %, et pourquoi il est désactivé ⁽²⁾

Qwen3.8 embarque une **tête de prédiction multi-tokens à l'intérieur des poids**. Le
modèle propose plusieurs tokens d'avance, le moteur les vérifie en une seule passe avant.
Les moteurs qui implémentent la règle d'acceptation par ratio de probabilités préservent
exactement la distribution de sortie ; nous n'avons pas vérifié cette propriété
nous-mêmes, et il ne faut pas l'accepter sur parole depuis un benchmark — lisez
l'implémentation de votre moteur.

Presque tous les moteurs la livrent **désactivée**.

| Moteur | Drapeau | Activé par défaut ? |
|---|---|---|
| vmlx | `--native-mtp-depth` | **oui** |
| MTPLX | `--mtp --depth 3` | oui |
| vllm-mlx | `--enable-mtp` | non |
| llama.cpp | `--spec-type draft-mtp` | non |
| LM Studio | `--speculative-draft-mtp` | non |
| mlx-vlm | `--draft-kind mtp` + dépôt de drafter séparé | non |
| oMLX | ne s'est pas engagé sur Qwen3.8 dans nos runs | — |
| Ollama · mlx-lm · rapid-mlx | pas de support | — |

Nous avons mesuré le coût de l'ignorance sur le même fichier de poids, le même contexte
65 536, tout identique sauf deux drapeaux : **LM Studio passe de 23,1 à 27,8 tok/s,
+20 %.** Aucune interface graphique ne l'expose.

Effet de second ordre, et il compte davantage : **comparer deux moteurs sur leurs valeurs
par défaut revient à comparer deux régimes différents.** vmlx drafte, llama.cpp non.

## Le premier token s'étale sur 350×. Le prefill ne l'explique pas.

De 99 ms à 33 195 ms d'un bout à l'autre du tableau. Ce qui décide, c'est la
**granularité du cache de préfixe** — quelle part d'un prompt répété survit d'un tour à
l'autre. Mesuré sur la même phase (le tour à chaud, où la latence du premier token est
relevée) :

| Moteur | Réutilise | Re-prefill à chaque tour | Premier token |
|---|---|---|---|
| llama.cpp | 7 526 / 7 530 — **au token près** | 4 tokens | 125 ms |
| oMLX | 6 144 / 7 530 — **blocs de 1024 tokens** | 1 386 tokens | 1 944 ms |
| mlx-vlm | 0 / 7 530 | 7 530 tokens | 9 982 ms |

6 144, c'est six fois 1 024. oMLX réutilise des blocs entiers et re-prefill tout ce qui
n'en remplit pas un — 1 386 tokens, à chaque tour, indéfiniment. C'est là tout l'écart
entre 125 ms et 2 secondes.

⚠️ **Ne comparez pas entre moteurs les taux de réutilisation agrégés sur la session.**
Leurs plafonds diffèrent selon la part du prompt de test qui est cachable, et les comparer
produit des paradoxes qui disparaissent dès qu'on compare la même phase. Nous avons commis
cette erreur dans une version antérieure de cette page.

Nous ne publions **pas** de colonne de débit de prefill. Le nôtre provenait d'une unique
requête à froid non répétée, qui inclut, pour les moteurs à chargement paresseux, la
lecture de 20 GB sur disque — LM Studio a mesuré 216 tok/s sur cette requête et 938 sur la
suivante. Cela aurait été un chiffre fabriqué.

## Les tokens par seconde ne sont pas une vitesse

D'une quantification à l'autre d'un même modèle, les tok/s mesurent en partie la longueur
des sorties, pas leur vitesse d'arrivée :

| Build | tok/s | chars/s |
|---|---|---|
| Bare-Speed | 56,0 | 200,8 |
| Optimized-Speed | 44,4 | **203,1** |
| Optimized-Quality | 40,8 | 165,7 |

Bare-Speed mène de 26 % en tokens par seconde et se retrouve **derrière** en caractères
par seconde. Même tokenizer sur les trois — ce qui diffère, c'est ce que les
quantifications ont choisi d'écrire. Publiez la définition avec le chiffre.

## Ce que nous recommandons

**Pour un agent autonome local : MTPLX avec `Qwen3.8-27B-MTPLX-Optimized-Speed`, MTP en
profondeur 3.** Rapide, 99 ms jusqu'au premier token, réutilisation de préfixe au token
près, 27 GB.

Pas Bare-Speed, bien qu'il mène sur le papier. Les trois builds diffèrent par leur
divergence par rapport à bf16, publiée par l'auteur des quantifications : **0,00105** pour
Optimized-Quality, **0,0220** pour Optimized-Speed, **0,0376** pour Bare-Speed. Sa mesure,
pas la nôtre, non reproduite — mais c'est le seul chiffre de fidélité dont quiconque
dispose, et Bare-Speed se situe un ordre de grandeur au-dessus de Quality.

Pas Optimized-Quality non plus : il coûte **8,3 GB de plus** pour un avantage que personne
n'a démontré sur une tâche.

**Faites-le tourner avec le raisonnement actif.** Qwen recommande le niveau d'effort
`xhigh` pour le travail agentique, et indique que dans les tâches agentiques multi-tours un
effort plus faible *« peut conduire à une analyse insuffisante, à davantage d'échecs et à
des reprises répétées, ce qui peut augmenter la latence totale »*. MTPLX 2.7.1 signale par
ailleurs le raisonnement désactivé comme un problème connu sur Qwen3.8. À noter : `high`
n'existe pas sur ce modèle — Qwen n'expose que `low`, `medium` et `xhigh`, et `xhigh` est
la valeur par défaut.

## Ce que nous n'avons pas pu mesurer

**vmlx et vllm-mlx ont été tentés et manquent à l'appel.** Tous deux supportent le MTP
natif — vmlx l'a activé par défaut — donc leur absence est un vrai trou dans cette
comparaison, pas une erreur d'arrondi. vllm-mlx est mort au démarrage sur une erreur de
quoting en ligne de commande ; vmlx tournait encore au moment de la publication.

**Le raisonnement était désactivé partout, pour rendre les moteurs comparables.** C'est
une décision de mesure et non de déploiement — voir la recommandation ci-dessus. Nous
n'avons aucun chiffre à proposer sur ce que le raisonnement fait à ces moteurs, et nous
n'allons pas en extrapoler un.

**Réserves de version.** Les lignes MTPLX ont tourné sur **2.6.0**, avant que le moteur ne
livre une famille de modèles `qwen3_8` — il servait Qwen3.8 sous les valeurs par défaut de
Qwen3.6, dont un contrat d'échantillonnage différent. Cela n'affecte pas le débit ; cela
affecte tout ce qui touche au comportement. La ligne oMLX provient d'un build de
développement temporaire dont l'export n'a pas capturé la chaîne de version : cette ligne
n'est donc pas reproductible telle que publiée. Et notre export mlx-vlm s'auto-identifie
comme `mlxlm 0.31.3_2` — seul le log de lancement prouve que `mlx_vlm.server` était le
serveur.

**Le classement du premier token entre les trois builds MTPLX est à l'intérieur de son
propre bruit** — des coefficients de variation de 0,33 à 0,66 sur cette métrique. 99, 101
et 118 ms ne sont pas séparables. La colonne de débit est bien plus stable (CV 0,01-0,04).

**La dispersion test-retest sur des relances identiques de la même commande a atteint
7,5 %** (37,97 / 40,82 / 39,35 tok/s sur trois runs d'Optimized-Quality), et la mémoire a
bougé de 5 GB entre deux relances. Traitez tout écart inférieur à 8 % comme nul.

**Le réglage n'a pas été symétrique.** llama.cpp a reçu des drapeaux de cache explicites
(`--cache-reuse 256 --slot-prompt-similarity 0.5`, flash attention, 131k KV) que les
moteurs MLX n'ont pas eus. MTPLX a tourné sur `--profile turbo`, pas sur sa valeur par
défaut. C'est une comparaison de configurations que nous déploierions, pas des valeurs par
défaut sorties de la boîte.

## Reproduire ces mesures

Chaque chiffre provient d'une carte certifiée produite par [asiai](https://asiai.dev), par
un chemin scripté unique avec gates de solitude, preuves d'identité du modèle servi et
échantillonnage thermique. Exports bruts disponibles.

S'il ne faut retenir qu'une chose : **vérifiez si votre moteur dispose de la prédiction
multi-tokens, et si elle est activée.**
