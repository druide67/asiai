---
description: asiaiをインストールして、2分以内に初めてのLLMベンチマークを実行しましょう。コマンド1つ、依存関係ゼロ、すべてのApple Silicon Macで動作します。
---

# はじめに

**Apple Silicon AI** — マルチエンジンLLMベンチマーク＆モニタリングCLI。

asiaiは、Mac上で推論エンジンを並べて比較します。同じモデルをOllamaとLM Studioにロードし、`asiai bench`を実行すれば、数値が得られます。推測なし、感覚なし — tok/s、TTFT、電力効率、エンジンごとの安定性だけです。

## クイックスタート

```bash
pipx install asiai        # 推奨: 隔離インストール
```

またはHomebrewで:

```bash
brew tap druide67/tap
brew install asiai
```

その他のオプション:

```bash
uvx asiai detect           # インストールせずに実行 (uvが必要)
pip install asiai           # 標準pipインストール
```

### 初回起動

```bash
asiai setup                # インタラクティブウィザード — ハードウェア、エンジン、モデルを検出
asiai detect               # またはエンジン検出に直接進む
```

次にベンチマーク:

```bash
asiai bench -m qwen3.5 --runs 3 --power
```

出力例:

```
  Mac Mini M4 Pro — Apple M4 Pro  RAM: 64.0 GB (42% used)  Pressure: normal

Benchmark: qwen3.5

  Engine       tok/s (±stddev)    Tokens   Duration     TTFT       VRAM    Thermal
  ────────── ───────────────── ───────── ────────── ──────── ────────── ──────────
  lmstudio    72.6 ± 0.0 (stable)   435    6.20s    0.28s        —    nominal
  ollama      30.4 ± 0.1 (stable)   448   15.28s    0.25s   26.0 GB   nominal

  Winner: lmstudio (2.4x faster)
  Power: lmstudio 13.2W (5.52 tok/s/W) — ollama 16.0W (1.89 tok/s/W)
```

## 測定項目

| メトリクス | 説明 |
|--------|-------------|
| **tok/s** | 生成速度（トークン/秒）、プロンプト処理を除く |
| **TTFT** | 最初のトークンまでの時間 — プロンプト処理のレイテンシ |
| **Power** | GPU消費電力（ワット）（`sudo powermetrics`） |
| **tok/s/W** | エネルギー効率 — ワットあたりの毎秒トークン数 |
| **Stability** | 実行間のばらつき: stable (<5%)、variable (<10%)、unstable (>10%) |
| **VRAM** | メモリ使用量 — ネイティブ（Ollama、LM Studio）または`ri_phys_footprint`による推定（全エンジン） |
| **Thermal** | CPUスロットリング状態と速度制限パーセンテージ |

## 対応エンジン

| エンジン | ポート | API |
|--------|------|-----|
| [Ollama](https://ollama.com) | 11434 | ネイティブ |
| [LM Studio](https://lmstudio.ai) | 1234 | OpenAI互換 |
| [mlx-lm](https://github.com/ml-explore/mlx-examples) | 8080 | OpenAI互換 |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | 8080 | OpenAI互換 |
| [oMLX](https://github.com/jundot/omlx) | 8000 | OpenAI互換 |
| [vllm-mlx](https://github.com/vllm-project/vllm) | 8000 | OpenAI互換 |
| [Exo](https://github.com/exo-explore/exo) | 52415 | OpenAI互換 |

## カスタムポート

エンジンが標準以外のポートで動作している場合、asiaiは通常プロセス検出で自動的に見つけます。手動で登録することもできます:

```bash
asiai config add omlx http://localhost:8800 --label mac-mini
```

手動で追加されたエンジンは永続化され、自動削除されることはありません。詳細は[config](commands/config.md)をご覧ください。

## 要件

- Apple Silicon（M1 / M2 / M3 / M4）搭載のmacOS
- Python 3.11以上
- ローカルで動作する推論エンジンが少なくとも1つ

## 依存関係ゼロ

コアはPython標準ライブラリのみを使用 — `urllib`、`sqlite3`、`subprocess`、`argparse`。`requests`なし、`psutil`なし、`rich`なし。

オプションのエクストラ:

- `asiai[web]` — チャート付きFastAPI Webダッシュボード
- `asiai[tui]` — Textualターミナルダッシュボード
- `asiai[mcp]` — AIエージェント統合用MCPサーバー
- `asiai[all]` — Web + TUI + MCP
- `asiai[dev]` — pytest、ruff、pytest-cov
