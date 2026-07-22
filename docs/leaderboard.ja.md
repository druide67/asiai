---
description: Apple Silicon Mac全体のコミュニティベンチマーク結果。エンジン、モデル、ハードウェア別にtok/sを比較。自分の結果も提出できます。
---

# コミュニティリーダーボード

<div id="leaderboard-app" data-label-loading="読み込み中..." data-label-count="{n} 件の結果" data-label-updated="更新: {t}" data-label-error="api.asiai.dev に接続できませんでした" data-label-empty="結果が見つかりませんでした">

<div class="lb-filters" markdown>
<div class="lb-filter-row">
  <input type="text" id="lb-chip" placeholder="チップで絞り込み（例：M4 Pro）" class="lb-input">
  <input type="text" id="lb-model" placeholder="モデルで絞り込み（例：qwen2.5）" class="lb-input">
  <button id="lb-search" class="lb-btn">検索</button>
  <button id="lb-clear" class="lb-btn lb-btn-secondary">クリア</button>
</div>
<div class="lb-status">
  <span id="lb-count"></span>
  <span id="lb-updated"></span>
</div>
</div>

<div class="lb-table-wrap">
<table id="lb-table" class="lb-table">
<thead>
<tr>
  <th class="lb-sortable" data-col="engine">エンジン</th>
  <th class="lb-sortable" data-col="model">モデル</th>
  <th class="lb-sortable lb-active-sort" data-col="median_tok_s">tok/s</th>
  <th class="lb-sortable" data-col="median_ttft_ms">TTFT</th>
  <th>チップ · RAM</th>
  <th>Quant</th>
  <th class="lb-sortable" data-col="median_power_watts">W</th>
  <th class="lb-sortable" data-col="median_tok_s_per_watt">tok/s/W</th>
  <th class="lb-sortable" data-col="last_submitted_at">最終提出</th>
  <th class="lb-sortable" data-col="samples">サンプル数</th>
</tr>
</thead>
<tbody id="lb-body">
<tr><td colspan="10" class="lb-loading">コミュニティデータを読み込み中...</td></tr>
</tbody>
</table>
</div>

<div class="lb-footer">
  <p>データソース：<a href="https://api.asiai.dev/api/v1/leaderboard">api.asiai.dev</a> — リアルタイム更新<br>
  結果を提供：<code>asiai bench --share</code></p>
</div>

</div>
