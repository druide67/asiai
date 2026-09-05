---
description: Résultats de benchmark communautaires sur les Mac Apple Silicon. Comparez les tok/s par moteur, modèle et matériel. Soumettez vos propres résultats.
---

# Classement communautaire

<div id="leaderboard-app" data-label-loading="Chargement..." data-label-count="{n} résultat(s)" data-label-updated="Mis à jour : {t}" data-label-error="Impossible de joindre api.asiai.dev" data-label-empty="Aucun résultat trouvé" data-label-provenance="{n} échantillon(s) énergie, base {b}">

<div class="lb-filters" markdown>
<div class="lb-filter-row">
  <input type="text" id="lb-chip" placeholder="Filtrer par puce (ex. M4 Pro)" class="lb-input">
  <input type="text" id="lb-model" placeholder="Filtrer par modèle (ex. qwen2.5)" class="lb-input">
  <button id="lb-search" class="lb-btn">Rechercher</button>
  <button id="lb-clear" class="lb-btn lb-btn-secondary">Effacer</button>

  <span class="lb-view-toggle" role="group"><button type="button" class="lb-view-btn lb-view-active" data-view="speed" aria-pressed="true">Vitesse</button><button type="button" class="lb-view-btn" data-view="energy" aria-pressed="false">Énergie</button></span>
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
  <th class="lb-sortable" data-col="engine">Moteur</th>
  <th class="lb-sortable" data-col="model">Modèle</th>
  <th class="lb-sortable lb-active-sort" data-col="median_tok_s">tok/s</th>
  <th class="lb-sortable" data-col="median_ttft_ms">TTFT</th>
  <th>Puce · RAM</th>
  <th>Quant</th>
  <th class="lb-sortable" data-col="median_power_watts">W GPU</th>
  <th class="lb-sortable" data-col="median_tok_s_per_watt">tok/s/W (GPU)</th>
  <th class="lb-sortable lb-col-energy" data-col="median_soc_watts">W SoC</th>
  <th class="lb-sortable lb-col-energy" data-col="median_energy_per_token_j">J/tok</th>
  <th class="lb-sortable lb-col-energy" data-col="median_energy_per_token_active_j">J/tok actif</th>
  <th class="lb-sortable lb-col-energy" data-col="median_idle_soc_watts">W repos</th>
  <th class="lb-sortable" data-col="last_submitted_at">Dernier envoi</th>
  <th class="lb-sortable" data-col="samples">Échantillons</th>
</tr>
</thead>
<tbody id="lb-body">
<tr><td colspan="14" class="lb-loading">Chargement des données communautaires...</td></tr>
</tbody>
</table>
</div>

<div class="lb-footer">
  <p>Données de <a href="https://api.asiai.dev/api/v1/leaderboard">api.asiai.dev</a> — mises à jour en direct.<br>
  Contribuez vos résultats : <code>asiai bench --share</code></p>
</div>

</div>
