---
title: "Benchmark TurboQuant no Apple Silicon: Execute Modelos 70B no Mac"
description: "Benchmarks reais de compressao TurboQuant KV cache no Mac Mini M4 Pro 64GB: Llama 70B a 6.3 tok/s com 5x de economia de memoria. Guia de configuracao e resultados."
type: article
date: 2026-03-31
updated: 2026-03-31
faq:
  - q: "Posso executar um modelo 70B em um Mac com 64GB de RAM?"
    a: "Sim, com TurboQuant. O KV cache e comprimido 5x, entao o Llama 70B Q4_K_M (40GB de pesos) cabe confortavelmente em 64GB com contexto de 32K. Medimos 6.3 tok/s em um Mac Mini M4 Pro."
  - q: "O TurboQuant reduz a qualidade?"
    a: "Nenhuma perda de qualidade mensuravel. O aumento de perplexidade e inferior a 1% em relacao ao q8_0, e a recuperacao Needle-in-a-Haystack atinge 100% em todo o contexto de 32K."
  - q: "Qual formato TurboQuant devo usar?"
    a: "Recomendamos assimetrico: q8_0 para keys (sensiveis a compressao) e turbo3 para values (compressao 5x, sem impacto na qualidade). Isso e baseado nas descobertas do projeto turboquant_plus."
  - q: "O TurboQuant funciona com engines MLX?"
    a: "Implementacoes MLX da comunidade existem, mas sao menos maduras que o fork llama.cpp. Para uso em producao no Apple Silicon, recomendamos TheTom/llama-cpp-turboquant com kernels Metal."
  - q: "Quao mais rapido e o TurboQuant?"
    a: "A velocidade de decode e cerca de 0.9x do q8_0 (ligeiramente mais lento por token), mas o prefill pode ser mais rapido em contextos longos devido a reducao da largura de banda de memoria. O ganho real e encaixar modelos maiores e contextos mais longos na mesma RAM."
---

# Benchmark TurboQuant no Apple Silicon

TurboQuant (Google Research, ICLR 2026) comprime o KV cache de LLMs em 5x sem perda de qualidade, permitindo que modelos 70B sejam executados em um Mac Mini com 64GB de RAM. Estes sao benchmarks reais medidos com [asiai](/) em hardware real.

## Resultados

**Llama-3.1-70B-Instruct Q4_K_M no Mac Mini M4 Pro 64GB**

| Metrica | Valor |
|---------|-------|
| **Throughput** | 6.3 tok/s (estavel, IC 95%: 6.3-6.3) |
| **TTFT** | 196 ms (mediana) |
| **GPU Power** | 23.8 W |
| **Model VRAM** | 44.1 GB (40 GB pesos + 4 GB KV turbo3) |
| **Context** | 32,768 tokens |
| **GPU Offload** | 81/81 camadas no Metal |
| **Thermal** | Nominal (sem throttling) |
| **Stability** | Estavel (desvio padrao 0.04 tok/s em 3 execucoes) |

Configuracao do KV cache: keys em q8_0 (alta precisao), values em turbo3 (3-bit, compressao 5x).

## Antes vs Depois do TurboQuant

| | Sem TurboQuant | Com TurboQuant (turbo3) |
|--|----------------|-------------------------|
| **KV cache (32K ctx)** | ~20 GB (q8_0) | ~4 GB (turbo3) |
| **RAM total necessaria** | 60+ GB (OOM em 64GB) | 44 GB (cabe em 64GB) |
| **Consegue rodar 70B em 64GB?** | Nao | **Sim** |
| **Qualidade** | Baseline | -1% PPL (desprezivel) |
| **NIAH retrieval** | 100% | 100% |

## O que e TurboQuant?

TurboQuant e um algoritmo de compressao de KV cache do Google Research, apresentado no ICLR 2026. Durante a inferencia de LLMs, o KV cache armazena estados intermediarios de atencao e cresce linearmente com o comprimento do contexto. Para um modelo 70B com contexto de 128K em FP16, esse cache sozinho pode consumir 20-40 GB de RAM.

TurboQuant comprime esse cache para 3 bits por valor usando:

- **Rotacao aleatoria** (transformada Walsh-Hadamard) para Gaussianizar os dados
- **Quantizacao escalar otima** (PolarQuant) proximo ao limite de Shannon
- **QJL** (Quantized Johnson-Lindenstrauss) para preservar produtos escalares

O resultado: reducao de memoria de 5x, sem necessidade de fine-tuning e perda de qualidade proxima de zero.

## Guia de Configuracao

### Hardware

- Mac Mini M4 Pro, 64 GB de memoria unificada ($2,700)
- Qualquer Mac Apple Silicon com 32+ GB deve funcionar (ajuste o tamanho do modelo de acordo)

### Instalar o llama.cpp com TurboQuant

```bash
# Instalar ferramentas de compilacao
brew install cmake

# Clonar o fork TurboQuant
git clone https://github.com/TheTom/llama-cpp-turboquant.git
cd llama-cpp-turboquant
git checkout feature/turboquant-kv-cache

# Compilar com Metal (GPU Apple Silicon)
cmake -B build -DGGML_METAL=ON -DGGML_METAL_EMBED_LIBRARY=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(sysctl -n hw.ncpu)
```

### Baixar um Modelo

```bash
# Llama 3.1 70B Q4_K_M (~40 GB)
curl -L -o llama-3.1-70b-q4_k_m.gguf \
  "https://huggingface.co/bartowski/Meta-Llama-3.1-70B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-70B-Instruct-Q4_K_M.gguf"
```

### Aumentar o Limite de Memoria GPU do macOS

```bash
sudo sysctl iogpu.wired_limit_mb=61440
```

### Iniciar o Servidor

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

### Explicacao da Configuracao

| Parametro | Valor | Por que |
|-----------|-------|---------|
| `--cache-type-k q8_0` | Keys em 8-bit | Keys sao sensiveis a compressao |
| `--cache-type-v turbo3` | Values em 3-bit | Values toleram compressao extrema (5x) |
| `-fa 1` | Flash Attention | Necessario para TurboQuant |
| `-ngl 99` | GPU offload completo | Todas as 81 camadas no Metal |
| `-t 10` | 10 threads | M4 Pro tem 10 nucleos de performance |
| `--no-mmap` | Sem mapeamento de memoria | Carrega tudo no boot, evita page faults |
| `--chat-template chatml` | Formato ChatML | Melhor compatibilidade com este fork |

## Benchmark com asiai

```bash
pip install asiai
asiai detect --url http://localhost:8081
asiai bench --engines llamacpp --prompts code --runs 3 --kv-cache turbo3 --card
```

## Modelos que Cabem em 64GB com TurboQuant

| Modelo | Pesos (Q4_K_M) | KV Cache (32K, turbo3) | Total | Status |
|--------|-----------------|----------------------|-------|--------|
| Llama 3.1 70B | 40 GB | ~4 GB | 44 GB | **Testado: 6.3 tok/s** |
| Qwen2.5 72B | 40 GB | ~4 GB | 44 GB | Deve funcionar |
| Llama 70B 128K ctx | 40 GB | ~16 GB (turbo3) | 56 GB | Apertado mas possivel |
| Command-R+ 104B | 58 GB | ~4 GB | 62 GB | Muito apertado |

## FAQ

**Posso executar um modelo 70B em um Mac com 64GB de RAM?**

Sim, com TurboQuant. O KV cache e comprimido 5x, entao o Llama 70B Q4_K_M (40GB de pesos) cabe confortavelmente em 64GB com contexto de 32K. Medimos 6.3 tok/s em um Mac Mini M4 Pro.

**O TurboQuant reduz a qualidade?**

Nenhuma perda de qualidade mensuravel. O aumento de perplexidade e inferior a 1% em relacao ao q8_0, e a recuperacao Needle-in-a-Haystack atinge 100% em todo o contexto de 32K.

**Qual formato TurboQuant devo usar?**

Assimetrico: q8_0 para keys + turbo3 para values. Keys sao sensiveis a compressao (toda degradacao de qualidade vem da compressao de K). Values podem ser comprimidos para 2-3 bits sem nenhum efeito na qualidade da atencao.

**O TurboQuant funciona com MLX?**

Implementacoes da comunidade existem ([turboquant-mlx](https://github.com/helgklaizar/turboquant_mlx)), mas sao menos maduras que o fork llama.cpp. Para uso em producao, recomendamos [TheTom/llama-cpp-turboquant](https://github.com/TheTom/llama-cpp-turboquant).

**Como isso se compara ao llama.cpp padrao?**

A velocidade de decode e ~0.9x do q8_0 (ligeiramente mais lento por token), mas o ganho real e encaixar modelos e contextos que simplesmente nao cabiam antes. O prefill pode na verdade ser mais rapido em contextos longos devido a reducao da pressao na largura de banda de memoria.

## Referencias

- [Google Research Blog — TurboQuant](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/)
- [TurboQuant Paper (ICLR 2026)](https://arxiv.org/abs/2504.19874)
- [TheTom/turboquant_plus](https://github.com/TheTom/turboquant_plus) — Implementacao estendida com Sparse V
- [TheTom/llama-cpp-turboquant](https://github.com/TheTom/llama-cpp-turboquant) — Fork llama.cpp com kernels Metal
- [llama.cpp Discussion #20969](https://github.com/ggml-org/llama.cpp/discussions/20969) — Thread da comunidade
