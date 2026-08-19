---
title: "Le meilleur moteur pour un agent local sur Qwen3.8-27B : MTPLX, et ce n'est pas serré"
description: "Onze configurations, huit moteurs, un M5 Max. Pour du travail d'agent, le gagnant prend toutes les mesures qui comptent : 99 ms au premier jeton, réutilisation de préfixe au token près, 44 tok/s, 27 Go. Et le drapeau qui rapporte 20 à 50 % est éteint par défaut chez quatre des six moteurs qui le supportent."
type: article
date: 2026-08-16
updated: 2026-08-16
---

# Le meilleur moteur pour un agent local sur Qwen3.8-27B

**Lancez MTPLX avec `Qwen3.8-27B-MTPLX-Optimized-Speed` et `--mtp --depth 3`.**

Nous avons mesuré onze configurations sur huit moteurs, sur un seul M5 Max. Pour du
travail d'agent, il gagne sur toutes les mesures qui comptent, et le deuxième n'est pas
près :

| | MTPLX Optimized-Speed | llama.cpp b10434 +MTP | Ollama 0.32.13 |
|---|---|---|---|
| Premier jeton | **99 ms** | 125 ms | 240 ms |
| Premier jeton, 56k froid | **301 ms** | 365 ms | 574 ms |
| Réutilisation de préfixe | **7 530 / 7 530** | 7 526 / 7 530 | 0 / 7 530 |
| Débit | **44,4 tok/s** | 31,8 | 32,8 |
| Mémoire | **27 Go** | 36,8 Go | 30,3 Go |

Face à llama.cpp — le plus proche sur la latence — cela fait +40 % de débit, 26 ms de
moins par tour et 10 Go de mémoire en moins. Ollama est le plus rapide des autres à
32,8 tok/s, donc l'avance en débit sur le champ entier est de +35 %. C'est ce que nous
faisons tourner en production.

## Pourquoi ces mesures, et pas les tokens par seconde

Un agent n'est pas un chat. Il ne déroule pas une longue réponse d'un trait — il enchaîne
des dizaines de tours courts, et **chaque tour relit tout ce qui précède**. Le chiffre que
vous ressentez est donc le temps au premier jeton, payé une fois par tour, et il dépend
presque entièrement de la capacité du moteur à garder le prompt précédent en cache.

Sur le tableau complet, le premier jeton s'étale sur **335×** (de 99 ms à 33 secondes)
quand le débit ne s'étale que sur **2,4×** (de 23,1 à 56,0 tok/s). Et dès qu'on fixe le
fichier de poids et qu'on coupe la spéculation des deux côtés, le débit tombe à **4,9 %**
— du bruit — alors que le premier jeton diffère encore d'un facteur 77. Dans les deux cas
la même conclusion : pour un agent, choisissez sur la latence et la réutilisation de
préfixe ; le débit départage les ex æquo.

Deux moteurs réutilisent au token près (MTPLX, llama.cpp). Un réutilise par blocs de
1 024 tokens et recalcule 1 386 tokens *à chaque tour, indéfiniment* (oMLX, 1 968 ms).
Trois ne réutilisent rien du tout et repaient le prompt entier à chaque fois — mlx-vlm à
9 982 ms, rapid-mlx à 33 195 ms. Sur une session d'agent de 60 tours, ce dernier coûte
**33 minutes d'attente pure**.

## Le tableau complet

« À chaud » et « à 56k » sont des tok/s. Premier jeton sur le tour à chaud ; @56k sur un
prompt froid de 55 839 tokens.

| Moteur | Poids | À chaud | À 56k | Premier jeton | @56k | Mémoire | tok/s/W |
|---|---|---|---|---|---|---|---|
| MTPLX Bare-Speed | MTPLX 4 bits g64 | **56,0** | **46,5** | 101 ms | 322 ms | 22,0 Go | 0,694 |
| **MTPLX Optimized-Speed** | MTPLX 4 bits g32 | 44,4 | 37,5 | **99 ms** | **301 ms** | 27,0 Go | 0,623 |
| mlx-vlm + drafter MTP | MLX 4 bits ⁽¹⁾ | 43,3 | 28,9 | 9 982 ms | 100 733 ms | 15,5 Go | **0,744** |
| MTPLX Optimized-Quality | MTPLX 8 bits g64 | 40,8 | 30,3 | 118 ms | 100 243 ms | 32,9 Go | 0,575 |
| Ollama 0.32.13 | GGUF (non déclaré) | 32,8 | 21,7 | 240 ms | 574 ms | 30,3 Go | 0,451 |
| llama.cpp b10434 + MTP | GGUF Q5_K_XL ⁽²⁾ | 31,8 | 22,7 | 125 ms | 365 ms | 36,8 Go | 0,395 |
| rapid-mlx 0.12.11 | MLX 4 bits ⁽¹⁾ | 30,2 | 24,7 | 33 195 ms | 287 548 ms | 15,0 Go | 0,544 |
| oMLX 0.6.0-dev | oQ4e-mtp (tiers) | 29,8 | 24,6 | 1 968 ms | 1 991 ms | 16,7 Go | 0,512 |
| mlx-lm 0.31.3 | MLX 4 bits ⁽¹⁾ | 28,8 | 24,0 | 432 ms | 799 ms | **14,6 Go** | 0,472 |
| LM Studio 0.4.21 **+MTP** | GGUF Q5_K_XL ⁽²⁾ | 27,8 | 23,4 | 419 ms | 825 ms | 36,3 Go | 0,422 |
| LM Studio 0.4.21 par défaut | GGUF Q5_K_XL ⁽²⁾ | 23,1 | 18,7 | 359 ms | 865 ms | 35,2 Go | 0,351 |

⁽¹⁾ ⁽²⁾ = fichier de poids identique au bit près. Les lignes MTPLX ont tourné sur la
2.6.0. Une cellule, un export. Toutes les colonnes sont des médianes du tour à chaud.
`tok/s/W` divise le débit de décodage par la puissance du **SoC entier** (de 58 à 83 W
selon le moteur) — pas du GPU seul, qui classerait autrement.

**Comment le lire.** Les écarts de débit inférieurs à 8 % sont du bruit : d'Ollama à
LM Studio+MTP (32,8 à 27,8), ces moteurs sont à égalité, pas classés. Les deux entrées à
100 secondes sont des défauts de cache, pas une vitesse de moteur : Optimized-Quality fait
118 ms à chaud et revient à 498 ms sur le tour 56k répété. La mémoire n'est pas comparable
entre familles (llama.cpp mappe son fichier : 36,8 Go résidents = 19,4 Go physiques).

## Ce qui surprend : le serveur ne compte presque pas

mlx-vlm, mlx-lm et rapid-mlx ont servi le *même fichier*,
`lmstudio-community/Qwen3.8-27B-MLX-4bit`, snapshot `6067b15c`, octet pour octet. Deux
d'entre eux tournaient nus, sans spéculation :

**30,2 contre 28,8 tok/s. Un écart de 4,9 % — sous notre propre bruit de relance.**

Changer de serveur MLX ne rapporte rien. Le troisième, mlx-vlm, atteint 43,3 — mais il
tournait avec le drafter MTP chargé. **Ces +50 % viennent du drapeau, pas du serveur** —
voir l'annexe sur la prédiction multi-token, qui arrive à la même conclusion par l'autre
bout.

## Choisir sous une autre contrainte

Notre recommandation optimise le travail d'agent. Si la vôtre diffère, le tableau répond
déjà :

- **Empreinte minimale** → mlx-lm, 14,6 Go. Vous perdez la granularité du cache de préfixe.
- **Meilleure autonomie** → mlx-vlm, 0,744 tok/s/W. Inutilisable pour un agent (9 982 ms au
  premier jeton), excellent en traitement par lots.
- **Débit brut** → MTPLX Bare-Speed, 56,0 tok/s. Nous le déconseillons : l'auteur des
  quantifications publie une divergence par rapport à bf16 de 0,0376 contre 0,0220 pour
  Optimized-Speed — 36× plus loin de bf16 que le build 8 bits. Sa mesure, pas la nôtre, non
  reproduite.
- **Vous êtes déjà sur llama.cpp** → restez-y. Ajoutez `--spec-type draft-mtp` et vous
  comblez l'essentiel de l'écart ; 125 ms au premier jeton conviennent à un agent.

## Faites-le tourner avec le raisonnement actif

Qwen recommande `xhigh` pour le travail agentique et avertit qu'un effort plus faible
*« peut conduire à une analyse insuffisante, à davantage d'échecs et à des reprises
répétées »*. MTPLX 2.7.1 signale par ailleurs le raisonnement désactivé comme un problème
connu sur Qwen3.8. `high` n'existe pas sur ce modèle — `low`, `medium`, `xhigh` seulement,
et `xhigh` est la valeur par défaut.

⚠️ À noter : le niveau d'effort est une **variable de gabarit de conversation, pas un champ
d'API** — envoyé comme paramètre de requête ordinaire, il est ignoré en silence. Il doit
être posé au lancement.

## Quatre limites qui changent votre lecture

1. **Rien ici n'a mené une tâche à son terme.** La sortie était plafonnée à 400 tokens et
   chaque exécution a atteint ce plafond. Ce sont des débits de flux sur des continuations
   tronquées.
2. **Le raisonnement était coupé pour toutes les mesures**, afin de rendre les moteurs
   comparables. Ce n'est pas ainsi que nous déployons — voir plus haut. Nous n'avons aucun
   chiffre sur ce que le raisonnement coûte à chaque moteur.
3. **Les réglages n'étaient pas symétriques.** llama.cpp a reçu des drapeaux de cache
   explicites que les moteurs MLX n'ont pas eus ; MTPLX tournait en `--profile turbo` ; les
   paramètres d'échantillonnage et les limites thermiques diffèrent d'un moteur à l'autre.
   Les écarts *entre familles* sont indicatifs, pas propres.
4. **Nous recommandons le moteur qui seul sait lire son propre format de quantification,
   mesuré avec notre propre outil, publié sur notre propre site.** Les lignes MTPLX sont les
   seules où moteur et format de poids ne peuvent pas être séparés. Pesez-le en conséquence
   — la table des drapeaux, en annexe, est la partie de cette page qu'il ne nous coûte rien
   d'avoir juste.

Deux moteurs à MTP natif, vmlx et vllm-mlx, n'ont pas pu être mesurés à temps.

## Annexe : le drapeau MTP, moteur par moteur

Qwen3.8 embarque une tête de prédiction multi-token **dans ses poids**. Le modèle propose
plusieurs tokens d'avance, le moteur les vérifie en une passe. Quatre des six moteurs qui
la supportent la livrent **éteinte**.

| Moteur | Drapeau | Activé d'origine ? |
|---|---|---|
| MTPLX ⁽ᵐ⁾ | `--mtp --depth 3` | **oui** |
| vmlx ⁽ᵈ⁾ | `--native-mtp-depth` | **oui** |
| llama.cpp ⁽ᵐ⁾ | `--spec-type draft-mtp --spec-draft-n-max 4` | non |
| LM Studio ⁽ᵐ⁾ | `--speculative-draft-mtp` | non |
| mlx-vlm ⁽ᵐ⁾ | `--draft-kind mtp --draft-model mlx-community/Qwen3.8-27B-MTP-4bit` | non |
| vllm-mlx ⁽ᵈ⁾ | `--enable-mtp` | non |
| Ollama · mlx-lm · rapid-mlx | pas de support | — |

⁽ᵐ⁾ attesté par nos propres lignes de lancement et journaux. ⁽ᵈ⁾ d'après la documentation
du projet uniquement.

**Nous avons mesuré ce que coûte l'ignorance** : même fichier de poids, même contexte de
65 536, même séquence thermique, tout identique sauf deux drapeaux. **LM Studio passe de
23,1 à 27,8 tok/s, soit +19,9 %.** Aucune interface graphique ne le montre. Sur mlx-vlm, la
même tête vaut +50 %.

À noter : le drafter est embarqué dans le GGUF pour llama.cpp et LM Studio, mais mlx-vlm
exige un **second dépôt** téléchargé à côté.

**Vérifiez qu'il est réellement engagé** — un drapeau accepté n'est pas un drapeau qui
fonctionne :

```
# llama.cpp / LM Studio — le journal doit mentionner un contexte de draft au démarrage
grep -i "draft" server.log        # « creating MTP draft context »
# tout moteur compatible OpenAI — le taux d'acceptation doit être à 0,9 ou plus
curl -s localhost:8080/v1/chat/completions -d '…' | jq '.timings'
```

## Reproduire ceci

Chaque chiffre vient d'une carte certifiée produite par [asiai](https://asiai.dev), via un
chemin unique et scripté, avec gates de solitude, preuves d'identité du modèle servi et
échantillonnage thermique. Exports bruts, lignes de lancement complètes et texte des
prompts : demandez-les et nous les publions.

Si vous ne retenez qu'une chose : **vérifiez si votre moteur dispose de la prédiction
multi-token, et si elle est activée.**
