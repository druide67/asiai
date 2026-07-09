---
description: Community benchmark results across Apple Silicon Macs. Compare tok/s by engine, model and hardware. Submit your own results.
---

# Community Leaderboard

<div id="leaderboard-app">

<div class="lb-filters" markdown>
<div class="lb-filter-row">
  <input type="text" id="lb-chip" placeholder="Filter by chip (e.g. M4 Pro)" class="lb-input">
  <input type="text" id="lb-model" placeholder="Filter by model (e.g. qwen2.5)" class="lb-input">
  <button id="lb-search" class="lb-btn">Search</button>
  <button id="lb-clear" class="lb-btn lb-btn-secondary">Clear</button>
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
  <th class="lb-sortable" data-col="engine">Engine</th>
  <th class="lb-sortable" data-col="model">Model</th>
  <th class="lb-sortable lb-active-sort" data-col="median_tok_s">tok/s</th>
  <th class="lb-sortable" data-col="median_ttft_ms">TTFT</th>
  <th>Chip</th>
  <th>RAM</th>
  <th>Quant</th>
  <th class="lb-sortable" data-col="median_power_watts">W</th>
  <th class="lb-sortable" data-col="median_tok_s_per_watt">tok/s/W</th>
  <th class="lb-sortable" data-col="last_submitted_at">Last seen</th>
  <th class="lb-sortable" data-col="samples">Samples</th>
</tr>
</thead>
<tbody id="lb-body">
<tr><td colspan="11" class="lb-loading">Loading community data...</td></tr>
</tbody>
</table>
</div>

<div class="lb-footer">
  <p>Data from <a href="https://api.asiai.dev/api/v1/leaderboard">api.asiai.dev</a> — updated live.<br>
  Contribute your results: <code>asiai bench --share</code></p>
</div>

</div>
