---
description: Apple Silicon Mac 전체의 커뮤니티 벤치마크 결과. 엔진, 모델, 하드웨어별 tok/s를 비교하세요. 자신의 결과도 제출할 수 있습니다.
---

# 커뮤니티 리더보드

<div id="leaderboard-app" data-label-loading="로딩 중..." data-label-count="{n}개 결과" data-label-updated="업데이트: {t}" data-label-error="api.asiai.dev에 연결할 수 없습니다" data-label-empty="결과를 찾을 수 없습니다">

<div class="lb-filters" markdown>
<div class="lb-filter-row">
  <input type="text" id="lb-chip" placeholder="칩으로 필터링 (예: M4 Pro)" class="lb-input">
  <input type="text" id="lb-model" placeholder="모델로 필터링 (예: qwen2.5)" class="lb-input">
  <button id="lb-search" class="lb-btn">검색</button>
  <button id="lb-clear" class="lb-btn lb-btn-secondary">초기화</button>
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
  <th class="lb-sortable" data-col="engine">엔진</th>
  <th class="lb-sortable" data-col="model">모델</th>
  <th class="lb-sortable lb-active-sort" data-col="median_tok_s">tok/s</th>
  <th class="lb-sortable" data-col="median_ttft_ms">TTFT</th>
  <th>칩</th>
  <th>RAM</th>
  <th>Quant</th>
  <th class="lb-sortable" data-col="median_power_watts">W</th>
  <th class="lb-sortable" data-col="median_tok_s_per_watt">tok/s/W</th>
  <th class="lb-sortable" data-col="last_submitted_at">최근 제출</th>
  <th class="lb-sortable" data-col="samples">샘플</th>
</tr>
</thead>
<tbody id="lb-body">
<tr><td colspan="11" class="lb-loading">커뮤니티 데이터 로딩 중...</td></tr>
</tbody>
</table>
</div>

<div class="lb-footer">
  <p>데이터 소스: <a href="https://api.asiai.dev/api/v1/leaderboard">api.asiai.dev</a> — 실시간 업데이트<br>
  결과 제출: <code>asiai bench --share</code></p>
</div>

</div>
