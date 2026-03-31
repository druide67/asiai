---
title: "Apple Silicon 上的 TurboQuant Benchmark：在 Mac 上运行 70B 模型"
description: "Mac Mini M4 Pro 64GB 上 TurboQuant KV cache 压缩的真实 benchmark 数据：Llama 70B 达到 6.3 tok/s，内存节省 5 倍。配置指南与结果。"
type: article
date: 2026-03-31
updated: 2026-03-31
faq:
  - q: "64GB RAM 的 Mac 能运行 70B 模型吗？"
    a: "可以，使用 TurboQuant。KV cache 被压缩 5 倍，因此 Llama 70B Q4_K_M（40GB 权重）在 32K 上下文下可以轻松装入 64GB 内存。我们在 Mac Mini M4 Pro 上测得 6.3 tok/s。"
  - q: "TurboQuant 会降低质量吗？"
    a: "没有可测量的质量损失。与 q8_0 相比，困惑度增加不到 1%，Needle-in-a-Haystack 检索在 32K 上下文中得分为 100%。"
  - q: "应该使用哪种 TurboQuant 格式？"
    a: "我们推荐非对称格式：keys 使用 q8_0（对压缩敏感），values 使用 turbo3（5 倍压缩，无质量影响）。这基于 turboquant_plus 项目的研究发现。"
  - q: "TurboQuant 支持 MLX 引擎吗？"
    a: "社区已有 MLX 实现，但不如 llama.cpp fork 成熟。对于 Apple Silicon 上的生产环境，我们推荐使用带有 Metal kernels 的 TheTom/llama-cpp-turboquant。"
  - q: "TurboQuant 快多少？"
    a: "解码速度约为 q8_0 的 0.9 倍（每个 token 略慢），但在长上下文下 prefill 可能更快，因为内存带宽压力减小。真正的收益在于能在相同的 RAM 中运行更大的模型和更长的上下文。"
---

# Apple Silicon 上的 TurboQuant Benchmark

TurboQuant（Google Research，ICLR 2026）将 LLM 的 KV cache 压缩 5 倍且无质量损失，使 70B 模型能够在 64GB RAM 的 Mac Mini 上运行。以下是使用 [asiai](/) 在真实硬件上测量的 benchmark 数据。

## 结果

**Llama-3.1-70B-Instruct Q4_K_M 在 Mac Mini M4 Pro 64GB 上的表现**

| 指标 | 值 |
|------|-----|
| **Throughput** | 6.3 tok/s（稳定，95% 置信区间：6.3-6.3） |
| **TTFT** | 196 ms（中位数） |
| **GPU Power** | 23.8 W |
| **Model VRAM** | 44.1 GB（40 GB 权重 + 4 GB KV turbo3） |
| **Context** | 32,768 tokens |
| **GPU Offload** | 81/81 层在 Metal 上 |
| **Thermal** | 正常（无降频） |
| **Stability** | 稳定（3 次运行标准差 0.04 tok/s） |

KV cache 配置：keys 使用 q8_0（高精度），values 使用 turbo3（3-bit，5 倍压缩）。

## TurboQuant 使用前后对比

| | 不使用 TurboQuant | 使用 TurboQuant (turbo3) |
|--|-------------------|--------------------------|
| **KV cache (32K ctx)** | ~20 GB (q8_0) | ~4 GB (turbo3) |
| **总 RAM 需求** | 60+ GB（64GB 上 OOM） | 44 GB（可装入 64GB） |
| **64GB 能运行 70B 吗？** | 不能 | **可以** |
| **质量** | Baseline | -1% PPL（可忽略） |
| **NIAH retrieval** | 100% | 100% |

## 什么是 TurboQuant？

TurboQuant 是 Google Research 的 KV cache 压缩算法，在 ICLR 2026 上发表。在 LLM 推理过程中，KV cache 存储中间注意力状态，并随上下文长度线性增长。对于 FP16 下 128K 上下文的 70B 模型，仅此 cache 就可能消耗 20-40 GB RAM。

TurboQuant 使用以下技术将 cache 压缩到每个值 3 bit：

- **随机旋转**（Walsh-Hadamard 变换）使数据高斯化
- **最优标量量化**（PolarQuant）接近 Shannon 极限
- **QJL**（Quantized Johnson-Lindenstrauss）保持点积不变

结果：内存减少 5 倍，无需 fine-tuning，质量损失接近零。

## 配置指南

### 硬件

- Mac Mini M4 Pro，64 GB 统一内存（$2,700）
- 任何 32+ GB 的 Apple Silicon Mac 均可使用（根据情况调整模型大小）

### 安装 TurboQuant llama.cpp

```bash
# 安装构建工具
brew install cmake

# 克隆 TurboQuant fork
git clone https://github.com/TheTom/llama-cpp-turboquant.git
cd llama-cpp-turboquant
git checkout feature/turboquant-kv-cache

# 使用 Metal（Apple Silicon GPU）编译
cmake -B build -DGGML_METAL=ON -DGGML_METAL_EMBED_LIBRARY=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(sysctl -n hw.ncpu)
```

### 下载模型

```bash
# Llama 3.1 70B Q4_K_M (~40 GB)
curl -L -o llama-3.1-70b-q4_k_m.gguf \
  "https://huggingface.co/bartowski/Meta-Llama-3.1-70B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-70B-Instruct-Q4_K_M.gguf"
```

### 提高 macOS GPU 内存限制

```bash
sudo sysctl iogpu.wired_limit_mb=61440
```

### 启动服务器

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

### 配置说明

| 参数 | 值 | 原因 |
|------|-----|------|
| `--cache-type-k q8_0` | Keys 使用 8-bit | Keys 对压缩敏感 |
| `--cache-type-v turbo3` | Values 使用 3-bit | Values 可承受极端压缩（5 倍） |
| `-fa 1` | Flash Attention | TurboQuant 必需 |
| `-ngl 99` | 完全 GPU offload | 全部 81 层在 Metal 上 |
| `-t 10` | 10 线程 | M4 Pro 有 10 个性能核心 |
| `--no-mmap` | 不使用内存映射 | 启动时全部加载，避免 page faults |
| `--chat-template chatml` | ChatML 格式 | 与此 fork 兼容性最佳 |

## 使用 asiai 进行 Benchmark

```bash
pip install asiai
asiai detect --url http://localhost:8081
asiai bench --engines llamacpp --prompts code --runs 3 --kv-cache turbo3 --card
```

## 使用 TurboQuant 后 64GB 可运行的模型

| 模型 | 权重 (Q4_K_M) | KV Cache (32K, turbo3) | 总计 | 状态 |
|------|---------------|----------------------|------|------|
| Llama 3.1 70B | 40 GB | ~4 GB | 44 GB | **已测试：6.3 tok/s** |
| Qwen2.5 72B | 40 GB | ~4 GB | 44 GB | 理论可行 |
| Llama 70B 128K ctx | 40 GB | ~16 GB (turbo3) | 56 GB | 较紧但可行 |
| Command-R+ 104B | 58 GB | ~4 GB | 62 GB | 非常紧张 |

## FAQ

**64GB RAM 的 Mac 能运行 70B 模型吗？**

可以，使用 TurboQuant。KV cache 被压缩 5 倍，因此 Llama 70B Q4_K_M（40GB 权重）在 32K 上下文下可以轻松装入 64GB 内存。我们在 Mac Mini M4 Pro 上测得 6.3 tok/s。

**TurboQuant 会降低质量吗？**

没有可测量的质量损失。与 q8_0 相比，困惑度增加不到 1%，Needle-in-a-Haystack 检索在 32K 上下文中得分为 100%。

**应该使用哪种 TurboQuant 格式？**

非对称格式：keys 使用 q8_0 + values 使用 turbo3。Keys 对压缩敏感（所有质量下降都来自 K 的压缩）。Values 可以压缩到 2-3 bit 而对注意力质量没有任何影响。

**TurboQuant 支持 MLX 吗？**

社区已有实现（[turboquant-mlx](https://github.com/helgklaizar/turboquant_mlx)），但不如 llama.cpp fork 成熟。对于生产环境，我们推荐 [TheTom/llama-cpp-turboquant](https://github.com/TheTom/llama-cpp-turboquant)。

**与标准 llama.cpp 相比如何？**

解码速度约为 q8_0 的 ~0.9 倍（每个 token 略慢），但真正的收益在于能运行之前根本装不下的模型和上下文。由于内存带宽压力减小，长上下文下的 prefill 实际上可能更快。

## 参考资料

- [Google Research Blog — TurboQuant](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/)
- [TurboQuant Paper (ICLR 2026)](https://arxiv.org/abs/2504.19874)
- [TheTom/turboquant_plus](https://github.com/TheTom/turboquant_plus) — 带有 Sparse V 的扩展实现
- [TheTom/llama-cpp-turboquant](https://github.com/TheTom/llama-cpp-turboquant) — 带有 Metal kernels 的 llama.cpp fork
- [llama.cpp Discussion #20969](https://github.com/ggml-org/llama.cpp/discussions/20969) — 社区讨论帖
