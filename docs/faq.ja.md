---
title: "よくある質問"
description: "asiai に関するよくある質問：対応エンジン、Apple Siliconの要件、MacでのLLMベンチマーク、RAM要件など。"
type: faq
faq:
  - q: "asiai とは何ですか？"
    a: "asiai はApple Silicon MacでLLM推論エンジンのベンチマークと監視を行うオープンソースCLIツールです。7つのエンジン（Ollama、LM Studio、mlx-lm、llama.cpp、oMLX、vllm-mlx、Exo）をサポートし、tok/s、TTFT、消費電力、VRAM使用量を測定します。"
  - q: "Apple Siliconで最速のLLMエンジンは？"
    a: "M4 Pro 64GBでQwen3-Coder-30Bを使用したベンチマークでは、LM Studio（MLXバックエンド）が102 tok/sを達成し、Ollamaの70 tok/sと比較して46%高速です。ただし、Ollamaの方が最初のトークンまでのレイテンシは低いです。"
  - q: "asiai はIntel Macで動作しますか？"
    a: "いいえ。asiai はApple Silicon（M1、M2、M3、M4）が必要です。Apple Siliconチップでのみ利用可能なGPUメトリクス、IOReport電力監視、ハードウェア検出用のmacOS固有APIを使用しています。"
  - q: "ローカルでLLMを実行するにはどのくらいのRAMが必要ですか？"
    a: "Q4量子化の7Bモデル：最低8 GB。13B：16 GB。30B：32-64 GB。Qwen3.5-35B-A3BなどのMoEモデルはアクティブパラメータが約7 GBのみで、16 GB Macに最適です。"
  - q: "MacにはOllamaとLM Studioのどちらが良いですか？"
    a: "用途によります。LM Studio（MLX）はスループットと電力効率に優れています。Ollama（llama.cpp）は最初のトークンのレイテンシが低く、大規模コンテキストウィンドウ（32K超）の処理に優れています。詳細な比較はasiai.dev/ollama-vs-lmstudioをご覧ください。"
  - q: "asiai にsudoやroot権限は必要ですか？"
    a: "いいえ。GPU可観測性（ioreg）と電力監視（IOReport）を含むすべての機能がsudo不要で動作します。powermetricsとのクロスバリデーション用のオプション --power フラグのみがsudoを使用します。"
  - q: "asiai のインストール方法は？"
    a: "pip (pip install asiai) または Homebrew (brew tap druide67/tap && brew install asiai) でインストールできます。Python 3.11以上が必要です。"
  - q: "AIエージェントはasiai を使用できますか？"
    a: "はい。asiai には11ツールと3リソースを備えたMCPサーバーが含まれています。pip install asiai[mcp] でインストールし、MCPクライアント（Claude Code、Cursorなど）で asiai mcp として設定してください。"
  - q: "電力測定の精度は？"
    a: "IOReportの電力読み取り値はsudo powermetricsと比較して1.5%未満の差異で、LM Studio（MLX）とOllama（llama.cpp）の両方で20サンプルにわたって検証されています。"
  - q: "複数のモデルを同時にベンチマークできますか？"
    a: "はい。asiai bench --compare を使用してクロスモデルベンチマークを実行できます。model@engine構文で精密な制御が可能で、最大8つの比較スロットをサポートします。"
  - q: "ベンチマーク結果を共有するには？"
    a: "asiai bench --share を実行して結果を匿名でコミュニティリーダーボードに提出できます。--card を追加すると共有可能な1200x630のベンチマークカード画像を生成します。"
  - q: "asiai はどのメトリクスを測定しますか？"
    a: "7つのコアメトリクス：tok/s（生成速度）、TTFT（最初のトークンまでの時間）、power（GPU+CPUワット数）、tok/s/W（エネルギー効率）、VRAM使用量、実行間の安定性、サーマルスロットリング状態。"
---

# よくある質問

## 一般

**asiai とは何ですか？**

asiai はApple Silicon MacでLLM推論エンジンのベンチマークと監視を行うオープンソースCLIツールです。7つのエンジン（Ollama、LM Studio、mlx-lm、llama.cpp、oMLX、vllm-mlx、Exo）をサポートし、tok/s、TTFT、消費電力、VRAM使用量をゼロ依存関係で測定します。

**asiai はIntel MacやLinuxで動作しますか？**

いいえ。asiai はApple Silicon（M1、M2、M3、M4）が必要です。Apple Siliconでのみ利用可能なmacOS固有のAPI（`sysctl`、`vm_stat`、`ioreg`、`IOReport`、`launchd`）を使用しています。

**asiai にsudoやroot権限は必要ですか？**

いいえ。GPU可観測性（`ioreg`）と電力監視（`IOReport`）を含むすべての機能がsudo不要で動作します。`powermetrics`とのクロスバリデーション用のオプション `--power` フラグのみがsudoを使用します。

## エンジンとパフォーマンス

**Apple Siliconで最速のLLMエンジンは？**

M4 Pro 64GBでQwen3-Coder-30B（Q4_K_M）を使用したベンチマークでは、LM Studio（MLXバックエンド）が**102 tok/s**を達成し、Ollamaの**70 tok/s**と比較して46%高速です。LM Studioは電力効率も82%優れています（8.23対4.53 tok/s/W）。[詳細な比較](ollama-vs-lmstudio.md)をご覧ください。

**MacにはOllamaとLM Studioのどちらが良いですか？**

用途によります：

- **LM Studio（MLX）**：スループットに最適（コード生成、長い応答）。より高速で効率的、VRAM使用量が少ない。
- **Ollama（llama.cpp）**：レイテンシに最適（チャットボット、インタラクティブな使用）。TTFTが速い。大規模コンテキストウィンドウ（32Kトークン超）に優れている。

**ローカルでLLMを実行するにはどのくらいのRAMが必要ですか？**

| モデルサイズ | 量子化 | 必要RAM |
|------------|--------|---------|
| 7B | Q4_K_M | 最低8 GB |
| 13B | Q4_K_M | 最低16 GB |
| 30B | Q4_K_M | 32-64 GB |
| 35B MoE（3Bアクティブ） | Q4_K_M | 16 GB（アクティブパラメータのみロード） |

## ベンチマーク

**最初のベンチマークの実行方法は？**

3つのコマンド：

```bash
pip install asiai     # インストール
asiai detect          # エンジン検出
asiai bench           # ベンチマーク実行
```

**ベンチマークにはどのくらい時間がかかりますか？**

クイックベンチマーク（`asiai bench --quick`）は約2分です。複数プロンプトと3回の実行を含む完全なクロスエンジン比較は10〜15分かかります。

**電力測定の精度は？**

IOReportの電力読み取り値は `sudo powermetrics` と比較して1.5%未満の差異で、LM Studio（MLX）とOllama（llama.cpp）の両方で20サンプルにわたって検証されています。

**他のMacユーザーと結果を比較できますか？**

はい。`asiai bench --share` を実行して結果を匿名で[コミュニティリーダーボード](leaderboard.md)に提出できます。`asiai compare` で自分のMacの立ち位置を確認できます。

## AIエージェント統合

**AIエージェントはasiai を使用できますか？**

はい。asiai には11ツールと3リソースを備えたMCPサーバーが含まれています。`pip install "asiai[mcp]"` でインストールし、MCPクライアント（Claude Code、Cursor、Windsurf）で `asiai mcp` として設定してください。[エージェント統合ガイド](agent.md)をご覧ください。

**どのMCPツールが利用できますか？**

11ツール：`check_inference_health`、`get_inference_snapshot`、`list_models`、`detect_engines`、`run_benchmark`、`get_recommendations`、`diagnose`、`get_metrics_history`、`get_benchmark_history`、`refresh_engines`、`compare_engines`。

3リソース：`asiai://status`、`asiai://models`、`asiai://system`。
