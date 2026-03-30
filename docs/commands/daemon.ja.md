---
description: "asiai をMacでバックグラウンドデーモンとして実行：起動時に自動開始の監視、Webダッシュボード、Prometheusメトリクス。"
---

# asiai daemon

macOS launchd LaunchAgentによるバックグラウンドサービスを管理します。

## サービス

| サービス | 説明 | モデル |
|---------|------|--------|
| `monitor` | 定期的にシステム + 推論メトリクスを収集 | 周期的（`StartInterval`） |
| `web` | Webダッシュボードを永続サービスとして実行 | 常駐（`KeepAlive`） |

## 使用方法

```bash
# 監視デーモン（デフォルト）
asiai daemon start                     # 監視開始（60秒ごと）
asiai daemon start --interval 30       # カスタム間隔
asiai daemon start --alert-webhook URL # Webhookアラートを有効化

# Webダッシュボードサービス
asiai daemon start web                 # 127.0.0.1:8899でWeb開始
asiai daemon start web --port 9000     # カスタムポート
asiai daemon start web --host 0.0.0.0  # ネットワークに公開（認証なし！）

# ステータス（すべてのサービスを表示）
asiai daemon status

# 停止
asiai daemon stop                      # monitor停止
asiai daemon stop web                  # web停止
asiai daemon stop --all                # すべてのサービスを停止

# ログ
asiai daemon logs                      # monitorログ
asiai daemon logs web                  # webログ
asiai daemon logs web -n 100           # 最後の100行
```

## 仕組み

各サービスは `~/Library/LaunchAgents/` に個別のlaunchd LaunchAgent plistをインストールします：

- **Monitor**: 設定された間隔（デフォルト：60秒）で `asiai monitor --quiet` を実行。データはSQLiteに保存。`--alert-webhook` が指定された場合、状態遷移（メモリプレッシャー、サーマル、エンジンダウン）時にアラートをPOST。
- **Web**: `asiai web --no-open` を永続プロセスとして実行。クラッシュ時に自動再起動（`KeepAlive: true`、`ThrottleInterval: 10s`）。

両サービスはログイン時に自動起動（`RunAtLoad: true`）。

## セキュリティ

- サービスは**ユーザーレベル**で実行（root不要）
- Webダッシュボードはデフォルトで `127.0.0.1` にバインド（ローカルホストのみ）
- `--host 0.0.0.0` 使用時に警告を表示 — 認証は設定されていません
- ログは `~/.local/share/asiai/` に保存
