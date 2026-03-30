---
description: Apple Siliconでサイドバイサイドのベンチマークを実行。エンジン比較、tok/s、TTFT、電力効率を測定。結果を共有。
---

# asiai bench

標準化プロンプトによるクロスエンジンベンチマーク。

## 使用方法

```bash
asiai bench [options]
```

## オプション

| オプション | 説明 |
|-----------|------|
| `-m, --model MODEL` | ベンチマーク対象モデル（デフォルト：自動検出） |
| `-e, --engines LIST` | エンジンフィルター（例：`ollama,lmstudio,mlxlm`） |
| `-p, --prompts LIST` | プロンプトタイプ：`code`、`tool_call`、`reasoning`、`long_gen` |
| `-r, --runs N` | プロンプトあたりの実行回数（デフォルト：3、中央値 + 標準偏差用） |
| `--power` | sudo powermetricsで電力をクロスバリデーション（IOReportは常時有効） |
| `--context-size SIZE` | コンテキストフィルプロンプト：`4k`、`16k`、`32k`、`64k` |
| `--export FILE` | 結果をJSONファイルにエクスポート |
| `-H, --history PERIOD` | 過去のベンチマークを表示（例：`7d`、`24h`） |
| `-Q, --quick` | クイックベンチマーク：1プロンプト（code）、1回実行（約15秒） |
| `--compare MODEL [MODEL...]` | クロスモデル比較（2〜8モデル、`-m`と排他） |
| `--card` | 共有可能なベンチマークカードを生成（ローカルSVG、`--share`でPNG） |
| `--share` | コミュニティベンチマークデータベースに結果を共有 |

## 例

```bash
asiai bench -m qwen3.5 --runs 3 --power
```

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

## プロンプト

4つの標準化プロンプトが異なる生成パターンをテストします：

| 名前 | トークン | テスト内容 |
|------|---------|-----------|
| `code` | 512 | 構造化コード生成（PythonでBST） |
| `tool_call` | 256 | JSON関数呼び出し / 指示追従 |
| `reasoning` | 384 | 多段階数学問題 |
| `long_gen` | 1024 | 持続スループット（bashスクリプト） |

`--context-size` を使用すると、大規模コンテキストフィルプロンプトでテストできます。

## クロスエンジンモデルマッチング

ランナーはエンジン間でモデル名を自動解決します — `gemma2:9b`（Ollama）と `gemma-2-9b`（LM Studio）は同じモデルとしてマッチングされます。

## JSONエクスポート

結果を共有・分析用にエクスポート：

```bash
asiai bench -m qwen3.5 --export bench.json
```

JSONにはマシンメタデータ、エンジンごとの統計（中央値、CI 95%、P50/P90/P99）、生のランごとのデータ、前方互換性のためのスキーマバージョンが含まれます。

## リグレッション検出

各ベンチマーク後、asiai は過去7日間の履歴と比較し、パフォーマンスリグレッション（エンジンアップデートやmacOSアップグレード後など）を警告します。

## クイックベンチマーク

1プロンプト、1回実行の高速ベンチマーク（約15秒）：

```bash
asiai bench --quick
asiai bench -Q -m qwen3.5
```

デモ、GIF、クイックチェックに最適です。デフォルトで `code` プロンプトが使用されます。必要に応じて `--prompts` でオーバーライドできます。

## クロスモデル比較

`--compare` で複数モデルを1セッションで比較：

```bash
# 利用可能な全エンジンに自動展開
asiai bench --compare qwen3.5:4b deepseek-r1:7b

# 特定エンジンにフィルター
asiai bench --compare qwen3.5:4b deepseek-r1:7b -e ollama

# @で各モデルをエンジンに固定
asiai bench --compare qwen3.5:4b@lmstudio deepseek-r1:7b@ollama
```

`@` 表記は文字列の**最後の** `@` で分割するため、`@` を含むモデル名も正しく処理されます。

### ルール

- `--compare` と `--model` は**排他的** — どちらか一方を使用。
- 2〜8モデルスロットを受け付け。
- `@` なしの場合、各モデルは利用可能なすべてのエンジンに展開されます。

### セッションタイプ

スロットリストに基づいて自動的にセッションタイプが検出されます：

| タイプ | 条件 | 例 |
|--------|------|-----|
| **engine** | 同一モデル、異なるエンジン | `--compare qwen3.5:4b@lmstudio qwen3.5:4b@ollama` |
| **model** | 異なるモデル、同一エンジン | `--compare qwen3.5:4b deepseek-r1:7b -e ollama` |
| **matrix** | モデルとエンジンの混合 | `--compare qwen3.5:4b@lmstudio deepseek-r1:7b@ollama` |

### 他のフラグとの組み合わせ

`--compare` はすべての出力・実行フラグと組み合わせ可能：

```bash
asiai bench --compare qwen3.5:4b deepseek-r1:7b --quick
asiai bench --compare qwen3.5:4b deepseek-r1:7b --card --share
asiai bench --compare qwen3.5:4b deepseek-r1:7b --runs 5 --power
```

## ベンチマークカード

共有可能なベンチマークカードを生成：

```bash
asiai bench --card                    # SVGをローカルに保存
asiai bench --card --share            # SVG + PNG（コミュニティAPI経由）
asiai bench --quick --card --share    # クイックベンチ + カード + 共有
```

カードは1200x630のダークテーマ画像で以下を含みます：
- モデル名とハードウェアチップバッジ
- スペックバナー：量子化、RAM、GPUコア、コンテキストサイズ
- エンジンごとのtok/sターミナルスタイルバーチャート
- デルタ付き勝者ハイライト（例：「2.4x」）
- メトリクスチップ：tok/s、TTFT、安定性、VRAM、電力（W + tok/s/W）、エンジンバージョン
- asiai ブランディング

SVGは `~/.local/share/asiai/cards/` に保存されます。`--share` を使用すると、APIからPNGもダウンロードされます。

## コミュニティ共有

結果を匿名で共有：

```bash
asiai bench --share
```

コミュニティリーダーボードは `asiai leaderboard` で表示できます。

## サーマルドリフト検出

3回以上の実行時、asiai は連続する実行間でのtok/sの単調減少を検出します。tok/sが一貫して低下する場合（5%超）、サーマルスロットリングの蓄積の可能性を示す警告が出力されます。
