/* Community leaderboard client — shared by every locale of docs/leaderboard*.md.
 *
 * Localized UI strings come from data-label-* attributes on #leaderboard-app
 * (set per-locale in the Markdown pages); English defaults live here.
 * All API data is inserted via textContent / DOM APIs only — never innerHTML.
 */
(function () {
  "use strict";

  var API = "https://api.asiai.dev/api/v1/leaderboard";
  var EMPTY = "—";
  var DAY_MS = 86400000;
  var FRESH_DAYS = 7;
  var RECENT_DAYS = 30;

  function init() {
    var app = document.getElementById("leaderboard-app");
    if (!app || app.dataset.lbInitialized === "1") return;
    app.dataset.lbInitialized = "1";

    var labels = {
      loading: app.dataset.labelLoading || "Loading...",
      count: app.dataset.labelCount || "{n} result(s)",
      updated: app.dataset.labelUpdated || "Updated: {t}",
      error: app.dataset.labelError || "Could not reach api.asiai.dev",
      empty: app.dataset.labelEmpty || "No results found"
    };
    var lang = document.documentElement.lang || undefined;
    var data = [];
    var sortCol = "median_tok_s";
    var sortAsc = false;

    function clearChildren(el) {
      while (el.firstChild) el.removeChild(el.firstChild);
    }

    function columnCount() {
      var ths = app.querySelectorAll("#lb-table thead th");
      return ths.length || 11;
    }

    function setMessage(msg) {
      var tbody = document.getElementById("lb-body");
      clearChildren(tbody);
      var tr = document.createElement("tr");
      var td = document.createElement("td");
      td.setAttribute("colspan", String(columnCount()));
      td.className = "lb-loading";
      td.textContent = msg;
      tr.appendChild(td);
      tbody.appendChild(tr);
    }

    function isNum(v) {
      return typeof v === "number" && isFinite(v);
    }

    /* Defensive formatters: absent/malformed/zero fields render as "—".
     * The API never fabricates a 0 for v2 aggregates, and median_ttft_ms
     * is 0.0 when no sample reported TTFT — so non-positive means "no data". */
    function fmtNum(v, digits, suffix) {
      if (!isNum(v) || v <= 0) return EMPTY;
      return v.toFixed(digits) + (suffix || "");
    }

    function fmtList(v) {
      if (!Array.isArray(v) || !v.length) return EMPTY;
      return v.filter(function (x) { return typeof x === "string" && x; }).join(", ") || EMPTY;
    }

    function fetchData() {
      var chip = document.getElementById("lb-chip").value.trim();
      var model = document.getElementById("lb-model").value.trim();
      var params = new URLSearchParams();
      if (chip) params.set("chip", chip);
      if (model) params.set("model", model);
      var url = params.toString() ? API + "?" + params : API;

      setMessage(labels.loading);

      fetch(url)
        .then(function (r) { return r.json(); })
        .then(function (d) {
          data = d.results || d;
          if (!Array.isArray(data)) { data = []; }
          render();
          document.getElementById("lb-count").textContent =
            labels.count.replace("{n}", String(data.length));
          document.getElementById("lb-updated").textContent =
            labels.updated.replace("{t}", new Date().toLocaleTimeString());
        })
        .catch(function () {
          setMessage(labels.error);
        });
    }

    function createCell(text, className) {
      var td = document.createElement("td");
      if (className) td.className = className;
      td.textContent = text;
      return td;
    }

    /* "Last seen" cell: locale-formatted date + freshness dot
     * (green <= 7 days, orange <= 30 days, none beyond). */
    function createLastSeenCell(iso) {
      var td = document.createElement("td");
      td.className = "lb-seen";
      var d = typeof iso === "string" ? new Date(iso) : null;
      if (!d || isNaN(d.getTime())) {
        td.textContent = EMPTY;
        return td;
      }
      var dateSpan = document.createElement("span");
      try {
        dateSpan.textContent = d.toLocaleDateString(lang);
      } catch (e) {
        dateSpan.textContent = d.toLocaleDateString();
      }
      td.appendChild(dateSpan);
      var ageDays = (Date.now() - d.getTime()) / DAY_MS;
      if (ageDays <= RECENT_DAYS) {
        var badge = document.createElement("span");
        badge.className = "lb-badge " +
          (ageDays <= FRESH_DAYS ? "lb-badge-fresh" : "lb-badge-recent");
        badge.title = iso;
        td.appendChild(badge);
      }
      return td;
    }

    function render() {
      var sorted = data.slice().sort(function (a, b) {
        var va = a[sortCol] || 0;
        var vb = b[sortCol] || 0;
        if (typeof va === "string" || typeof vb === "string") {
          va = String(va).toLowerCase();
          vb = String(vb).toLowerCase();
        }
        return sortAsc ? (va > vb ? 1 : -1) : (va < vb ? 1 : -1);
      });

      var tbody = document.getElementById("lb-body");
      clearChildren(tbody);

      if (!sorted.length) {
        setMessage(labels.empty);
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

        tr.appendChild(createCell(fmtNum(r.median_ttft_ms, 0, " ms")));
        tr.appendChild(createCell(r.hw_chip || "?", "lb-chip"));
        tr.appendChild(createCell(r.hw_ram_gb ? r.hw_ram_gb + " GB" : "?"));

        /* v2 aggregate fields — additive, may be absent on any group. */
        tr.appendChild(createCell(fmtList(r.quantizations), "lb-chip"));
        tr.appendChild(createCell(fmtNum(r.median_power_watts, 1), "lb-num"));
        tr.appendChild(createCell(fmtNum(r.median_tok_s_per_watt, 2), "lb-num"));
        tr.appendChild(createLastSeenCell(r.last_submitted_at));

        tr.appendChild(createCell(String(r.samples || 0)));

        tbody.appendChild(tr);
      }
    }

    app.querySelectorAll(".lb-sortable").forEach(function (th) {
      th.addEventListener("click", function () {
        var col = th.dataset.col;
        if (sortCol === col) { sortAsc = !sortAsc; }
        else { sortCol = col; sortAsc = false; }
        app.querySelectorAll(".lb-sortable").forEach(function (t) {
          t.classList.remove("lb-active-sort", "lb-sort-asc");
        });
        th.classList.add("lb-active-sort");
        if (sortAsc) th.classList.add("lb-sort-asc");
        render();
      });
    });

    document.getElementById("lb-search").addEventListener("click", fetchData);
    document.getElementById("lb-clear").addEventListener("click", function () {
      document.getElementById("lb-chip").value = "";
      document.getElementById("lb-model").value = "";
      fetchData();
    });
    document.getElementById("lb-chip").addEventListener("keydown", function (e) {
      if (e.key === "Enter") fetchData();
    });
    document.getElementById("lb-model").addEventListener("keydown", function (e) {
      if (e.key === "Enter") fetchData();
    });

    fetchData();
  }

  /* extra_javascript is injected at the end of <body>, but stay defensive. */
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
  /* Material "instant loading" support (no-op unless the feature is enabled). */
  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(function () { init(); });
  }
})();
