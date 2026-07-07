# ADR 0001 — Audit-journal read access for local agents (MCP)

- Status: accepted
- Date: 2026-07-07
- Scope: `asiai auth login --scope`, `POST /api/v1/fleet/audit-tail`, MCP tool `fleet_audit_tail`

## Context

The fleet audit journal (`~/.local/share/asiai/fleet-audit.jsonl`) records
who did what on the fleet: write commands, their targets, outcomes, source
IPs and token ids. The web dashboard exposes it to a logged-in operator.
Agents (LLM assistants talking to the asiai MCP server) legitimately need
to read it too — "what happened on the fleet tonight?" is a natural
diagnostic question — but the MCP server is a local stdio process with no
authentication of its own, and its output feeds an LLM context that may
leave the machine.

A hard truth shapes the whole design: **no local mechanism can
distinguish the human operator from an agent running under the same user
account.** Any agent with shell access can mint a login code itself.
Biometric approval (Touch ID / LocalAuthentication) would be a real
human-vs-agent barrier but was rejected: headless nodes have no
biometrics, and it is disproportionate for a read. True identity
separation is a future service-account story.

So this gate is **not an access-control barrier against local agents**
— pretending otherwise would be security theater. What it actually buys:

- **Attribution** — every read maps to a code minted at a known time
  from a shell, and the read itself lands in the journal.
- **TTL** — access windows are short (code TTL ≤ 300 s) and single-use;
  nothing persistent accumulates.
- **One auth system** — the same shell-bound operator-code flow the
  dashboard uses, not a second mechanism to audit.

## Decision

Reuse the ephemeral shell-bound operator-login flow, hardened by five
invariants:

1. **Scope is bound to the code at mint, never chosen at exchange.**
   `asiai auth login --scope audit:read` writes the scope into the code
   file; every consumer inherits it verbatim. A code minted `audit:read`
   can never open a write-capable session, whatever endpoint receives it
   (`consume_login_code` returns the mint-time scope; unknown scopes fail
   closed). Conversely the one-shot exchange refuses `full`-scope codes:
   one scope, one exchange surface — mint decides use.
2. **Redacted output, metadata only.** The exchange response feeds an
   LLM context, so it carries a field whitelist (`ts`, `actor_type`,
   `event`, `source_ip`, `token_id`, `nickname`, `command`, `status`,
   `http_status`, `duration_ms`, `scope`, exchange bookkeeping). Raw
   command arguments (`args`) and free-form `error` text are dropped by
   construction, as is any unknown/future field. No login code, token
   value or secret name ever passes.
3. **Bounded window + rate limit.** `lines` ≤ 200 (default 50),
   `since_hours` ≤ 24 (default 6), and the route charges an
   all-requests rate limit (6/min per peer) — a leaked context cannot
   exfiltrate the whole history in one sweep, nor scrape it in a loop.
4. **REST funnel only.** The MCP tool POSTs to the hub's
   `/api/v1/fleet/audit-tail`; it never opens the journal file or the
   database directly. One read path, one place where redaction and
   journaling happen.
5. **The read is itself journaled** — an `audit_read` event with an
   exchange id and the returned line count — and bounded (the rate
   limit caps the self-referential noise).

The exchange is deliberately **session-less**: one code buys exactly one
redacted read. Managing a cookie/CSRF session lifecycle in a non-browser
consumer would add surface for nothing; with no session there is nothing
to revoke. This is a hardening relative to the session-based design that
was originally reviewed.

## Deployment note — where does the output go?

`fleet_snapshot` / `fleet_health` / `fleet_audit_tail` responses enter
the consuming LLM's context. With a **local** model, the journal never
leaves the machine. With a **cloud** assistant, every (redacted) read
exfiltrates who-did-what metadata to a third party. That trade-off is
the deployer's to make — in a single-operator home lab it is usually
acceptable — but it is a decision, not an accident, and condition 2
exists precisely to keep its blast radius small.

## Alternatives considered

- **Expose the journal unauthenticated on the MCP server** — rejected:
  no attribution, no bound, and a silent default toward exfiltration.
- **A dedicated machine token for reads** — rejected: second credential
  system to rotate/audit, still no human/agent distinction.
- **Touch ID / LocalAuthentication at mint** — rejected (headless nodes,
  disproportionate for reads); revisit with service accounts.
- **Reusing the full web session from the MCP process** — rejected in
  favor of the one-shot exchange (see above).
