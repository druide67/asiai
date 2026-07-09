---
description: Community-Benchmark-Ergebnisse auf Apple-Silicon-Macs. Vergleichen Sie tok/s nach Engine, Modell und Hardware. Reichen Sie Ihre eigenen Ergebnisse ein.
---

# Community-Leaderboard

<div id="leaderboard-app" data-label-loading="Wird geladen..." data-label-count="{n} Ergebnis(se)" data-label-updated="Aktualisiert: {t}" data-label-error="api.asiai.dev nicht erreichbar" data-label-empty="Keine Ergebnisse gefunden">

<div class="lb-filters" markdown>
<div class="lb-filter-row">
  <input type="text" id="lb-chip" placeholder="Nach Chip filtern (z.B. M4 Pro)" class="lb-input">
  <input type="text" id="lb-model" placeholder="Nach Modell filtern (z.B. qwen2.5)" class="lb-input">
  <button id="lb-search" class="lb-btn">Suchen</button>
  <button id="lb-clear" class="lb-btn lb-btn-secondary">Zurücksetzen</button>
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
  <th class="lb-sortable" data-col="model">Modell</th>
  <th class="lb-sortable lb-active-sort" data-col="median_tok_s">tok/s</th>
  <th class="lb-sortable" data-col="median_ttft_ms">TTFT</th>
  <th>Chip</th>
  <th>RAM</th>
  <th>Quant</th>
  <th class="lb-sortable" data-col="median_power_watts">W</th>
  <th class="lb-sortable" data-col="median_tok_s_per_watt">tok/s/W</th>
  <th class="lb-sortable" data-col="last_submitted_at">Zuletzt gesehen</th>
  <th class="lb-sortable" data-col="samples">Proben</th>
</tr>
</thead>
<tbody id="lb-body">
<tr><td colspan="11" class="lb-loading">Community-Daten werden geladen...</td></tr>
</tbody>
</table>
</div>

<div class="lb-footer">
  <p>Daten von <a href="https://api.asiai.dev/api/v1/leaderboard">api.asiai.dev</a> — live aktualisiert.<br>
  Tragen Sie Ihre Ergebnisse bei: <code>asiai bench --share</code></p>
</div>

</div>
