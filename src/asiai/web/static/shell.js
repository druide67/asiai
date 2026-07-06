/* Global shell — runs on every page.
 *
 * Two small responsibilities, both fail-silent (a page must render fine
 * with the fleet API absent or this script erroring):
 *   1. operator session status + logout, visible outside /fleet;
 *   2. cross-page alert dot on the Fleet nav item.
 *
 * Node scoping deliberately does NOT live here: the multi-node pages
 * carry their own multi-select chips (multinode.js) and the cockpit its
 * master column — a global mono select drove nothing and lied about it.
 *
 * Rendering rule (same as fleet.js): createElement/textContent only,
 * never innerHTML with dynamic data.
 */
(function () {
    'use strict';

    var ALERT_POLL_MS = 45000;
    var SESSION_POLL_MS = 60000;

    var topbar = document.getElementById('sh-topbar');
    var sessionHost = document.getElementById('sh-session');
    var alertDot = document.getElementById('sh-fleet-attn');

    function el(tag, cls, text) {
        var node = document.createElement(tag);
        if (cls) node.className = cls;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    // ── operator session ────────────────────────────────────────
    function renderSession(info) {
        if (!sessionHost) return;
        // The topbar reveals as soon as session state is known — for BOTH
        // outcomes (read-only included), it no longer waits on fleet data.
        if (topbar) topbar.hidden = false;
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

    pollSession();
    pollAlert();
    setInterval(pollSession, SESSION_POLL_MS);
    setInterval(pollAlert, ALERT_POLL_MS);
})();
