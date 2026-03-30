---
description: ブラウザでリアルタイムLLM監視ダッシュボード。GPUメトリクス、エンジンヘルス、パフォーマンス履歴。セットアップ不要。
---

# asiai web

視覚的な監視とベンチマークのためのWebダッシュボードを起動します。

## 使用方法

```bash
asiai web
asiai web --port 9000
asiai web --host 0.0.0.0
asiai web --no-open
```

## オプション

| オプション | デフォルト | 説明 |
|-----------|----------|------|
| `--port` | `8899` | リスンするHTTPポート |
| `--host` | `127.0.0.1` | バインドするホスト |
| `--no-open` | | ブラウザを自動的に開かない |
| `--db` | `~/.local/share/asiai/asiai.db` | SQLiteデータベースのパス |

## 必要条件

Webダッシュボードには追加の依存関係が必要です：

```bash
pip install asiai[web]
# またはすべてをインストール：
pip install asiai[all]
```

## ページ

### ダッシュボード（`/`）

エンジンステータス、ロード済みモデル、メモリ使用量、最新ベンチマーク結果を含むシステム概要。

### ベンチマーク（`/bench`）

ブラウザから直接クロスエンジンベンチマークを実行：

- **Quick Bench** ボタン — 1プロンプト、1回実行、約15秒
- 詳細オプション：エンジン、プロンプト、実行回数、コンテキストサイズ（4K/16K/32K/64K）、電力
- SSEによるライブ進行状況
- 勝者ハイライト付き結果テーブル
- スループットとTTFTチャート
- **共有カード** — ベンチマーク後に自動生成（API経由のPNG、SVGフォールバック）
- **共有セクション** — リンクコピー、PNG/SVGダウンロード、X/Redditで共有、JSONエクスポート

### 履歴（`/history`）

ベンチマークとシステムメトリクスの時系列可視化：

- システムチャート：CPU負荷、メモリ%、GPU使用率（renderer/tiler分割）
- エンジンアクティビティ：TCP接続、処理中リクエスト、KVキャッシュ使用率%
- ベンチマークチャート：エンジンごとのスループット（tok/s）とTTFT
- プロセスメトリクス：ベンチマーク実行中のエンジンCPU%とRSSメモリ
- 時間範囲フィルター（1h / 24h / 7d / 30d / 90d）またはカスタム日付範囲
- コンテキストサイズ表示付きデータテーブル（例：「code (64K ctx)」）

### モニター（`/monitor`）

5秒リフレッシュのリアルタイムシステム監視：

- CPU負荷スパークライン
- メモリゲージ
- サーマル状態
- ロード済みモデルリスト

### ドクター（`/doctor`）

システム、エンジン、データベースのインタラクティブヘルスチェック。`asiai doctor` と同じチェックをビジュアルインターフェースで。

## APIエンドポイント

WebダッシュボードはプログラムアクセスのためのREST APIエンドポイントを公開します。

### `GET /api/status`

軽量ヘルスチェック。10秒キャッシュ、500ms未満で応答。

```json
{
  "status": "ok",
  "ts": 1709700000,
  "uptime": 86400,
  "engines": {"ollama": true, "lmstudio": false},
  "memory_pressure": "normal",
  "thermal_level": "nominal"
}
```

ステータス値：`ok`（全エンジン到達可能）、`degraded`（一部停止）、`error`（全停止）。

### `GET /api/snapshot`

フルシステム + エンジンスナップショット。5秒キャッシュ。CPU負荷、メモリ、サーマル状態、ロード済みモデルを含むエンジンごとのステータス。

### `GET /api/benchmarks`

フィルター付きベンチマーク結果。tok/s、TTFT、電力、context_size、engine_versionを含むランごとのデータを返します。

| パラメータ | デフォルト | 説明 |
|-----------|----------|------|
| `hours` | `168` | 時間範囲（0 = 全件） |
| `model` | | モデル名でフィルター |
| `engine` | | エンジン名でフィルター |
| `since` / `until` | | Unixタイムスタンプ範囲（hoursを上書き） |

### `GET /api/engine-history`

エンジンステータス履歴（到達性、TCP接続、KVキャッシュ、予測トークン）。

| パラメータ | デフォルト | 説明 |
|-----------|----------|------|
| `hours` | `168` | 時間範囲 |
| `engine` | | エンジン名でフィルター |

### `GET /api/benchmark-process`

ベンチマーク実行中のプロセスレベルCPUとメモリメトリクス（7日間保持）。

| パラメータ | デフォルト | 説明 |
|-----------|----------|------|
| `hours` | `168` | 時間範囲 |
| `engine` | | エンジン名でフィルター |

### `GET /api/metrics`

Prometheusエクスポジションフォーマット。システム、エンジン、モデル、ベンチマークメトリクスをカバーするゲージ。

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'asiai'
    static_configs:
      - targets: ['localhost:8899']
    metrics_path: '/api/metrics'
    scrape_interval: 30s
```

メトリクス：

| メトリクス | タイプ | 説明 |
|-----------|--------|------|
| `asiai_cpu_load_1m` | gauge | CPU負荷平均（1分） |
| `asiai_memory_used_bytes` | gauge | 使用メモリ |
| `asiai_thermal_speed_limit_pct` | gauge | CPU速度制限% |
| `asiai_engine_reachable{engine}` | gauge | エンジン到達性（0/1） |
| `asiai_engine_models_loaded{engine}` | gauge | ロード済みモデル数 |
| `asiai_engine_tcp_connections{engine}` | gauge | 確立済みTCP接続 |
| `asiai_engine_requests_processing{engine}` | gauge | 処理中リクエスト |
| `asiai_engine_kv_cache_usage_ratio{engine}` | gauge | KVキャッシュ使用率（0-1） |
| `asiai_engine_tokens_predicted_total{engine}` | counter | 累積予測トークン |
| `asiai_model_vram_bytes{engine,model}` | gauge | モデルごとのVRAM |
| `asiai_bench_tok_per_sec{engine,model}` | gauge | 最新ベンチマークtok/s |

## 注意事項

- ダッシュボードはデフォルトで `127.0.0.1` にバインド（ローカルホストのみ）
- ネットワークに公開するには `--host 0.0.0.0` を使用（例：リモート監視用）
- ポート `8899` は推論エンジンポートとの競合を避けるために選択
