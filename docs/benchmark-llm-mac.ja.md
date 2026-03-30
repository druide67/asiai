---
title: "MacでLLMをベンチマークする方法"
description: "MacでLLM推論をベンチマークする方法：Apple Siliconで複数エンジンを使用してtok/s、TTFT、電力、VRAMを測定するステップバイステップガイド。"
type: howto
date: 2026-03-28
updated: 2026-03-29
duration: PT5M
steps:
  - name: "asiai をインストール"
    text: "pip (pip install asiai) または Homebrew (brew tap druide67/tap && brew install asiai) で asiai をインストールします。"
  - name: "エンジンを検出"
    text: "'asiai detect' を実行して、Mac上で動作中の推論エンジン（Ollama、LM Studio、llama.cpp、mlx-lm、oMLX、vLLM-MLX、Exo）を自動的に検出します。"
  - name: "ベンチマークを実行"
    text: "'asiai bench' を実行して、エンジン間の最適なモデルを自動検出し、tok/s、TTFT、電力、VRAMを測定するクロスエンジン比較を実行します。"
---

# MacでLLMをベンチマークする方法

Macでローカル LLMを実行していますか？実際のパフォーマンスの測定方法をご紹介します — 感覚ではなく、「なんとなく速い」でもなく、実際のtok/s、TTFT、消費電力、メモリ使用量です。

## なぜベンチマークが必要なのか？

同じモデルでも推論エンジンによって速度が大きく異なります。Apple Siliconでは、MLXベースのエンジン（LM Studio、mlx-lm、oMLX）はllama.cppベースのエンジン（Ollama）と比較して、同じモデルで**2倍速い**場合があります。測定しなければ、パフォーマンスを活かしきれません。

## クイックスタート（2分）

### 1. asiai をインストール

```bash
pip install asiai
```

またはHomebrew経由：

```bash
brew tap druide67/tap
brew install asiai
```

### 2. エンジンを検出

```bash
asiai detect
```

asiai はMac上で動作中のエンジン（Ollama、LM Studio、llama.cpp、mlx-lm、oMLX、vLLM-MLX、Exo）を自動的に検出します。

### 3. ベンチマークを実行

```bash
asiai bench
```

これだけです。asiai はエンジン間で最適なモデルを自動検出し、クロスエンジン比較を実行します。

## 測定される項目

| メトリクス | 意味 |
|-----------|------|
| **tok/s** | 1秒あたりの生成トークン数（生成のみ、プロンプト処理を除く） |
| **TTFT** | 最初のトークンまでの時間 — 生成開始までのレイテンシ |
| **Power** | 推論中のGPU + CPU消費電力（IOReport経由、sudo不要） |
| **tok/s/W** | エネルギー効率 — ワットあたりの1秒あたりトークン数 |
| **VRAM** | モデルが使用するメモリ（ネイティブAPIまたは `ri_phys_footprint` による推定） |
| **Stability** | 実行間のばらつき：stable（CV 5%未満）、variable（10%未満）、unstable（10%以上） |
| **Thermal** | ベンチマーク中にMacがスロットリングしたかどうか |

## 出力例

```
Mac16,11 — Apple M4 Pro  RAM: 64.0 GB  Pressure: normal

Benchmark: qwen3-coder-30b

  Engine        tok/s   Tokens Duration     TTFT       VRAM    Thermal
  lmstudio      102.2      537    7.00s    0.29s    24.2 GB    nominal
  ollama         69.8      512   17.33s    0.18s    32.0 GB    nominal

  Winner: lmstudio (+46% tok/s)

  Power Efficiency
    lmstudio     102.2 tok/s @ 12.4W = 8.23 tok/s/W
    ollama        69.8 tok/s @ 15.4W = 4.53 tok/s/W
```

*M4 Pro 64GBでの実際のベンチマーク出力例。ハードウェアとモデルによって結果は異なります。[さらに結果を見る →](ollama-vs-lmstudio.md)*

## 詳細オプション

### 特定のエンジンを比較

```bash
asiai bench --engines ollama,lmstudio,omlx
```

### 複数プロンプトと実行回数

```bash
asiai bench --prompts code,reasoning,tool_call --runs 3
```

### 大規模コンテキストベンチマーク

```bash
asiai bench --context-size 64K
```

### 共有可能なカードを生成

```bash
asiai bench --card --share
```

ベンチマークカード画像を作成し、結果を[コミュニティリーダーボード](leaderboard.md)と共有します。

## Apple Siliconのヒント

### メモリが重要

16GB Macでは、14GB以下のモデル（ロード時）を使用してください。MoEモデル（Qwen3.5-35B-A3B、3Bアクティブ）が最適です — 7Bクラスのメモリ使用量で35Bクラスの品質を提供します。

### エンジン選択は想像以上に重要

MLXエンジンはほとんどのモデルでApple Silicon上のllama.cppよりも大幅に高速です。実際の数値については[Ollama対LM Studio比較](ollama-vs-lmstudio.md)をご覧ください。

### サーマルスロットリング

MacBook Air（ファンなし）は5〜10分の持続推論でスロットリングが発生します。Mac Mini/Studio/Proはスロットリングなしで持続ワークロードに対応します。asiai はサーマルスロットリングを自動的に検出・報告します。

## コミュニティと比較

他のApple Siliconマシンと自分のMacを比較できます：

```bash
asiai compare
```

または[オンラインリーダーボード](leaderboard.md)をご覧ください。

## FAQ

**Q: Apple Siliconで最速のLLM推論エンジンは？**
A: M4 Pro 64GBでのベンチマークでは、LM Studio（MLXバックエンド）がトークン生成で最速です — Ollama（llama.cpp）より46%高速。ただし、Ollamaの方がTTFT（最初のトークンまでの時間）は低いです。[詳細な比較](ollama-vs-lmstudio.md)をご覧ください。

**Q: Macで30Bモデルを実行するにはどのくらいのRAMが必要ですか？**
A: Q4_K_M量子化の30Bモデルは、エンジンによって24〜32 GBのユニファイドメモリを使用します。最低32 GB、理想的には64 GBのRAMが必要です。Qwen3.5-35B-A3Bなどの MoEモデルはアクティブパラメータが約7 GBのみです。

**Q: asiai はIntel Macで動作しますか？**
A: いいえ。asiai はApple Silicon（M1/M2/M3/M4）が必要です。Apple Siliconでのみ利用可能なGPUメトリクス、電力監視、ハードウェア検出用のmacOS固有APIを使用しています。

**Q: M4ではOllamaとLM Studioのどちらが速いですか？**
A: LM Studioはスループットで高速です（Qwen3-Coder-30Bで102 tok/s対70 tok/s）。Ollamaは最初のトークンレイテンシ（0.18s対0.29s）と大規模コンテキストウィンドウ（32Kトークン超）で高速で、llama.cppのプリフィルは最大3倍速です。

**Q: ベンチマークにはどのくらい時間がかかりますか？**
A: クイックベンチマークは約2分です。複数プロンプトと実行回数を含む完全なクロスエンジン比較は10〜15分かかります。高速な単一実行テストには `asiai bench --quick` を使用してください。

**Q: 他のMacユーザーと結果を比較できますか？**
A: はい。`asiai bench --share` を実行して結果を匿名で[コミュニティリーダーボード](leaderboard.md)に提出できます。`asiai compare` で他のApple Siliconマシンとの比較ができます。

## さらに詳しく

- [ベンチマーク手法](methodology.md) — asiai が信頼性の高い測定を確保する方法
- [ベンチマークのベストプラクティス](benchmark-best-practices.md) — 正確な結果を得るためのヒント
- [エンジン比較](ollama-vs-lmstudio.md) — Ollama対LM Studioの直接対決
