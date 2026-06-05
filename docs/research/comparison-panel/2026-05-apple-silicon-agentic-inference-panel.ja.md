# Apple Silicon エージェント推論パネル

> Apple Silicon M シリーズ上で Qwen 3.6 ファミリーのモデルを動かす推論エンジン
> （llama.cpp、mlx-lm、LM Studio、Rapid-MLX、vLLM-MLX、oMLX、vMLX、Ollama）
> 横断の比較ベンチマークパネル。`asiai bench --agentic-mode` および
> `asiai bench --burst-mode` で計測。
>
> **ワークロードの対象**: エージェント・オーケストレーター級 — ターンあたり約 60-80 回の
> ツールコール、約 7 KB の同一システムプロンプト、コールごとに変化するユーザーメッセージ。
> これは素朴な prefix キャッシュにとっての最悪ケースである: 同じプロンプトでの
> キャッシュではなく、真の USER 横断キャッシュ再利用が要求される。
>
> **スループット値の読み方**: セクション 1 の decode レートは Qwen3 デフォルトの
> chat テンプレート（thinking ON）を使用しているため、推論トークンを含む —
> thinking モデルでの実効エージェント・スループットはこれより低い。Thinking は
> グローバルな ON/OFF ではなく、タスクごとのトレードオフである（注意点 1）。
>
> 2026-06 公開 · 貢献・訂正は
> [github.com/druide67/asiai](https://github.com/druide67/asiai/issues) から歓迎。

## ⚠️ 読み進める前の既知の注意点

1. **Thinking モードはタスクごとのトレードオフである。** Qwen3 デフォルトテンプレート
   （thinking ON）では、Qwen 3.6 / Qwopus は約 6-7 倍多くのトークンを出力するため、
   セクション 1 の decode 値は**推論トークンを含み**、実効エージェント・スループットは
   より低い。Thinking ON は記述式の複数セクション成果物には**必須**である
   （thinking OFF のモデルは成果物をスキップする）が、アトミックなツールコールの
   クリーンさを**犠牲にする**（asiai の計測では thinking OFF で約 100% のクリーンな
   ツールコール、thinking ON + `preserve_thinking` ON で約 77.8%、実行間で決定的;
   `enable_thinking=on` + `preserve_thinking=off` は使い物にならない — 推論が
   コンテキストに蓄積すると決定的に HTTP 500）。Thinking は 1 つのグローバルフラグ
   ではなく、**タスク次元ごと**に設定すること。
2. **Rapid-MLX と vLLM-MLX はエンジンを共有している。** Rapid-MLX は
   `waybarrios/vllm-mlx` のコミュニティ・フォークである; 下記で別々の行として
   現れるのはバージョンと機能が分岐しているためだが、prefix キャッシュの
   スナップショット機構は同じ系統である。
3. **MTP: Qwen 3.6 は実在のヘッドを持つ; バックエンドが重要。** Qwen 3.6 の公式
   `config.json` は `mtp_num_hidden_layers=1` を保持している（Qwen の命名 —
   DeepSeek の `num_nextn_predict_layers` キーでは**ない**ため、`nextn` のみを
   チェックすると誤って「ヘッドなし」と結論づける）。一部の再量子化された
   GGUF/MLX アーティファクトは config フラグを保ったまま MTP テンソルを落として
   いる — フラグだけでなく weight インデックス内のテンソルを検証すること。
   llama.cpp ネイティブ MTP（`--spec-type draft-mtp`）はヘッドを埋め込んだ
   **`-MTP-GGUF` を必要とする**; 素の GGUF はドラフトできない。リリース版の
   mlx-lm はヘッドをネイティブな speculative decoding として動かさない（PR
   [ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990) が
   それを追加）。LM Studio は GGUF を llama.cpp 派生のバックエンドにルーティング
   し、MLX を `mlx-engine` にルーティングする。
4. **単一パスの計測、分散レポートなし** — セクション 1 / 2 の数値は単一の観測値で
   ある。分散レポート（N パス横断の中央値 + 最小 + 最大）は `--burst-runs N` で
   サポートされているが、再ベンチは保留中である。

| セクション | トピック | ステータス |
|---------|-------|--------|
| 1 | Single-call performance | 🟡 8 cells, thinking-mode ON (decode includes reasoning tokens) |
| 2 | Concurrent burst (30/60/80 parallel calls) | 🟡 smoke cell + 2 partial concurrent points; no normalized 30/60/80 panel |
| 3 | Caches & optimizations | ✅ 8 engines covered |
| 4 | Memory & resources | ✅ idle + under-load swap (+0) + footprint measured |
| 5 | Model quality (public leaderboards) | 🟡 vendor/self-reported figures (llm-stats) |
| — | **asiai direct measurements** | ✅ dev-quality, thinking ablation, MTP, instruction-following |
| 6 | Operational (license, endpoints, maintenance) | ✅ 8 engines covered |
| 7 | Quality benchmark weighting | 🟡 default weighting, override via `--weights` planned |
| 8 | Custom long-horizon eval (proposal) | 🟡 scoped, not yet built |

---

## セクション 1 — 単一コール性能

> ⚠️ **上記の注意点 1 とともに読むこと**: この表のすべての数値は Qwen3 デフォルトの
> thinking モードのトークン（reasoning_content）を含む。実効エージェント・スループットは
> `chat_template_kwargs={"enable_thinking": false}` で再実行する必要がある。列は
> 「実効スループット」ではなく「decode (t/s)」とラベル付けされている。
>
> 「下限見積もり」列は `60 × (TTFT + max_tokens/decode)` で、逐次ディスパッチを
> 仮定している（Rapid-MLX の single-slot がこれを強制する）。これは本番の tick 予測
> では**ない** — 手法上の注意点については[セクション 7](#section-7) を参照。
>
> 📌 **テスト済みバージョン (May 2026)**: Rapid-MLX 0.6.66、LM Studio 0.4.14、
> llama.cpp b9270。エンジンのバージョンは Apple Silicon 上で毎週入れ替わる — 各数値は
> 現行ではなく日付付きのものとして扱うこと。（asiai-measurements セクションは llama.cpp
> b9430 を使用。）

| # | Engine | Model | Format | Warm decode (t/s) ¹ | TTFT warm (ms) | TTFT prefix-test median (ms) | TTFT cold (ms) | Lower-bound estimate (60 calls × single-call, optimistic) | Source fixture |
|---|--------|-------|--------|--------------------:|---------------:|----------------------------:|---------------:|----------------------------------------------------------:|----------------|
| 1 | Rapid-MLX 0.6.66 (fork of vllm-mlx) | Qwopus 3.6-35B-A3B-v1 (zaydiscold MLX-4bit) | MLX-4bit | **109.1** ¹ | 139 | **131** | 2074 | ~3.6 min | `cell-rapidmlx-qwopus35b.json` |
| 2 | Rapid-MLX 0.6.66 | Qwen 3.6-35B-A3B-UD (MLX-4bit) | MLX-4bit | 106.9 ¹ | 321 | 319 | 2095 | ~4 min | `cell-rapidmlx-35b-a3b.json` |
| 3 | Rapid-MLX 0.6.66 | Qwopus 3.6-27B-v2 (Jackrong MLX-4bit) | MLX-4bit | 31.8 ¹ | 323 | 323 | 8647 | ~13 min | `cell-rapidmlx-qwopus.json` |
| 4 | Rapid-MLX 0.6.66 | Qwen 3.6-27B-UD (MLX-4bit) | MLX-4bit | 20.5 ¹ | 527 | 527 | 8954 | ~23 min | `cell-rapidmlx-full-27bud.json` |
| 5 | LM Studio 0.4.14 (GGUF backend) ² | Qwen 3.6-35B-A3B-MTP (Unsloth GGUF) | GGUF Q4 + MTP | **123.9** ¹ ² | 309 | 5965 | 6063 | ~3.5 min warm / ~9.2 min prefix-changing | `cell-lmstudio-mtp-qwen35b.json` |
| 6 | LM Studio 0.4.14 (GGUF backend) ² | Qwopus 3.6-35B-A3B-v1 (Jackrong GGUF) | GGUF Q4_K_S | 105.6 ¹ | 292 | 5785 | 5624 | ~3.5 min warm / ~9.6 min prefix-changing | `cell-lmstudio-qwopus35b.json` |
| 7 | llama.cpp b9270 | Qwen 3.6-35B-A3B (UD Q5_K_XL) | GGUF Q5_K_XL | 80.9 ¹ | 3000 | 3000 | n/a | ~8 min | (baseline reference) |
| 8 | llama.cpp b9270 | Qwopus 3.6-27B-v2 (Jackrong GGUF Q4) | GGUF Q4 | 25.3 ¹ | 13000 | 13000 | n/a | ~30 min | (baseline reference) |

¹ **Thinking モードの注意点**: 数値はデフォルトの chat テンプレート（thinking ON）で
取得した。ツールコール・ワークロードでの実世界の実効スループットは、推論トークンが
出力を 6-7 倍に膨らませる場合、Qwopus/Qwen3.6 ファインチューンで典型的には 4-12 t/s
である。これらの decode 値を再現するには、リクエストのペイロードで
`chat_template_kwargs={"enable_thinking": false}` を渡すこと。

² **LM Studio バックエンド**: 行 5-6 は GGUF ファイルを使用しており、これは
LM Studio の llama.cpp 派生バックエンドを経由する（MLX ランタイム `mlx-engine`
ではない）。行 5 の MTP の主張はこのバックエンドの実装を反映したものであり、
mlx-engine の speculative decoding ではない。リリース版の mlx-lm は MTP ヘッドを
ネイティブな speculative decoding として動かさない（その `sanitize()` は変換中に
歴史的に MTP の重みを落としていた; ネイティブサポートは PR
[ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990) にある）。
したがって仮想的な MLX フォーマットの MTP モデルも、リリース版の mlx-engine 上では
恩恵を受けないだろう。

### 主な観察

- 現実的なエージェントパターン（同一システム + 変化するユーザープロンプト）では、
  **Rapid-MLX + Qwopus 35B-A3B-v1** が 131 ms の prefix-test 中央値 TTFT を
  実現するのに対し、LM Studio GGUF バックエンドは 5965 ms（**約 44 倍速い**）。
  この優位性は vllm-mlx の prefix キャッシュ・スナップショット機構に由来する
  （ソースコードレベルの判別はセクション 3 を参照）。
- 純粋な decode スループット（ウォームパス）では、**Unsloth MTP を伴う LM Studio
  GGUF バックエンド**が 123.9 t/s を記録するのに対し、Rapid-MLX は 109.1 t/s
  （+13.5%）。この差は MTP ヘッドを保持する GGUF 上での LM Studio の llama.cpp
  派生バックエンドの speculative decoding を反映したものであり、Apple-MLX の
  ゲインではない（リリース版の mlx-engine はヘッドを動かさない — 脚注 2 を参照）。
  ネイティブな llama.cpp パスでは、MTP は MoE 35B-A3B でネットポジティブである —
  セクション 3 を参照。
- すべての `Qwen 3.6 family` 構成（ハイブリッド DeltaNet + full-attention）は、
  RNN ステートのスナップショットを保持する **Rapid-MLX を除いて**、USER 横断の
  prefix キャッシュに失敗する。llama.cpp / LM Studio GGUF では
  `llama_memory_can_shift=false`; mlx-lm / oMLX では recurrent/SSM ステートを
  任意のトークン境界で分割できない。このアーキテクチャに対する上流 llama.cpp の
  修正はマージされていない
  ([#23121](https://github.com/ggml-org/llama.cpp/pull/23121) はクローズ;
  `preserve_thinking` はこれに対処しない、
  [#22615](https://github.com/ggml-org/llama.cpp/issues/22615)）。
- **Single-slot 直列化の確認**: スモークバースト試験（セクション 2）は
  Rapid-MLX 0.6.66 が並行コールを FIFO で直列化することを示している
  （burst=5 で p50 ≈ p95 ≈ max）。ターンあたり 60-80 コールでは、このエンジンでは
  総ウォールタイムがバーストサイズに線形にスケールする。マルチスロットエンジン
  （例: llama.cpp `--parallel N`）は異なる挙動をするが、Qwen3.6 ハイブリッドでの
  `--parallel N` はスロットごとの prefix キャッシュを無効化する（アーキテクチャ上の制約）。

---

## セクション 2 — 並行バースト (30/60/80 並行コール)

> パターン: 約 200 ms のウィンドウ内で 30 から 80 の並行な
> `POST /v1/chat/completions` コールを発射。複数の MCP/ツールコールを並行で
> ディスパッチするエージェントループをシミュレートする。`asiai bench --burst-mode`
> でネイティブに計測。
>
> 🟡 **ステータス**: 1 スモークセル計測済み（Rapid-MLX burst-5）。フルパネルは保留中。

### スモークセル (Rapid-MLX 0.6.66 + Qwopus 35B-A3B-v1, burst=5)

| burst N | wall-time (s) | p50 latency (ms) | p95 latency (ms) | max latency (ms) | agg throughput (t/s) |
|--------:|--------------:|-----------------:|-----------------:|-----------------:|---------------------:|
| 5 | 2.8 | 2615 | 2792 | 2812 | 88.8 |

**スモークの所見**: `p50 ≈ p95 ≈ max` は 5 つのコールが**サーバー側で直列化された**
（single-slot エンジン）ことを示す。Rapid-MLX 0.6.66 は並行リクエストの
スケジューリングをサポートしていないように見える — コールは内部で FIFO に
キューイングされる。60/80 コール規模で検証すること。

### フル並行パネル — 未計測

正規化された 30/60/80 並行パネルは実行されていない（ここの計測値は並行バーストでは
なく逐次のエージェント・モードである）。他所に存在する 2 つの部分的な並行データポイント:

- **TurboQuant**（K=`q8_0` V=`turbo2`、Qwen3-4B、M4 Pro）: シングルストリームは
  −8% であるにもかかわらず、**4-parallel で集約 +9%**（68.5 → 74.7 t/s） — KV
  圧縮が並行のヘッドルームを買い戻す。
- **oMLX** 連続バッチング（mlx-lm `BatchGenerator`）: **burst-8 で集約 ×1.8**
  （12.8 → 22.9 t/s）だが、27B-dense が RAM を飽和させてスワップに入ると
  **burst-30 で崩壊する**（17.3 t/s） — クラッシュは 0 件。

すべてのエンジン横断の専用バースト・モードパネルは延期されている。

---

## セクション 3 — キャッシュと最適化

| # | Couple | Cache reuse cross-USER | Snapshot persists cross-restart | MTP support | MTP accept rate | TurboQuant compat | KV cache native types | Native parallel slots |
|---|--------|---|---|---|---|---|---|---|
| 1 | Rapid-MLX + Qwopus 35B-A3B-v1 | ✅ YES (RNN-state snapshot, see ³ below) | ✅ persistent in `~/.cache/vllm-mlx/` | ❌ released MLX runtime doesn't run the MTP head as speculative decode (mlx-lm PR #990 pending) | n/a | ❌ MLX only | MLX native (no quant flag exposed) | ⚠️ single slot (smoke burst confirms FIFO serialization) |
| 2 | Rapid-MLX + Qwen 35B-A3B-UD | ✅ YES ³ | ✅ persistent | ❌ | n/a | ❌ | MLX native | ⚠️ single slot |
| 3 | LM Studio + Qwen 35B-A3B-MTP | ❌ NO (architectural hybrid limitation) | n/a | ✅ via mlx-engine v1.8.1 | **82.1 %** (on coding task) | ❌ | mlx-engine v1.8.1 (4bit MLX) | configurable via GUI |
| 4 | LM Studio + Qwopus 35B-A3B-v1 | ❌ NO | n/a | ❌ no heads | n/a | ❌ | mlx-engine v1.8.1 (Q4_K_S GGUF) | configurable via GUI |
| 5 | llama.cpp + Qwen 3.6-35B-A3B | ❌ NO (architectural hybrid limitation) | n/a | ✅ `--spec-type draft-mtp` on a `-MTP-GGUF` (a plain GGUF cannot draft). Net-positive on the MoE 35B-A3B — asiai measures **+38%** decode (base) / **+17%** (Qwopus) on M5 Max (see § asiai measurements) | benefit = intra-session decode delta (no acceptance rate logged) | ✅ turbo2/3/4 V cache | `fp16`, `q8_0`, `q5_0`, `turbo2/3/4` | ⚠️ `--parallel N` works mechanically but **disables prefix cache per slot on hybrid arch** (each slot owns its KV, the `--cache-reuse N` flag is already silently disabled here). Use with caution. |
| 6 | mlx-lm | ❌ NO (PRs #923, #188, #192 pending upstream) | n/a | ❌ broken on hybrid arch | n/a | ❌ | MLX native | ❌ (single slot) |
| 7 | oMLX | ❌ NO (tool calling lost post-cache-hit, issue #825) | partial | ❌ | n/a | ❌ | MLX native + tiered SSD cache | ❌ |
| 8 | vLLM-MLX (`waybarrios`, upstream of Rapid-MLX) | ⚠️ trie prefix-cache, no documented hybrid/DeltaNet support (Rapid-MLX rows 1-2 add the RNN-state snapshot on top) | n/a | ⚠️ MTP added in prerelease 0.4.0rc1 | n/a | ❌ | MLX + paged-attention | ✅ |

³ **Rapid-MLX prefix キャッシュ**: キャッシュはハイブリッド attention の KV スラブ +
RNN ステートのスナップショットを格納し、`<repo>--<sys_prompt_hash>` ごとにキー付けされ、
`~/.cache/vllm-mlx/` 配下に永続化される。観測された約 131 ms の TTFT prefix-test は、
ディスクからの再ロードではなく、RAM 内の KV スラブの再アタッチに加えて変化した
ユーザーの forward パスである。

**oMLX ラージコンテキスト・キャッシュ。** oMLX の 2 段ページド SSD KV キャッシュは、
同一プロンプトのキャッシュヒット時に 55K トークンの prefill を約 115 s から
約 **3.5 s** の TTFT に変える（×33; 55,296 / 55,837 トークンがキャッシュされる）。
小さいプロンプト（約 7.5K）では優位性はなく（約 2-5 s、= mlx-lm）、decode は
約 19 t/s（生の速度向上なし）。これは USER 横断ではなく同一プロンプトの再利用で
あり（oMLX は USER 横断を行わない）; 再起動横断の永続性は文書化されているが
まだ A/B テストされていない。

**TurboQuant KV 圧縮**（llama.cpp）。K=`q8_0` V=`turbo2` は KV RAM を約 **28%**
削減し（4B モデル、M4 Pro で 22.9 → 16.4 GB）、ツールコールの妥当性は不変（10/10）、
シングルストリーム −8% にもかかわらず **4-parallel で集約 +9%** を得る。対称な
K=`turbo3` V=`turbo3` は約 −56% RAM に達するが品質を劣化させる（early-stop、
反復） — 非対称の `q8_0`/`turbo2` が実用的な構成である。

---

## セクション 4 — メモリとリソース (Apple Silicon M5 Max 128 GB)

| # | Couple | Working-set RAM (GB) | Disk footprint (GB) | Swap Δ idle | Swap Δ under load | SOLO required? | Cohabitation safe? |
|---|--------|---|---|---|---|---|---|
| 1 | Rapid-MLX + Qwopus 35B-A3B-v1 | ~22 | 19.9 (MLX-4bit) | +0 | **+0 MB** | ⚠️ SOLO (cohabit thrash to 0.4 t/s) | ❌ |
| 2 | Rapid-MLX + Qwen 35B-A3B-UD | ~24 | 20.0 (MLX-4bit) | +0 | **+0 MB** | ⚠️ SOLO | ❌ |
| 3 | LM Studio + Qwen 35B-A3B-MTP | 21.6 | 23.2 (Q4 + MTP heads) | +0 | **+0 MB** | not tested | not tested |
| 4 | LM Studio + Qwopus 35B-A3B-v1 | 18.5 | 19.9 (Q4_K_S) | +0 | **+0 MB** | not tested | not tested |
| 5 | llama.cpp + Qwen 3.6-35B-A3B (reference) | ~16 | ~16 (Q5_K_XL) | +0 | **+0 MB** | ❌ | ✅ with `--parallel 2/3` |

> **「負荷下」** = 50K トークンの prefill を含む 8 フェーズのエージェント・ベンチ
> （計測された最も重い*逐次*メモリ・ストレス）、M5 Max 128 GB、SOLO: スワップデルタは
> **すべてのエンジンで 0 MB / 0 swapout** — モデル + KV が free/inactive メモリに収まり、
> 100 GB 超のヘッドルームがある。これは逐次負荷時のメモリであり、60 並行時の
> メモリでは**ない**（セクション 2 を参照）。Working-set RAM は見積もりである; 計測された
> RSS には mmap された GGUF / wired な MLX ページが含まれるため、真の増分フットプリント
> はこれより低い（MTP ヘッドは約 +3 GB を加える）。

### 観察

- **Rapid-MLX は GPU 上での SOLO 動作を必要とする**: 別のアクティブに decode する
  エンジンとの同居は 5.4 → 14.2 GB のスワップデルタと 0.4 t/s への decode 崩壊を
  引き起こす。同じ Apple Silicon GPU 上で 2 つ目のエンジンを起動しないこと。
- **LM Studio MTP** のディスクフットプリントは、MTP の重みブロックのために
  MTP ヘッドなしの Q4_K_S に対して +13% である。+17% の decode ゲインに比べれば
  無視できるコストである。
- M5 Max 128 GB のユニファイドメモリでは: テストしたすべての 35B-A3B 構成が
  ロード後に 100 GB 超のヘッドルームを残す — RAM は制約要因ではない。
- M4 Pro 64 GB では: `Q5_K_XL` は補助モデルと並べると**収まらない**（本番で
  スワップ・スラッシュを観測）。`Q4_K_S` は収まる。

---

## セクション 5 — モデル品質

> ここの公開ベンチマーク値は**ベンダー / 自己申告**であり、リーダーボード
> （llm-stats）が集約したものであって、独立に検証されたものではない。依拠する前に
> [llm-stats](https://llm-stats.com) · [LiveBench](https://livebench.ai) ·
> [SWE-bench](https://swebench.com) でクロスバリデートすること。Apple Silicon 上での
> asiai 自身の直接計測は次のセクションにある。
>
> 著者のみの主張（Jackrong/Qwopus、Unsloth 自己評価）は別途フラグ付けされ、
> 公開リーダーボードの列からは除外されている。
>
> 🔴 **重大な所見**: いくつかのコミュニティ・モデルカードで引用される
> 「Hessling agentic」ベンチマークは**独立に再現可能ではない** — 16 プロンプト、
> 単一のキュレーター、中立なリーダーボード統合なし。3 人のアドバイザー全員が
> これをスモークテストとしてのみ扱うことを推奨する。

### オープンウェイトの Qwen 3.6 ベースモデル

> 公開リーダーボード値（llm-stats）、自己申告。27B-dense は SWE-bench で
> 35B-A3B MoE を上回る — 下記の asiai 自身の dev-quality の所見と一致する
> （MoE ベースこそがツールコールの空オブジェクトバグを引き起こすものである）。
> MTP ヘッドは decode 速度の機能であり、モデルの品質スコアは変えない。

| Model | Architecture | SWE-bench Verified | GPQA Diamond | MMLU-Pro | Terminal-Bench 2.0 | BFCL |
|-------|--------------|-------------------:|-------------:|---------:|-------------------:|------|
| Qwen 3.6-35B-A3B-Instruct | MoE 35B / 3B active | 73.4% | 86.0% | 85.2% | 24.6% | absent from board |
| Qwen 3.6-27B-Dense Instruct | Dense 27B hybrid | 77.2% | 87.8% | 86.2% | 59.3% (vendor) | absent from board |

> Terminal-Bench **2.0** は古い Terminal-Bench v1 よりはるかに難しい（コミュニティ
> カードは 35B-A3B の v1 で約 51.5% を引用している）; ここの 24.6% は 2.0 世代である。

### Qwopus 3.6 ファミリー — 著者申告のみ、**独立に検証されていない**

Jackrong が HuggingFace で公開した Qwopus 3.6 ファインチューンは、Qwen ベースに
対する大幅なゲインを主張している。2026 年 5 月時点で、これらの主張は中立な
リーダーボード上で**独立に再現されていない**。第三者による BFCL / SWE-bench の
再実行が利用可能になるまで、実験的なものとして扱うこと。

| Model (author claims) | MMLU-Pro | SWE-bench Verified | Hessling agentic (16 prompts) |
|-----------------------|---------:|-------------------:|------------------------------:|
| Qwopus 3.6-35B-A3B-v1 (Jackrong) | claimed 88+ | claimed 75+ | claimed 88.6 ⚠ non-reproducible |
| Qwopus 3.6-27B-v2 (Jackrong) | claimed 87.43 | claimed 75.25 | n/a |

⚠ Jackrong のモデルカードで引用される「Hessling agentic」ベンチマークは、中立な
リーダーボード統合のない 16 プロンプトのキュレーター固有の評価のようである。
照会した 3 つのアドバイザリ全員（Grok-4、GPT-5、Gemini Advanced）が、これを
スモークテストとしてのみ扱うことを推奨する。

### フロンティアのアンカー (mid-2026)

> すべての数値は**ベンダー / 自己申告**で、llm-stats が集約したものである — そこで
> 独立に検証されたものは一つもない。**Terminal-Bench 2.0** は例外である（tbench
> チームが提出を再実行する; 行はピーク agent×model スコア）。GPQA はベンダーの
> 「Diamond」値であり、セットはほぼ飽和している — おおよその値として扱うこと。

| Model | SWE-bench Verified | GPQA Diamond | MMLU-Pro | Terminal-Bench 2.0 | Source |
|-------|-------------------:|-------------:|---------:|-------------------:|--------|
| Claude Opus 4.8 | 88.6% | 93.6% | n/a | — (no TB submission) | llm-stats / Anthropic |
| Claude Opus 4.7 | 87.6% | 94.2% | n/a | **90.2%** | llm-stats / tbench |
| Claude Sonnet 4.6 | 79.6% | 89.9% | n/a | 53.4% | llm-stats / tbench |
| GPT-5.5 | n/a\* (SWE-Pro 58.6%) | 93.6% | n/a | 84.7% | OpenAI / tbench |
| GPT-5 (base) | 74.9% | 85.7% | n/a | 49.6% | llm-stats / tbench |
| Gemini 3.1 Pro | 80.6% | ~94.4% | n/a | 80.2% | llm-stats / tbench |
| DeepSeek-V4-Pro-Max | 80.6% | 90.1% | 87.5% | n/a | vendor (DeepSeek) |
| Llama-3.3-70B-Instruct | n/a | n/a | 68.9% | n/a | Meta (baseline) |

\* GPT-5.5 には公開された SWE-bench *Verified* スコアがない（OpenAI は SWE-bench Pro
Public 58.6% を報告している）; 流布している「88.7% SWE-bench」の数値はいかなる
一次ソースにも存在しない。注意: **Qwen 3.6 に 235B-A22B は存在しない** — オープン
ファミリーは 27B-dense と 35B-A3B（以下）である; 235B-A22B は前の Qwen3 世代である。

### 同クラスのオープンウェイトのベースライン

| Model | MMLU-Pro | SWE-bench Verified | Notes |
|-------|---------:|-------------------:|-------|
| Llama-3.3-70B-Instruct | ~75-80 | ~40-50 | Older but well-characterized baseline |
| Mistral Codestral 25.05 / Devstral | high (coding-specialized) | medium-high | Strong editor-style completion fidelity, weaker on reasoning |
| GLM-4.6-Coder (Zhipu) | vendor claims very high | disputed | Significant skepticism around evaluation methodology (consensus) |

### この判断のために非推奨とした品質ベンチマーク

- **HumanEval / HumanEval+** — 2026 年に飽和し、すべてのフロンティアモデルが 90% 超、シグナルが残っていない。
- **GSM8K** — 飽和、コーディング・エージェントへのシグナルなし。
- **MMLU (original)** — MMLU-Pro に取って代わられた。
- **著者申告の「Hessling agentic」16 プロンプト** — 再現不可、スモークテストとしてのみ扱う。

### オープンな品質の問い（研究ギャップ）

1. **GB-RAM あたり品質ベンチマーク**: 標準は存在しない。提案するプロキシ式:
   `AgentScorePerGB = (0.5·SWE + 0.3·BFCL + 0.2·TerminalBench) / RAM_resident`。
2. **ロングホライズン安定性 (60+ ツールコール)**: 最も近い既存ベンチマークは
   τ-bench、PencilPuzzleBench (>1000 turns)、MultiAgentBench、TRAIL である。
   それらのいずれも「60-80 の逐次ツールコールにわたるスキーマの正しさと戦略的
   一貫性」を特に計測していない — そのベンチマークギャップは 3 人のアドバイザー
   全員が認めている。
3. **変換を意識した評価 (MLX-4bit vs GGUF Q4_K_M vs Q5_K_XL)**: 標準化された
   リーダーボードはない。コミュニティの報告は分かれる — MLX-4bit は GGUF Q5_K_M
   よりツールコールの安定性の保持が悪いと主張する者もいれば、逆を言う者もいる。
   **実践的な助言**: コミットする前に、各 quant に対して自分自身の本番ワークロード
   を実行すること。
4. **Qwopus 3.6 ファミリーの品質検証**: 第三者による BFCL + SWE-bench の再実行が
   必要である。著者の主張が本番判断を駆動すべきではない。

---

## asiai 直接計測 — Apple Silicon, mid-2026

> 上記の公開リーダーボードが示さないもの: asiai が Apple Silicon 上で直接実行した
> 計測（High Power Mode の M5 Max 128 GB、M4 Pro 64 GB）、llama.cpp b9430、
> 決定的（temp 0）、公開の Qwen 3.6 ファミリーと Opus 蒸留の **Qwopus** ファイン
> チューン上で。注意点: M5 ラップトップでのセッション横断の絶対スループットは
> ±15%（thermal/load）である; **セッション内の ±MTP の連続デルタ**のみがタイトで
> あり、M5↔M4 の絶対値は比較できない（quant が異なる）。

### Dev-quality / ツールコール (`asiai bench --code`)

- **ベースの Qwen 3.6-35B-A3B (MoE)** はディープコンテキストのターンで
  `edit_file.edits` を空のオブジェクトに崩壊させる — **3/3 ラン、Q4_K_S と Q5_K_XL
  の両方で**、同じ chat テンプレート。ツールコールのクリーン **87.5%**、編集ターンの
  クリーン **66.7%**。これは quant でもテンプレートでもなく、MoE ベースのツールコール
  生成の挙動である。
- **dense 27B**（Q5_K_XL）と **Qwopus-35B-A3B**（Q4_K_S）はいずれも **100% クリーン
  / 0 バグ**をスコアする — Qwopus は MoE の約 4 倍の decode レートで dense-27B の
  ツールコール信頼性に達する。
- より難しいツールコール・ストレススイートの下では、Qwopus は **100% / 0** を
  維持するのに対し、dense 27B は **88.9% / 3 バグ**に落ちる（同じ空オブジェクトの
  失敗）。しかし式評価器のトラップ（`**` と単項マイナスの優先順位）では、**dense 27B
  が正しく Qwopus が間違っている** — 結果が分かれる。（回復率は重みに敏感でノイジー
  である — 見出しにはしない。）

### Thinking アブレーション (`asiai bench --thinking-ablation`, Qwopus-35B-A3B, 3 deterministic runs)

| Config | Tool-call clean | Note |
|--------|----------------:|------|
| `enable_thinking=off` | **100%** | the only fully-clean config |
| `enable_thinking=on` + `preserve_thinking=on` | 77.8% | 2/9 turns dirty |
| `enable_thinking=on` + `preserve_thinking=off` | 11.1% | turns 2-8 → HTTP 500 (context corruption); avoid |

### MTP スループット (`--spec-type draft-mtp`, warm decode, intra-session ±MTP)

| Model / hardware | MTP off | MTP on | Δ |
|------------------|--------:|-------:|--:|
| 35B-A3B base · M5 Max | 85.5 t/s | **118.4 t/s** | **+38%** |
| Qwopus 35B-A3B · M5 Max | 105.7 t/s | 123.3 t/s | +17% |
| 27B-dense · M5 Max | 23.8 t/s | 28.0 t/s | +18% |
| Qwopus 27B · M5 Max | 25.9 t/s | 26.7 t/s | +3% |
| 35B-A3B MoE · M4 Pro | 36.3 t/s | 44.6 t/s | +23% |
| 27B-dense · M4 Pro | 10.4 t/s | 9.7 t/s | **−6%** |

MTP のゲインは **(MoE > dense) × (M5 > M4)** としてスケールする — MoE では強く
ポジティブ、遅い dense パスでは限界的からネガティブである（draft オーバーヘッドが
償却されない）。MLX 側の MTP（mlx_vlm）は失格である: ロングコンテキストを壊す
（空出力、75% 有効）。見出し: llama.cpp 上の 35B-A3B MoE + MTP は M5 Max で約
**118 t/s** の decode を持続する（M4 Pro で約 44 t/s）、27B-dense の約 4 倍、
約 1.5 tok/s/W、TTFT 約 62 ms、出力妥当性 100%。Qwopus ファインチューンの MTP ヘッドはベースよりも弱い（Qwopus 27B +3% / 35B +17%、対してベースは 27B-dense +18% / 35B-A3B +38%） — ファインチューニングはドラフトヘッドを劣化させる。

### Instruction-following (`asiai bench --instruct`, research-brief)

Thinking のトレードオフは複数ステップの成果物で牙を剝く: `enable_thinking=false`
では、Qwopus-35B はツール作業を行うが、要求された複数セクションのブリーフを
**0%** しか提供しない（二次ステップで止まる）; thinking を ON にすると、ベース
モデルがそれを **100%** 提供する（5/5 セクション）。これは上記のツールコールの
結果とは逆方向に引っ張る — thinking-off はアトミックなツールコールには最もクリーン
だが記述式の成果物を抑制する — これこそ asiai が thinking を 1 つのグローバル
スイッチではなく**タスク次元ごと**に設定する理由である。

---

## セクション 6 — 運用面

> 📌 機能スナップショット (mid-2026)。エンジンのバージョンは Apple Silicon 上で
> 毎週入れ替わる — これらのセルは時点のものであり、バージョン固定の保証ではない。

| # | Engine | License | Stream OAI-compat | `/v1/models` | `/health` | `/metrics` (Prometheus) | Tool calling | Auto-DL HF | Persisted prefix cache | Maintainer activity |
|---|--------|---------|---|---|---|---|---|---|---|---|
| 1 | Rapid-MLX 0.6.66 | Apache-2.0 | ✅ | ✅ | ✅ (HTML page) | ❌ (logs only) | ✅ | ✅ HF Hub auto-DL on serve | ✅ `~/.cache/vllm-mlx/prefix_cache/` | community (raullenchai) |
| 2 | LM Studio 0.4.14 | proprietary | ✅ | ✅ | partial (websocket) | ❌ | ✅ | ✅ via `lms get` CLI | ❌ | Element Labs |
| 3 | llama.cpp b9270 | MIT | ✅ | ✅ | ✅ | ✅ `--metrics` | ✅ | manual (GGUF on disk) | ❌ (`--cache-reuse N` arch-disabled on hybrid) | ggerganov very active |
| 4 | mlx-lm | MIT | ✅ | ✅ | ✅ | ❌ | partial | ✅ HF auto | ❌ | Apple ml-explore active |
| 5 | oMLX | MIT | ✅ | ✅ | ✅ | ❌ | ✅ (caveat: post-cache-hit bug) | ✅ | partial (tiered SSD) | jundot active |
| 6 | vLLM-MLX | Apache-2.0 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ paged-attention | vllm-project active |
| 7 | vMLX (Mamba/SSM) | Apache-2.0 | ✅ | ✅ | ✅ | partial | untested | partial | untested | community |
| 8 | Ollama | MIT | ✅ | partial | ✅ `/api/version` | ❌ | partial | ✅ `ollama pull` | ❌ | Ollama Inc. very active |

---

## セクション 7 — エージェント・コーディング・ワークロードのための品質ベンチマーク重み付け

> これはオーケストレーター級のワークロード（ターンあたり 60-80 の逐次ツールコール、
> スキーマ検証された出力、ロングコンテキストのシステムプロンプト）に対する
> **asiai のデフォルト重み付け**である。2026 年 5 月に照会した 3 つのフロンティア
> LLM アドバイザリ（Grok-4、GPT-5、Gemini Advanced）に基づいているが、**コミュニティ
> のコンセンサスではない** — 権威あるものではなく出発点として扱うこと。将来の
> `--weights` フラグ（計画中）でオーバーライドする。

| Benchmark | What it measures | Why it matters here | Consensus weight |
|-----------|------------------|---------------------|-----------------:|
| **SWE-bench Verified** | Real GitHub repo navigation + patch + test repair | Best proxy for code-editing fidelity inside an agent loop | **35 %** |
| **BFCL v3** (Berkeley Function Calling Leaderboard) | Multi-turn function-call accuracy, argument fidelity, schema adherence | Direct predictor of orchestrator stability across many tool calls | **25 %** |
| **TerminalBench 2.0 / MCP-Atlas** | CLI and MCP task execution autonomy | "Does the agent survive 40+ actions without derailing" | **20 %** |
| **LiveBench Coding** | Contamination-resistant coding tasks (refreshed monthly) | Catches train-test leakage that inflates HumanEval-class scores | **10 %** |
| **Custom long-horizon stability eval** | 60-80 sequential tool calls with cumulative context growth, malformed JSON recovery | The benchmark that does not exist yet in public form — see Section 8 | **10 %** |

### 重み付けから意図的に外したベンチマーク

- MMLU-Pro、GPQA Diamond、HumanEval+ — 一般的な能力シグナルとしては有用だが、
  2026 年のエビデンスによればエージェントループの信頼性とは**弱くしか相関しない**。
  フロンティアラボの確認は、single-shot 推論スコアがもはや十分な粒度では自律
  エージェントの成功を予測しないことを示している。
- 第三者の再実行を伴わない著者申告の集約値（Jackrong Hessling、Unsloth 自己評価、
  GLM-4.6-Coder ベンダー主張）。

---

## セクション 8 — カスタム「耐久」ベンチマーク提案（研究機会）

3 人のアドバイザー全員が同じギャップに収束する: **オーケストレーター・ワークロードを
最もよく特徴づけるベンチマークはまだ公開されていない**。それを構築することが、
欠けているシグナルを得る唯一の方法である。

### 提案するスコープ

- 軌跡あたり **80 の逐次ツールコール**
- **毎ターンのスキーマ検証**（厳格な JSON / 構造化出力）
- **累積コンテキスト成長**（軌跡全体で 10K → 50K トークン）
- **中断 / 回復テスト**（軌跡途中のキャンセル + 再開）
- **不正な XML/JSON からの回復**（エージェントは自己修正するか？）
- **リポジトリ編集の永続性**（ターン N で行った編集はターン 60 でも保持されているか？）

これは asiai のロードマップ上にある（バースト・モードの後の、ロングホライズン
耐久モード）。構築されれば、この特定のニッチにおける初の公開ベンチマークとなる。

---

## 手法

- **ハードウェア**: MacBook Pro M5 Max 128 GB ユニファイドメモリ、macOS 26.4.1。
- **ワークロード**: オーケストレーター級 — システムプロンプト約 7 KB、ユーザー
  プロンプト約 150-200 トークン、ターンあたり 60-80 コール。
- **計測したフェーズ**（single-call、agentic-mode v1.6.0）:
  - `cold`: 新規起動後の最初のコール
  - `warm`: cold と全く同じプロンプト（ウォームキャッシュ）
  - `prefix-test-1/2/3`: 同一システム、ユーザー変化 — USER 横断のキャッシュ再利用を計測
  - `cold-prefix`: 同一システム、再起動後 — 永続キャッシュを計測
- **prefix キャッシュ再利用の判定**: `median(prefix-test) / cold < 0.2` なら `YES`、
  そうでなければ `NO`。
- **アンチバイアス措置**: SOLO モード（同居エンジンなし）、thermal アイドルの
  ベースライン、mmap ウォームアップフェーズ。
- **品質ゲート**（asiai bench が自動追跡）:
  - `early_stop`: 中央値完了の `<0.5×` のランが少なくとも 2 つ
  - `memory_pressure`: スワップデルタ `>500 MB` または swapout デルタ `>1000`
  - `duplicate_processes`: ベンチ中に複数のエンジンプロセスを検出

完全なプロトコルは `asiai bench --agentic-mode` / `--burst-mode` の計測
（power/thermal、エンジンフットプリント、KV 占有率、prefix キャッシュフェーズ）で
ある — asiai CLI ドキュメントを参照。

---

## オープンな問い

1. **vLLM-MLX/Rapid-MLX 上の MTP — （部分的に）解決済み。** vLLM-MLX はプレリリース
   **0.4.0rc1**（2026-05-21）で MTP を追加した; 理論上の組み合わせ「MLX + MTP 装備の
   Qwopus 35B-A3B + USER 横断スナップショット」は、Rapid-MLX フォークが 0.4.x を
   追従すれば decode と TTFT の両方で勝ちうる。Rapid-MLX が MTP パスを取り込む時期を
   追跡すること。
2. **MLX ランタイム上の MTP — 現状。** リリース版の mlx-lm は MTP ヘッドを
   ネイティブな speculative decoding として動かさない（`sanitize()` が変換中に
   MTP の重みを落とす; ネイティブサポートは未マージの PR
   [ml-explore/mlx-lm#990](https://github.com/ml-explore/mlx-lm/pull/990) にある）。
   LM Studio の `mlx-engine` は mlx-lm をラップしているため、これを継承する —
   セクション 1 の行 5 における +13.5% の decode ゲインは LM Studio の
   **llama.cpp 派生バックエンド**に由来するものであり（ファイルは GGUF）、
   mlx-engine の speculative decoding ではない。
3. **60-80 コール規模での Rapid-MLX/vllm-mlx のバースト挙動**: スモークテストは
   burst=5 で single-slot FIFO を確認している。フルパネルは保留中（セクション 2）。
   関連する上流の論点は、vllm-mlx がハイブリッドアーキテクチャのモデルに対して
   連続バッチング / マルチスロット・スケジューリングを計画しているかどうかである。
4. **Qwen 3.6 ハイブリッド上の `llama_memory_can_shift=false`** — 上流ではまだ
   壊れている。[#18497](https://github.com/ggml-org/llama.cpp/issues/18497) は
   クローズ（フル再処理を文書化）; [#22384](https://github.com/ggml-org/llama.cpp/issues/22384)
   は *issue*（completed としてクローズ）であって、マージされた修正では**ない**;
   実際の修正 PR [#23121](https://github.com/ggml-org/llama.cpp/pull/23121) は
   **未マージでクローズ**された（パッチはフォーク上にのみ存在する）。「単に
   `preserve_thinking` を有効にするだけ」という回避策は、オープンな issue
   [#22615](https://github.com/ggml-org/llama.cpp/issues/22615) によって反証されている
   （0.67× の高速化 = キャッシュが不活性のまま）。ハイブリッド DeltaNet 層は構造上、
   shift 可能なキャッシュステートを公開しない。
5. **Qwopus 3.6 品質の独立再現**: 第三者による BFCL / SWE-bench の再実行が必要で
   ある。著者公開の数値は、クロス検証されるまで本番判断を駆動すべきではない。
6. **vllm-mlx vs Rapid-MLX の系統 — 解決済み。** Rapid-MLX は `waybarrios/vllm-mlx`
   のコミュニティ**ハードフォーク**であり、薄いラッパーではない: エンジンを
   in-tree でベンダリングし（パッケージ名はまだ `vllm_mlx`）、上流パッケージに
   pip 依存せず、大幅に分岐している（Rapid-MLX 0.6.74 vs 上流 0.3.0）。共有された
   `vllm_mlx` パッケージ名と `~/.cache/vllm-mlx/` ディレクトリは、帰属の混乱を
   頻繁に引き起こす源である（セクション 3、注意点 2 を参照）。

---

*このパネルは継続更新されるドキュメントである。貢献、訂正、追加のベンチセルは
[github.com/druide67/asiai](https://github.com/druide67/asiai/issues) から歓迎する。*
