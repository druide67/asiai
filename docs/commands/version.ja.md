---
description: "asiai のバージョン、Python環境、エージェント登録ステータスを1つのコマンドで確認。"
---

# asiai version

バージョンとシステム情報を表示します。

## 使用方法

```bash
asiai version
asiai --version
```

## 出力

`version` サブコマンドは拡張されたシステムコンテキストを表示します：

```
asiai 1.0.1
  Apple M4 Pro, 64 GB RAM
  Engines: ollama, lmstudio
  Daemon: monitor, web
```

`--version` フラグはバージョン文字列のみを表示します：

```
asiai 1.0.1
```

## 用途

- イシューやバグレポートでのクイックシステムチェック
- エージェントのコンテキスト収集（チップ、RAM、利用可能なエンジン）
- スクリプト用：`VERSION=$(asiai version | head -1)`
