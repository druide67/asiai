/* Community leaderboard client — shared by every locale of docs/leaderboard*.md.
 *
 * Localized UI strings come from data-label-* attributes on #leaderboard-app
 * (set per-locale in the Markdown pages); English defaults live here.
 * All API data is inserted via textContent / DOM APIs only — never innerHTML.
 *
 * Two views, one table. "speed" (default) shows the legacy GPU-rail power
 * columns; "energy" shows the metrics_version-4 SoC block (package watts,
 * joules per token, active J/tok, loaded idle) with its provenance. A group
 * that only ever submitted GPU-rail power renders "—" in the energy view —
 * never its GPU value dressed up as SoC.
 */
(function () {
  "use strict";

  var API = "https://api.asiai.dev/api/v1/leaderboard";
  var EMPTY = "—";
  var DAY_MS = 86400000;
  var FRESH_DAYS = 7;
  var RECENT_DAYS = 30;
  var VIEW_KEY = "asiai-lb-view";
  var VIEWS = { speed: true, energy: true };

  /* Columns that live in exactly one view. Everything else is shared. */
  var VIEW_COLS = {
    median_power_watts: "speed",
    median_tok_s_per_watt: "speed",
    median_soc_watts: "energy",
    median_energy_per_token_j: "energy",
    median_energy_per_token_active_j: "energy",
    median_idle_soc_watts: "energy"
  };
  /* Lower is better: the default direction on first click is ascending. */
  var ASC_FIRST = {
    median_ttft_ms: true,
    median_energy_per_token_j: true,
    median_energy_per_token_active_j: true,
    median_idle_soc_watts: true
  };

  function init() {
    var app = document.getElementById("leaderboard-app");
    if (!app || app.dataset.lbInitialized === "1") return;
    app.dataset.lbInitialized = "1";

    var labels = {
      loading: app.dataset.labelLoading || "Loading...",
      count: app.dataset.labelCount || "{n} result(s)",
      updated: app.dataset.labelUpdated || "Updated: {t}",
      error: app.dataset.labelError || "Could not reach api.asiai.dev",
      empty: app.dataset.labelEmpty || "No results found",
      provenance: app.dataset.labelProvenance || "{n} energy sample(s), base {b}"
    };
    var lang = document.documentElement.lang || undefined;
    var data = [];
    var sortCol = "median_tok_s";
    var sortAsc = false;
    var view = readView();

    function readView() {
      try {
        var v = window.localStorage.getItem(VIEW_KEY);
        if (v && VIEWS[v]) return v;
      } catch (e) { /* storage blocked: default view */ }
      return "speed";
    }

    function storeView(v) {
      try { window.localStorage.setItem(VIEW_KEY, v); } catch (e) { /* ignore */ }
    }

    function clearChildren(el) {
      while (el.firstChild) el.removeChild(el.firstChild);
    }

    /* Only the columns visible in the current view count for colspan. */
    function columnCount() {
      var ths = app.querySelectorAll("#lb-table thead th");
      var n = 0;
      for (var i = 0; i < ths.length; i++) {
        var col = ths[i].dataset.col;
        if (!col || !VIEW_COLS[col] || VIEW_COLS[col] === view) n++;
      }
      return n || ths.length || 10;
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

    function applyView() {
      var table = document.getElementById("lb-table");
      table.classList.toggle("lb-view-energy", view === "energy");
      table.classList.toggle("lb-view-speed", view === "speed");
      app.querySelectorAll(".lb-view-btn").forEach(function (b) {
        var active = b.dataset.view === view;
        b.classList.toggle("lb-view-active", active);
        b.setAttribute("aria-pressed", active ? "true" : "false");
      });
      /* A sort column hidden by the view switch falls back to tok/s. */
      if (VIEW_COLS[sortCol] && VIEW_COLS[sortCol] !== view) {
        sortCol = "median_tok_s";
        sortAsc = false;
        markSortHeader();
      }
    }

    function markSortHeader() {
      app.querySelectorAll(".lb-sortable").forEach(function (t) {
        t.classList.remove("lb-active-sort", "lb-sort-asc");
        if (t.dataset.col === sortCol) {
          t.classList.add("lb-active-sort");
          if (sortAsc) t.classList.add("lb-sort-asc");
        }
      });
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

    /* Energy cell: the value, plus a provenance dot when the group carries a
     * gated SoC block. Groups without one show "—" and no dot — the absence of
     * a measurement is information, a zero would be a lie. */
    function createEnergyCell(r, key, digits) {
      var td = createCell(fmtNum(r[key], digits), "lb-num lb-col-energy");
      if (isNum(r[key]) && r[key] > 0 && isNum(r.energy_samples) && r.energy_samples > 0) {
        var dot = document.createElement("span");
        dot.className = "lb-prov";
        var bases = Array.isArray(r.energy_bases) ? r.energy_bases.join(", ") : "";
        dot.title = labels.provenance
          .replace("{n}", String(r.energy_samples))
          .replace("{b}", bases || "?");
        td.appendChild(dot);
      }
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

    /* Rows without a value for the sort column always sink to the bottom,
     * whichever the direction. The old `|| 0` put "no data" FIRST when sorting
     * ascending — exactly the rows a J/tok ranking must not lead with. */
    function compare(a, b) {
      var va = a[sortCol];
      var vb = b[sortCol];
      var aMissing = va === undefined || va === null || va === "" ||
        (typeof va === "number" && !(va > 0));
      var bMissing = vb === undefined || vb === null || vb === "" ||
        (typeof vb === "number" && !(vb > 0));
      if (aMissing && bMissing) return 0;
      if (aMissing) return 1;
      if (bMissing) return -1;
      if (typeof va === "string" || typeof vb === "string") {
        va = String(va).toLowerCase();
        vb = String(vb).toLowerCase();
      }
      if (va === vb) return 0;
      var less = va < vb ? -1 : 1;
      return sortAsc ? less : -less;
    }

    function render() {
      var sorted = data.slice().sort(compare);

      /* Row 1 only shows the accent tok/s while it truly is the best tok/s
       * (sorted by tok/s, descending) — see .lb-sorted-tok in the CSS. */
      document.getElementById("lb-table").classList.toggle(
        "lb-sorted-tok", sortCol === "median_tok_s" && !sortAsc);

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

        /* Chip + RAM stacked in a single cell (design craft pass). */
        var hwTd = document.createElement("td");
        hwTd.className = "lb-hw";
        var chipSpan = document.createElement("span");
        chipSpan.className = "lb-hw-chip";
        chipSpan.textContent = r.hw_chip || "?";
        hwTd.appendChild(chipSpan);
        var ramSpan = document.createElement("span");
        ramSpan.className = "lb-hw-ram";
        ramSpan.textContent = r.hw_ram_gb ? r.hw_ram_gb + " GB" : "?";
        hwTd.appendChild(ramSpan);
        tr.appendChild(hwTd);

        /* v2 aggregate fields — additive, may be absent on any group. */
        tr.appendChild(createCell(fmtList(r.quantizations), "lb-quant"));

        /* Speed view: GPU rail alone (legacy submissions). */
        tr.appendChild(createCell(fmtNum(r.median_power_watts, 1), "lb-num lb-col-speed"));
        tr.appendChild(createCell(fmtNum(r.median_tok_s_per_watt, 2), "lb-num lb-col-speed"));

        /* Energy view: SoC block (v2.1 additive aggregates). */
        tr.appendChild(createEnergyCell(r, "median_soc_watts", 1));
        tr.appendChild(createEnergyCell(r, "median_energy_per_token_j", 3));
        tr.appendChild(createEnergyCell(r, "median_energy_per_token_active_j", 3));
        tr.appendChild(createEnergyCell(r, "median_idle_soc_watts", 1));

        tr.appendChild(createLastSeenCell(r.last_submitted_at));

        tr.appendChild(createCell(String(r.samples || 0)));

        tbody.appendChild(tr);
      }
    }

    app.querySelectorAll(".lb-sortable").forEach(function (th) {
      th.addEventListener("click", function () {
        var col = th.dataset.col;
        if (sortCol === col) { sortAsc = !sortAsc; }
        else { sortCol = col; sortAsc = !!ASC_FIRST[col]; }
        markSortHeader();
        render();
      });
    });

    app.querySelectorAll(".lb-view-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var v = btn.dataset.view;
        if (!VIEWS[v] || v === view) return;
        view = v;
        storeView(v);
        applyView();
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

    applyView();
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
