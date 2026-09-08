---
description: Community benchmark results across Apple Silicon Macs. Compare tok/s by engine, model and hardware. Submit your own results.
---

# Community Leaderboard

<div id="leaderboard-app" data-label-provenance="{n} energy sample(s), base {b}">

<div class="lb-filters" markdown>
<div class="lb-filter-row">
  <input type="text" id="lb-chip" placeholder="Filter by chip (e.g. M4 Pro)" class="lb-input">
  <input type="text" id="lb-model" placeholder="Filter by model (e.g. qwen2.5)" class="lb-input">
  <button id="lb-search" class="lb-btn">Search</button>
  <button id="lb-clear" class="lb-btn lb-btn-secondary">Clear</button>

  <span class="lb-view-toggle" role="group"><button type="button" class="lb-view-btn lb-view-active" data-view="speed" aria-pressed="true">Speed</button><button type="button" class="lb-view-btn" data-view="energy" aria-pressed="false">Energy</button></span>
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
  <th>Chip · RAM</th>
  <th>Quant</th>
  <th class="lb-sortable lb-col-speed" data-col="median_power_watts">GPU W</th>
  <th class="lb-sortable lb-col-speed" data-col="median_tok_s_per_watt">tok/s/W (GPU)</th>
  <th class="lb-sortable lb-col-energy" data-col="median_soc_watts">SoC W</th>
  <th class="lb-sortable lb-col-energy" data-col="median_energy_per_token_j">J/tok</th>
  <th class="lb-sortable lb-col-energy" data-col="median_energy_per_token_active_j">J/tok active</th>
  <th class="lb-sortable lb-col-energy" data-col="median_idle_soc_watts">Idle W</th>
  <th class="lb-sortable" data-col="last_submitted_at">Last seen</th>
  <th class="lb-sortable" data-col="samples">Samples</th>
</tr>
</thead>
<tbody id="lb-body">
<tr><td colspan="14" class="lb-loading">Loading community data...</td></tr>
</tbody>
</table>
</div>

<div class="lb-legend" markdown>
<p><strong>Energy columns.</strong> <em>SoC W</em>: package power (GPU, CPU, Neural Engine, DRAM, memory controllers) from Apple's IOReport counters during the measured prompts. <em>J/tok</em>: that energy per generated token, prompt processing included — a lower bound on what a wall meter reads. <em>J/tok active</em>: minus the engine's loaded idle (<em>Idle W</em>). <em>GPU W</em>: the GPU rail alone, legacy. A dash means not measured — never a zero. Details: <a href="../metrics-spec/#m9-soc_watts-soc-package-power">metrics spec M9–M12</a>.</p>
</div>

<div class="lb-footer">
  <p>Data from <a href="https://api.asiai.dev/api/v1/leaderboard">api.asiai.dev</a> — updated live.<br>
  Contribute your results: <code>asiai bench --share</code></p>
</div>

</div>
