/* Global shell — runs on every page.
 *
 * Three small responsibilities, all fail-silent (a page must render fine
 * with the fleet API absent or this script erroring):
 *   1. node switcher in the topbar (persisted, shared with the fleet
 *      cockpit through localStorage);
 *   2. operator session status + logout, visible outside /fleet;
 *   3. cross-page alert dot on the Fleet nav item.
 *
 * Rendering rule (same as fleet.js): createElement/textContent only,
 * never innerHTML with dynamic data.
 */
(function () {
    'use strict';

    // Shared with fleet.js: the cockpit reads/writes the same key so the
    // node picked here is the node the cockpit opens on.
    var NODE_KEY = 'asiai-fleet-node';
    var ALERT_POLL_MS = 45000;
    var SESSION_POLL_MS = 60000;

    var topbar = document.getElementById('sh-topbar');
    var sessionHost = document.getElementById('sh-session');
    var nodeSelect = document.getElementById('sh-node-select');
    var alertDot = document.getElementById('sh-fleet-attn');

    function el(tag, cls, text) {
        var node = document.createElement(tag);
        if (cls) node.className = cls;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    // ── node switcher ───────────────────────────────────────────
    function initNodes() {
        if (!nodeSelect) return;
        fetch('/api/v1/fleet/nodes')
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
                var nodes = data && Array.isArray(data.nodes) ? data.nodes : [];
                if (!nodes.length) return; // fleet not configured: keep the bar hidden
                nodeSelect.textContent = '';
                nodes.forEach(function (n) {
                    if (!n || typeof n.nickname !== 'string') return;
                    var opt = document.createElement('option');
                    opt.value = n.nickname;
                    opt.textContent = n.nickname;
                    nodeSelect.appendChild(opt);
                });
                var saved = null;
                try { saved = localStorage.getItem(NODE_KEY); } catch (e) { /* private mode */ }
                if (saved && nodeSelect.querySelector('option[value="' + CSS.escape(saved) + '"]')) {
                    nodeSelect.value = saved;
                }
                nodeSelect.addEventListener('change', function () {
                    try { localStorage.setItem(NODE_KEY, nodeSelect.value); } catch (e) { /* ignored */ }
                });
                if (topbar) topbar.hidden = false;
            })
            .catch(function () { /* fleet API absent — shell stays dormant */ });
    }

    // ── operator session ────────────────────────────────────────
    function renderSession(info) {
        if (!sessionHost) return;
        sessionHost.textContent = '';
        var authenticated = !!(info && info.authenticated);
        var dot = el('span', 'sh-session-dot' + (authenticated ? ' on' : ''));
        sessionHost.appendChild(dot);
        if (!authenticated) {
            sessionHost.appendChild(el('span', null, 'read-only'));
            var login = el('a', null, 'Operator login');
            login.href = '/login';
            sessionHost.appendChild(login);
            return;
        }
        var mins = '';
        if (info.expires_at) {
            mins = ' · ' + Math.max(0, Math.floor((info.expires_at * 1000 - Date.now()) / 60000)) + ' min';
        }
        sessionHost.appendChild(el('span', null, 'operator' + mins));
        var out = el('button', 'sh-logout', 'Logout');
        out.type = 'button';
        out.addEventListener('click', function () {
            fetch('/logout', { method: 'POST' })
                .then(pollSession)
                .catch(function () { /* next poll reconciles */ });
        });
        sessionHost.appendChild(out);
        if (topbar) topbar.hidden = false;
    }

    function pollSession() {
        if (!sessionHost) return;
        fetch('/api/v1/operator/session')
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (info) { if (info) renderSession(info); })
            .catch(function () { /* transient — keep last rendering */ });
    }

    // ── fleet alert dot ─────────────────────────────────────────
    function pollAlert() {
        if (!alertDot) return;
        fetch('/api/v1/fleet/health-summary')
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (d) {
                if (!d) return;
                var engines = d.unhealthy_engines || 0;
                var nodes = d.unreachable_nodes || 0;
                if (engines + nodes > 0) {
                    alertDot.hidden = false;
                    var bits = [];
                    if (engines) bits.push(engines + ' engine' + (engines > 1 ? 's' : '') + ' unhealthy');
                    if (nodes) bits.push(nodes + ' node' + (nodes > 1 ? 's' : '') + ' unreachable');
                    alertDot.title = bits.join(', ');
                } else {
                    alertDot.hidden = true;
                    alertDot.removeAttribute('title');
                }
            })
            .catch(function () { /* transient — keep last state */ });
    }

    initNodes();
    pollSession();
    pollAlert();
    setInterval(pollSession, SESSION_POLL_MS);
    setInterval(pollAlert, ALERT_POLL_MS);
})();
