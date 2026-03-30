---
description: AIエージェントが推論エンジンを監視し、ベンチマークを実行し、ハードウェアに基づく推奨を取得するための11ツールを公開するMCPサーバー。
---

# asiai mcp

MCP（Model Context Protocol）サーバーを起動し、AIエージェントが推論インフラストラクチャを監視・ベンチマークできるようにします。

## 使用方法

```bash
asiai mcp                          # stdioトランスポート（Claude Code）
asiai mcp --transport sse          # SSEトランスポート（ネットワークエージェント）
asiai mcp --transport sse --port 9000
```

## オプション

| オプション | 説明 |
|-----------|------|
| `--transport` | トランスポートプロトコル：`stdio`（デフォルト）、`sse`、`streamable-http` |
| `--host` | バインドアドレス（デフォルト：`127.0.0.1`） |
| `--port` | SSE/HTTPトランスポートのポート（デフォルト：`8900`） |
| `--register` | asiai エージェントネットワークへのオプトイン登録（匿名） |

## ツール（11）

| ツール | 説明 | 読み取り専用 |
|--------|------|------------|
| `check_inference_health` | クイックヘルスチェック：エンジン稼働/停止、メモリプレッシャー、サーマル、GPU | はい |
| `get_inference_snapshot` | 全メトリクスを含むフルシステムスナップショット | はい |
| `list_models` | 全エンジンのロード済みモデル一覧 | はい |
| `detect_engines` | 推論エンジンの再スキャン | はい |
| `run_benchmark` | ベンチマークまたはクロスモデル比較を実行（レート制限：1回/分） | いいえ |
| `get_recommendations` | ハードウェアに基づくエンジン/モデル推奨 | はい |
| `diagnose` | 診断チェック実行（`asiai doctor` と同等） | はい |
| `get_metrics_history` | 過去のメトリクスをクエリ（1-168時間） | はい |
| `get_benchmark_history` | フィルター付きで過去のベンチマーク結果をクエリ | はい |
| `compare_engines` | モデルに対するエンジン性能を判定付きで比較；履歴からのマルチモデル比較をサポート | はい |
| `refresh_engines` | サーバー再起動なしでエンジンを再検出 | はい |

## リソース（3）

| リソース | URI | 説明 |
|---------|-----|------|
| システムステータス | `asiai://status` | 現在のシステムヘルス（メモリ、サーマル、GPU） |
| モデル | `asiai://models` | 全エンジンのロード済みモデル |
| システム情報 | `asiai://system` | ハードウェア情報（チップ、RAM、コア、OS、稼働時間） |

## Claude Code統合

Claude Code MCP設定（`~/.claude/claude_desktop_config.json`）に追加：

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

その後、Claudeに「推論のヘルスをチェックして」や「qwen3.5でOllamaとLM Studioを比較して」と聞いてみてください。

## ベンチマークカード

`run_benchmark` ツールは `card` パラメータでカード生成をサポート。`card=true` の場合、1200x630のSVGベンチマークカードが生成され、レスポンスに `card_path` が返されます。

```json
{"tool": "run_benchmark", "arguments": {"model": "qwen3.5", "card": true}}
```

クロスモデル比較（`model`と排他、最大8スロット）：

```json
{"tool": "run_benchmark", "arguments": {"compare": ["qwen3.5:4b", "deepseek-r1:7b"], "card": true}}
```

PNG + 共有のCLI相当：

```bash
asiai bench --quick --card --share    # クイックベンチ + カード + 共有（約15秒）
```

詳細は[ベンチマークカード](../benchmark-card.md)ページを参照。

## エージェント登録

asiai エージェントネットワークに参加してコミュニティ機能（リーダーボード、比較、パーセンタイル統計）を利用：

```bash
asiai mcp --register                  # 初回登録、以降はハートビート
asiai unregister                      # ローカル資格情報を削除
```

登録は**オプトインかつ匿名**です — ハードウェア情報（チップ、RAM）とエンジン名のみが送信されます。IP、ホスト名、個人データは保存されません。資格情報は `~/.local/share/asiai/agent.json`（chmod 600）に保存されます。

以降の `asiai mcp --register` 呼び出しでは、再登録の代わりにハートビートが送信されます。APIに到達できない場合、MCPサーバーは登録なしで通常起動します。

登録ステータスは `asiai version` で確認できます。

## ネットワークエージェント

他のマシン上のエージェント用（例：ヘッドレスMac Miniの監視）：

```bash
asiai mcp --transport sse --host 0.0.0.0 --port 8900
```

詳細なセットアップ手順は[エージェント統合ガイド](../agent.md)を参照。
