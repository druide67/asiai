---
description: "asiai の設定方法：MacでのLLMベンチマーク用にエンジンURL、ポート、永続設定を管理。"
---

# asiai config

永続的なエンジン設定を管理します。`asiai detect` で検出されたエンジンは、次回の検出を高速化するために `~/.config/asiai/engines.json` に自動保存されます。

## 使用方法

```bash
asiai config show              # 既知のエンジンを表示
asiai config add <engine> <url> [--label NAME]  # エンジンを手動追加
asiai config remove <url>      # エンジンを削除
asiai config reset             # すべての設定をクリア
```

## サブコマンド

### show

URL、バージョン、ソース（auto/manual）、最終確認タイムスタンプと共にすべての既知エンジンを表示。

```
$ asiai config show
Known engines (3):
  ollama v0.17.7 at http://localhost:11434  (auto)  last seen 2m ago
  lmstudio v0.4.6 at http://localhost:1234  (auto)  last seen 2m ago
  omlx v0.9.2 at http://localhost:8800 [mac-mini]  (manual)  last seen 5m ago
```

### add

非標準ポートのエンジンを手動登録。手動エンジンは自動プルーニングされません。

```bash
asiai config add omlx http://localhost:8800 --label mac-mini
asiai config add ollama http://192.168.0.16:11434 --label mini
```

### remove

URLでエンジンエントリを削除。

```bash
asiai config remove http://localhost:8800
```

### reset

設定ファイル全体を削除。次の `asiai detect` でエンジンをゼロから再検出します。

## 仕組み

設定ファイルは検出時に発見されたエンジンを保存します：

- **Autoエントリ**（`source: auto`）：`asiai detect` が新しいエンジンを見つけたときに自動作成。7日間非アクティブ後にプルーニング。
- **Manualエントリ**（`source: manual`）：`asiai config add` で作成。自動プルーニングされません。

`asiai detect` の3層検出カスケードはこの設定をレイヤー1（最速）として使用し、続いてポートスキャン（レイヤー2）とプロセス検出（レイヤー3）を行います。詳細は [detect](detect.md) を参照。

## 設定ファイルの場所

```
~/.config/asiai/engines.json
```
