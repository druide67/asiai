/* asiai — Fleet cockpit (master-detail + operator write actions).
 *
 * Same-origin only: every fetch targets the dashboard's own origin (CSP
 * connect-src 'self'); the node Bearer token never reaches this file — the
 * server-side proxy at POST /fleet/{nickname}/action holds it.
 *
 * SECURITY: all data-driven rendering goes through createElement/textContent.
 * Nicknames, engine names, model names and error strings come from remote
 * nodes and must never be interpolated into innerHTML.
 */

(function () {
    'use strict';

    var REFRESH_MS = 10000;
    var TOAST_MS = 5200;
    var MAX_TOASTS = 3;
    var OPTIMISTIC_MS = 30000;
    var DESTRUCTIVE = { purge: true, install: true, uninstall: true, upgrade: true };

    var state = {
        page: (document.getElementById('fl-root') || {}).dataset
            ? document.getElementById('fl-root').dataset.flPage || 'fleet'
            : 'fleet',
        snapshot: null,
        selected: null,
        session: { authenticated: false, csrf: null, expiresAt: null },
        pending: {},   // "nick/engine" -> command in flight (renders LOADING)
        fresh: {},     // "nick/engine" -> {assume, expires} post-action optimistic state
        menuOpen: null,
        auditEvents: null,
        auditFilter: { actor: 'all', window: 'all' },
        refreshTimer: null,
        lastPollOk: null,   // Date.now() of the last successful snapshot fetch
    };

    // A cockpit must never present dead data as live: past this age the
    // banner degrades to an explicit staleness warning.
    var STALE_MS = 30000;

    // ── tiny DOM builder ────────────────────────────────────────

    function el(tag, opts, children) {
        var node = document.createElement(tag);
        opts = opts || {};
        if (opts.cls) node.className = opts.cls;
        if (opts.text !== undefined) node.textContent = opts.text;
        if (opts.title) node.title = opts.title;
        if (opts.type) node.type = opts.type;
        if (opts.attrs) {
            Object.keys(opts.attrs).forEach(function (k) { node.setAttribute(k, opts.attrs[k]); });
        }
        if (opts.on) {
            Object.keys(opts.on).forEach(function (evt) { node.addEventListener(evt, opts.on[evt]); });
        }
        (children || []).forEach(function (c) { if (c) node.appendChild(c); });
        return node;
    }

    function lockIcon(w, h) {
        var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('width', w || 9);
        svg.setAttribute('height', h || 11);
        svg.setAttribute('viewBox', '0 0 10 12');
        svg.setAttribute('fill', 'none');
        var rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('y', '5'); rect.setAttribute('width', '10'); rect.setAttribute('height', '7');
        rect.setAttribute('rx', '1.5'); rect.setAttribute('fill', 'currentColor');
        var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', 'M2.5 5V3.5a2.5 2.5 0 0 1 5 0V5');
        path.setAttribute('stroke', 'currentColor'); path.setAttribute('stroke-width', '1.4');
        path.setAttribute('fill', 'none');
        svg.appendChild(rect); svg.appendChild(path);
        var span = el('span', { cls: 'fl-lock' });
        span.appendChild(svg);
        return span;
    }

    function clockIcon() {
        var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('width', '13'); svg.setAttribute('height', '13'); svg.setAttribute('viewBox', '0 0 14 14');
        svg.setAttribute('fill', 'none');
        var c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        c.setAttribute('cx', '7'); c.setAttribute('cy', '7'); c.setAttribute('r', '5.6');
        c.setAttribute('stroke', 'currentColor'); c.setAttribute('stroke-width', '1.3');
        var p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        p.setAttribute('d', 'M7 4.2V7l2 1.4');
        p.setAttribute('stroke', 'currentColor'); p.setAttribute('stroke-width', '1.3');
        p.setAttribute('stroke-linecap', 'round');
        svg.appendChild(c); svg.appendChild(p);
        return svg;
    }

    // ── formatting ──────────────────────────────────────────────

    function gb(bytes) { return bytes > 0 ? bytes / 1073741824 : 0; }

    function fmtGB(bytes, digits) {
        var v = gb(bytes);
        return v.toFixed(digits === undefined ? 1 : digits);
    }

    function fmtCtx(n) {
        if (!n || n <= 0) return '';
        if (n >= 1024) return Math.round(n / 1024) + 'K';
        return String(n);
    }

    function portOf(url) {
        var m = /:(\d+)(\/|$)/.exec(url || '');
        return m ? m[1] : null;
    }

    function timeHMS(ts) {
        return new Date(ts * 1000).toTimeString().slice(0, 8);
    }

    function timeWithDate(ts) {
        // Drawer entries can span weeks: prefix a short date for anything
        // that is not from today (client clock, like the rest of the UI).
        var d = new Date(ts * 1000);
        var hm = d.toTimeString().slice(0, 5);
        if (d.toDateString() === new Date().toDateString()) return d.toTimeString().slice(0, 8);
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' ' + hm;
    }

    function sessionLeft() {
        if (!state.session.expiresAt) return '';
        var mins = Math.max(0, Math.floor((state.session.expiresAt * 1000 - Date.now()) / 60000));
        var h = Math.floor(mins / 60);
        var mm = String(mins % 60).padStart(2, '0');
        return h + ' h ' + mm + ' min left';
    }

    // ── engine state mapping ────────────────────────────────────
    //
    // The fleet snapshot exposes reachable/models per engine, not the rich
    // EngineState of aisrv (unhealthy/disabled/not_installed stay dormant
    // until the snapshot carries them). LOADING is the optimistic state
    // while an action is in flight or just confirmed.

    function engineKey(nick, engineName) { return nick + '/' + engineName; }

    var LIVE_STATES = { running: true, unhealthy: true, degraded: true, loading: true };

    function snapshotStateOf(engine, nodeOk) {
        if (!nodeOk) return 'stopped';
        // Rich lifecycle state from an aisctl-serve-equipped node; fall back
        // to the reachable/unreachable split for nodes that don't report it.
        if (typeof engine.state === 'string' && BADGE_LABEL[engine.state]) {
            if (!LIVE_STATES[engine.state] && engine.reachable) {
                // launchd says stopped/not_installed but the API answers:
                // the engine serves OUTSIDE launchd (a desktop app, a hand-
                // launched server). Observed reality wins over paper state.
                return 'running';
            }
            return engine.state;
        }
        return engine.reachable ? 'running' : 'stopped';
    }

    function engineStateOf(nick, engine, nodeOk) {
        // Same key the card and runAction use (the manifest name when
        // known), or the optimistic LOADING would miss homonymous cards.
        var key = engineKey(nick, engineLabel(engine));
        if (state.pending[key]) return 'loading';
        var fresh = state.fresh[key];
        if (fresh) {
            if (Date.now() > fresh.expires) {
                delete state.fresh[key];
            } else {
                var snapState = snapshotStateOf(engine, nodeOk);
                if (snapState === fresh.assume) {
                    delete state.fresh[key];  // snapshot caught up
                } else {
                    return fresh.assume;
                }
            }
        }
        return snapshotStateOf(engine, nodeOk);
    }

    var BADGE_LABEL = {
        running: 'RUNNING', unhealthy: 'UNHEALTHY', loading: 'LOADING',
        stopped: 'STOPPED', disabled: 'STANDBY', not_installed: 'NOT INSTALLED',
        degraded: 'DEGRADED', loaded: 'LOADED', available: 'AVAILABLE',
    };

    function engineLabel(engine) {
        // Manifest name when the node reports one (aisctl serve): it
        // distinguishes the N homonymous "llamacpp" detection entries.
        return engine.engine_id || engine.name;
    }

    function engineActionTarget(engine) {
        // The write funnel validates against MANIFEST names: acting on a
        // detection alias ("llamacpp") would command the base-manifest
        // engine, not the aux instance this card displays.
        return engine.engine_id || engine.name;
    }

    var RAM_PALETTE = ['#06b6d4', '#3b82f6', '#8b5cf6', '#a855f7', '#ec4899', '#22d3ee', '#818cf8'];

    // ── session ─────────────────────────────────────────────────

    function refreshSession() {
        return fetch('/api/v1/operator/session')
            .then(function (r) { return r.json(); })
            .then(function (info) {
                var was = state.session.authenticated;
                state.session.authenticated = !!info.authenticated;
                state.session.csrf = info.csrf_token || null;
                state.session.expiresAt = info.expires_at || null;
                if (was !== state.session.authenticated) renderAll();
                else renderSessionFooter();
            })
            .catch(function () { /* transient — keep last known session state */ });
    }

    function submitLogin(code, modal) {
        var body = new URLSearchParams();
        body.set('code', code);
        return fetch('/login', { method: 'POST', body: body })
            .then(function (r) {
                if (r.redirected || r.ok) {
                    closeOverlay();
                    return refreshSession().then(function () {
                        toast('ok', 'Operator session opened', 'all write actions unlocked');
                        if (state.page === 'journal') loadJournalPage();
                        else renderAll();
                    });
                }
                if (r.status === 429) {
                    return r.json().then(function (b) {
                        loginModalError(modal, 'Rate limited — retry in ' + Math.ceil(b.retry_after || 60) + ' s.');
                    });
                }
                loginModalError(modal, 'Invalid or expired code — codes live 60 s. Run asiai auth login again.');
            })
            .catch(function () {
                loginModalError(modal, 'Network error — is the dashboard still reachable?');
            });
    }

    function doLogout() {
        fetch('/logout', { method: 'POST' })
            .then(function () {
                return refreshSession();
            })
            .then(function () {
                toast('info', 'Session closed', 'dashboard back to read-only');
                renderAll();
            })
            .catch(function () { /* ignored: next session refresh reconciles */ });
    }

    // ── snapshot ────────────────────────────────────────────────

    function refreshSnapshot() {
        return fetch('/api/v1/fleet/snapshot')
            .then(function (r) {
                if (!r.ok) throw new Error('snapshot http ' + r.status);
                return r.json();
            })
            .then(function (snap) {
                state.snapshot = snap;
                state.lastPollOk = Date.now();
                var nicknames = (snap.nodes || []).map(function (n) { return n.nickname; });
                // Re-sync a stale selection so the master highlight and the
                // detail panel never silently diverge.
                if (nicknames.length && nicknames.indexOf(state.selected) === -1) {
                    state.selected = nicknames[0];
                }
                renderAll();
            })
            .catch(function () {
                // Keep the last snapshot but re-render: past STALE_MS the
                // banner must degrade instead of claiming "nominal" forever.
                renderAll();
            });
    }

    function snapshotIsStale() {
        return state.lastPollOk !== null && Date.now() - state.lastPollOk > STALE_MS;
    }

    function selectedNode() {
        if (!state.snapshot || !state.snapshot.nodes) return null;
        for (var i = 0; i < state.snapshot.nodes.length; i++) {
            if (state.snapshot.nodes[i].nickname === state.selected) return state.snapshot.nodes[i];
        }
        return state.snapshot.nodes[0] || null;
    }

    function enginesOf(node) {
        if (!node || !node.ok || !node.snapshot) return [];
        var engines = node.snapshot.engines_status;
        if (!Array.isArray(engines)) return [];
        // A node could ship a malformed entry; one bad element must not
        // throw mid-render and freeze the whole cockpit.
        return engines.filter(function (e) {
            return e && typeof e === 'object' && typeof e.name === 'string';
        });
    }

    // ── actions (the write funnel) ──────────────────────────────

    function postAction(nick, command, args, confirmValue) {
        var payload = { command: command, args: args || {} };
        if (confirmValue !== undefined) payload.confirm = confirmValue;
        return fetch('/fleet/' + encodeURIComponent(nick) + '/action', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': state.session.csrf || '',
            },
            body: JSON.stringify(payload),
        });
    }

    var LONG_COMMANDS = { install: true, upgrade: true, load: true };

    function runAction(nick, engineName, command, extraArgs, confirmValue) {
        var key = engineKey(nick, engineName || command);
        if (state.pending[key]) return;  // double-submit guard
        var args = {};
        if (engineName) args.engine = engineName;
        if (extraArgs) Object.keys(extraArgs).forEach(function (k) { args[k] = extraArgs[k]; });

        state.pending[key] = command;
        renderAll();
        var progressSub = LONG_COMMANDS[command]
            ? 'forwarding to ' + nick + ' · may take several minutes'
            : 'forwarding to ' + nick;
        var progress = toast('progress', titleFor(command, engineName, nick) + '…', progressSub);

        postAction(nick, command, args, confirmValue)
            .then(function (r) {
                return r.json().catch(function () { return {}; }).then(function (body) {
                    return { status: r.status, headers: r.headers, body: body };
                });
            })
            .then(function (res) {
                delete state.pending[key];
                dismissToast(progress);
                if (res.status < 400) {
                    onActionSuccess(nick, engineName, command, res.body);
                } else {
                    onActionError(nick, engineName, command, res);
                }
                renderAll();
                setTimeout(refreshSnapshot, 2000);
                setTimeout(refreshSnapshot, 12000);
            })
            .catch(function () {
                delete state.pending[key];
                dismissToast(progress);
                toast('err', 'Network error — ' + command, 'action may still be running · see journal');
                renderAll();
            });
    }

    function titleFor(command, engineName, nick) {
        var verb = command.charAt(0).toUpperCase() + command.slice(1);
        return engineName ? verb + ' ' + engineName : verb + ' ' + nick;
    }

    function onActionSuccess(nick, engineName, command, body) {
        var key = engineKey(nick, engineName || command);
        var secs = body && body.duration_ms ? (body.duration_ms / 1000).toFixed(1) + ' s' : '';
        var assume = null;
        if (command === 'stop' || command === 'uninstall') assume = 'stopped';
        // unload keeps the engine RUNNING (only the model is dropped)
        if (command === 'start' || command === 'restart' || command === 'load' || command === 'unload') {
            assume = 'running';
        }
        if (assume) state.fresh[key] = { assume: assume, expires: Date.now() + OPTIMISTIC_MS };

        var subs = {
            stop: 'stopped on ' + nick + (secs ? ' · ' + secs : ''),
            start: 'serving on ' + nick + (secs ? ' · ' + secs : ''),
            restart: 'restart completed' + (secs ? ' in ' + secs : ''),
            unload: 'model unloaded on ' + nick,
            load: 'model loaded on ' + nick,
            purge: 'memory purged on ' + nick + (secs ? ' · ' + secs : ''),
            install: 'installed on ' + nick,
            uninstall: 'removed from ' + nick,
            upgrade: 'upgraded on ' + nick + (secs ? ' · ' + secs : ''),
        };
        toast('ok', titleFor(command, engineName, nick), subs[command] || ('done · ' + nick));
    }

    function onActionError(nick, engineName, command, res) {
        var err = (res.body && res.body.error) || ('http_' + res.status);
        var detail = (res.body && res.body.detail) || '';
        if (res.status === 401) {
            openLoginModal();
            return;
        }
        if (res.status === 403) {
            refreshSession();
            toast('err', 'Session check failed', 'CSRF invalid or session expired — retry after login');
            return;
        }
        var known = {
            unknown_node: 'node is not in this hub’s fleet registry',
            node_not_writable: 'no auth token for this node — add one with asiai fleet add',
            confirmation_required: 'typed confirmation required for destructive commands',
            bad_payload: detail || 'request rejected by validation',
            rate_limited: 'retry in ' + (res.headers.get('Retry-After') || '60') + ' s',
            forwards_busy: 'all forward slots busy — retry shortly',
            node_unreachable: 'node edge did not answer',
            node_protocol_error: 'node answered garbage — check its asiai_url',
            node_timeout: 'node timed out — the command may still finish · see journal',
            aisctl_serve_unavailable: 'aisctl serve is not running on the node',
        };
        toast('err', titleFor(command, engineName, nick) + ' failed', known[err] || (err + (detail ? ' · ' + detail : '')));
    }

    // ── graduated confirmation (1g) + UMA advisory (1f) ─────────

    function confirmAction(node, engine, command) {
        if (!state.session.authenticated) { openLoginModal(); return; }
        var nick = node.nickname;
        var engineName = engine ? engineActionTarget(engine) : null;

        if (DESTRUCTIVE[command]) {
            openTypeToConfirm(nick, engineName, command, node);
            return;
        }
        openSimpleConfirm(nick, engineName, command, node, engine);
    }

    function openSimpleConfirm(nick, engineName, command, node, engine) {
        var conns = engine ? engine.tcp_connections || 0 : 0;
        var procs = engine ? engine.requests_processing || 0 : 0;
        var freed = engine && engine.vram_total > 0 ? fmtGB(engine.vram_total) + ' GB' : null;

        var bodyText = '';
        if (command === 'stop') {
            bodyText = conns > 0
                ? ''
                : 'No active connections.' + (freed ? ' Frees ' + freed + ' on ' + nick + '.' : '');
        } else if (command === 'restart') {
            bodyText = conns > 0 ? '' : 'No active connections. Expected downtime a few seconds.';
        } else if (command === 'start') {
            bodyText = '';
        } else if (command === 'unload') {
            bodyText = 'Unloads the model' + (freed ? ' and frees ' + freed : '') + ' — the engine keeps running.';
        }

        var children = [
            el('h3', { cls: 'fl-modal-title', text: titleFor(command, engineName, nick) + '?' }),
            el('div', { cls: 'fl-modal-sub', text: nick }),
        ];
        if (bodyText) children.push(el('div', { cls: 'fl-modal-body', text: bodyText }));

        if (conns > 0 && (command === 'stop' || command === 'restart')) {
            children.push(el('div', { cls: 'fl-blast' }, [
                el('div', {
                    cls: 'fl-blast-title',
                    text: command === 'restart' ? 'Restart will drop live traffic' : 'This engine is serving traffic',
                }),
                el('div', { cls: 'fl-blast-figures' }, [
                    el('span', {}, [el('b', { text: String(conns) }), el('span', { cls: 'dim', text: ' active conn' })]),
                    el('span', {}, [el('b', { text: String(procs) }), el('span', { cls: 'dim', text: ' requests processing' })]),
                ]),
                el('div', { cls: 'fl-blast-note', text: 'In-flight requests will fail. Clients will see connection resets.' }),
            ]));
        }

        if (command === 'start') children.push(buildUmaAdvisory(node, engine));

        var confirmVariant = command === 'start' ? 'primary'
            : command === 'restart' ? 'accent'
            : command === 'stop' ? (conns > 0 ? 'danger' : 'ghost')
            : 'ghost';
        var confirmLabel = command.charAt(0).toUpperCase() + command.slice(1);

        children.push(el('div', { cls: 'fl-modal-footer' }, [
            el('button', { cls: 'fl-modal-cancel', text: 'Cancel', on: { click: closeOverlay } }),
            el('button', {
                cls: 'fl-btn ' + confirmVariant,
                text: confirmLabel,
                on: {
                    click: function () {
                        closeOverlay();
                        runAction(nick, engineName, command);
                    },
                },
            }),
        ]));

        openModal(children);
    }

    function openTypeToConfirm(nick, engineName, command, node) {
        // Destructive verbs: the typed nickname is re-verified SERVER-side
        // (command_spec DESTRUCTIVE_COMMANDS) — this dialog cannot be relaxed.
        var input = el('input', {
            cls: 'fl-input danger-focus',
            type: 'text',
            attrs: { placeholder: nick, autocomplete: 'off', spellcheck: 'false' },
        });
        var confirmBtn = el('button', {
            cls: 'fl-btn danger',
            text: titleFor(command, engineName, nick),
            attrs: { disabled: 'disabled' },
            on: {
                click: function () {
                    if (input.value.trim() !== nick) return;
                    closeOverlay();
                    runAction(nick, engineName, command, null, nick);
                },
            },
        });
        input.addEventListener('input', function () {
            if (input.value.trim() === nick) confirmBtn.removeAttribute('disabled');
            else confirmBtn.setAttribute('disabled', 'disabled');
        });
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && input.value.trim() === nick) confirmBtn.click();
        });

        var scope = {
            purge: 'Purges inference memory on the whole node — every engine drops its caches.',
            uninstall: 'Removes the engine and its LaunchDaemon from ' + nick + '. The model files stay in the shared cache.',
            upgrade: 'Upgrades the engine package on ' + nick + '. The engine restarts on the new version.',
            install: 'Installs the engine and its LaunchDaemon on ' + nick + '.',
        };

        var children = [
            el('h3', { cls: 'fl-modal-title danger', text: titleFor(command, engineName, nick) + '?' }),
            el('div', { cls: 'fl-modal-sub', text: nick }),
            el('div', { cls: 'fl-modal-body', text: scope[command] || 'This action is destructive and is never auto-reverted.' }),
            el('div', { cls: 'fl-confirm-label' }, [
                document.createTextNode('Type '),
                el('code', { text: nick }),
                document.createTextNode(' to confirm'),
            ]),
            input,
            el('div', { cls: 'fl-modal-footer' }, [
                el('button', { cls: 'fl-modal-cancel', text: 'Cancel', on: { click: closeOverlay } }),
                confirmBtn,
            ]),
        ];
        if (command === 'install') children.splice(3, 0, buildUmaAdvisory(node, null));
        openModal(children);
        input.focus();
    }

    function buildUmaAdvisory(node, engine) {
        // Memory-plan advisory shell: real node memory now + the 8 GB floor
        // marker. The computed verdict (weights + KV projection) needs a
        // server-side planner that does not exist yet — until it ships this
        // block informs, never blocks.
        var snap = node.snapshot || {};
        var total = gb(snap.mem_total || 0);
        var used = gb(snap.mem_used || 0);
        var wrap = el('div', {});
        if (total <= 0) return wrap;

        var usedPct = Math.min(100, (used / total) * 100);
        var floorPct = Math.max(0, ((total - 8) / total) * 100);

        wrap.appendChild(el('div', { cls: 'fl-plan-rows' }, [
            el('div', { cls: 'fl-plan-row' }, [
                el('span', { cls: 'k', text: 'Unified RAM in use now' }),
                el('span', { cls: 'v', text: used.toFixed(1) + ' / ' + total.toFixed(0) + ' GB' }),
            ]),
            el('div', { cls: 'fl-plan-row' }, [
                el('span', { cls: 'k' }, [
                    document.createTextNode('System headroom now '),
                    el('span', { cls: 'paren', text: '(floor 8 GB)' }),
                ]),
                el('span', { cls: 'v', text: Math.max(0, total - used).toFixed(1) + ' GB' }),
            ]),
        ]));

        var bar = el('div', { cls: 'fl-plan-bar' });
        var track = el('div', { cls: 'fl-plan-track' });
        var usedSeg = el('span', { cls: 'fl-plan-used', title: 'in use · ' + used.toFixed(1) + ' GB' });
        usedSeg.style.width = usedPct + '%';
        track.appendChild(usedSeg);
        bar.appendChild(track);
        var floor = el('div', { cls: 'fl-plan-floor' });
        floor.style.left = floorPct + '%';
        bar.appendChild(floor);
        bar.appendChild(el('div', { cls: 'fl-plan-legend' }, [
            el('span', { text: '▪ in use' }),
            el('span', { text: '┆ 8 GB floor' }),
        ]));
        wrap.appendChild(bar);

        wrap.appendChild(el('div', { cls: 'fl-plan-verdict advisory' }, [
            el('span', { cls: 'fl-plan-badge advisory', text: 'ADVISORY' }),
            el('p', { text: 'The UMA guard (memory plan with projected footprint) computes server-side in a later release. Current usage is shown for reference — starting is not blocked.' }),
        ]));
        return wrap;
    }

    // ── login modal (1h) ────────────────────────────────────────

    function openLoginModal() {
        var input = el('input', {
            cls: 'fl-input',
            type: 'password',
            attrs: { placeholder: 'aop_…', autocomplete: 'off' },
        });
        var errorSlot = el('div', {});
        var modal;

        function submit() {
            var code = input.value.trim();
            if (!code) return;
            submitLogin(code, { input: input, errorSlot: errorSlot });
        }
        input.addEventListener('keydown', function (e) { if (e.key === 'Enter') submit(); });

        modal = openModal([
            el('div', { cls: 'fl-login-header' }, [
                el('span', { cls: 'fl-login-icon' }, [lockIcon(12, 14)]),
                el('div', {}, [
                    el('h3', { cls: 'fl-modal-title', text: 'Operator session required' }),
                    el('div', { cls: 'fl-login-sub', text: 'Write actions are bootstrapped from your shell.' }),
                ]),
            ]),
            el('div', { cls: 'fl-terminal' }, [
                el('div', {}, [
                    el('span', { cls: 'prompt', text: '$ ' }),
                    el('span', { cls: 'cmd', text: 'asiai auth login' }),
                ]),
                el('div', { cls: 'hint', text: '→ one-time code · valid 60 s · single use' }),
                el('div', { cls: 'code', text: 'aop_…' }),
            ]),
            el('div', { cls: 'fl-confirm-label', text: 'Paste code' }),
            input,
            errorSlot,
            el('div', { cls: 'fl-modal-footer' }, [
                el('button', { cls: 'fl-modal-cancel', text: 'Cancel', on: { click: closeOverlay } }),
                el('button', { cls: 'fl-btn primary', text: 'Open session', on: { click: submit } }),
            ]),
            el('div', { cls: 'fl-footnote', text: 'HttpOnly cookie · SameSite=Lax · failed attempts rate-limited' }),
        ]);
        input.focus();
        return modal;
    }

    function loginModalError(modal, message) {
        if (!modal || !modal.errorSlot) return;
        modal.errorSlot.textContent = '';
        modal.errorSlot.appendChild(el('div', { cls: 'fl-form-error', text: message }));
        if (modal.input) modal.input.classList.add('error');
    }

    // ── modal/overlay plumbing ──────────────────────────────────

    function overlayHost() { return document.getElementById('fl-overlays'); }

    var _restoreFocus = null;

    function closeOverlay() {
        var host = overlayHost();
        if (host) host.textContent = '';
        document.removeEventListener('keydown', escListener);
        document.removeEventListener('keydown', trapListener);
        if (_restoreFocus && document.contains(_restoreFocus)) _restoreFocus.focus();
        _restoreFocus = null;
    }

    function escListener(e) { if (e.key === 'Escape') closeOverlay(); }

    function _focusables(container) {
        return container.querySelectorAll(
            'button:not([disabled]), input:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])'
        );
    }

    // aria-modal promises containment: cycle Tab inside the open overlay so
    // the keyboard cannot reach (and activate) the action buttons behind it.
    function trapListener(e) {
        if (e.key !== 'Tab') return;
        var host = overlayHost();
        if (!host || !host.firstChild) return;
        var items = _focusables(host);
        if (!items.length) return;
        var first = items[0];
        var last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last.focus();
        } else if (!e.shiftKey && (document.activeElement === last || !host.contains(document.activeElement))) {
            e.preventDefault();
            first.focus();
        }
    }

    function openModal(children) {
        var host = overlayHost();
        if (!host) return null;
        host.textContent = '';
        _restoreFocus = document.activeElement;
        var card = el('div', { cls: 'fl-modal', attrs: { role: 'dialog', 'aria-modal': 'true' } }, children);
        var overlay = el('div', { cls: 'fl-modal-overlay' }, [card]);
        overlay.addEventListener('click', function (e) { if (e.target === overlay) closeOverlay(); });
        host.appendChild(overlay);
        document.addEventListener('keydown', escListener);
        document.addEventListener('keydown', trapListener);
        return { card: card };
    }

    // ── toasts ──────────────────────────────────────────────────

    function toastsHost() { return document.getElementById('fl-toasts'); }

    function toast(kind, title, sub) {
        var host = toastsHost();
        if (!host) return null;
        while (host.children.length >= MAX_TOASTS) {
            // Never evict an in-flight progress toast: it is the only trace
            // of a long-running command. Prefer the oldest finished toast.
            var victim = null;
            for (var i = 0; i < host.children.length; i++) {
                if (!host.children[i].querySelector('.fl-spinner')) { victim = host.children[i]; break; }
            }
            host.removeChild(victim || host.firstChild);
        }
        var lead = kind === 'progress'
            ? el('span', { cls: 'fl-spinner' })
            : el('span', { cls: 'fl-dot ' + (kind === 'ok' ? 'ok' : kind === 'err' ? 'err' : 'info') });
        var node = el('div', { cls: 'fl-toast' + (kind === 'err' ? ' error' : '') }, [
            el('div', { cls: 'fl-toast-row' }, [
                lead,
                el('div', {}, [
                    el('div', { cls: 'fl-toast-title', text: title }),
                    sub ? el('div', { cls: 'fl-toast-sub', text: sub }) : null,
                ]),
            ]),
        ]);
        host.appendChild(node);
        if (kind !== 'progress') setTimeout(function () { dismissToast(node); }, TOAST_MS);
        return node;
    }

    function dismissToast(node) {
        if (node && node.parentNode) node.parentNode.removeChild(node);
    }

    // ── audit journal (1i) ──────────────────────────────────────

    function fetchAudit(limit) {
        return fetch('/api/v1/fleet/audit?limit=' + (limit || 100))
            .then(function (r) {
                if (r.status === 401) return { unauthorized: true };
                if (!r.ok) return { error: true };
                return r.json();
            });
    }

    function auditTarget(ev) {
        var t = ev.nickname || '';
        var engine = ev.args && ev.args.engine ? ev.args.engine : null;
        if (engine) t += ' / ' + engine;
        if (!t && ev.event) t = 'session';
        return t || '—';
    }

    function auditNote(ev) {
        if (ev.error) return ev.error;
        if (ev.duration_ms !== undefined && ev.duration_ms !== null) return ev.duration_ms + ' ms';
        return '';
    }

    function auditEntry(ev) {
        var status = ev.status || 'ok';
        var dotCls = status === 'ok' ? 'ok' : status === 'denied' ? 'denied' : 'other';
        var verdictCls = status === 'ok' ? 'fl-verdict-ok' : 'fl-verdict-denied';
        var actorType = ev.actor_type || 'machine';
        var line2 = [
            el('span', { cls: 'fl-actor ' + actorType, text: actorType === 'machine' ? 'machine · fleet' : actorType }),
            el('span', { cls: verdictCls, text: status.toUpperCase() }),
        ];
        var note = auditNote(ev);
        if (note) line2.push(el('span', { cls: 'fl-audit-note', text: note }));

        return el('div', { cls: 'fl-audit-entry' }, [
            el('span', { cls: 'fl-audit-time', text: ev.ts ? timeWithDate(ev.ts) : '' }),
            el('span', { cls: 'fl-audit-dot ' + dotCls }),
            el('div', { cls: 'fl-audit-content' }, [
                el('div', { cls: 'fl-audit-line1' }, [
                    el('b', { text: ev.command || ev.event || 'command' }),
                    el('span', { cls: 'sep', text: ' · ' }),
                    el('span', { cls: 'target', text: auditTarget(ev) }),
                ]),
                el('div', { cls: 'fl-audit-line2' }, line2),
            ]),
        ]);
    }

    function openDrawer() {
        var host = overlayHost();
        if (!host) return;
        host.textContent = '';
        var body = el('div', { cls: 'fl-drawer-body' }, [
            el('div', { cls: 'fl-audit-empty', text: 'Loading journal…' }),
        ]);
        var backdrop = el('div', { cls: 'fl-drawer-backdrop', on: { click: closeOverlay } });
        var drawer = el('div', { cls: 'fl-drawer' }, [
            el('div', { cls: 'fl-drawer-header' }, [
                el('span', { cls: 'fl-drawer-title', text: 'Audit journal' }),
                el('span', { cls: 'fl-drawer-sub', text: 'write actions · latest' }),
                el('button', { cls: 'fl-drawer-close', text: '✕', on: { click: closeOverlay }, attrs: { 'aria-label': 'Close' } }),
            ]),
            body,
            el('div', { cls: 'fl-drawer-footer' }, [
                el('a', { text: 'Open full journal →', attrs: { href: '/journal' } }),
            ]),
        ]);
        host.appendChild(backdrop);
        host.appendChild(drawer);
        _restoreFocus = document.activeElement;
        document.addEventListener('keydown', escListener);
        document.addEventListener('keydown', trapListener);

        fetchAudit(20).then(function (data) {
            body.textContent = '';
            if (data.unauthorized) {
                body.appendChild(el('div', { cls: 'fl-audit-empty', text: 'Operator session required to read the journal.' }));
                return;
            }
            if (data.error || !Array.isArray(data.events)) {
                body.appendChild(el('div', { cls: 'fl-audit-empty', text: 'Could not load the journal.' }));
                return;
            }
            if (!data.events.length) {
                body.appendChild(el('div', { cls: 'fl-audit-empty', text: 'No write actions recorded yet.' }));
                return;
            }
            data.events.forEach(function (ev) { body.appendChild(auditEntry(ev)); });
        }).catch(function () {
            body.textContent = '';
            body.appendChild(el('div', { cls: 'fl-audit-empty', text: 'Could not load the journal.' }));
        });
    }

    // ── journal full page ───────────────────────────────────────

    function loadJournalPage() {
        state.auditEvents = null;
        renderJournalPage();
        fetchAudit(500).then(function (data) {
            state.auditEvents = data;
            renderJournalPage();
        }).catch(function () {
            // A load failure must never render as an empty journal: an
            // operator checking after an incident would read "no actions".
            state.auditEvents = { error: true };
            renderJournalPage();
        });
    }

    function renderJournalPage() {
        var root = document.getElementById('fl-journal');
        if (!root) return;
        root.textContent = '';

        if (state.auditEvents === null) {
            root.appendChild(el('div', { cls: 'fl-journal-state', text: 'Loading journal…' }));
            return;
        }
        if (state.auditEvents.unauthorized) {
            var msg = el('div', { cls: 'fl-journal-state' });
            msg.appendChild(document.createTextNode('The journal is operator-only. '));
            // Same auth path as the cockpit: contextual modal, no page bounce.
            var link = el('a', {
                text: 'Open an operator session',
                attrs: { href: '#' },
                on: {
                    click: function (e) { e.preventDefault(); openLoginModal(); },
                },
            });
            msg.appendChild(link);
            msg.appendChild(document.createTextNode(' to read it.'));
            root.appendChild(msg);
            return;
        }
        if (state.auditEvents.error || !Array.isArray(state.auditEvents.events)) {
            var errMsg = el('div', { cls: 'fl-journal-state' });
            errMsg.appendChild(document.createTextNode('Could not load the journal — the audit read failed. '));
            var retry = el('a', {
                text: 'Retry',
                attrs: { href: '#' },
                on: { click: function (e) { e.preventDefault(); loadJournalPage(); } },
            });
            errMsg.appendChild(retry);
            root.appendChild(errMsg);
            return;
        }

        var filters = el('div', { cls: 'fl-filters' });
        [['all', 'all'], ['operator', 'operator'], ['machine', 'machine'], ['denied only', 'denied']].forEach(function (f) {
            filters.appendChild(el('button', {
                cls: 'fl-chip' + (state.auditFilter.actor === f[1] ? ' active' : ''),
                text: f[0],
                on: { click: function () { state.auditFilter.actor = f[1]; renderJournalPage(); } },
            }));
        });
        var spacer = el('span', {});
        spacer.style.marginLeft = 'auto';
        filters.appendChild(spacer);
        [['24 h', '24h'], ['7 d', '7d'], ['all time', 'all']].forEach(function (f) {
            filters.appendChild(el('button', {
                cls: 'fl-chip' + (state.auditFilter.window === f[1] ? ' active' : ''),
                text: f[0],
                on: { click: function () { state.auditFilter.window = f[1]; renderJournalPage(); } },
            }));
        });
        root.appendChild(filters);

        var events = state.auditEvents.events || [];
        var now = Date.now() / 1000;
        var horizon = state.auditFilter.window === '24h' ? now - 86400
            : state.auditFilter.window === '7d' ? now - 7 * 86400 : 0;
        var shown = events.filter(function (ev) {
            if (horizon && (!ev.ts || ev.ts < horizon)) return false;
            if (state.auditFilter.actor === 'denied') return ev.status && ev.status !== 'ok';
            if (state.auditFilter.actor !== 'all') return (ev.actor_type || '') === state.auditFilter.actor;
            return true;
        });

        if (!shown.length) {
            root.appendChild(el('div', { cls: 'fl-journal-state', text: 'No entries match these filters.' }));
            return;
        }

        if (events.length >= 500) {
            root.appendChild(el('div', {
                cls: 'fl-day-label',
                text: 'Showing the last 500 events — older entries live in the JSONL file on the node',
            }));
        }

        var byDay = {};
        var dayOrder = [];
        shown.forEach(function (ev) {
            var d = ev.ts ? new Date(ev.ts * 1000) : new Date(0);
            var key = d.toDateString();
            if (!byDay[key]) { byDay[key] = []; dayOrder.push({ key: key, date: d }); }
            byDay[key].push(ev);
        });

        var today = new Date().toDateString();
        var yesterday = new Date(Date.now() - 86400000).toDateString();

        dayOrder.forEach(function (day) {
            var human = day.date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            var label = day.key === today ? 'Today — ' + human
                : day.key === yesterday ? 'Yesterday — ' + human
                : day.date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
            root.appendChild(el('div', { cls: 'fl-day-label', text: label }));
            var table = el('div', { cls: 'fl-journal-table' });
            byDay[day.key].forEach(function (ev) {
                var status = ev.status || 'ok';
                var actorType = ev.actor_type || 'machine';
                var row = el('div', { cls: 'fl-journal-row' }, [
                    el('span', { cls: 'time', text: ev.ts ? timeHMS(ev.ts) : '' }),  // day label carries the date
                    el('span', { cls: 'actor' }, [
                        el('span', { cls: 'fl-actor ' + actorType, text: actorType === 'machine' ? 'machine · fleet' : actorType }),
                    ]),
                    el('span', { cls: 'action', text: ev.command || ev.event || 'command' }),
                    el('span', { cls: 'target', text: auditTarget(ev) }),
                ]);
                var note = auditNote(ev);
                if (note) row.appendChild(el('span', { cls: 'note', text: note }));
                row.appendChild(el('span', { cls: 'verdict' }, [
                    el('span', {
                        cls: status === 'ok' ? 'fl-verdict-ok' : 'fl-verdict-denied',
                        text: status.toUpperCase(),
                    }),
                ]));
                table.appendChild(row);
            });
            root.appendChild(table);
        });
    }

    // ── master column rendering ─────────────────────────────────

    function nodeHealth(node) {
        if (!node.ok) return 'down';
        var engines = enginesOf(node);
        for (var i = 0; i < engines.length; i++) {
            var st = engineStateOf(node.nickname, engines[i], true);
            if (st === 'unhealthy' || st === 'degraded') return 'warn';
        }
        return 'ok';
    }

    function ramSegments(node, height) {
        var engines = enginesOf(node);
        var snap = node.snapshot || {};
        var total = snap.mem_total || 0;
        var bar = el('div', { cls: 'fl-rambar' + (height === 'lg' ? ' lg' : '') });
        if (total <= 0) return { bar: bar, legend: [] };

        var legend = [];
        var enginesRam = 0;
        engines.forEach(function (e) { enginesRam += e.vram_total || 0; });
        var systemRam = Math.max(0, (snap.mem_used || 0) - enginesRam);

        var sysSeg = el('span', { title: 'system · ' + fmtGB(systemRam) + ' GB' });
        sysSeg.style.width = Math.min(100, (systemRam / total) * 100) + '%';
        sysSeg.style.background = 'var(--fl-system-seg)';
        bar.appendChild(sysSeg);
        legend.push({ name: 'system', ram: systemRam, color: 'var(--fl-system-seg)' });

        var idx = 0;
        engines.forEach(function (e) {
            var ram = e.vram_total || 0;
            if (gb(ram) <= 0.05) return;
            var color = RAM_PALETTE[idx % RAM_PALETTE.length];
            idx += 1;
            var seg = el('span', { title: engineLabel(e) + ' · ' + fmtGB(ram) + ' GB' });
            seg.style.width = Math.min(100, (ram / total) * 100) + '%';
            seg.style.background = color;
            bar.appendChild(seg);
            legend.push({ name: engineLabel(e), ram: ram, color: color });
        });
        return { bar: bar, legend: legend };
    }

    function renderMaster() {
        var listHost = document.getElementById('fl-master-list');
        var subHost = document.getElementById('fl-master-sub');
        if (!listHost) return;
        listHost.textContent = '';

        var snap = state.snapshot;
        if (!snap || !snap.nodes || !snap.nodes.length) {
            if (subHost) subHost.textContent = 'no nodes polled yet';
            return;
        }

        var fleetUsed = 0, fleetTotal = 0, fleetWatts = 0, serving = 0, totalEngines = 0, haveWatts = false;
        snap.nodes.forEach(function (node) {
            var s = node.snapshot || {};
            fleetUsed += gb(s.mem_used || 0);
            fleetTotal += gb(s.mem_total || 0);
            if (typeof s.power_total_watts === 'number') { fleetWatts += s.power_total_watts; haveWatts = true; }
            enginesOf(node).forEach(function (e) {
                totalEngines += 1;
                if (engineStateOf(node.nickname, e, node.ok) === 'running') serving += 1;
            });
        });
        if (subHost) {
            var parts = [fleetUsed.toFixed(1) + ' / ' + fleetTotal.toFixed(0) + ' GB'];
            if (haveWatts) parts.push(fleetWatts.toFixed(1) + ' W');
            parts.push(serving + '/' + totalEngines + ' serving');
            subHost.textContent = parts.join(' · ');
        }

        snap.nodes.forEach(function (node) {
            var health = nodeHealth(node);
            var dot = el('span', { cls: 'fl-dot' });
            dot.style.background = health === 'down' ? 'var(--red)' : health === 'warn' ? 'var(--yellow)' : 'var(--green)';
            dot.style.boxShadow = health === 'down' ? '0 0 9px rgba(239,68,68,.5)'
                : health === 'warn' ? '0 0 9px rgba(234,179,8,.5)' : '0 0 9px rgba(34,197,94,.5)';

            var s = node.snapshot || {};
            var engines = enginesOf(node);
            var running = 0;
            var squares = [];
            engines.forEach(function (e) {
                var st = engineStateOf(node.nickname, e, node.ok);
                if (st === 'running') running += 1;
                squares.push(el('span', { cls: 'fl-sq st-' + st, title: engineLabel(e) + ' · ' + BADGE_LABEL[st].toLowerCase() }));
            });

            var row2, row3meta;
            if (node.ok && s.mem_total) {
                var segs = ramSegments(node);
                row2 = el('div', { cls: 'fl-node-row2' }, [
                    segs.bar,
                    el('span', { cls: 'fl-node-ramtxt', text: fmtGB(s.mem_used || 0) + '/' + fmtGB(s.mem_total, 0) }),
                ]);
                var metaParts = [running + '/' + engines.length + ' serving'];
                if (typeof s.power_total_watts === 'number') metaParts.push(s.power_total_watts.toFixed(1) + ' W');
                row3meta = metaParts.join(' · ');
            } else {
                row2 = el('div', { cls: 'fl-node-row2' }, [
                    el('span', { cls: 'fl-node-ramtxt', text: node.ok ? 'no snapshot' : 'unreachable' }),
                ]);
                row3meta = node.ok ? '' : (node.error_class || 'no reply');
            }

            var card = el('button', {
                cls: 'fl-node' + (node.nickname === state.selected ? ' selected' : ''),
                type: 'button',
                on: {
                    click: function () {
                        state.selected = node.nickname;
                        state.menuOpen = null;
                        renderAll();
                    },
                },
            }, [
                el('div', { cls: 'fl-node-row1' }, [
                    dot,
                    el('span', { cls: 'fl-node-name', text: node.nickname }),
                    el('span', { cls: 'fl-node-chip', text: Math.round(node.latency_ms) + ' ms' }),
                ]),
                row2,
                el('div', { cls: 'fl-node-row3' }, squares.concat([
                    el('span', { cls: 'fl-node-meta', text: row3meta }),
                ])),
            ]);
            listHost.appendChild(card);
        });
    }

    function renderSessionFooter() {
        var host = document.getElementById('fl-master-footer');
        if (!host) return;
        host.textContent = '';
        if (state.session.authenticated) {
            var dot = el('span', { cls: 'fl-dot sm' });
            dot.style.background = 'var(--green)';
            dot.style.boxShadow = '0 0 8px rgba(34,197,94,.5)';
            host.appendChild(el('div', { cls: 'fl-session-row' }, [
                dot,
                el('span', { cls: 'fl-session-label', text: 'Operator' }),
                el('span', { cls: 'fl-session-left', text: sessionLeft() }),
                el('button', { cls: 'fl-logout-btn', text: 'Log out', on: { click: doLogout } }),
            ]));
        } else {
            host.appendChild(el('button', {
                cls: 'fl-login-btn',
                on: { click: openLoginModal },
            }, [lockIcon(10, 12), el('span', { text: 'Operator login' })]));
        }
    }

    // ── banner (fleet-wide) ─────────────────────────────────────

    function renderBanner() {
        var host = document.getElementById('fl-banner');
        if (!host || !state.snapshot) return;
        host.textContent = '';

        var downNodes = [];
        var loadingKeys = Object.keys(state.pending);
        var serving = 0, nodesUp = 0;
        var sickEngines = [];
        (state.snapshot.nodes || []).forEach(function (node) {
            if (!node.ok) { downNodes.push(node.nickname); return; }
            nodesUp += 1;
            enginesOf(node).forEach(function (e) {
                var st = engineStateOf(node.nickname, e, true);
                if (st === 'running') serving += 1;
                if (st === 'unhealthy' || st === 'degraded') {
                    sickEngines.push(engineLabel(e) + ' on ' + node.nickname);
                }
            });
        });

        var variant, dotCls, title, sub;
        if (snapshotIsStale()) {
            var age = Math.round((Date.now() - state.lastPollOk) / 1000);
            variant = 'unhealthy'; dotCls = 'unhealthy';
            title = 'Fleet snapshot is stale — polling is failing';
            sub = 'last successful poll ' + age + ' s ago · data below may be dead';
            host.className = 'fl-banner ' + variant;
            host.appendChild(el('span', { cls: 'fl-dot ' + dotCls }));
            host.appendChild(el('span', { cls: 'fl-banner-title', text: title }));
            host.appendChild(el('span', { cls: 'fl-banner-sub', text: sub }));
            return;
        }
        if (downNodes.length) {
            variant = 'unhealthy'; dotCls = 'unhealthy';
            title = downNodes.length + ' node' + (downNodes.length > 1 ? 's' : '') + ' unreachable — ' + downNodes.join(', ');
            sub = 'poll failed · check the node or its asiai_url';
        } else if (sickEngines.length) {
            variant = 'unhealthy'; dotCls = 'unhealthy';
            title = sickEngines.length + ' engine' + (sickEngines.length > 1 ? 's' : '') + ' unhealthy — ' + sickEngines[0];
            sub = 'process alive · API not responding';
        } else if (loadingKeys.length) {
            variant = 'loading'; dotCls = 'loading';
            title = 'Command in flight — ' + loadingKeys[0];
            sub = 'nothing is burning';
        } else {
            variant = 'nominal'; dotCls = 'nominal';
            title = 'All systems nominal';
            sub = serving + ' engine' + (serving === 1 ? '' : 's') + ' serving · ' + nodesUp + ' node' + (nodesUp === 1 ? '' : 's') + ' up';
        }

        host.className = 'fl-banner ' + variant;
        host.appendChild(el('span', { cls: 'fl-dot ' + dotCls }));
        host.appendChild(el('span', { cls: 'fl-banner-title', text: title }));
        host.appendChild(el('span', { cls: 'fl-banner-sub', text: sub }));
    }

    // ── engine card (1c) ────────────────────────────────────────

    function actionButton(label, variant, handler) {
        var locked = !state.session.authenticated;
        var children = [];
        if (locked) children.push(lockIcon(9, 11));
        children.push(el('span', { text: label }));
        return el('button', {
            cls: 'fl-btn ' + variant + (locked ? ' locked' : ''),
            type: 'button',
            on: { click: locked ? openLoginModal : handler },
        }, children);
    }

    function menuItem(label, destructive, handler) {
        var locked = !state.session.authenticated;
        var children = [];
        if (locked) children.push(lockIcon(9, 11));
        children.push(el('span', { text: label }));
        return el('button', {
            cls: 'fl-menu-item' + (destructive ? ' destructive' : ''),
            type: 'button',
            on: {
                click: function () {
                    state.menuOpen = null;
                    renderAll();
                    if (locked) { openLoginModal(); return; }
                    handler();
                },
            },
        }, children);
    }

    function engineCard(node, engine) {
        var nick = node.nickname;
        var st = engineStateOf(nick, engine, node.ok);
        var key = engineKey(nick, engineLabel(engine));
        var models = Array.isArray(engine.models) ? engine.models : [];

        var header = el('div', { cls: 'fl-card-header' }, [
            el('span', { cls: 'fl-dot st-' + st }),
            el('span', {
                cls: 'fl-card-name',
                text: engineLabel(engine),
                title: engine.display_hint || engineLabel(engine),
            }),
            el('span', { cls: 'fl-badge st-' + st, text: BADGE_LABEL[st] }),
        ]);

        var modelLine;
        if (st === 'running' || st === 'loading' || st === 'unhealthy' || st === 'degraded') {
            if (models.length) {
                var m = models[0];
                var bits = [m.name];
                if (m.quantization) bits.push(m.quantization);
                var ctx = fmtCtx(m.context_length);
                if (ctx) bits.push('ctx ' + ctx);
                var line = bits.join(' · ');
                // Multi-model engines (ollama, LM Studio): show the count,
                // full list in the tooltip.
                var full = line;
                if (models.length > 1) {
                    line += ' · +' + (models.length - 1) + ' more';
                    full = models.map(function (x) { return x.name; }).join('\n');
                }
                modelLine = el('div', { cls: 'fl-card-model', text: line, title: full });
            } else {
                modelLine = el('div', { cls: 'fl-card-model faint', text: 'no model loaded' });
            }
        } else if (typeof engine.state === 'string') {
            // Rich lifecycle state: not serving. When the node reports what
            // the installed plist WOULD load (aisrv >= 0.8), show it.
            modelLine = engine.model
                ? el('div', { cls: 'fl-card-model faint', text: 'preset: ' + engine.model, title: engine.model })
                : el('div', { cls: 'fl-card-model empty', text: '—' });
        } else {
            modelLine = el('div', {
                cls: 'fl-card-model empty',
                text: node.ok ? 'not reachable on this poll' : '—',
            });
        }

        var card = el('div', { cls: 'fl-card st-' + st }, [header, modelLine]);

        if (st === 'loading') {
            var pendingCmd = state.pending[key] || 'command';
            card.appendChild(el('div', { cls: 'fl-progress' }, [
                el('div', { cls: 'fl-progress-track' }, [el('div', { cls: 'fl-stripe' })]),
                el('div', { cls: 'fl-progress-label', text: pendingCmd + ' in flight · waiting for the node' }),
            ]));
        }

        // Stats grid: RAM / KV / Conn / Port
        var alive = st === 'running' || st === 'unhealthy' || st === 'loading';
        var ramCell = alive && engine.vram_total > 0
            ? el('div', { cls: 'fl-cell-value', text: fmtGB(engine.vram_total) + ' GB' })
            : el('div', { cls: 'fl-cell-value off', text: alive ? '0 GB' : '—' });

        var kvCell;
        var kv = engine.kv_cache_usage_ratio;
        if (alive && typeof kv === 'number' && kv >= 0) {
            var kvPct = Math.round(kv * 100);
            var kvCls = kvPct > 95 ? 'kv-crit' : kvPct > 80 ? 'kv-warn' : 'kv-ok';
            kvCell = el('div', { cls: 'fl-cell-value ' + kvCls, text: kvPct + '%' });
        } else {
            kvCell = el('div', { cls: 'fl-cell-value off', text: '—' });
        }

        var conns = engine.tcp_connections || 0;
        var connCell = alive
            ? el('div', { cls: 'fl-cell-value' + (conns > 0 ? '' : ' off'), text: String(conns) })
            : el('div', { cls: 'fl-cell-value off', text: '—' });

        var port = portOf(engine.url);
        var portCell = el('div', { cls: 'fl-cell-value' + (port ? ' dim' : ' off'), text: port ? ':' + port : '—' });

        card.appendChild(el('div', { cls: 'fl-card-stats' }, [
            el('div', {}, [el('div', { cls: 'fl-cell-label', text: 'RAM' }), ramCell]),
            el('div', {}, [el('div', { cls: 'fl-cell-label', text: 'KV cache' }), kvCell]),
            el('div', {}, [el('div', { cls: 'fl-cell-label', text: 'Conn' }), connCell]),
            el('div', {}, [el('div', { cls: 'fl-cell-label', text: 'Port' }), portCell]),
        ]));

        // Action row — real funnel verbs only (command_spec whitelist)
        var actions = el('div', { cls: 'fl-card-actions' });
        var nodeWritable = node.ok;

        function confirmHandler(command) {
            return function () { confirmAction(node, engine, command); };
        }

        if (st === 'loading') {
            actions.appendChild(el('button', {
                cls: 'fl-btn ghost',
                text: 'Working…',
                attrs: { disabled: 'disabled' },
            }));
        } else if (!nodeWritable) {
            actions.appendChild(el('button', {
                cls: 'fl-btn ghost',
                text: 'Node unreachable',
                attrs: { disabled: 'disabled' },
            }));
        } else if (st === 'running' || st === 'unhealthy' || st === 'degraded') {
            var repair = st === 'unhealthy' || st === 'degraded';
            actions.appendChild(actionButton('Restart', repair ? 'accent' : 'ghost', confirmHandler('restart')));
            actions.appendChild(actionButton('Stop', 'ghost', confirmHandler('stop')));
        } else if (st === 'not_installed' || st === 'available') {
            // Starting an unprovisioned engine would just fail: the honest
            // verb is install (destructive → typed confirmation).
            actions.appendChild(actionButton('Install', 'accent', confirmHandler('install')));
        } else {
            actions.appendChild(actionButton('Start', 'primary', confirmHandler('start')));
        }

        // Overflow ⋯ menu
        if (st !== 'loading' && st !== 'not_installed' && nodeWritable) {
            var locked = !state.session.authenticated;
            var moreBtn = el('button', {
                cls: 'fl-more' + (state.menuOpen === key ? ' open' : '') + (locked ? ' locked' : ''),
                text: '…',
                type: 'button',
                attrs: { 'aria-label': 'More actions', 'aria-haspopup': 'true' },
                on: {
                    click: function (e) {
                        e.stopPropagation();
                        state.menuOpen = state.menuOpen === key ? null : key;
                        renderAll();
                    },
                },
            });
            actions.appendChild(moreBtn);

            if (state.menuOpen === key) {
                var menu = el('div', { cls: 'fl-menu', attrs: { role: 'menu' } });
                if ((st === 'running' || st === 'unhealthy') && models.length) {
                    menu.appendChild(menuItem('Unload model', false, function () {
                        confirmAction(node, engine, 'unload');
                    }));
                }
                menu.appendChild(menuItem('Purge node memory', true, function () {
                    confirmAction(node, null, 'purge');
                }));
                menu.appendChild(el('div', { cls: 'fl-menu-sep' }));
                menu.appendChild(menuItem('Upgrade engine', true, function () {
                    confirmAction(node, engine, 'upgrade');
                }));
                menu.appendChild(menuItem('Uninstall', true, function () {
                    confirmAction(node, engine, 'uninstall');
                }));
                actions.appendChild(menu);
            }
        }

        card.appendChild(actions);
        return card;
    }

    // ── detail panel ────────────────────────────────────────────

    function renderDetail() {
        var host = document.getElementById('fl-detail-body');
        if (!host) return;
        host.textContent = '';
        var node = selectedNode();
        if (!node) {
            host.appendChild(el('div', { cls: 'fl-empty', text: 'Select a node in the fleet column.' }));
            return;
        }
        var s = node.snapshot || {};
        var engines = enginesOf(node);

        // Header: name + meta + Power/Latency/Serving stats
        var health = nodeHealth(node);
        var dot = el('span', { cls: 'fl-dot lg' });
        dot.style.background = health === 'down' ? 'var(--red)' : health === 'warn' ? 'var(--yellow)' : 'var(--green)';
        dot.style.boxShadow = '0 0 10px ' + (health === 'down' ? 'rgba(239,68,68,.5)' : health === 'warn' ? 'rgba(234,179,8,.5)' : 'rgba(34,197,94,.5)');

        var metaBits = [];
        if (s.cpu_cores) metaBits.push(s.cpu_cores + 'C');
        if (s.uptime) metaBits.push('up ' + Math.floor(s.uptime / 86400) + ' d');
        if (!node.ok) metaBits.push(node.error_class || 'unreachable');

        var running = 0;
        engines.forEach(function (e) {
            if (engineStateOf(node.nickname, e, node.ok) === 'running') running += 1;
        });

        var stats = el('div', { cls: 'fl-stats' });
        if (typeof s.power_total_watts === 'number') {
            stats.appendChild(el('div', {}, [
                el('div', { cls: 'fl-stat-label', text: 'Power' }),
                el('div', { cls: 'fl-stat-value power' }, [
                    document.createTextNode(s.power_total_watts.toFixed(1)),
                    el('span', { cls: 'unit', text: ' W' }),
                ]),
            ]));
        }
        stats.appendChild(el('div', {}, [
            el('div', { cls: 'fl-stat-label', text: 'Latency' }),
            el('div', { cls: 'fl-stat-value', text: Math.round(node.latency_ms) + ' ms' }),
        ]));
        stats.appendChild(el('div', {}, [
            el('div', { cls: 'fl-stat-label', text: 'Serving' }),
            el('div', { cls: 'fl-stat-value', text: running + '/' + engines.length }),
        ]));

        host.appendChild(el('div', { cls: 'fl-detail-head' }, [
            el('div', {}, [
                el('div', { cls: 'fl-node-row1' }, [dot, el('span', { cls: 'fl-detail-name', text: node.nickname })]),
                el('div', { cls: 'fl-detail-meta', text: metaBits.join(' · ') }),
            ]),
            stats,
        ]));

        if (!node.ok) {
            host.appendChild(el('div', { cls: 'fl-empty' }, [
                document.createTextNode('This node did not answer the last poll. Write actions are paused until it is reachable again.'),
            ]));
            return;
        }

        // Unified memory card
        if (s.mem_total) {
            var segs = ramSegments(node, 'lg');
            var umaCard = el('div', { cls: 'fl-uma-card' }, [
                el('div', { cls: 'fl-uma-title-row' }, [
                    el('span', { cls: 'fl-label-micro', text: 'Unified memory' }),
                    el('span', { cls: 'fl-uma-value' }, [
                        el('b', { text: fmtGB(s.mem_used || 0) }),
                        document.createTextNode(' / ' + fmtGB(s.mem_total, 0) + ' GB'),
                    ]),
                ]),
                segs.bar,
            ]);
            var legend = el('div', { cls: 'fl-uma-legend' });
            segs.legend.forEach(function (item) {
                var sq = el('span', { cls: 'fl-legend-sq' });
                sq.style.background = item.color;
                legend.appendChild(el('span', { cls: 'fl-legend-item' }, [
                    sq,
                    el('span', { text: item.name + ' · ' + fmtGB(item.ram) + ' GB' }),
                ]));
            });
            umaCard.appendChild(legend);
            host.appendChild(umaCard);
        }

        // Engine cards grid
        if (engines.length) {
            // Operational priority: what needs attention first, dormant
            // manifests last (and folded away below).
            var ORDER = {
                unhealthy: 0, degraded: 0, loading: 1, running: 2,
                loaded: 3, stopped: 4, disabled: 5, available: 6, not_installed: 9,
            };
            var sorted = engines.slice().sort(function (a, b) {
                var sa = engineStateOf(node.nickname, a, node.ok);
                var sb = engineStateOf(node.nickname, b, node.ok);
                var d = (ORDER[sa] !== undefined ? ORDER[sa] : 8) - (ORDER[sb] !== undefined ? ORDER[sb] : 8);
                if (d !== 0) return d;
                return engineLabel(a) < engineLabel(b) ? -1 : 1;
            });
            var active = [];
            var dormant = [];
            sorted.forEach(function (e) {
                var st = engineStateOf(node.nickname, e, node.ok);
                (st === 'not_installed' ? dormant : active).push(e);
            });

            if (active.length) {
                var grid = el('div', { cls: 'fl-engines' });
                active.forEach(function (e) { grid.appendChild(engineCard(node, e)); });
                host.appendChild(grid);
            }
            if (dormant.length) {
                var details = el('details', { cls: 'fl-dormant' });
                details.appendChild(el('summary', {
                    cls: 'fl-dormant-summary',
                    text: dormant.length + ' engine' + (dormant.length > 1 ? 's' : '') + ' not installed on this node',
                }));
                var dgrid = el('div', { cls: 'fl-engines' });
                dormant.forEach(function (e) { dgrid.appendChild(engineCard(node, e)); });
                details.appendChild(dgrid);
                host.appendChild(details);
            }
        } else {
            host.appendChild(el('div', { cls: 'fl-empty', text: 'No engines reported by this node.' }));
        }
    }

    // ── nav alert dot (sidebar Fleet item) ──────────────────────

    function renderNavAlert() {
        var link = document.querySelector('.sidebar-nav a[href="/fleet"]');
        if (!link) return;
        var existing = link.querySelector('.fl-nav-alert');
        var alert = false;
        (state.snapshot && state.snapshot.nodes || []).forEach(function (node) {
            if (!node.ok) alert = true;
            enginesOf(node).forEach(function (e) {
                var st = engineStateOf(node.nickname, e, node.ok);
                if (st === 'unhealthy' || st === 'degraded') alert = true;
            });
        });
        if (alert && !existing) link.appendChild(el('span', { cls: 'fl-nav-alert' }));
        if (!alert && existing) existing.remove();
    }

    // ── top-level render ────────────────────────────────────────

    function renderAll() {
        if (state.page === 'journal') {
            renderJournalPage();
            return;
        }
        // Full re-render every poll: preserve the scroll positions the
        // operator is actually using, or a 10 s tick yanks them to the top.
        var masterList = document.getElementById('fl-master-list');
        var detailBody = document.getElementById('fl-detail-body');
        var masterScroll = masterList ? masterList.scrollTop : 0;
        var detailScroll = detailBody ? detailBody.scrollTop : 0;
        renderMaster();
        renderSessionFooter();
        renderBanner();
        renderDetail();
        renderNavAlert();
        if (masterList) masterList.scrollTop = masterScroll;
        if (detailBody) detailBody.scrollTop = detailScroll;
    }

    // ── boot ────────────────────────────────────────────────────

    function boot() {
        var root = document.getElementById('fl-root');
        if (!root) return;
        state.page = root.dataset.flPage || 'fleet';

        if (state.page === 'journal') {
            refreshSession();
            loadJournalPage();
            return;
        }

        var journalBtn = document.getElementById('fl-journal-open');
        if (journalBtn) journalBtn.addEventListener('click', openDrawer);

        refreshSession().then(refreshSnapshot);
        state.refreshTimer = setInterval(refreshSnapshot, REFRESH_MS);
        // Re-poll the session itself (not just the countdown): expiry or a
        // logout in another tab must re-lock the buttons within a minute.
        setInterval(refreshSession, 60000);
        document.addEventListener('click', function () {
            if (state.menuOpen !== null) { state.menuOpen = null; renderAll(); }
        });
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
    else boot();
})();
