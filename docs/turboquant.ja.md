---
title: "Apple Silicon での TurboQuant Benchmark：Mac で 70B モデルを実行する"
description: "Mac Mini M4 Pro 64GB での TurboQuant KV cache 圧縮の実測 benchmark：Llama 70B が 6.3 tok/s、メモリ使用量 5 分の 1。セットアップガイドと結果。"
type: article
date: 2026-03-31
updated: 2026-03-31
faq:
  - q: "64GB RAM の Mac で 70B モデルを実行できますか？"
    a: "はい、TurboQuant を使えば可能です。KV cache が 5 倍に圧縮されるため、Llama 70B Q4_K_M（40GB の重み）は 32K コンテキストで 64GB に余裕を持って収まります。Mac Mini M4 Pro で 6.3 tok/s を計測しました。"
  - q: "TurboQuant は品質を低下させますか？"
    a: "測定可能な品質低下はありません。q8_0 と比較してパープレキシティの増加は 1% 未満で、Needle-in-a-Haystack 検索は 32K コンテキスト全体で 100% のスコアです。"
  - q: "どの TurboQuant フォーマットを使うべきですか？"
    a: "非対称をお勧めします：keys に q8_0（圧縮に敏感）、values に turbo3（5 倍圧縮、品質への影響なし）。これは turboquant_plus プロジェクトの知見に基づいています。"
  - q: "TurboQuant は MLX エンジンで動作しますか？"
    a: "コミュニティによる MLX 実装はありますが、llama.cpp fork ほど成熟していません。Apple Silicon での本番利用には、Metal kernels を備えた TheTom/llama-cpp-turboquant をお勧めします。"
  - q: "TurboQuant はどのくらい高速ですか？"
    a: "デコード速度は q8_0 の約 0.9 倍（トークンあたりわずかに遅い）ですが、長いコンテキストではメモリ帯域幅の負荷が軽減されるため prefill が高速になることがあります。真の利点は、同じ RAM でより大きなモデルとより長いコンテキストを実行できることです。"
---

# Apple Silicon での TurboQuant Benchmark

TurboQuant（Google Research、ICLR 2026）は LLM の KV cache を品質低下なしに 5 倍圧縮し、64GB RAM の Mac Mini で 70B モデルの実行を可能にします。以下は [asiai](/) を使用して実際のハードウェアで計測した benchmark 結果です。

## 結果

**Llama-3.1-70B-Instruct Q4_K_M（Mac Mini M4 Pro 64GB）**

| 指標 | 値 |
|------|-----|
| **Throughput** | 6.3 tok/s（安定、95% 信頼区間：6.3-6.3） |
| **TTFT** | 196 ms（中央値） |
| **GPU Power** | 23.8 W |
| **Model VRAM** | 44.1 GB（40 GB 重み + 4 GB KV turbo3） |
| **Context** | 32,768 tokens |
| **GPU Offload** | Metal 上に 81/81 レイヤー |
| **Thermal** | 正常（スロットリングなし） |
| **Stability** | 安定（3 回の実行で標準偏差 0.04 tok/s） |

KV cache 設定：keys は q8_0（高精度）、values は turbo3（3-bit、5 倍圧縮）。

## TurboQuant 導入前後の比較

| | TurboQuant なし | TurboQuant あり (turbo3) |
|--|----------------|--------------------------|
| **KV cache (32K ctx)** | ~20 GB (q8_0) | ~4 GB (turbo3) |
| **必要な RAM 合計** | 60+ GB（64GB では OOM） | 44 GB（64GB に収まる） |
| **64GB で 70B を実行可能？** | いいえ | **はい** |
| **品質** | Baseline | -1% PPL（無視できる程度） |
| **NIAH retrieval** | 100% | 100% |

## TurboQuant とは？

TurboQuant は Google Research による KV cache 圧縮アルゴリズムで、ICLR 2026 で発表されました。LLM の推論中、KV cache は中間的な注意力の状態を保存し、コンテキスト長に比例して線形に増大します。FP16 で 128K コンテキストの 70B モデルの場合、この cache だけで 20-40 GB の RAM を消費する可能性があります。

TurboQuant は以下の技術を使用して cache を 1 値あたり 3 bit に圧縮します：

- **ランダム回転**（Walsh-Hadamard 変換）によるデータのガウス化
- **最適スカラー量子化**（PolarQuant）による Shannon 限界への接近
- **QJL**（Quantized Johnson-Lindenstrauss）による内積の保存

結果：メモリ使用量 5 分の 1、fine-tuning 不要、品質低下はほぼゼロです。

## セットアップガイド

### ハードウェア

- Mac Mini M4 Pro、64 GB ユニファイドメモリ（$2,700）
- 32+ GB の Apple Silicon Mac であれば動作するはずです（モデルサイズを適宜調整してください）

### TurboQuant llama.cpp のインストール

```bash
# ビルドツールのインストール
brew install cmake

# TurboQuant fork のクローン
git clone https://github.com/TheTom/llama-cpp-turboquant.git
cd llama-cpp-turboquant
git checkout feature/turboquant-kv-cache

# Metal（Apple Silicon GPU）でビルド
cmake -B build -DGGML_METAL=ON -DGGML_METAL_EMBED_LIBRARY=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(sysctl -n hw.ncpu)
```

### モデルのダウンロード

```bash
# Llama 3.1 70B Q4_K_M (~40 GB)
curl -L -o llama-3.1-70b-q4_k_m.gguf \
  "https://huggingface.co/bartowski/Meta-Llama-3.1-70B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-70B-Instruct-Q4_K_M.gguf"
```

### macOS GPU メモリ制限の引き上げ

```bash
sudo sysctl iogpu.wired_limit_mb=61440
```

### サーバーの起動

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

### 設定の説明

| パラメータ | 値 | 理由 |
|-----------|-----|------|
| `--cache-type-k q8_0` | Keys を 8-bit で | Keys は圧縮に敏感です |
| `--cache-type-v turbo3` | Values を 3-bit で | Values は極端な圧縮（5 倍）に耐えます |
| `-fa 1` | Flash Attention | TurboQuant に必須です |
| `-ngl 99` | 完全 GPU offload | 全 81 レイヤーを Metal 上に配置 |
| `-t 10` | 10 スレッド | M4 Pro は 10 個のパフォーマンスコアを搭載 |
| `--no-mmap` | メモリマッピングなし | 起動時にすべてロードし、page faults を回避 |
| `--chat-template chatml` | ChatML フォーマット | この fork との互換性が最良 |

## asiai での Benchmark

```bash
pip install asiai
asiai detect --url http://localhost:8081
asiai bench --engines llamacpp --prompts code --runs 3 --kv-cache turbo3 --card
```

## TurboQuant で 64GB に収まるモデル

| モデル | 重み (Q4_K_M) | KV Cache (32K, turbo3) | 合計 | ステータス |
|--------|---------------|----------------------|------|----------|
| Llama 3.1 70B | 40 GB | ~4 GB | 44 GB | **テスト済み：6.3 tok/s** |
| Qwen2.5 72B | 40 GB | ~4 GB | 44 GB | 動作見込み |
| Llama 70B 128K ctx | 40 GB | ~16 GB (turbo3) | 56 GB | ギリギリだが可能 |
| Command-R+ 104B | 58 GB | ~4 GB | 62 GB | 非常にギリギリ |

## FAQ

**64GB RAM の Mac で 70B モデルを実行できますか？**

はい、TurboQuant を使えば可能です。KV cache が 5 倍に圧縮されるため、Llama 70B Q4_K_M（40GB の重み）は 32K コンテキストで 64GB に余裕を持って収まります。Mac Mini M4 Pro で 6.3 tok/s を計測しました。

**TurboQuant は品質を低下させますか？**

測定可能な品質低下はありません。q8_0 と比較してパープレキシティの増加は 1% 未満で、Needle-in-a-Haystack 検索は 32K コンテキスト全体で 100% のスコアです。

**どの TurboQuant フォーマットを使うべきですか？**

非対称：keys に q8_0 + values に turbo3。Keys は圧縮に敏感です（すべての品質低下は K の圧縮に起因します）。Values は 2-3 bit まで圧縮しても注意力の品質に影響はありません。

**TurboQuant は MLX で動作しますか？**

コミュニティによる実装があります（[turboquant-mlx](https://github.com/helgklaizar/turboquant_mlx)）が、llama.cpp fork ほど成熟していません。本番利用には [TheTom/llama-cpp-turboquant](https://github.com/TheTom/llama-cpp-turboquant) をお勧めします。

**標準の llama.cpp と比べてどうですか？**

デコード速度は q8_0 の約 0.9 倍（トークンあたりわずかに遅い）ですが、真の利点は以前は収まらなかったモデルやコンテキストを実行できることです。メモリ帯域幅の負荷が軽減されるため、長いコンテキストでは prefill が実際に高速になることがあります。

## 参考文献

- [Google Research Blog — TurboQuant](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/)
- [TurboQuant Paper (ICLR 2026)](https://arxiv.org/abs/2504.19874)
- [TheTom/turboquant_plus](https://github.com/TheTom/turboquant_plus) — Sparse V を備えた拡張実装
- [TheTom/llama-cpp-turboquant](https://github.com/TheTom/llama-cpp-turboquant) — Metal kernels を備えた llama.cpp fork
- [llama.cpp Discussion #20969](https://github.com/ggml-org/llama.cpp/discussions/20969) — コミュニティスレッド
