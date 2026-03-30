---
description: asiaiがエンジンを検出し、IOReportでGPUメトリクスを収集し、時系列データを保存する仕組み。技術的な詳細解説。
---

# アーキテクチャ

asiaiのデータフロー — ハードウェアセンサーからターミナル、ブラウザ、AIエージェントまで。

## 概要

![asiai architecture overview](assets/architecture.svg)

## 主要ファイル

| レイヤー | ファイル | 役割 |
|-------|-------|------|
| **エンジン** | `src/asiai/engines/` | ABC `InferenceEngine` + 7つのアダプター（Ollama、LM Studio、mlx-lm、llama.cpp、oMLX、vllm-mlx、Exo）。OpenAI互換エンジン用の`OpenAICompatEngine`基底クラス。 |
| **コレクター** | `src/asiai/collectors/` | システムメトリクス: `gpu.py`（ioreg）、`system.py`（CPU、メモリ、サーマル）、`processes.py`（lsofによる推論アクティビティ）。 |
| **ベンチマーク** | `src/asiai/benchmark/` | `runner.py`（ウォームアップ + N回実行、中央値、標準偏差、CI95）、`prompts.py`（テストプロンプト）、`card.py`（SVGカード生成）。 |
| **ストレージ** | `src/asiai/storage/` | `db.py`（SQLite WAL、全CRUD）、`schema.py`（テーブル + マイグレーション）。 |
| **CLI** | `src/asiai/cli.py` | Argparseエントリポイント、全12コマンド。 |
| **Web** | `src/asiai/web/` | FastAPI + htmx + SSE + ApexChartsダッシュボード。ルートは`routes/`内。 |
| **MCP** | `src/asiai/mcp/` | FastMCPサーバー、11ツール + 3リソース。トランスポート: stdio、SSE、streamable-http。 |
| **アドバイザー** | `src/asiai/advisor/` | ハードウェア対応レコメンデーション（モデルサイジング、エンジン選択）。 |
| **ディスプレイ** | `src/asiai/display/` | ANSIフォーマッター（`formatters.py`）、CLIレンダラー（`cli_renderer.py`）、TUI（`tui.py`）。 |

## データフロー

### モニタリング（デーモンモード）

```
60秒ごと:
  collectors → snapshot dict → store_snapshot(db) → models table
                                                  → metrics table
  engines    → engine status → store_engine_status(db)
```

### ベンチマーク

```
CLI --bench → detect engines → pick model → warmup → N runs
           → compute median/stddev/CI95 → store_benchmark(db)
           → render table (ANSI or JSON)
           → optional: --share → POST to community API
           → optional: --card  → generate SVG card
```

### Webダッシュボード

```
Browser → FastAPI → Jinja2 template (initial render)
       → htmx SSE → /api/v1/stream → real-time updates
       → ApexCharts → /api/v1/metrics?hours=N → historical graphs
```

### MCPサーバー

```
AI agent → stdio/SSE/HTTP → FastMCP → tool call
        → runs collector/benchmark in thread pool (asyncio.to_thread)
        → returns structured JSON
```

## 設計原則

1. **コアの依存関係ゼロ** — CLI、コレクター、エンジン、ストレージはPython標準ライブラリのみを使用。オプションのエクストラ（`[web]`、`[tui]`、`[mcp]`）は必要な場合にのみ依存関係を追加します。
2. **共有データレイヤー** — 同じSQLiteデータベースがCLI、Web、MCP、Prometheusに対応。別々のデータストアはありません。
3. **アダプターパターン** — 全7エンジンが`InferenceEngine` ABCを実装。新しいエンジンの追加 = 1ファイル + `detect.py`への登録。
4. **遅延インポート** — 各CLIコマンドはローカルで依存関係をインポートし、起動時間を短く保ちます。
5. **macOSネイティブ** — GPU用`ioreg`、デーモン用`launchd`、推論アクティビティ用`lsof`。Linuxの抽象化なし。
