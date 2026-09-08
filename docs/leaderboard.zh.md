---
description: Apple Silicon Mac 社区基准测试结果。按引擎、模型和硬件比较 tok/s。提交你的结果。
---

# 社区排行榜

<div id="leaderboard-app" data-label-loading="加载中..." data-label-count="{n} 条结果" data-label-updated="更新时间：{t}" data-label-error="无法连接 api.asiai.dev" data-label-empty="未找到结果" data-label-provenance="{n} 个能耗样本，基准 {b}">

<div class="lb-filters" markdown>
<div class="lb-filter-row">
  <input type="text" id="lb-chip" placeholder="按芯片筛选（如 M4 Pro）" class="lb-input">
  <input type="text" id="lb-model" placeholder="按模型筛选（如 qwen2.5）" class="lb-input">
  <button id="lb-search" class="lb-btn">搜索</button>
  <button id="lb-clear" class="lb-btn lb-btn-secondary">清除</button>

  <span class="lb-view-toggle" role="group"><button type="button" class="lb-view-btn lb-view-active" data-view="speed" aria-pressed="true">速度</button><button type="button" class="lb-view-btn" data-view="energy" aria-pressed="false">能耗</button></span>
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
  <th class="lb-sortable" data-col="engine">引擎</th>
  <th class="lb-sortable" data-col="model">模型</th>
  <th class="lb-sortable lb-active-sort" data-col="median_tok_s">tok/s</th>
  <th class="lb-sortable" data-col="median_ttft_ms">TTFT</th>
  <th>芯片 · RAM</th>
  <th>Quant</th>
  <th class="lb-sortable lb-col-speed" data-col="median_power_watts">GPU W</th>
  <th class="lb-sortable lb-col-speed" data-col="median_tok_s_per_watt">tok/s/W (GPU)</th>
  <th class="lb-sortable lb-col-energy" data-col="median_soc_watts">SoC W</th>
  <th class="lb-sortable lb-col-energy" data-col="median_energy_per_token_j">J/tok</th>
  <th class="lb-sortable lb-col-energy" data-col="median_energy_per_token_active_j">J/tok 活跃</th>
  <th class="lb-sortable lb-col-energy" data-col="median_idle_soc_watts">空闲 W</th>
  <th class="lb-sortable" data-col="last_submitted_at">最近提交</th>
  <th class="lb-sortable" data-col="samples">样本数</th>
</tr>
</thead>
<tbody id="lb-body">
<tr><td colspan="14" class="lb-loading">正在加载社区数据...</td></tr>
</tbody>
</table>
</div>

<div class="lb-footer">
  <p>数据来自 <a href="https://api.asiai.dev/api/v1/leaderboard">api.asiai.dev</a> — 实时更新。<br>
  贡献你的结果：<code>asiai bench --share</code></p>
</div>

</div>
