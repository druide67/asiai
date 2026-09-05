---
description: Risultati benchmark della community su Mac Apple Silicon. Confronta tok/s per motore, modello e hardware. Invia i tuoi risultati.
---

# Classifica comunitaria

<div id="leaderboard-app" data-label-loading="Caricamento..." data-label-count="{n} risultato/i" data-label-updated="Aggiornato: {t}" data-label-error="Impossibile raggiungere api.asiai.dev" data-label-empty="Nessun risultato trovato" data-label-provenance="{n} campione/i energia, base {b}">

<div class="lb-filters" markdown>
<div class="lb-filter-row">
  <input type="text" id="lb-chip" placeholder="Filtra per chip (es. M4 Pro)" class="lb-input">
  <input type="text" id="lb-model" placeholder="Filtra per modello (es. qwen2.5)" class="lb-input">
  <button id="lb-search" class="lb-btn">Cerca</button>
  <button id="lb-clear" class="lb-btn lb-btn-secondary">Cancella</button>

  <span class="lb-view-toggle" role="group"><button type="button" class="lb-view-btn lb-view-active" data-view="speed" aria-pressed="true">Velocità</button><button type="button" class="lb-view-btn" data-view="energy" aria-pressed="false">Energia</button></span>
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
  <th class="lb-sortable" data-col="engine">Motore</th>
  <th class="lb-sortable" data-col="model">Modello</th>
  <th class="lb-sortable lb-active-sort" data-col="median_tok_s">tok/s</th>
  <th class="lb-sortable" data-col="median_ttft_ms">TTFT</th>
  <th>Chip · RAM</th>
  <th>Quant</th>
  <th class="lb-sortable" data-col="median_power_watts">W GPU</th>
  <th class="lb-sortable" data-col="median_tok_s_per_watt">tok/s/W (GPU)</th>
  <th class="lb-sortable lb-col-energy" data-col="median_soc_watts">W SoC</th>
  <th class="lb-sortable lb-col-energy" data-col="median_energy_per_token_j">J/tok</th>
  <th class="lb-sortable lb-col-energy" data-col="median_energy_per_token_active_j">J/tok attivo</th>
  <th class="lb-sortable lb-col-energy" data-col="median_idle_soc_watts">W riposo</th>
  <th class="lb-sortable" data-col="last_submitted_at">Ultimo invio</th>
  <th class="lb-sortable" data-col="samples">Campioni</th>
</tr>
</thead>
<tbody id="lb-body">
<tr><td colspan="14" class="lb-loading">Caricamento dati della community...</td></tr>
</tbody>
</table>
</div>

<div class="lb-footer">
  <p>Dati da <a href="https://api.asiai.dev/api/v1/leaderboard">api.asiai.dev</a> — aggiornamento in tempo reale.<br>
  Contribuisci con i tuoi risultati: <code>asiai bench --share</code></p>
</div>

</div>
