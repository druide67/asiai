---
description: Apple Silicon Mac 전체의 커뮤니티 벤치마크 결과. 엔진, 모델, 하드웨어별 tok/s를 비교하세요. 자신의 결과도 제출할 수 있습니다.
---

# 커뮤니티 리더보드

<div id="leaderboard-app">

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

<table id="lb-table" class="lb-table">
<thead>
<tr>
  <th class="lb-sortable" data-col="engine">엔진</th>
  <th class="lb-sortable" data-col="model">모델</th>
  <th class="lb-sortable lb-active-sort" data-col="median_tok_s">tok/s</th>
  <th class="lb-sortable" data-col="median_ttft_ms">TTFT</th>
  <th>칩</th>
  <th>RAM</th>
  <th class="lb-sortable" data-col="samples">샘플</th>
</tr>
</thead>
<tbody id="lb-body">
<tr><td colspan="7" class="lb-loading">커뮤니티 데이터 로딩 중...</td></tr>
</tbody>
</table>

<div class="lb-footer">
  <p>데이터 소스: <a href="https://api.asiai.dev/api/v1/leaderboard">api.asiai.dev</a> — 실시간 업데이트<br>
  결과 제출: <code>asiai bench --share</code></p>
</div>

</div>

<style>
.lb-filter-row {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-bottom: 0.5rem;
}
.lb-input {
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--md-default-fg-color--lightest);
  border-radius: 4px;
  background: var(--md-default-bg-color);
  color: var(--md-default-fg-color);
  font-size: 0.85rem;
  min-width: 200px;
}
.lb-input:focus {
  outline: none;
  border-color: var(--md-primary-fg-color);
}
.lb-btn {
  padding: 0.5rem 1.2rem;
  border: none;
  border-radius: 4px;
  background: var(--md-primary-fg-color);
  color: var(--md-primary-bg-color);
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 600;
}
.lb-btn:hover { opacity: 0.9; }
.lb-btn-secondary {
  background: var(--md-default-fg-color--lightest);
  color: var(--md-default-fg-color);
}
.lb-status {
  display: flex;
  justify-content: space-between;
  font-size: 0.8rem;
  color: var(--md-default-fg-color--light);
  margin-bottom: 1rem;
}
.lb-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}
.lb-table th {
  text-align: left;
  padding: 0.6rem 0.8rem;
  border-bottom: 2px solid var(--md-primary-fg-color);
  font-weight: 600;
  white-space: nowrap;
}
.lb-table td {
  padding: 0.5rem 0.8rem;
  border-bottom: 1px solid var(--md-default-fg-color--lightest);
}
.lb-table tbody tr:hover {
  background: var(--md-default-fg-color--lightest);
}
.lb-sortable { cursor: pointer; user-select: none; }
.lb-sortable:hover { color: var(--md-primary-fg-color); }
.lb-sortable::after { content: " \2195"; opacity: 0.3; font-size: 0.75rem; }
.lb-active-sort::after { content: " \2193"; opacity: 1; }
.lb-active-sort.lb-sort-asc::after { content: " \2191"; opacity: 1; }
.lb-loading { text-align: center; padding: 2rem; color: var(--md-default-fg-color--light); }
.lb-tok { font-weight: 600; font-variant-numeric: tabular-nums; }
.lb-chip { font-size: 0.8rem; color: var(--md-default-fg-color--light); }
.lb-footer { margin-top: 1.5rem; font-size: 0.85rem; color: var(--md-default-fg-color--light); }
.lb-footer code { font-size: 0.8rem; }
.lb-bar {
  display: inline-block;
  height: 6px;
  border-radius: 3px;
  background: var(--md-primary-fg-color);
  margin-left: 0.5rem;
  vertical-align: middle;
}
@media (max-width: 768px) {
  .lb-input { min-width: 140px; }
  .lb-table { font-size: 0.8rem; }
  .lb-table th, .lb-table td { padding: 0.4rem; }
}
</style>

<script>
(function() {
  var API = "https://api.asiai.dev/api/v1/leaderboard";
  var data = [];
  var sortCol = "median_tok_s";
  var sortAsc = false;

  function clearChildren(el) {
    while (el.firstChild) el.removeChild(el.firstChild);
  }

  function setMessage(msg) {
    var tbody = document.getElementById("lb-body");
    clearChildren(tbody);
    var tr = document.createElement("tr");
    var td = document.createElement("td");
    td.setAttribute("colspan", "7");
    td.className = "lb-loading";
    td.textContent = msg;
    tr.appendChild(td);
    tbody.appendChild(tr);
  }

  function fetchData() {
    var chip = document.getElementById("lb-chip").value.trim();
    var model = document.getElementById("lb-model").value.trim();
    var params = new URLSearchParams();
    if (chip) params.set("chip", chip);
    if (model) params.set("model", model);
    var url = params.toString() ? API + "?" + params : API;

    setMessage("로딩 중...");

    fetch(url)
      .then(function(r) { return r.json(); })
      .then(function(d) {
        data = d.results || d;
        if (!Array.isArray(data)) { data = []; }
        render();
        document.getElementById("lb-count").textContent = data.length + "개 결과";
        document.getElementById("lb-updated").textContent =
          "업데이트: " + new Date().toLocaleTimeString();
      })
      .catch(function() {
        setMessage("api.asiai.dev에 연결할 수 없습니다");
      });
  }

  function createCell(text, className) {
    var td = document.createElement("td");
    if (className) td.className = className;
    td.textContent = text;
    return td;
  }

  function render() {
    var sorted = data.slice().sort(function(a, b) {
      var va = a[sortCol] || 0;
      var vb = b[sortCol] || 0;
      if (typeof va === "string") {
        va = va.toLowerCase();
        vb = (vb || "").toLowerCase();
      }
      return sortAsc ? (va > vb ? 1 : -1) : (va < vb ? 1 : -1);
    });

    var tbody = document.getElementById("lb-body");
    clearChildren(tbody);

    if (!sorted.length) {
      setMessage("결과를 찾을 수 없습니다");
      return;
    }

    var maxTok = 1;
    for (var i = 0; i < data.length; i++) {
      var t = data[i].median_tok_s || 0;
      if (t > maxTok) maxTok = t;
    }

    for (var j = 0; j < sorted.length; j++) {
      var r = sorted[j];
      var tr = document.createElement("tr");

      tr.appendChild(createCell(r.engine || "?"));

      var modelTd = document.createElement("td");
      var modelB = document.createElement("strong");
      modelB.textContent = r.model || "?";
      modelTd.appendChild(modelB);
      tr.appendChild(modelTd);

      var tokTd = document.createElement("td");
      tokTd.className = "lb-tok";
      tokTd.textContent = (r.median_tok_s || 0).toFixed(1);
      var bar = document.createElement("span");
      bar.className = "lb-bar";
      bar.style.width = Math.round(((r.median_tok_s || 0) / maxTok) * 80) + "px";
      tokTd.appendChild(bar);
      tr.appendChild(tokTd);

      var ttft = r.median_ttft_ms;
      tr.appendChild(createCell(ttft ? ttft.toFixed(0) + " ms" : "\u2014"));
      tr.appendChild(createCell(r.hw_chip || "?", "lb-chip"));
      tr.appendChild(createCell(r.hw_ram_gb ? r.hw_ram_gb + " GB" : "?"));
      tr.appendChild(createCell(String(r.samples || 0)));

      tbody.appendChild(tr);
    }
  }

  document.querySelectorAll(".lb-sortable").forEach(function(th) {
    th.addEventListener("click", function() {
      var col = th.dataset.col;
      if (sortCol === col) { sortAsc = !sortAsc; }
      else { sortCol = col; sortAsc = false; }
      document.querySelectorAll(".lb-sortable").forEach(function(t) {
        t.classList.remove("lb-active-sort", "lb-sort-asc");
      });
      th.classList.add("lb-active-sort");
      if (sortAsc) th.classList.add("lb-sort-asc");
      render();
    });
  });

  document.getElementById("lb-search").addEventListener("click", fetchData);
  document.getElementById("lb-clear").addEventListener("click", function() {
    document.getElementById("lb-chip").value = "";
    document.getElementById("lb-model").value = "";
    fetchData();
  });
  document.getElementById("lb-chip").addEventListener("keydown", function(e) {
    if (e.key === "Enter") fetchData();
  });
  document.getElementById("lb-model").addEventListener("keydown", function(e) {
    if (e.key === "Enter") fetchData();
  });

  fetchData();
})();
</script>
