/* Multi-node Dashboard & Monitor (Lot 2, direction D).
 *
 * One engine for both pages: a fleet ribbon (whole-park aggregates), a
 * detailed READ-ONLY block per node, and multi-select chips that filter
 * which blocks show (all checked by default — an unknown node is shown).
 * Actions live in the Fleet cockpit only; every block links there and
 * pre-selects its node through the cockpit's own localStorage key.
 *
 * Data: GET /api/v1/fleet/snapshot (12 s poll, 10 s server cache).
 * Zero-fleet fallback: a single "this host" block fed by the local
 * GET /api/v1/snapshot, so the product works before any `fleet add`.
 *
 * Rendering rule (same as fleet.js/shell.js): createElement/textContent
 * only — never innerHTML with dynamic data.
 */
(function () {
    'use strict';

    var root = document.querySelector('[data-mn-page]');
    if (!root) return;
    var PAGE = root.getAttribute('data-mn-page'); // 'dashboard' | 'monitor'

    // Monitor is the LIVE page: poll faster (the hub cache still bounds
    // freshness at ~10 s; the counter tween below absorbs identical polls).
    var POLL_MS = PAGE === 'monitor' ? 6000 : 12000;
    var HIDDEN_KEY = 'asiai-fleet-nodes-hidden'; // JSON array of UNchecked nicknames
    var COCKPIT_NODE_KEY = 'asiai-fleet-node';   // the cockpit's mono selection
    var SPARK_POINTS = 48;                       // ~5 min of history at 6 s
    var REDUCED_MOTION = !!(window.matchMedia
        && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

    // Reachability wins over launchd paperwork — same display rule as the
    // cockpit (a serving engine is RUNNING whatever its rich state says).
    var LIVE_STATES = { running: 1, unhealthy: 1, degraded: 1, loading: 1 };
    // Dormant-but-provisioned states get their own row; the rest folds.
    var DORMANT_ROW = { stopped: 1, disabled: 1, loaded: 1 };

    var state = {
        fleet: null,        // last fleet snapshot ({nodes:[...]}), or null
        localSnap: null,    // zero-fleet fallback: local /api/v1/snapshot
        localOnly: false,
        hidden: loadHidden(),
        history: {},        // nickname -> {cpu:[...], gpu:[...]} ring buffers
    };

    // ── live counters (the "you can SEE it inferring" effect) ───
    //
    // Full-DOM re-renders every poll would freeze any CSS animation, so
    // moving numbers are driven by ONE rAF loop over a registry keyed by
    // metric: each poll re-attaches the freshly created element and sets a
    // new target; the observed rate (delta ÷ time between two DIFFERENT
    // values) keeps the number rolling BETWEEN polls — a generating LLM
    // never stops counting, an idle one sits still. Identical polls (hub
    // cache) don't stutter: the rate simply carries until the next change.
    var counters = {};

    function tween(key, target, eln, fmt) {
        var c = counters[key];
        var now = Date.now();
        if (!c) {
            c = counters[key] = { shown: target, target: target, rate: 0, changedAt: now };
        } else if (target !== c.target) {
            var dt = now - c.changedAt;
            c.rate = dt > 0 ? (target - c.target) / dt : 0;
            c.changedAt = now;
            c.target = target;
        }
        c.el = eln;
        c.fmt = fmt;
        eln.textContent = fmt(REDUCED_MOTION ? target : c.shown);
    }

    // Observed throughput over a sliding window. llama.cpp only adds a
    // request's tokens to the counter when the request FINISHES, so the
    // per-poll delta lies during long generations (one +2500 jump after
    // 70s reads as ~400 t/s on a 6s poll). A 30s window averages jumps
    // back to the real decode rate, and smooths short-request bursts too.
    // The window lives on the counter entry so pruneHidden clears both.
    function observedRate(key, target) {
        var c = counters[key];
        if (!c) return 0;
        var now = Date.now();
        var w = c.win || (c.win = []);
        w.push({ t: now, v: target });
        while (w.length && now - w[0].t > 30000) w.shift();
        var span = now - w[0].t;
        if (span < 4000 || w.length < 2) return 0;
        return ((target - w[0].v) / span) * 1000;
    }

    var lastTick = Date.now();
    function tick() {
        var now = Date.now();
        var dt = now - lastTick;
        lastTick = now;
        Object.keys(counters).forEach(function (key) {
            var c = counters[key];
            if (!c.el || !c.el.isConnected || c.shown === c.target) return;
            if (c.rate > 0 && c.target > c.shown) {
                c.shown = Math.min(c.target, c.shown + c.rate * dt);
            } else {
                // Resets (engine restart) and downward moves snap — a token
                // counter must never be seen rolling backwards.
                c.shown = c.target;
            }
            c.el.textContent = c.fmt(c.shown);
        });
        window.requestAnimationFrame(tick);
    }
    if (!REDUCED_MOTION && PAGE === 'monitor') window.requestAnimationFrame(tick);

    function loadHidden() {
        try {
            var raw = localStorage.getItem(HIDDEN_KEY);
            var arr = raw ? JSON.parse(raw) : [];
            return Array.isArray(arr) ? arr.filter(function (x) { return typeof x === 'string'; }) : [];
        } catch (e) { return []; }
    }

    function saveHidden() {
        try { localStorage.setItem(HIDDEN_KEY, JSON.stringify(state.hidden)); } catch (e) { /* private mode */ }
    }

    function el(tag, cls, text) {
        var node = document.createElement(tag);
        if (cls) node.className = cls;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function fmtGB(bytes) {
        return (bytes / (1024 * 1024 * 1024)).toFixed(1);
    }

    function engineStateOf(engine, nodeOk) {
        var st = engine.state;
        if (!LIVE_STATES[st] && engine.reachable) return 'running';
        if (st) return st;
        return engine.reachable && nodeOk ? 'running' : 'stopped';
    }

    function engineLabel(e) { return e.engine_id || e.name || 'engine'; }

    // ── data ────────────────────────────────────────────────────
    function poll() {
        fetch('/api/v1/fleet/snapshot')
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (snap) {
                if (!snap) return;
                var nodes = Array.isArray(snap.nodes) ? snap.nodes : [];
                if (!nodes.length) { state.localOnly = true; return pollLocal(); }
                state.localOnly = false;
                state.fleet = snap;
                pruneHidden(nodes);
                pushHistory(nodes);
                renderAll();
            })
            .catch(function () { renderAll(); /* ages drift -> STALE badges say it */ });
    }

    // A nickname removed from the fleet must not haunt localStorage: an
    // unchecked-then-removed node would silently keep filtering forever.
    // Same hygiene for the in-memory registries (sparkline history and
    // rolling counters — their keys are prefixed by the nickname).
    function pruneHidden(nodes) {
        var known = {};
        nodes.forEach(function (n) { known[n.nickname] = 1; });
        var pruned = state.hidden.filter(function (nick) { return known[nick]; });
        if (pruned.length !== state.hidden.length) {
            state.hidden = pruned;
            saveHidden();
        }
        Object.keys(state.history).forEach(function (k) { if (!known[k]) delete state.history[k]; });
        Object.keys(counters).forEach(function (k) { if (!known[k.split('/')[0]]) delete counters[k]; });
    }

    function pollLocal() {
        fetch('/api/v1/snapshot')
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (snap) {
                if (!snap) return;
                state.localSnap = { data: snap, at: Date.now() / 1000 };
                pushHistory([{ nickname: 'this host', ok: true, snapshot: snap }]);
                renderAll();
            })
            .catch(function () { renderAll(); });
    }

    function pushHistory(nodes) {
        nodes.forEach(function (n) {
            var s = n.snapshot || {};
            var h = state.history[n.nickname] || (state.history[n.nickname] = { cpu: [], gpu: [] });
            var cores = s.cpu_cores || 0;
            if (cores && typeof s.cpu_load_1 === 'number') {
                h.cpu.push(Math.max(0, Math.min(100, (s.cpu_load_1 / cores) * 100)));
                if (h.cpu.length > SPARK_POINTS) h.cpu.shift();
            }
            if (typeof s.gpu_utilization_pct === 'number' && s.gpu_utilization_pct >= 0) {
                h.gpu.push(Math.max(0, Math.min(100, s.gpu_utilization_pct)));
                if (h.gpu.length > SPARK_POINTS) h.gpu.shift();
            }
        });
    }

    // ── derived ─────────────────────────────────────────────────
    function visibleNodes() {
        var nodes = state.fleet && state.fleet.nodes ? state.fleet.nodes : [];
        // The chip bar only exists at >= 2 nodes, so the hidden filter must
        // not apply below that — or a lone node unchecked BEFORE its sibling
        // was removed becomes unrecoverable (audit finding: dead-end UI).
        if (nodes.length < 2) return nodes;
        return nodes.filter(function (n) { return state.hidden.indexOf(n.nickname) === -1; });
    }

    function nodeHealth(node) {
        if (!node.ok) return 'down';
        var warn = false;
        enginesOf(node).forEach(function (e) {
            var st = engineStateOf(e, node.ok);
            if (st === 'unhealthy' || st === 'degraded') warn = true;
        });
        return warn ? 'warn' : 'ok';
    }

    function enginesOf(node) {
        var s = node.snapshot || {};
        var engines = s.engines_status;
        if (!Array.isArray(engines)) return [];
        return engines.filter(function (e) {
            return e && typeof e === 'object' && typeof e.name === 'string';
        });
    }

    function ageOf(node) {
        if (!node.reached_at) return null;
        return Math.max(0, Math.round(Date.now() / 1000 - node.reached_at));
    }

    // ── shared renderers ────────────────────────────────────────
    function ageBadge(node) {
        if (!node.ok) return el('span', 'mn-age stale', 'UNREACHABLE');
        var age = ageOf(node);
        if (age === null) return el('span', 'mn-age slow', 'AGE ?');
        if (age > 30) return el('span', 'mn-age stale', 'STALE · ' + age + ' s');
        if (age > 15) return el('span', 'mn-age slow', 'SLOW · ' + age + ' s');
        return el('span', 'mn-age fresh', age + ' s');
    }

    function healthDot(health) {
        // Same palette as the cockpit's node health: red / yellow / green.
        var dot = el('span', 'fl-dot');
        dot.style.background = health === 'down' ? 'var(--red)' : health === 'warn' ? 'var(--yellow)' : 'var(--green)';
        dot.style.boxShadow = '0 0 8px ' + (health === 'down' ? 'rgba(239,68,68,.5)'
            : health === 'warn' ? 'rgba(234,179,8,.5)' : 'rgba(34,197,94,.45)');
        return dot;
    }

    function nodeHead(node) {
        var head = el('div', 'mn-node-head');
        head.appendChild(healthDot(nodeHealth(node)));
        head.appendChild(el('span', 'mn-node-name', node.nickname));
        head.appendChild(ageBadge(node));
        var s = node.snapshot || {};
        var bits = [];
        if (s.cpu_cores) bits.push(s.cpu_cores + 'C');
        if (s.uptime) bits.push('up ' + Math.floor(s.uptime / 86400) + ' d');
        head.appendChild(el('span', 'mn-node-meta', bits.join(' · ')));
        return head;
    }

    function memCell(s) {
        var wrap = el('div');
        wrap.appendChild(el('div', 'mn-klabel', 'Memory'));
        var used = s.mem_used || 0;
        var total = s.mem_total || 0;
        var kpi = el('div', 'mn-kpi', total ? fmtGB(used) : '—');
        if (total) {
            var small = el('small');
            small.textContent = '/ ' + fmtGB(total) + ' GB';
            kpi.appendChild(small);
        }
        wrap.appendChild(kpi);
        var pct = total ? (used / total) * 100 : 0;
        var bar = el('div', 'mn-bar');
        var fill = el('i', pct > 90 ? 'crit' : pct > 75 ? 'warn' : '');
        fill.style.width = Math.min(100, pct).toFixed(0) + '%';
        bar.appendChild(fill);
        wrap.appendChild(bar);
        return wrap;
    }

    function vitalsCell(s) {
        var wrap = el('div');
        wrap.appendChild(el('div', 'mn-klabel', 'CPU · GPU · Power'));
        var load = typeof s.cpu_load_1 === 'number' ? s.cpu_load_1.toFixed(1) : '—';
        var gpu = typeof s.gpu_utilization_pct === 'number' && s.gpu_utilization_pct >= 0
            ? Math.round(s.gpu_utilization_pct) + ' %' : '—';
        var kpi = el('div', 'mn-kpi plain', load + ' load · ' + gpu + ' gpu');
        wrap.appendChild(kpi);
        var watts = typeof s.power_total_watts === 'number' ? s.power_total_watts.toFixed(1) + ' W' : '— W';
        var line = el('div', 'mn-line');
        line.appendChild(el('b', null, watts));
        line.appendChild(document.createTextNode(
            ' · pressure ' + (s.mem_pressure || '—') + ' · thermal ' + (s.thermal_level || '—')));
        wrap.appendChild(line);
        return wrap;
    }

    function modelOf(engine) {
        if (Array.isArray(engine.models) && engine.models.length && engine.models[0].name) {
            var extra = engine.models.length > 1 ? ' +' + (engine.models.length - 1) : '';
            return engine.models[0].name + extra;
        }
        if (engine.model) return 'preset: ' + engine.model;
        return '';
    }

    function enginesList(node) {
        var host = el('div', 'mn-engines');
        var live = [], dormant = [], folded = 0;
        enginesOf(node).forEach(function (e) {
            var st = engineStateOf(e, node.ok);
            if (LIVE_STATES[st]) live.push([e, st]);
            else if (DORMANT_ROW[st]) dormant.push([e, st]);
            else folded += 1;
        });
        live.concat(dormant).forEach(function (pair) {
            var e = pair[0], st = pair[1];
            var row = el('div', 'mn-row');
            row.appendChild(el('span', 'fl-dot sm st-' + st));
            row.appendChild(el('span', 'nm', engineLabel(e)));
            var meta = modelOf(e);
            var port = String(e.url || '').match(/:(\d+)(\/|$)/);
            row.appendChild(el('span', 'meta', (meta ? meta + ' · ' : '') + (LIVE_STATES[st] ? (port ? ':' + port[1] : st) : st)));
            host.appendChild(row);
        });
        if (!live.length && !dormant.length && !folded) {
            host.appendChild(el('div', 'mn-more', 'no engines reported'));
        }
        if (folded) {
            host.appendChild(el('div', 'mn-more', '+ ' + folded + ' available / not installed'));
        }
        return host;
    }

    function manageLink(node) {
        var a = el('a', 'mn-manage', 'manage in Fleet →');
        a.href = '/fleet';
        a.addEventListener('click', function () {
            try { localStorage.setItem(COCKPIT_NODE_KEY, node.nickname); } catch (e) { /* ignored */ }
        });
        return a;
    }

    // ── page renderers ──────────────────────────────────────────
    function renderRibbon() {
        var host = document.getElementById('mn-ribbon');
        if (!host) return;
        host.textContent = '';
        var nodes = state.fleet && state.fleet.nodes ? state.fleet.nodes : [];
        if (state.localOnly || !nodes.length) { host.hidden = true; return; }
        host.hidden = false;

        var used = 0, total = 0, serving = 0, engines = 0, watts = 0, up = 0, alarms = 0;
        nodes.forEach(function (n) {
            if (n.ok) up += 1; else alarms += 1;
            var s = n.snapshot || {};
            used += s.mem_used || 0;
            total += s.mem_total || 0;
            watts += typeof s.power_total_watts === 'number' ? s.power_total_watts : 0;
            enginesOf(n).forEach(function (e) {
                engines += 1;
                var st = engineStateOf(e, n.ok);
                if (st === 'running') serving += 1;
                if (st === 'unhealthy' || st === 'degraded') alarms += 1;
            });
        });

        function item(value, label, cls) {
            var it = el('div', 'mn-ribbon-item');
            it.appendChild(el('b', cls || null, value));
            it.appendChild(el('span', null, label));
            return it;
        }
        host.appendChild(item(total ? fmtGB(used) + ' / ' + fmtGB(total) + ' GB' : '—', 'fleet memory'));
        host.appendChild(item(serving + ' / ' + engines, 'serving'));
        host.appendChild(item(watts.toFixed(1) + ' W', 'power'));
        host.appendChild(item(String(alarms), 'attention · ' + up + '/' + nodes.length + ' up', alarms ? 'bad' : 'ok'));
        var link = el('a', 'mn-ribbon-link', 'open Fleet →');
        link.href = '/fleet';
        host.appendChild(link);
    }

    function renderChips() {
        var host = document.getElementById('mn-chips');
        if (!host) return;
        host.textContent = '';
        var nodes = state.fleet && state.fleet.nodes ? state.fleet.nodes : [];
        if (state.localOnly || nodes.length < 2) { host.hidden = true; return; }
        host.hidden = false;

        host.appendChild(el('span', 'mn-chipbar-label', 'Nodes'));
        nodes.forEach(function (n) {
            var off = state.hidden.indexOf(n.nickname) !== -1;
            var chip = el('button', 'mn-chip' + (off ? ' off' : ''));
            chip.type = 'button';
            chip.setAttribute('aria-pressed', off ? 'false' : 'true');
            chip.appendChild(el('span', 'tick', '✓'));
            chip.appendChild(el('span', null, n.nickname));
            chip.addEventListener('click', function () {
                var i = state.hidden.indexOf(n.nickname);
                if (i === -1) state.hidden.push(n.nickname);
                else state.hidden.splice(i, 1);
                saveHidden();
                renderAll();
            });
            host.appendChild(chip);
        });
        var shown = nodes.length - nodes.filter(function (n) { return state.hidden.indexOf(n.nickname) !== -1; }).length;
        host.appendChild(el('span', 'mn-chip-count', shown + '/' + nodes.length + ' shown'));
    }

    function dashboardBlock(node) {
        var block = el('div', 'mn-node' + (node.ok ? '' : ' stale'));
        block.appendChild(nodeHead(node));
        var s = node.snapshot || {};
        var stats = el('div', 'mn-stats');
        stats.appendChild(memCell(s));
        stats.appendChild(vitalsCell(s));
        block.appendChild(stats);
        block.appendChild(enginesList(node));
        block.appendChild(manageLink(node));
        return block;
    }

    function sparkCell(nick, kind, label) {
        var wrap = el('div');
        wrap.appendChild(el('div', 'mn-klabel', label));
        var spark = el('div', 'mn-spark');
        var hist = state.history[nick] || {};
        var h = hist[kind] || [];
        var last = null;
        for (var i = 0; i < SPARK_POINTS; i++) {
            var v = h[h.length - SPARK_POINTS + i];
            var bar = el('i', typeof v === 'number' && v > 55 ? 'hot' : '');
            bar.style.height = typeof v === 'number' ? Math.max(4, Math.min(100, v)).toFixed(0) + '%' : '2px';
            spark.appendChild(bar);
            if (typeof v === 'number') last = v;
        }
        wrap.appendChild(spark);
        wrap.appendChild(el('div', 'mn-line', last === null ? '—' : last.toFixed(0) + ' %'));
        return wrap;
    }

    // Rich engine ACTIVITY — the live heart of the Monitor. Only engines
    // with a pulse show up here (the Dashboard owns the state inventory):
    // rolling token counter, in-flight requests, KV pressure, connections.
    function activityRows(node) {
        var host = el('div', 'mn-engines');
        var shown = 0;
        enginesOf(node).forEach(function (e) {
            var st = engineStateOf(e, node.ok);
            if (!LIVE_STATES[st]) return;
            shown += 1;
            var row = el('div', 'mn-row');
            row.appendChild(el('span', 'fl-dot sm st-' + st));
            row.appendChild(el('span', 'nm', engineLabel(e)));
            var busy = (e.requests_processing || 0) > 0;
            if (busy) row.appendChild(el('span', 'mn-inferring', 'INFERRING'));

            var right = el('span', 'mn-activity');
            // KV cache pressure (llama.cpp /metrics; -1 = not exposed)
            var kv = e.kv_cache_usage_ratio;
            if (typeof kv === 'number' && kv >= 0) {
                var kvPct = Math.round(kv * 100);
                var kvBar = el('span', 'mn-kv');
                var kvFill = el('i', kvPct > 95 ? 'crit' : kvPct > 80 ? 'warn' : '');
                kvFill.style.width = Math.min(100, kvPct) + '%';
                kvBar.appendChild(kvFill);
                right.appendChild(el('span', 'mn-alabel', 'kv ' + kvPct + '%'));
                right.appendChild(kvBar);
            }
            var conns = e.tcp_connections || 0;
            right.appendChild(el('span', 'mn-alabel' + (conns ? ' on' : ''), conns + ' conn'));
            if (busy) right.appendChild(el('span', 'mn-alabel on', e.requests_processing + ' req'));

            // The rolling counter: total tokens generated by this engine.
            var tokens = e.tokens_predicted_total;
            if (typeof tokens === 'number' && tokens > 0) {
                var tokKey = node.nickname + '/' + engineLabel(e) + '/tokens';
                var counter = el('span', 'mn-tokens');
                tween(tokKey, tokens, counter, function (v) {
                    return Math.floor(v).toLocaleString('en-US') + ' tok';
                });
                right.appendChild(counter);
                // Observed completion throughput, Monitor-only (the
                // Dashboard is inventory). Fades out ~30s after the last
                // finished request; >10k t/s would be a page-load artifact.
                if (PAGE === 'monitor') {
                    var tps = Math.round(observedRate(tokKey, tokens));
                    if (tps > 0 && tps < 10000) {
                        right.appendChild(el('span', 'mn-rate', '~' + tps + ' t/s'));
                    }
                }
            }
            row.appendChild(right);
            host.appendChild(row);

            // Loaded models with their VRAM, under the engine row.
            (Array.isArray(e.models) ? e.models : []).forEach(function (m) {
                if (!m || !m.name) return;
                var mr = el('div', 'mn-row model');
                mr.appendChild(el('span', 'nm dim', m.name));
                mr.appendChild(el('span', 'meta',
                    typeof m.size_vram === 'number' && m.size_vram > 0 ? fmtGB(m.size_vram) + ' GB' : ''));
                host.appendChild(mr);
            });
        });
        if (!shown) host.appendChild(el('div', 'mn-more', 'no engine serving on this node'));
        return host;
    }

    function powerCell(node) {
        var s = node.snapshot || {};
        var wrap = el('div');
        wrap.appendChild(el('div', 'mn-klabel', 'Power'));
        var total = s.power_total_watts;
        var kpi = el('div', 'mn-kpi');
        if (typeof total === 'number' && total >= 0) {
            var span = el('span');
            tween(node.nickname + '/power', total, span, function (v) { return v.toFixed(1); });
            kpi.appendChild(span);
            var small = el('small');
            small.textContent = 'W';
            kpi.appendChild(small);
        } else {
            kpi.textContent = '—';
        }
        wrap.appendChild(kpi);
        var parts = [];
        [['gpu', s.power_gpu_watts], ['cpu', s.power_cpu_watts],
         ['ane', s.power_ane_watts], ['dram', s.power_dram_watts]].forEach(function (p) {
            if (typeof p[1] === 'number' && p[1] >= 0) parts.push(p[0] + ' ' + p[1].toFixed(1));
        });
        wrap.appendChild(el('div', 'mn-line', parts.length ? parts.join(' · ') + ' W' : ''));
        return wrap;
    }

    function systemLine(node) {
        var s = node.snapshot || {};
        var line = el('div', 'mn-line sys');
        var loads = [s.cpu_load_1, s.cpu_load_5, s.cpu_load_15].map(function (v) {
            return typeof v === 'number' ? v.toFixed(1) : '—';
        });
        var bits = ['load ' + loads.join(' / ')];
        bits.push('pressure ' + (s.mem_pressure || '—'));
        var thermal = 'thermal ' + (s.thermal_level || '—');
        if (typeof s.thermal_speed_limit === 'number' && s.thermal_speed_limit >= 0
            && s.thermal_speed_limit < 100) {
            thermal += ' (limit ' + s.thermal_speed_limit + '%)';
        }
        bits.push(thermal);
        var gpuMem = typeof s.gpu_mem_in_use === 'number' && s.gpu_mem_in_use > 0
            ? fmtGB(s.gpu_mem_in_use) + ' GB gpu wired' : null;
        if (gpuMem) bits.push(gpuMem);
        line.textContent = bits.join(' · ');
        return line;
    }

    function monitorBlock(node) {
        var block = el('div', 'mn-node' + (node.ok ? '' : ' stale'));
        block.appendChild(nodeHead(node));
        var s = node.snapshot || {};
        var stats = el('div', 'mn-stats');
        stats.appendChild(sparkCell(node.nickname, 'cpu', 'CPU'));
        stats.appendChild(sparkCell(node.nickname, 'gpu', 'GPU'));
        block.appendChild(stats);
        var stats2 = el('div', 'mn-stats');
        stats2.appendChild(memCell(s));
        stats2.appendChild(powerCell(node));
        block.appendChild(stats2);
        block.appendChild(systemLine(node));
        block.appendChild(activityRows(node));
        block.appendChild(manageLink(node));
        return block;
    }

    function renderGrid() {
        var host = document.getElementById('mn-grid');
        if (!host) return;
        host.textContent = '';

        if (state.localOnly) {
            if (!state.localSnap) { host.appendChild(el('div', 'mn-empty', 'Loading local snapshot…')); return; }
            var pseudo = {
                nickname: 'this host',
                ok: true,
                reached_at: state.localSnap.at,
                snapshot: state.localSnap.data,
            };
            host.appendChild(PAGE === 'monitor' ? monitorBlock(pseudo) : dashboardBlock(pseudo));
            var hint = el('div', 'mn-empty');
            hint.appendChild(document.createTextNode('No fleet configured — run '));
            var code = el('code', null, 'asiai fleet add <nickname> --url <asiai_url>');
            hint.appendChild(code);
            hint.appendChild(document.createTextNode(' to watch more nodes here.'));
            host.appendChild(hint);
            return;
        }

        if (!state.fleet) { host.appendChild(el('div', 'mn-empty', 'Polling fleet…')); return; }
        var visible = visibleNodes();
        if (!visible.length) {
            host.appendChild(el('div', 'mn-empty', 'All nodes unchecked — pick at least one chip above.'));
            return;
        }
        visible.forEach(function (n) {
            host.appendChild(PAGE === 'monitor' ? monitorBlock(n) : dashboardBlock(n));
        });
    }

    function renderAll() {
        renderRibbon();
        renderChips();
        renderGrid();
    }

    renderAll();
    poll();
    setInterval(poll, POLL_MS);
})();
