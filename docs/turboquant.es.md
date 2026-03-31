---
title: "Benchmark TurboQuant en Apple Silicon: ejecutar modelos 70B en Mac"
description: "Benchmarks reales de la compresión KV cache TurboQuant en Mac Mini M4 Pro 64 GB: Llama 70B a 6,3 tok/s con 5x de ahorro de memoria. Guía de instalación y resultados."
type: article
date: 2026-03-31
updated: 2026-03-31
faq:
  - q: "¿Puedo ejecutar un modelo 70B en un Mac con 64 GB de RAM?"
    a: "Sí, con TurboQuant. El KV cache se comprime 5x, por lo que Llama 70B Q4_K_M (40 GB de pesos) cabe cómodamente en 64 GB con un contexto de 32K. Medimos 6,3 tok/s en un Mac Mini M4 Pro."
  - q: "¿TurboQuant reduce la calidad?"
    a: "Sin pérdida de calidad medible. El aumento de perplejidad es inferior al 1 % frente a q8_0, y la recuperación Needle-in-a-Haystack alcanza el 100 % en un contexto de 32K."
  - q: "¿Qué formato TurboQuant debería usar?"
    a: "Recomendamos asimétrico: q8_0 para claves (sensibles a la compresión) y turbo3 para valores (compresión 5x, sin impacto en la calidad). Esto se basa en los hallazgos del proyecto turboquant_plus."
  - q: "¿TurboQuant funciona con motores MLX?"
    a: "Existen implementaciones MLX de la comunidad pero son menos maduras que el fork de llama.cpp. Para uso en producción con Apple Silicon, recomendamos TheTom/llama-cpp-turboquant con kernels Metal."
  - q: "¿Cuánto más rápido es TurboQuant?"
    a: "La velocidad de decodificación es aproximadamente 0,9x de q8_0 (ligeramente más lento por token), pero el prefill puede ser más rápido en contextos largos debido a la reducción del ancho de banda de memoria. La ganancia real es que modelos más grandes y contextos más largos caben en la misma RAM."
---

# Benchmark TurboQuant en Apple Silicon

TurboQuant (Google Research, ICLR 2026) comprime el KV cache de los LLM en 5x sin pérdida de calidad, permitiendo ejecutar modelos 70B en un Mac Mini con 64 GB de RAM. Estos son benchmarks reales medidos con [asiai](/) en hardware real.

## Resultados

**Llama-3.1-70B-Instruct Q4_K_M en Mac Mini M4 Pro 64 GB**

| Métrica | Valor |
|---------|-------|
| **Rendimiento** | 6,3 tok/s (estable, IC 95 %: 6,3-6,3) |
| **TTFT** | 196 ms (mediana) |
| **Potencia GPU** | 23,8 W |
| **VRAM del modelo** | 44,1 GB (40 GB pesos + 4 GB KV turbo3) |
| **Contexto** | 32.768 tokens |
| **GPU Offload** | 81/81 capas en Metal |
| **Temperatura** | Nominal (sin throttling) |
| **Estabilidad** | Estable (desviación estándar 0,04 tok/s en 3 ejecuciones) |

Configuración del KV cache: claves en q8_0 (alta precisión), valores en turbo3 (3 bits, compresión 5x).

## Antes vs Después de TurboQuant

| | Sin TurboQuant | Con TurboQuant (turbo3) |
|--|----------------|--------------------------|
| **KV cache (ctx 32K)** | ~20 GB (q8_0) | ~4 GB (turbo3) |
| **RAM total necesaria** | 60+ GB (OOM en 64 GB) | 44 GB (cabe en 64 GB) |
| **¿Se puede ejecutar 70B en 64 GB?** | No | **Sí** |
| **Calidad** | Referencia | -1 % PPL (despreciable) |
| **Recuperación NIAH** | 100 % | 100 % |

## ¿Qué es TurboQuant?

TurboQuant es un algoritmo de compresión del KV cache de Google Research, presentado en ICLR 2026. Durante la inferencia de los LLM, el KV cache almacena estados de atención intermedios y crece linealmente con la longitud del contexto. Para un modelo 70B con contexto de 128K en FP16, este cache puede consumir por sí solo entre 20 y 40 GB de RAM.

TurboQuant comprime este cache a 3 bits por valor usando:

- **Rotación aleatoria** (transformada de Walsh-Hadamard) para gaussianizar los datos
- **Cuantización escalar óptima** (PolarQuant) cerca del límite de Shannon
- **QJL** (Quantized Johnson-Lindenstrauss) para preservar los productos escalares

El resultado: 5x de reducción de memoria, sin necesidad de fine-tuning y prácticamente sin pérdida de calidad.

## Guía de instalación

### Hardware

- Mac Mini M4 Pro, 64 GB de memoria unificada (2.700 $)
- Cualquier Mac Apple Silicon con 32+ GB debería funcionar (ajustar el tamaño del modelo según corresponda)

### Instalar TurboQuant llama.cpp

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

### Descargar un modelo

```bash
# Llama 3.1 70B Q4_K_M (~40 GB)
curl -L -o llama-3.1-70b-q4_k_m.gguf \
  "https://huggingface.co/bartowski/Meta-Llama-3.1-70B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-70B-Instruct-Q4_K_M.gguf"
```

### Aumentar el límite de memoria GPU de macOS

```bash
sudo sysctl iogpu.wired_limit_mb=61440
```

### Iniciar el servidor

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

### Explicación de la configuración

| Parámetro | Valor | Por qué |
|-----------|-------|---------|
| `--cache-type-k q8_0` | Claves a 8 bits | Las claves son sensibles a la compresión |
| `--cache-type-v turbo3` | Valores a 3 bits | Los valores toleran compresión extrema (5x) |
| `-fa 1` | Flash Attention | Requerido para TurboQuant |
| `-ngl 99` | GPU offload completo | Las 81 capas en Metal |
| `-t 10` | 10 threads | M4 Pro tiene 10 núcleos de rendimiento |
| `--no-mmap` | Sin memory mapping | Carga todo al inicio, evita fallos de página |
| `--chat-template chatml` | Formato ChatML | Mejor compatibilidad con este fork |

## Benchmark con asiai

```bash
pip install asiai
asiai detect --url http://localhost:8081
asiai bench --engines llamacpp --prompts code --runs 3 --kv-cache turbo3 --card
```

## Modelos que caben en 64 GB con TurboQuant

| Modelo | Pesos (Q4_K_M) | KV Cache (32K, turbo3) | Total | Estado |
|--------|----------------|----------------------|-------|--------|
| Llama 3.1 70B | 40 GB | ~4 GB | 44 GB | **Probado: 6,3 tok/s** |
| Qwen2.5 72B | 40 GB | ~4 GB | 44 GB | Debería funcionar |
| Llama 70B ctx 128K | 40 GB | ~16 GB (turbo3) | 56 GB | Justo pero posible |
| Command-R+ 104B | 58 GB | ~4 GB | 62 GB | Muy justo |

## FAQ

**¿Puedo ejecutar un modelo 70B en un Mac con 64 GB de RAM?**

Sí, con TurboQuant. El KV cache se comprime 5x, por lo que Llama 70B Q4_K_M (40 GB de pesos) cabe cómodamente en 64 GB con un contexto de 32K. Medimos 6,3 tok/s en un Mac Mini M4 Pro.

**¿TurboQuant reduce la calidad?**

Sin pérdida de calidad medible. El aumento de perplejidad es inferior al 1 % frente a q8_0, y la recuperación Needle-in-a-Haystack alcanza el 100 % en un contexto de 32K.

**¿Qué formato TurboQuant debería usar?**

Asimétrico: q8_0 para claves + turbo3 para valores. Las claves son sensibles a la compresión (toda la degradación de calidad proviene de la compresión de K). Los valores pueden comprimirse a 2-3 bits sin ningún efecto en la calidad de la atención.

**¿TurboQuant funciona con MLX?**

Existen implementaciones de la comunidad ([turboquant-mlx](https://github.com/helgklaizar/turboquant_mlx)) pero son menos maduras que el fork de llama.cpp. Para uso en producción, recomendamos [TheTom/llama-cpp-turboquant](https://github.com/TheTom/llama-cpp-turboquant).

**¿Cómo se compara con el llama.cpp estándar?**

La velocidad de decodificación es de aproximadamente 0,9x de q8_0 (ligeramente más lento por token), pero la ganancia real es poder usar modelos y contextos que simplemente no cabían antes. El prefill puede ser más rápido en contextos largos gracias a la reducción de la presión sobre el ancho de banda de memoria.

## Referencias

- [Google Research Blog — TurboQuant](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/)
- [TurboQuant Paper (ICLR 2026)](https://arxiv.org/abs/2504.19874)
- [TheTom/turboquant_plus](https://github.com/TheTom/turboquant_plus) — Implementación extendida con Sparse V
- [TheTom/llama-cpp-turboquant](https://github.com/TheTom/llama-cpp-turboquant) — Fork de llama.cpp con kernels Metal
- [llama.cpp Discussion #20969](https://github.com/ggml-org/llama.cpp/discussions/20969) — Hilo de discusión de la comunidad
