---
description: Resultados de benchmarks comunitarios en Macs con Apple Silicon. Compara tok/s por motor, modelo y hardware. Envía tus propios resultados.
---

# Tabla de clasificación comunitaria

<div id="leaderboard-app" data-label-loading="Cargando..." data-label-count="{n} resultado(s)" data-label-updated="Actualizado: {t}" data-label-error="No se pudo contactar api.asiai.dev" data-label-empty="No se encontraron resultados">

<div class="lb-filters" markdown>
<div class="lb-filter-row">
  <input type="text" id="lb-chip" placeholder="Filtrar por chip (ej. M4 Pro)" class="lb-input">
  <input type="text" id="lb-model" placeholder="Filtrar por modelo (ej. qwen2.5)" class="lb-input">
  <button id="lb-search" class="lb-btn">Buscar</button>
  <button id="lb-clear" class="lb-btn lb-btn-secondary">Limpiar</button>
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
  <th class="lb-sortable" data-col="engine">Motor</th>
  <th class="lb-sortable" data-col="model">Modelo</th>
  <th class="lb-sortable lb-active-sort" data-col="median_tok_s">tok/s</th>
  <th class="lb-sortable" data-col="median_ttft_ms">TTFT</th>
  <th>Chip</th>
  <th>RAM</th>
  <th>Quant</th>
  <th class="lb-sortable" data-col="median_power_watts">W</th>
  <th class="lb-sortable" data-col="median_tok_s_per_watt">tok/s/W</th>
  <th class="lb-sortable" data-col="last_submitted_at">Último envío</th>
  <th class="lb-sortable" data-col="samples">Muestras</th>
</tr>
</thead>
<tbody id="lb-body">
<tr><td colspan="11" class="lb-loading">Cargando datos comunitarios...</td></tr>
</tbody>
</table>
</div>

<div class="lb-footer">
  <p>Datos de <a href="https://api.asiai.dev/api/v1/leaderboard">api.asiai.dev</a> — actualización en tiempo real.<br>
  Contribuye con tus resultados: <code>asiai bench --share</code></p>
</div>

</div>
