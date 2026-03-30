---
title: "Ollama vs LM Studio: Apple Siliconベンチマーク"
description: "Apple SiliconでのOllama vs LM Studioベンチマーク：M4 Proでの実測値によるtok/s、TTFT、電力、VRAMの比較。"
type: article
date: 2026-03-28
updated: 2026-03-29
dataset:
  name: "Apple Silicon M4 ProでのOllama vs LM Studioベンチマーク"
  description: "Mac Mini M4 Pro 64GBでQwen3-Coder-30Bを使用したOllama（llama.cpp）とLM Studio（MLX）の直接比較ベンチマーク。メトリクス：tok/s、TTFT、GPU電力、効率、VRAM。"
  date: "2026-03"
---

# Ollama vs LM Studio: Apple Siliconベンチマーク

Macで最も速い推論エンジンはどちらでしょうか？2026年3月にasiai 1.4.0を使用して、Ollama（llama.cppバックエンド）とLM Studio（MLXバックエンド）を同一モデル・同一ハードウェアで直接比較しました。

## テストセットアップ

| | |
|---|---|
| **ハードウェア** | Mac Mini M4 Pro、64 GBユニファイドメモリ |
| **モデル** | Qwen3-Coder-30B（MoEアーキテクチャ、Q4_K_M / MLX 4-bit） |
| **asiai バージョン** | 1.4.0 |
| **手法** | 1回ウォームアップ + エンジンごと1回測定、temperature=0、エンジン間でモデルアンロード（[詳細手法](methodology.md)） |

## 結果

| メトリクス | LM Studio (MLX) | Ollama (llama.cpp) | 差異 |
|-----------|-----------------|-------------------|------|
| **スループット** | 102.2 tok/s | 69.8 tok/s | **+46%** |
| **TTFT** | 291 ms | 175 ms | Ollamaが高速 |
| **GPU電力** | 12.4 W | 15.4 W | **-20%** |
| **効率** | 8.2 tok/s/W | 4.5 tok/s/W | **+82%** |
| **プロセスメモリ** | 21.4 GB (RSS) | 41.6 GB (RSS) | -49% |

!!! note "メモリ数値について"
    Ollamaはフルコンテキストウィンドウ（262Kトークン）用にKVキャッシュを事前割り当てするため、メモリフットプリントが膨らみます。LM StudioはKVキャッシュをオンデマンドで割り当てます。プロセスRSSはモデルウェイトだけでなく、エンジンプロセスが使用する総メモリを反映しています。

## 主な知見

### LM Studioがスループットで勝利（+46%）

MLXのネイティブMetal最適化により、Apple Siliconのユニファイドメモリからより多くの帯域幅を引き出します。MoEアーキテクチャでは、その優位性は顕著です。より大きなQwen3.5-35B-A3Bバリアントでは、さらに大きな差を計測しました：**71.2対30.3 tok/s（2.3倍）**。

### OllamaがTTFTで勝利

Ollamaのllama.cppバックエンドは初期プロンプトをより速く処理します（175ms対291ms）。短いプロンプトでのインタラクティブな使用では、Ollamaの方がレスポンスが良く感じられます。長い生成タスクでは、LM Studioのスループットの優位性が総時間を支配します。

### LM Studioの方が電力効率が高い（+82%）

8.2 tok/s/W対4.5で、LM Studioは1ジュールあたりほぼ2倍のトークンを生成します。バッテリー駆動のノートパソコンや常時稼働サーバーでの持続ワークロードにとって重要です。

### メモリ使用量：コンテキストが重要

プロセスメモリの大きな差（21.4対41.6 GB）は、部分的にOllamaが最大コンテキストウィンドウ用にKVキャッシュを事前割り当てすることに起因します。公平な比較のためには、ピークRSSではなく、ワークロード中の実際のコンテキスト使用量を考慮してください。

## 各エンジンの推奨用途

| 用途 | 推奨 | 理由 |
|------|------|------|
| **最大スループット** | LM Studio (MLX) | 46%高速な生成 |
| **インタラクティブチャット（低レイテンシ）** | Ollama | TTFTが低い（175対291 ms） |
| **バッテリー寿命 / 効率** | LM Studio | ワットあたり82%多いtok/s |
| **Docker / API互換性** | Ollama | より広いエコシステム、OpenAI互換API |
| **メモリ制約（16GB Mac）** | LM Studio | RSS低、オンデマンドKVキャッシュ |
| **マルチモデルサービング** | Ollama | 組み込みモデル管理、keep_alive |

## 他のモデル

スループットの差はモデルアーキテクチャによって異なります：

| モデル | LM Studio (MLX) | Ollama (llama.cpp) | 差 |
|--------|-----------------|-------------------|-----|
| Qwen3-Coder-30B (MoE) | 102.2 tok/s | 69.8 tok/s | +46% |
| Qwen3.5-35B-A3B (MoE) | 71.2 tok/s | 30.3 tok/s | +135% |

MoEモデルでは最大の差が見られます。MLXがMetal上でスパースエキスパートルーティングをより効率的に処理するためです。

## 自分でベンチマークを実行

```bash
pip install asiai
asiai bench --engines ollama,lmstudio --prompts code --runs 3 --card
```

asiai は同じモデル、同じプロンプト、同じハードウェアでエンジンを並べて比較します。メモリ競合を防ぐため、エンジン間でモデルは自動的にアンロードされます。

[詳細な手法を見る](methodology.md) · [コミュニティリーダーボードを見る](leaderboard.md) · [MacでLLMをベンチマークする方法](benchmark-llm-mac.md)
