---
title: "Benchmark TurboQuant sur Apple Silicon : faire tourner des modèles 70B sur Mac"
description: "Benchmarks réels de la compression KV cache TurboQuant sur Mac Mini M4 Pro 64 Go : Llama 70B à 6,3 tok/s avec 5x d'économie mémoire. Guide d'installation et résultats."
type: article
date: 2026-03-31
updated: 2026-03-31
faq:
  - q: "Peut-on faire tourner un modèle 70B sur un Mac avec 64 Go de RAM ?"
    a: "Oui, avec TurboQuant. Le KV cache est compressé 5x, donc Llama 70B Q4_K_M (40 Go de poids) tient confortablement dans 64 Go avec un contexte de 32K. Nous avons mesuré 6,3 tok/s sur un Mac Mini M4 Pro."
  - q: "TurboQuant réduit-il la qualité ?"
    a: "Aucune perte de qualité mesurable. L'augmentation de la perplexité est inférieure à 1 % par rapport à q8_0, et le score de récupération Needle-in-a-Haystack atteint 100 % sur un contexte de 32K."
  - q: "Quel format TurboQuant utiliser ?"
    a: "Nous recommandons le mode asymétrique : q8_0 pour les clés (sensibles à la compression) et turbo3 pour les valeurs (compression 5x, sans impact sur la qualité). Ceci est basé sur les résultats du projet turboquant_plus."
  - q: "TurboQuant fonctionne-t-il avec les moteurs MLX ?"
    a: "Des implémentations MLX communautaires existent mais sont moins matures que le fork llama.cpp. Pour un usage en production sur Apple Silicon, nous recommandons TheTom/llama-cpp-turboquant avec les kernels Metal."
  - q: "TurboQuant est-il plus rapide ?"
    a: "La vitesse de décodage est d'environ 0,9x par rapport à q8_0 (légèrement plus lent par token), mais le prefill peut être plus rapide sur de longs contextes grâce à la réduction de la bande passante mémoire. Le vrai gain est de faire tenir des modèles plus grands et des contextes plus longs dans la même RAM."
---

# Benchmark TurboQuant sur Apple Silicon

TurboQuant (Google Research, ICLR 2026) compresse le KV cache des LLM de 5x sans perte de qualité, permettant de faire tourner des modèles 70B sur un Mac Mini avec 64 Go de RAM. Voici des benchmarks réels mesurés avec [asiai](/) sur du matériel réel.

## Résultats

**Llama-3.1-70B-Instruct Q4_K_M sur Mac Mini M4 Pro 64 Go**

| Métrique | Valeur |
|----------|--------|
| **Débit** | 6,3 tok/s (stable, IC 95 % : 6,3-6,3) |
| **TTFT** | 196 ms (médiane) |
| **Puissance GPU** | 23,8 W |
| **VRAM modèle** | 44,1 Go (40 Go poids + 4 Go KV turbo3) |
| **Contexte** | 32 768 tokens |
| **GPU Offload** | 81/81 couches sur Metal |
| **Thermique** | Nominal (pas de throttling) |
| **Stabilité** | Stable (écart-type 0,04 tok/s sur 3 exécutions) |

Configuration du KV cache : clés en q8_0 (haute précision), valeurs en turbo3 (3 bits, compression 5x).

## Avant vs Après TurboQuant

| | Sans TurboQuant | Avec TurboQuant (turbo3) |
|--|-----------------|--------------------------|
| **KV cache (ctx 32K)** | ~20 Go (q8_0) | ~4 Go (turbo3) |
| **RAM totale nécessaire** | 60+ Go (OOM sur 64 Go) | 44 Go (tient dans 64 Go) |
| **Peut-on faire tourner 70B sur 64 Go ?** | Non | **Oui** |
| **Qualité** | Référence | -1 % PPL (négligeable) |
| **Récupération NIAH** | 100 % | 100 % |

## Qu'est-ce que TurboQuant ?

TurboQuant est un algorithme de compression du KV cache développé par Google Research, présenté à l'ICLR 2026. Pendant l'inférence des LLM, le KV cache stocke les états d'attention intermédiaires et croît linéairement avec la longueur du contexte. Pour un modèle 70B avec un contexte de 128K en FP16, ce cache seul peut consommer 20 à 40 Go de RAM.

TurboQuant compresse ce cache à 3 bits par valeur en utilisant :

- **Rotation aléatoire** (transformée de Walsh-Hadamard) pour gaussianiser les données
- **Quantification scalaire optimale** (PolarQuant) proche de la limite de Shannon
- **QJL** (Quantized Johnson-Lindenstrauss) pour préserver les produits scalaires

Le résultat : 5x de réduction mémoire, pas de fine-tuning nécessaire, et une perte de qualité quasi nulle.

## Guide d'installation

### Matériel

- Mac Mini M4 Pro, 64 Go de mémoire unifiée (2 700 $)
- Tout Mac Apple Silicon avec 32+ Go devrait fonctionner (ajustez la taille du modèle en conséquence)

### Installer TurboQuant llama.cpp

```bash
# Install build tools
brew install cmake

# Clone the TurboQuant fork
git clone https://github.com/TheTom/llama-cpp-turboquant.git
cd llama-cpp-turboquant
git checkout feature/turboquant-kv-cache

# Build with Metal (Apple Silicon GPU)
cmake -B build -DGGML_METAL=ON -DGGML_METAL_EMBED_LIBRARY=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(sysctl -n hw.ncpu)
```

### Télécharger un modèle

```bash
# Llama 3.1 70B Q4_K_M (~40 GB)
curl -L -o llama-3.1-70b-q4_k_m.gguf \
  "https://huggingface.co/bartowski/Meta-Llama-3.1-70B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-70B-Instruct-Q4_K_M.gguf"
```

### Augmenter la limite mémoire GPU de macOS

```bash
sudo sysctl iogpu.wired_limit_mb=61440
```

### Lancer le serveur

```bash
./build/bin/llama-server \
  -m llama-3.1-70b-q4_k_m.gguf \
  --cache-type-k q8_0 --cache-type-v turbo3 \
  -c 32768 \
  --port 8081 \
  --host 0.0.0.0 \
  -fa 1 \
  -ngl 99 \
  -t 10 \
  --no-mmap \
  --chat-template chatml
```

### Explication de la configuration

| Paramètre | Valeur | Pourquoi |
|-----------|--------|----------|
| `--cache-type-k q8_0` | Clés en 8 bits | Les clés sont sensibles à la compression |
| `--cache-type-v turbo3` | Valeurs en 3 bits | Les valeurs tolèrent une compression extrême (5x) |
| `-fa 1` | Flash Attention | Requis pour TurboQuant |
| `-ngl 99` | GPU offload complet | Les 81 couches sur Metal |
| `-t 10` | 10 threads | Le M4 Pro a 10 coeurs de performance |
| `--no-mmap` | Pas de memory mapping | Charge tout au démarrage, évite les défauts de page |
| `--chat-template chatml` | Format ChatML | Meilleure compatibilité avec ce fork |

## Benchmark avec asiai

```bash
pip install asiai
asiai detect --url http://localhost:8081
asiai bench --engines llamacpp --prompts code --runs 3 --kv-cache turbo3 --card
```

## Modèles compatibles 64 Go avec TurboQuant

| Modèle | Poids (Q4_K_M) | KV Cache (32K, turbo3) | Total | Statut |
|--------|-----------------|----------------------|-------|--------|
| Llama 3.1 70B | 40 Go | ~4 Go | 44 Go | **Testé : 6,3 tok/s** |
| Qwen2.5 72B | 40 Go | ~4 Go | 44 Go | Devrait fonctionner |
| Llama 70B ctx 128K | 40 Go | ~16 Go (turbo3) | 56 Go | Serré mais possible |
| Command-R+ 104B | 58 Go | ~4 Go | 62 Go | Très serré |

## FAQ

**Peut-on faire tourner un modèle 70B sur un Mac avec 64 Go de RAM ?**

Oui, avec TurboQuant. Le KV cache est compressé 5x, donc Llama 70B Q4_K_M (40 Go de poids) tient confortablement dans 64 Go avec un contexte de 32K. Nous avons mesuré 6,3 tok/s sur un Mac Mini M4 Pro.

**TurboQuant réduit-il la qualité ?**

Aucune perte de qualité mesurable. L'augmentation de la perplexité est inférieure à 1 % par rapport à q8_0, et le score de récupération Needle-in-a-Haystack atteint 100 % sur un contexte de 32K.

**Quel format TurboQuant utiliser ?**

Asymétrique : q8_0 pour les clés + turbo3 pour les valeurs. Les clés sont sensibles à la compression (toute la dégradation de qualité vient de la compression des K). Les valeurs peuvent être compressées à 2-3 bits sans aucun effet sur la qualité de l'attention.

**TurboQuant fonctionne-t-il avec MLX ?**

Des implémentations communautaires existent ([turboquant-mlx](https://github.com/helgklaizar/turboquant_mlx)) mais sont moins matures que le fork llama.cpp. Pour un usage en production, nous recommandons [TheTom/llama-cpp-turboquant](https://github.com/TheTom/llama-cpp-turboquant).

**Comment cela se compare-t-il au llama.cpp standard ?**

La vitesse de décodage est d'environ 0,9x par rapport à q8_0 (légèrement plus lent par token), mais le vrai gain est de faire tenir des modèles et des contextes qui ne tenaient tout simplement pas avant. Le prefill peut en fait être plus rapide sur de longs contextes grâce à la réduction de la pression sur la bande passante mémoire.

## Références

- [Google Research Blog — TurboQuant](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/)
- [TurboQuant Paper (ICLR 2026)](https://arxiv.org/abs/2504.19874)
- [TheTom/turboquant_plus](https://github.com/TheTom/turboquant_plus) — Implémentation étendue avec Sparse V
- [TheTom/llama-cpp-turboquant](https://github.com/TheTom/llama-cpp-turboquant) — Fork llama.cpp avec kernels Metal
- [llama.cpp Discussion #20969](https://github.com/ggml-org/llama.cpp/discussions/20969) — Fil de discussion communautaire
