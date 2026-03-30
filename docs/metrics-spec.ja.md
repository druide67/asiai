---
description: "asiai ベンチマークメトリクスの詳細定義：tok/s、TTFT、電力ワット、効率、VRAM、安定性、サーマル状態。"
---

# ベンチマークメトリクス仕様

> **バージョン**: 0.4.0
> **ステータス**: 実装済み
> **スコープ**: `asiai bench` — 全エンジン

## 背景

ベンチマーク結果は**エンジン間で比較可能**でなければなりません。各メトリクスには、すべてのエンジン実装が尊重すべき単一の定義があります。実装は異なる場合があります（サーバーサイドAPIまたはクライアントサイド測定）が、セマンティクスは同一でなければなりません。

## メトリクス

### M1. `tok_per_sec` — 生成速度

**定義**: プロンプト処理（TTFT）を除く**生成時間のみ**の1秒あたり生成トークン数。

```
generation_s = total_duration_s - ttft_s
tok_per_sec  = tokens_generated / generation_s    (if generation_s >= 0.01)
             = 0.0                                 (otherwise)
```

| エンジン | `generation_s` のソース |
|---------|----------------------|
| Ollama | `eval_duration / 1e9`（サーバーAPI — 直接） |
| OpenAI互換 | `elapsed_s - (ttft_ms / 1000)`（クライアントサイド） |

**根拠**: 大規模コンテキストサイズ（例：64kトークン）では、TTFTが総時間を支配する場合があります。tok/sにTTFTを含めると、高速ジェネレーターが遅く見えます（例：42 tok/sではなく3.2 tok/s）。

### M2. `ttft_ms` — 最初のトークンまでの時間

**定義**: リクエスト送信から最初の出力トークン受信までの時間（ミリ秒）。

| エンジン | ソース |
|---------|--------|
| Ollama | `prompt_eval_duration / 1e6`（サーバーAPI） |
| OpenAI互換 | `(time.monotonic() at 1st content chunk - t0) * 1000`（クライアント） |

注意：セマンティクスはわずかに異なります（サーバーとクライアントの測定）が、ローカルホストでの差は約1ms — 許容範囲です。

### M3. `total_duration_ms` — 総時間

**定義**: リクエストのウォールクロック総時間（プロンプト処理 + 生成）、ミリ秒。

**不変条件**: `total_duration_ms >= ttft_ms` — 常に。

| エンジン | ソース |
|---------|--------|
| Ollama | `total_duration / 1e6`（サーバーAPI） |
| OpenAI互換 | `elapsed_s * 1000`（クライアントウォールクロック） |

### M4. `tokens_generated` — トークン数

**定義**: モデルが生成した出力トークンの数。

**ソース（優先順位）**:
1. サーバーカウンター: Ollama `eval_count`、OpenAI互換 `usage.completion_tokens`
2. テキスト長推定: `max(1, len(text) // 4)`（ヒューリスティック：約4文字/トークン）
3. **絶対に** `len(text_parts)` を使用しない（SSEチャンク ≠ トークン）

### M5. `generation_duration_ms` — 生成時間

**定義**: 生成時間のみ（TTFTを除く）、ミリ秒。
分解 `total = ttft + generation` を明示的かつ監査可能にします。

| エンジン | ソース |
|---------|--------|
| Ollama | `eval_duration / 1e6`（サーバーAPI — 直接） |
| OpenAI互換 | `max(0, elapsed_s - ttft_s) * 1000`（計算値） |

### M6. `power_watts` — GPU電力

**定義**: **この特定のエンジン**の実行中の平均GPU電力（ワット）。

**スコープ**: エンジンごとに1つの `PowerMonitor`。最初のプロンプトの前に開始し、最後の実行の後に停止。各エンジンが独自の測定を取得 — セッション全体の平均ではありません。

ソース: `sudo powermetrics`（macOS）。

### M7. `tok_per_sec_per_watt` — エネルギー効率

```
tok_per_sec_per_watt = tok_per_sec / power_watts
```

補正済みtok/s（M1）とエンジンごとの電力（M6）を使用。

### M8. `std_dev_tok_s` — 分散（プールド）

**定義**: プールドプロンプト内標準偏差 — プロンプト間の分散を混在させずに、実行間のノイズを捕捉します。

```
For each prompt_type p with runs [v1, v2, ..., vn]:
    var_p = sum((vi - mean_p)^2) / n    (population variance)

pooled_variance = mean(var_p for all p with n >= 2)
std_dev_tok_s   = sqrt(pooled_variance)
```

**安定性分類**（変更なし）：
- CV < 5% → `stable`
- CV < 10% → `variable`
- CV >= 10% → `unstable`

CV = `(std_dev_tok_s / avg_tok_s) * 100`

## 実装マップ

| メトリクス | `base.py` | `ollama.py` | `openai_compat.py` | `runner.py` | `reporter.py` |
|-----------|-----------|-------------|--------------------|-----------  |----------------|
| M1 tok/s | フィールド | サーバーAPI | クライアント（TTFT除外） | パススルー | 平均 |
| M2 ttft_ms | フィールド | サーバーAPI | クライアントストリーミング | パススルー | 平均 |
| M3 total_duration_ms | フィールド | サーバーAPI | クライアントウォールクロック | パススルー | 平均 |
| M4 tokens_generated | フィールド | サーバーAPI | サーバーまたは `len//4` | パススルー | 平均 |
| M5 generation_duration_ms | フィールド | サーバーAPI | 計算値 | dictに保存 | — |
| M6 power_watts | — | — | — | エンジンごとのモニター | パススルー |
| M7 tok/s/W | — | — | — | 計算値 | パススルー |
| M8 std_dev | — | — | — | — | プールドプロンプト内 |

## ベンチマークプロトコル

1. **ウォームアップ**: エンジンごとに1回の計測外生成（`"Hello"`、max_tokens=1）でキャッシュをプライミング。
2. **計測実行**: デフォルトでプロンプトごと・エンジンごとに3回実行（`--runs` で設定可能）。
3. **サンプリング**: 決定論的出力のため、全エンジンで `temperature=0`（グリーディ）。
4. **レポーティング**: 中央値tok/sをプライマリメトリクス（SPEC標準）、平均 +/- 標準偏差をセカンダリとして使用。
5. **スロットリング**: いずれかの実行中に `thermal_speed_limit < 100%` の場合に警告を出力。
6. **メタデータ**: engine_version、model_format、model_quantization、hw_chip、os_version を再現性のために結果ごとに保存。

完全な手法監査については [benchmark-best-practices.md](benchmark-best-practices.md) を参照してください。
