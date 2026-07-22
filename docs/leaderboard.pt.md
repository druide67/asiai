---
description: Resultados de benchmark da comunidade em Macs com Apple Silicon. Compare tok/s por motor, modelo e hardware. Envie seus próprios resultados.
---

# Leaderboard da Comunidade

<div id="leaderboard-app" data-label-loading="Carregando..." data-label-count="{n} resultado(s)" data-label-updated="Atualizado: {t}" data-label-error="Não foi possível acessar api.asiai.dev" data-label-empty="Nenhum resultado encontrado">

<div class="lb-filters" markdown>
<div class="lb-filter-row">
  <input type="text" id="lb-chip" placeholder="Filtrar por chip (ex: M4 Pro)" class="lb-input">
  <input type="text" id="lb-model" placeholder="Filtrar por modelo (ex: qwen2.5)" class="lb-input">
  <button id="lb-search" class="lb-btn">Buscar</button>
  <button id="lb-clear" class="lb-btn lb-btn-secondary">Limpar</button>
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
  <th>Chip · RAM</th>
  <th>Quant</th>
  <th class="lb-sortable" data-col="median_power_watts">W</th>
  <th class="lb-sortable" data-col="median_tok_s_per_watt">tok/s/W</th>
  <th class="lb-sortable" data-col="last_submitted_at">Último envio</th>
  <th class="lb-sortable" data-col="samples">Amostras</th>
</tr>
</thead>
<tbody id="lb-body">
<tr><td colspan="10" class="lb-loading">Carregando dados da comunidade...</td></tr>
</tbody>
</table>
</div>

<div class="lb-footer">
  <p>Dados de <a href="https://api.asiai.dev/api/v1/leaderboard">api.asiai.dev</a> — atualizado em tempo real.<br>
  Contribua com seus resultados: <code>asiai bench --share</code></p>
</div>

</div>
