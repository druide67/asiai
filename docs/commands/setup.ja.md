---
description: "asiai クイックセットアップ：エンジン設定、接続テスト、Apple Silicon MacがLLMベンチマークの準備完了か確認。"
---

# asiai setup

初回ユーザー向けのインタラクティブセットアップウィザード。ハードウェアを検出し、推論エンジンをチェックし、次のステップを提案します。

## 使用方法

```bash
asiai setup
```

## 処理内容

1. **ハードウェア検出** — Apple SiliconチップとRAMを特定
2. **エンジンスキャン** — インストール済み推論エンジン（Ollama、LM Studio、mlx-lm、llama.cpp、oMLX、vllm-mlx、Exo）をチェック
3. **モデルチェック** — 検出されたすべてのエンジンのロード済みモデルを一覧表示
4. **デーモンステータス** — 監視デーモンが実行中かどうかを表示
5. **次のステップ** — セットアップ状態に基づいてコマンドを提案

## 出力例

```
  Setup Wizard

  Hardware:  Apple M4 Pro, 64 GB RAM

  Engines:
    ✓ ollama (v0.17.7) — 3 models loaded
    ✓ lmstudio (v0.4.5) — 1 model loaded

  Daemon: running (monitor + web)

  Suggested next steps:
    • asiai bench              Run your first benchmark
    • asiai monitor --watch    Watch metrics live
    • asiai web                Open the dashboard
```

## エンジンが見つからない場合

エンジンが検出されない場合、セットアップはインストールガイダンスを提供します：

```
  Engines:
    No inference engines detected.

  To get started, install an engine:
    brew install ollama && ollama serve
    # or download LM Studio from https://lmstudio.ai
```
