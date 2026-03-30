---
description: AIエージェントにLLM推論のリアルタイム可視性を提供します。自律的なエンジン監視のための11ツールを備えたMCPサーバーです。
type: faq
faq:
  - q: "asiai にはroot/sudo権限が必要ですか？"
    a: "いいえ。GPU可観測性はioreg（権限不要）を使用します。電力メトリクスもsudo不要のIOReportを使用します。クロスバリデーション用のオプション --power フラグのみがsudo powermetricsを使用します。"
  - q: "APIのレスポンスタイムは？"
    a: "/api/status は500ms未満で応答します（10秒キャッシュ）。/api/snapshot は全エンジンからライブデータを収集するため1〜3秒かかります。"
  - q: "asiai をLinuxで実行できますか？"
    a: "いいえ。asiai はmacOS Apple Silicon専用です。sysctl、vm_stat、ioreg、IOReport、launchd など、すべてmacOS固有のAPIを使用しています。"
  - q: "複数のMacを監視するには？"
    a: "各Macで asiai daemon start web --host 0.0.0.0 を実行し、Prometheusで /api/metrics をスクレイプして、Grafanaで可視化します。"
  - q: "エンジンがクラッシュした場合は？"
    a: "asiai はエンジン障害を自動的に検出します。診断には asiai doctor を使用してください。自動通知のために asiai alert add でWebhookアラートを設定できます。"
---

# エージェント統合ガイド

> **AIエージェントの方へ**: お使いのフレームワークがMCPをサポートしている場合は[MCP](#mcp-model-context-protocol)を使用し、それ以外の場合は[REST API](#rest-apiリファレンス)を使用してください。セットアップについては[クイックスタート](#クイックスタート)をご覧ください。

## 概要

asiai は、2つの仕組みを通じてMacのLLM推論インフラストラクチャをAIエージェントに公開します：

- **MCPサーバー** — [Model Context Protocol](https://modelcontextprotocol.io)によるネイティブツール統合。MCPをサポートするAIエージェント（Claude Code、Cursor、Cline、その他のMCP対応クライアント）に最適です。
- **REST API** — 標準的なHTTP/JSONエンドポイント。エージェントフレームワーク、スウォームオーケストレーター、およびHTTP対応のあらゆるシステム（CrewAI、AutoGen、LangGraph、カスタムエージェント）に最適です。

どちらも同じ機能にアクセスできます：

- システムヘルス（CPU、RAM、GPU、サーマル、スワップ）の**監視**
- 実行中の推論エンジンとロードされたモデルの**検出**
- GPU可観測性と推論アクティビティシグナルを使用したパフォーマンス問題の**診断**
- プログラムによるモデルの**ベンチマーク**とリグレッションの追跡
- ハードウェアに基づく最適なモデル/エンジンの**推奨**の取得

ローカルアクセスには認証は不要です。すべてのインターフェースはデフォルトで `127.0.0.1` にバインドされます。

### どの統合方法を使うべきですか？

| 基準 | MCP | REST API |
|------|-----|----------|
| エージェントがMCPをサポートしている | **MCPを使用** | — |
| スウォーム / マルチエージェントオーケストレーター | — | **REST APIを使用** |
| ポーリング / スケジュール監視 | — | **REST APIを使用** |
| Prometheus / Grafana統合 | — | **REST APIを使用** |
| インタラクティブAIアシスタント（Claude Code、Cursor） | **MCPを使用** | — |
| Dockerコンテナ内のエージェント | — | **REST APIを使用** |
| カスタムスクリプトまたは自動化 | — | **REST APIを使用** |

## クイックスタート

### asiai のインストール

```bash
# Homebrew（推奨）
brew tap druide67/tap && brew install asiai

# pip（MCPサポート付き）
pip install "asiai[mcp]"

# pip（REST APIのみ）
pip install asiai
```

### オプションA: MCPサーバー（MCP対応エージェント向け）

```bash
# MCPサーバーを起動（stdioトランスポート — Claude Code、Cursorなどで使用）
asiai mcp
```

手動でサーバーを起動する必要はありません — MCPクライアントが自動的に `asiai mcp` を起動します。詳細は下記の[MCPセットアップ](#mcp-model-context-protocol)をご覧ください。

### オプションB: REST API（HTTPベースのエージェント向け）

```bash
# フォアグラウンド（開発用）
asiai web --no-open

# バックグラウンドデーモン（本番環境）
asiai daemon start web
```

APIは `http://127.0.0.1:8899` で利用可能です。ポートは `--port` で設定できます：

```bash
asiai daemon start web --port 8642
```

リモートアクセス（別マシンのAIエージェントやDockerコンテナから）の場合：

```bash
asiai daemon start web --host 0.0.0.0
```

> **注意:** エージェントがDocker内で実行されている場合、`127.0.0.1` にはアクセスできません。ホストのネットワークIP（例：`192.168.0.16`）またはDocker Desktop for Macの `host.docker.internal` を使用してください。

### 動作確認

```bash
# REST API
curl http://127.0.0.1:8899/api/status

# MCP（利用可能なツールの一覧）
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | asiai mcp
```

---

## MCP (Model Context Protocol)

asiai は推論監視をネイティブツールとして公開する[MCPサーバー](https://modelcontextprotocol.io)を実装しています。MCP対応のクライアントは直接接続してこれらのツールを使用できます — HTTPのセットアップやURL管理は不要です。

### セットアップ

#### ローカル（同一マシン）

MCPクライアント設定（例：Claude Codeの `~/.claude/settings.json`）に追加してください：

```json
{
  "mcpServers": {
    "asiai": {
      "command": "asiai",
      "args": ["mcp"]
    }
  }
}
```

asiai が仮想環境にインストールされている場合：

```json
{
  "mcpServers": {
    "asiai": {
      "command": "/path/to/.venv/bin/asiai",
      "args": ["mcp"]
    }
  }
}
```

#### リモート（SSH経由の別マシン）

```json
{
  "mcpServers": {
    "asiai": {
      "command": "ssh",
      "args": [
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        "your-mac-host",
        "cd /path/to/asiai && .venv/bin/asiai mcp"
      ]
    }
  }
}
```

#### SSEトランスポート（ネットワーク）

HTTPベースのMCPトランスポートを好む環境の場合：

```bash
asiai mcp --transport sse --host 127.0.0.1 --port 8900
```

### MCPツールリファレンス

すべてのツールはJSONを返します。読み取り専用ツールは2秒未満で応答します。`run_benchmark` のみがアクティブな操作です。

| ツール | 説明 | パラメータ |
|--------|------|------------|
| `check_inference_health` | クイックヘルスチェック — エンジンの稼働/停止状態、メモリプレッシャー、サーマル、GPU使用率 | — |
| `get_inference_snapshot` | フルシステム状態のスナップショット（履歴用にSQLiteに保存） | — |
| `list_models` | 全エンジンにロードされた全モデル（VRAM、量子化、コンテキスト長） | — |
| `detect_engines` | 3層検出：設定、ポートスキャン、プロセス検出。非標準ポートのエンジンも自動検出 | — |
| `run_benchmark` | モデルのベンチマークまたはクロスモデル比較を実行。レート制限：60秒に1回 | `model`（任意）、`runs`（1〜10、デフォルト3）、`compare`（文字列リスト、任意、`model`と排他、最大8） |
| `get_recommendations` | ハードウェアに応じたモデル/エンジンの推奨 | — |
| `diagnose` | 診断チェック（システム、エンジン、デーモンヘルス）を実行 | — |
| `get_metrics_history` | SQLiteからの過去のシステムメトリクス | `hours`（1〜168、デフォルト24） |
| `get_benchmark_history` | 過去のベンチマーク結果 | `hours`（1〜720、デフォルト24）、`model`（任意）、`engine`（任意） |
| `compare_engines` | 指定モデルに対するエンジン比較のランキングと判定；履歴からのマルチモデル比較をサポート | `model`（必須） |
| `refresh_engines` | MCPサーバーを再起動せずにエンジンを再検出 | — |

### MCPリソース

ツールを呼び出さずに利用可能な静的データエンドポイント：

| URI | 説明 |
|-----|------|
| `asiai://status` | 現在のヘルスステータス（メモリ、サーマル、GPU） |
| `asiai://models` | 全エンジンのロード済みモデル |
| `asiai://system` | ハードウェア情報（チップ、RAM、コア数、OS、稼働時間） |

### MCPセキュリティ

- **sudo不要**: MCPモードでは電力メトリクスが無効化されます（`power=False` が強制）
- **レート制限**: ベンチマークは60秒に1回に制限
- **入力クランプ**: `hours` は1〜168、`runs` は1〜10にクランプ
- **デフォルトでローカル**: stdioトランスポートはネットワーク露出なし；SSEは `127.0.0.1` にバインド

### MCPの制限事項

- **再接続なし**: SSH接続が切断された場合（ネットワーク問題、Macのスリープ）、MCPサーバーは停止し、クライアントは手動で再接続する必要があります。無人監視には、ポーリングによるREST APIの方が堅牢です。
- **シングルクライアント**: stdioトランスポートは一度に1つのクライアントにのみ対応します。複数クライアントの同時アクセスが必要な場合は、SSEトランスポートを使用してください。

---

## REST APIリファレンス

asiai のAPIは**読み取り専用**です — 監視とレポートのみで、エンジンの制御は行いません。モデルのロード/アンロードには、エンジン固有のコマンド（`ollama pull`、`lms load` など）を使用してください。

すべてのエンドポイントはHTTP 200でJSONを返します。エンジンに到達できない場合でも、そのエンジンの `"running": false` を含むHTTP 200のレスポンスが返されます — API自体は失敗しません。

| エンドポイント | 通常のレスポンスタイム | 推奨タイムアウト |
|--------------|----------------------|----------------|
| `GET /api/status` | 500ms未満（10秒キャッシュ） | 2秒 |
| `GET /api/snapshot` | 1〜3秒（ライブ収集） | 10秒 |
| `GET /api/metrics` | 500ms未満 | 2秒 |
| `GET /api/history` | 500ms未満 | 5秒 |
| `GET /api/engine-history` | 500ms未満 | 5秒 |

### `GET /api/status`

クイックヘルスチェック。10秒キャッシュ。レスポンスタイム500ms未満。

**レスポンス：**

```json
{
  "hostname": "mac-mini",
  "chip": "Apple M4 Pro",
  "ram_gb": 64.0,
  "cpu_percent": 12.3,
  "memory_pressure": "normal",
  "gpu_utilization_percent": 45.2,
  "engines": {
    "ollama": {
      "running": true,
      "models_loaded": 2,
      "port": 11434
    },
    "lmstudio": {
      "running": true,
      "models_loaded": 1,
      "port": 1234
    }
  },
  "asiai_version": "1.0.1",
  "uptime_seconds": 86400
}
```

### `GET /api/snapshot`

フルシステム状態。`/api/status` のすべてに加え、詳細なモデル情報、GPUメトリクス、サーマルデータを含みます。

**レスポンス：**

```json
{
  "system": {
    "hostname": "mac-mini",
    "chip": "Apple M4 Pro",
    "cores_p": 12,
    "cores_e": 4,
    "gpu_cores": 20,
    "ram_total_gb": 64.0,
    "ram_used_gb": 41.2,
    "ram_percent": 64.4,
    "swap_used_gb": 0.0,
    "memory_pressure": "normal",
    "cpu_percent": 12.3,
    "thermal_state": "nominal",
    "gpu_utilization_percent": 45.2,
    "gpu_renderer_percent": 38.1,
    "gpu_tiler_percent": 12.4,
    "gpu_memory_allocated_bytes": 8589934592
  },
  "engines": [
    {
      "name": "ollama",
      "running": true,
      "port": 11434,
      "models": [
        {
          "name": "qwen3.5:latest",
          "size_params": "35B",
          "size_vram_bytes": 21474836480,
          "quantization": "Q4_K_M",
          "context_length": 32768
        }
      ]
    }
  ],
  "timestamp": "2026-03-09T14:30:00Z"
}
```

### `GET /api/metrics`

Prometheus互換メトリクス。Prometheus、Datadog、またはその他の互換ツールでスクレイプできます。

**レスポンス (text/plain)：**

```
# HELP asiai_cpu_percent CPU usage percentage
# TYPE asiai_cpu_percent gauge
asiai_cpu_percent 12.3

# HELP asiai_ram_used_gb RAM used in GB
# TYPE asiai_ram_used_gb gauge
asiai_ram_used_gb 41.2

# HELP asiai_gpu_utilization_percent GPU utilization percentage
# TYPE asiai_gpu_utilization_percent gauge
asiai_gpu_utilization_percent 45.2

# HELP asiai_engine_up Engine availability (1=up, 0=down)
# TYPE asiai_engine_up gauge
asiai_engine_up{engine="ollama"} 1
asiai_engine_up{engine="lmstudio"} 1

# HELP asiai_models_loaded Number of models loaded per engine
# TYPE asiai_models_loaded gauge
asiai_models_loaded{engine="ollama"} 2
```

### `GET /api/history?hours=N`

SQLiteからの過去のシステムメトリクス。デフォルト：`hours=24`。最大：`hours=2160`（90日）。

**レスポンス：**

```json
{
  "points": [
    {
      "timestamp": "2026-03-09T14:00:00Z",
      "cpu_percent": 15.2,
      "ram_used_gb": 40.1,
      "ram_percent": 62.7,
      "swap_used_gb": 0.0,
      "memory_pressure": "normal",
      "thermal_state": "nominal",
      "gpu_utilization_percent": 42.0,
      "gpu_renderer_percent": 35.0,
      "gpu_tiler_percent": 10.0,
      "gpu_memory_allocated_bytes": 8589934592
    }
  ],
  "count": 144,
  "hours": 24
}
```

### `GET /api/engine-history?engine=X&hours=N`

エンジン固有のアクティビティ履歴。推論パターンの検出に便利です。

**パラメータ：**

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| `engine`  | はい | —         | エンジン名（ollama、lmstudioなど） |
| `hours`   | いいえ | 24      | 時間範囲 |

**レスポンス：**

```json
{
  "engine": "ollama",
  "points": [
    {
      "timestamp": "2026-03-09T14:00:00Z",
      "running": true,
      "tcp_connections": 3,
      "requests_processing": 1,
      "kv_cache_usage_percent": 45.2
    }
  ],
  "count": 144,
  "hours": 24
}
```

## メトリクスの解釈

### システムヘルスの閾値

| メトリクス | 正常 | 警告 | 危険 |
|-----------|------|------|------|
| `memory_pressure` | `normal` | `warn` | `critical` |
| `ram_percent` | 75%未満 | 75〜90% | 90%超 |
| `swap_used_gb` | 0 | 0.1〜2.0 | 2.0超 |
| `thermal_state` | `nominal` | `fair` | `serious` / `critical` |
| `cpu_percent` | 80%未満 | 80〜95% | 95%超 |

### GPUの閾値

| メトリクス | アイドル | 推論中 | 過負荷 |
|-----------|---------|--------|--------|
| `gpu_utilization_percent` | 0〜5% | 20〜80% | 90%超（持続） |
| `gpu_renderer_percent` | 0〜5% | 15〜70% | 85%超（持続） |
| `gpu_memory_allocated_bytes` | 1 GB未満 | 2〜48 GB | RAMの90%超 |

> **重要:** `gpu_utilization_percent = 0` はGPUがアイドル状態であることを意味し、故障ではありません。`-1.0` はメトリクスが利用できないこと（例：非対応ハードウェアまたは収集失敗）を意味します — 「GPU停止」として扱わないでください。

### 推論パフォーマンス

| メトリクス | 優秀 | 良好 | 劣化 |
|-----------|------|------|------|
| `tok/s`（7Bモデル） | 80超 | 40〜80 | 40未満 |
| `tok/s`（35Bモデル） | 40超 | 20〜40 | 20未満 |
| `tok/s`（70Bモデル） | 15超 | 8〜15 | 8未満 |
| `TTFT` | 100ms未満 | 100〜500ms | 500ms超 |

## 診断デシジョンツリー

### 生成速度低下（低tok/s）

```
tok/sが期待値を下回っていますか？
├── memory_pressureを確認
│   ├── "critical" → モデルがディスクにスワップ中。モデルをアンロードするかRAMを増設してください。
│   └── "normal" → 続行
├── thermal_stateを確認
│   ├── "serious"/"critical" → サーマルスロットリング。冷却を行い、通気を確認してください。
│   └── "nominal" → 続行
├── gpu_utilization_percentを確認
│   ├── 10%未満 → GPUが使用されていません。エンジン設定（num_gpuレイヤー）を確認してください。
│   ├── 90%超 → GPU飽和。同時リクエストを減らしてください。
│   └── 20-80% → 正常。モデルの量子化とコンテキストサイズを確認してください。
└── swap_used_gbを確認
    ├── 0超 → モデルがRAMに収まりません。より小さい量子化を使用してください。
    └── 0 → エンジンのバージョンを確認し、別のエンジンを試してください。
```

### エンジン無応答

```
engine.running == false?
├── プロセスの存在を確認: lsof -i :<port>
│   ├── プロセスなし → エンジンがクラッシュしました。再起動してください。
│   └── プロセスは存在するが応答なし → エンジンがハング。
├── memory_pressureを確認
│   ├── "critical" → OOMキルされました。先に他のモデルをアンロードしてください。
│   └── "normal" → エンジンのログを確認してください。
└── 試行: asiai doctor（包括的な診断）
```

### 高メモリプレッシャー / VRAMオーバーフロー

```
memory_pressure == "warn" または "critical"?
├── swap_used_gbを確認
│   ├── 2 GB超 → VRAMオーバーフロー。モデルがユニファイドメモリに収まりません。
│   │   ├── レイテンシが5〜50倍悪化します（ディスクスワップ）。
│   │   ├── モデルをアンロード: ollama rm <model>、lms unload
│   │   └── またはより小さい量子化を使用（Q4_K_M → Q3_K_S）。
│   └── 2 GB未満 → 管理可能ですが注意して監視してください。
├── 全エンジンのロード済みモデルを確認
│   ├── 複数の大型モデル → 未使用モデルをアンロード
│   │   ├── Ollama: ollama rm <model> または自動アンロードを待機
│   │   └── LM Studio: UIまたは lms unload でアンロード
│   └── 単一モデルがRAMの80%超 → より小さい量子化を使用
└── gpu_memory_allocated_bytesを確認
    └── ram_total_gbと比較。80%超の場合、次のモデルロードでスワップが発生します。
```

## 推論アクティビティシグナル

asiai は複数のシグナルを通じてアクティブな推論を検出します：

### GPU使用率

```
GET /api/snapshot → system.gpu_utilization_percent
```

- **5%未満**: 推論は実行されていません
- **20〜80%**: アクティブな推論（Apple Siliconユニファイドメモリの通常範囲）
- **90%超**: 大量の推論または複数の同時リクエスト

### TCP接続

```
GET /api/engine-history?engine=ollama&hours=1
```

アクティブな推論リクエストはそれぞれTCP接続を維持します。`tcp_connections` のスパイクはアクティブな生成を示します。

### エンジン固有メトリクス

`/metrics` を公開するエンジン（llama.cpp、vllm-mlx）の場合：

- `requests_processing > 0`: アクティブな推論
- `kv_cache_usage_percent > 0`: モデルにアクティブなコンテキストがあります

### 相関パターン

最も信頼性の高い推論検出は、複数のシグナルを組み合わせます：

```python
snapshot = get_snapshot()
gpu_active = snapshot["system"]["gpu_utilization_percent"] > 15
engine_busy = any(
    e.get("tcp_connections", 0) > 0
    for e in snapshot.get("engine_status", [])
)
inference_running = gpu_active and engine_busy
```

## コード例

### ヘルスチェック（Python、標準ライブラリのみ）

```python
import json
import urllib.request

ASIAI_URL = "http://127.0.0.1:8899"  # Docker: ホストIPまたはhost.docker.internalを使用

def check_health():
    """クイックヘルスチェック。ステータスのdictを返します。"""
    req = urllib.request.Request(f"{ASIAI_URL}/api/status")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())

def is_healthy(status):
    """ヘルスステータスを解釈します。"""
    issues = []
    if status.get("memory_pressure") != "normal":
        issues.append(f"memory_pressure: {status['memory_pressure']}")
    gpu = status.get("gpu_utilization_percent", 0)
    if gpu > 90:
        issues.append(f"gpu_utilization: {gpu}%")
    engines = status.get("engines", {})
    for name, info in engines.items():
        if not info.get("running"):
            issues.append(f"engine_down: {name}")
    return {"healthy": len(issues) == 0, "issues": issues}

# 使用例
status = check_health()
health = is_healthy(status)
if not health["healthy"]:
    print(f"Issues detected: {health['issues']}")
```

### フルシステム状態

```python
def get_full_state():
    """完全なシステムスナップショットを取得します。"""
    req = urllib.request.Request(f"{ASIAI_URL}/api/snapshot")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

def get_history(hours=24):
    """過去のメトリクスを取得します。"""
    req = urllib.request.Request(f"{ASIAI_URL}/api/history?hours={hours}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

# パフォーマンストレンドの検出
history = get_history(hours=6)
points = history["points"]
if len(points) >= 2:
    recent_gpu = points[-1].get("gpu_utilization_percent", 0)
    earlier_gpu = points[0].get("gpu_utilization_percent", 0)
    if recent_gpu > earlier_gpu * 1.5:
        print("GPU utilization trending up significantly")
```

## ベンチマークカード（共有可能な画像）

CLIで共有可能なベンチマークカード画像を生成できます：

```bash
asiai bench --card                    # SVGをローカルに保存（依存関係ゼロ）
asiai bench --card --share            # SVG + PNG（コミュニティAPI経由）
asiai bench --quick --card --share    # クイックベンチ + カード + 共有（約15秒）
```

モデル、チップ、エンジン比較バーチャート、勝者ハイライト、メトリクスチップを含む**1200x630のダークテーマカード**です。Reddit、X、Discord、GitHub READMEに最適化されています。

カードはSVGとして `~/.local/share/asiai/cards/` に保存されます。`--share` を追加すると、PNGダウンロードと共有可能なURLが取得できます — PNGはReddit、X、Discordへの投稿に必要です。

### MCP経由

`run_benchmark` MCPツールは `card` パラメータでカード生成をサポートします：

```json
{"tool": "run_benchmark", "arguments": {"model": "qwen3.5", "card": true}}
```

レスポンスには `card_path` が含まれます — MCPサーバーファイルシステム上のSVGファイルへの絶対パスです。

## Webhookアラート（プッシュ通知）

ポーリングの代わりに、状態変化が発生した際にasiai がプッシュ通知を送信するよう設定できます：

```bash
# Webhookを追加（Slack、Discord、または任意のURL）
asiai alert add https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# アラートのトリガー：
# - エンジンの停止 / 復帰
# - メモリプレッシャーの遷移（normal → warn → critical）
# - サーマルスロットリングの検出
```

アラートは**遷移時のみ**発火し（毎回のチェックではなく）、フラッディング防止のため5分間のクールダウンがあります。継続的なポーリングなしにインフラストラクチャの変化に対応する必要があるスウォームオーケストレーターに最適です。

アラートの一覧と削除：`asiai alert list`、`asiai alert remove <id>`。

## エージェントの識別

REST APIリクエストにエージェントを識別する `User-Agent` ヘッダーを含めることを**推奨**します：

```
User-Agent: asiai-agent/<framework>/<version>
```

例：

- `User-Agent: asiai-agent/openclaw/1.2.0`
- `User-Agent: asiai-agent/crewai/0.5`
- `User-Agent: asiai-agent/custom-orchestrator/1.0`

これは**必須ではありません** — User-Agentヘッダーなしのリクエストも正常に動作します。ただし、以下の点で役立ちます：

- **デバッグ** — ログでエージェントリクエストとブラウザアクセスを区別
- **エージェント別分析** — どのエージェントがAPIにアクセスし、頻度やエンドポイントを把握
- **マルチエージェント環境** — 複数のエージェントが同じasiai インスタンスを共有する際の識別

MCPクライアントの場合、識別は自動的です（MCPプロトコルにクライアントメタデータが含まれます）。

---

## エージェント登録（オプション）

登録は**完全に任意**です — asiai は登録なしで完全に動作します。デフォルトではテレメトリやフォンホームは一切ありません。

登録を選択すると、asiai エージェントネットワークに参加できます：1回のAPI呼び出し、メール不要、個人データ不要 — ハードウェア情報のみです。

```bash
curl -X POST https://api.asiai.dev/api/v1/agent-register \
  -H "Content-Type: application/json" \
  -d '{
    "chip": "Apple M4 Pro",
    "ram_gb": 64,
    "engines": ["ollama", "lmstudio"],
    "framework": "my-agent",
    "asiai_version": "1.0.1"
  }'
```

**レスポンス：**

```json
{
  "status": "registered",
  "agent_id": "a1b2c3d4e5f6",
  "agent_token": "secret_...",
  "total_agents": 42
}
```

`agent_id` と `agent_token` を `~/.local/share/asiai/agent.json` に安全に保存してください。コミュニティAPI呼び出しやベンチマーク提出に必要です。

### 登録で解放される機能

| 機能 | agent_idなし | agent_idあり |
|------|-------------|-------------|
| ローカルbench/monitor/web | はい | はい |
| `/api/status`、`/api/snapshot` | はい | はい |
| `--share` ベンチマーク | いいえ | **はい** |
| `asiai compare`（コミュニティ） | いいえ | **はい** |
| `asiai recommend --community` | いいえ | **はい** |
| パーセンタイル統計 | いいえ | **はい** |
| エージェントディレクトリ（同じチップのピアを検索） | いいえ | **はい** |
| パフォーマンスアラート（新エンジンがあなたを上回る） | いいえ | **近日公開** |

### ハートビート

定期的なハートビートで登録をアクティブに保ちます：

```bash
curl -X POST https://api.asiai.dev/api/v1/agent-heartbeat \
  -H "Content-Type: application/json" \
  -H "X-Agent-Id: a1b2c3d4e5f6" \
  -H "X-Agent-Token: secret_..." \
  -d '{
    "engines": ["ollama", "lmstudio"],
    "version": "1.0.1",
    "models_loaded": 3,
    "uptime_hours": 72
  }'
```

### プライバシー

- **IPアドレスの保存なし** — IPはレート制限にのみ使用され、エージェントレジストリには保存されません
- **個人データなし** — ハードウェア情報（チップ、RAM）、エンジン名、フレームワーク名のみ
- **オプトインのみ** — 明示的に登録しない限り、asiai はフォンホームしません
- **トークンセキュリティ** — `agent_token` は保存前にハッシュ化（SHA-256）されます；プレーンテキストは登録時に一度だけ返されます
- **レート制限データ** — レート制限テーブルのIPハッシュ（日替わりソルトのSHA-256）は30日後に自動的に削除されます

## FAQ

**Q: asiai にはroot/sudo権限が必要ですか？**
A: いいえ。GPU可観測性は `ioreg`（権限不要）を使用します。電力メトリクス（ベンチマークの `--power` フラグ）は `sudo powermetrics` を必要としますが、これはオプションです。

**Q: APIのレスポンスタイムは？**
A: `/api/status` は500ms未満で応答します（10秒キャッシュ）。`/api/snapshot` は1〜3秒かかります（全エンジンからライブデータを収集）。

**Q: asiai をLinuxで実行できますか？**
A: いいえ。asiai はmacOS Apple Silicon専用です。`sysctl`、`vm_stat`、`ioreg`、`launchd` など、すべてmacOS固有のAPIを使用しています。

**Q: 複数のMacを監視するには？**
A: 各Macで `asiai daemon start web --host 0.0.0.0` を実行してください。Prometheusで `/api/metrics` をスクレイプし、Grafanaで可視化します。

**Q: エンジンがクラッシュした場合は？**
A: asiai はエンジン障害を自動的に検出します。診断には `asiai doctor` を使用してください。自動通知のために `asiai alert add` でWebhookアラートを設定できます。
