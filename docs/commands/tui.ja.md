---
description: "asiai のターミナルUI：ターミナル内のインタラクティブダッシュボードでLLM推論エンジンをリアルタイム監視。"
---

# asiai tui

自動リフレッシュ付きのインタラクティブターミナルダッシュボード。

## 使用方法

```bash
asiai tui
```

## 必要条件

`tui` エクストラが必要です：

```bash
pip install asiai[tui]
```

ターミナルUI用に [Textual](https://textual.textualize.io/) がインストールされます。

## 機能

- リアルタイムシステムメトリクス（CPU、メモリ、サーマル）
- エンジンステータスとロード済みモデル
- 設定可能な間隔での自動リフレッシュ
