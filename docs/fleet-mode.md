# Fleet mode — multi-host observability + cross-host writes

`asiai` started as a single-host observability and benchmarking tool.
**Fleet mode** lets you declare several hosts that all run `asiai web`
and view their state side-by-side from one machine — without re-running
`asiai monitor` on every Mac you own.

- **Phase 1 — read-only** (shipped in `asiai`): list nodes, poll each
  one's snapshot in parallel, render a CLI table and an HTML grid.
- **Phase 2 — writes** (shipped in `asiai-inference-server` + Bearer
  auth in `asiai`): execute `purge`, `stop/start/restart`, `unload`,
  `install/uninstall`, `upgrade` on remote nodes via authenticated
  HTTP. See the **Phase 2 — write commands** section below.
- **Phase 3 — auto-discovery** (planned): mDNS Bonjour
  `_asiai-fleet._tcp.local`, TUI fleet panel, TLS/mTLS for off-LAN.

## What you need

- One Mac per node, each running `asiai >= 1.4` with the `web` extra
  installed (`pip install asiai[web]` or `pip install asiai[all]`).
- `asiai web` running on each remote node, **bound on a network
  interface that the orchestrator host can reach**:

  ```sh
  asiai web --host 0.0.0.0 --port 8899
  ```

  ⚠️ Binding `0.0.0.0` exposes the dashboard to every host on the local
  network. By default `asiai web` binds `127.0.0.1` and warns if you
  opt-in to `0.0.0.0`. Use Phase 1 only on a trusted LAN.

- On the orchestrator host, just `asiai` installed. The orchestrator
  does not need to run `asiai web` itself — it only needs CLI access.

## Configure the fleet

The fleet config lives at `~/.config/asiai/fleet.json` (perms `0o600`).
It is hand-editable but the CLI manages it for you:

```sh
asiai fleet add studio    --url http://192.0.2.10:8899 --role workstation
asiai fleet add laptop    --url http://192.0.2.11:8899 --role spare
asiai fleet add minihost  --url http://minihost.local:8899
asiai fleet list
```

`--role` is free text; use it for whatever taxonomy fits your setup.
The URL is passed verbatim to the HTTP client, so any hostname, IP, or
mDNS `.local` name works — including Tailscale `*.ts.net` addresses.

## Poll node status

`asiai fleet status` polls every node's `GET /api/v1/snapshot`
endpoint in parallel and prints an aggregated table:

```sh
asiai fleet status
asiai fleet status --json | jq '.nodes[] | {nickname, ok, latency_ms}'
asiai fleet ping studio        # check one node only
```

Per-node timeout is 5 seconds by default (`--timeout`). The aggregate
poll has a defensive 10-second cap: if a node's TCP connection dies
silently, the rest of the fleet's status is still returned.

The exit code is `0` when every node responded successfully, and `1` if
at least one node is down — convenient for shell scripts and CI checks.

## Browse the fleet in the web dashboard

`asiai web` on the orchestrator host gains a new `/fleet` page that
shows a card per node, refreshed every 10 seconds via HTMX. Each card
displays the engine list reported by the remote, the request latency,
and a status badge.

```sh
asiai web                          # main host on http://127.0.0.1:8899
open http://127.0.0.1:8899/fleet
```

## Phase 2 — write commands

Phase 2 adds **authenticated cross-host writes**. From the orchestrator,
`aisctl fleet push <nickname> <command>` POSTs a command to the
remote node's `asiai web`, which validates the Bearer token, applies a
per-token rate limit, writes an audit log line, and proxies to a
loopback `aisctl serve` companion process that runs the actual command.

Why two processes on the node? `asiai web` is the only LAN-facing
surface, so the trust boundary stays in one place. `aisctl serve`
listens on `127.0.0.1:8898` only and shares a per-startup loopback
secret with `asiai web` (file `~/.local/state/asiai/aisctl-serve-token`,
0o600). A LAN attacker who somehow bypasses `asiai web`'s auth still
needs filesystem access to that loopback token to reach `aisctl serve`.

### Whitelisted commands

| Command | Args required | Upstream timeout | Notes |
|---------|---------------|------------------|-------|
| `purge` | — | 30 s | `sudo /usr/sbin/purge` (low risk) |
| `unload <engine> [<model>]` | `engine` | 60 s | Native API unload, fallback restart |
| `stop <engine>` | `engine` | 60 s | LaunchDaemon `bootout` |
| `start <engine>` | `engine` | 120 s | LaunchDaemon `bootstrap` + health |
| `restart <engine>` | `engine` | 120 s | stop + start |
| `install <engine>` | `engine` | 300 s | Provision plist + sudoers |
| `uninstall <engine>` | `engine` | 120 s | Remove plist + pf anchor |
| `upgrade <engine>` | `engine` | 600 s | `brew upgrade` (formulas whitelisted) |

Anything outside this whitelist is rejected at the LAN edge with HTTP
400 before any subprocess is spawned. `upgrade` additionally enforces
a per-engine Homebrew formula whitelist (`ollama`, `llama.cpp`,
`lm-studio`, `rapid-mlx`, `turboquant`) to defend against argv
injection even if the engine regex is bypassed.

### Bootstrapping the auth surface on a node

```sh
# 1. On the node — initialize the auth file and copy the secret ONCE.
asiai auth init
# → prints token id + secret. Save the secret — asiai will never show it again.

# 2. On the node — start the loopback companion (one-shot or LaunchDaemon).
aisctl serve &
# → listens on 127.0.0.1:8898, writes ~/.local/state/asiai/aisctl-serve-token

# 3. On the orchestrator — register the node WITH the secret.
asiai fleet add studio \
  --url http://192.0.2.10:8899 \
  --role workstation \
  --auth-token <the-secret-from-step-1>
```

### Issuing a write

```sh
# Free unified memory on the studio.
aisctl fleet push studio purge

# Restart Ollama everywhere (loop in shell — no native broadcast yet).
for n in studio laptop minihost; do
  aisctl fleet push "$n" restart --engine ollama
done

# Unload a specific Ollama model without restarting the daemon.
aisctl fleet push studio unload --engine ollama --model llama3.2
```

`aisctl fleet push --json` emits a single JSON object per call so
agents and CI pipelines can parse the result.

### Token lifecycle on the node

```sh
asiai auth list                       # list tokens (no secrets shown)
asiai auth create --label laptop-2026  # add a new token
asiai auth rotate tok_abc123def456     # revoke + replace (returns new secret)
asiai auth revoke tok_abc123def456     # revoke without replacing
```

### Audit log

Every write attempt (denied or executed) appends one JSON object to
`~/.local/share/asiai/fleet-audit.jsonl` (0o600, rotated at 10 MB to
`.1`). Fields: `ts`, `source_ip`, `token_id`, `nickname`, `command`,
`args` (with secret-bearing keys redacted), `status`, `http_status`,
`duration_ms`, `exit_code`, `error`. Useful both for forensics and
for confirming that a command actually ran on the right host.

### What is NOT in Phase 2

- **Auto-discovery** (Bonjour/mDNS) — Phase 3.
- **TLS** between the orchestrator and the nodes — Phase 3.
- **TUI fleet panel** — Phase 3.
- **Broadcast commands** ("purge everywhere in one call") — would land
  before Phase 3 if the use case appears in practice; the shell loop
  above is fine for small fleets.
- **MCP write tools** — Phase 3.

## Security notes

### Phase 1 (read-only) defences

1. The Phase 1 dashboard is **read-only**: a compromised LAN peer can
   read your engine list and monitoring metrics but cannot trigger an
   inference run, purge memory, or restart an engine. This limits the
   blast radius significantly.
2. `fleet.json` is saved with `0o600` perms so other accounts on the
   same Mac cannot enumerate which hosts you monitor.
3. `auth_token` is never echoed by the JSON API or the HTML page
   (verified by the test suite).
4. If you need to expose nodes off-LAN, put them behind a VPN
   (Tailscale, WireGuard) rather than punching firewall holes. The
   `asiai_url` accepts the VPN hostname directly.

### Phase 2 (writes) threat model

| Threat | Defence |
|--------|---------|
| Unauthenticated LAN peer issues writes | `asiai web` requires `Authorization: Bearer <secret>`; missing → 401. |
| Brute-force secret enumeration | `secrets.token_urlsafe(32)` = 256 bits of entropy; constant-time `hmac.compare_digest` comparison against salted SHA-256 hashes; per-token rate limit (30/min). |
| Stolen secret used from elsewhere | `asiai auth rotate <id>` revokes + replaces in one step; audit log captures source IP per call. |
| Command injection through engine/model args | LAN edge regex (`^[a-z][a-z0-9_-]{0,31}$` for engines, HF naming for models); `subprocess.run(list)` without `shell=True`; `upgrade` uses a per-engine Homebrew formula whitelist. |
| Other local user POSTs directly to `aisctl serve` to bypass `asiai web`'s checks | `aisctl serve` binds 127.0.0.1 only AND requires a per-startup loopback Bearer secret stored at `~/.local/state/asiai/aisctl-serve-token` (0o600). |
| Token leaked in CLI output / shell history | Plaintext secret is shown EXACTLY ONCE at create/rotate time; the on-disk hash cannot be reversed. |
| Replay after a destructive command | Audit log JSONL keeps `ts`, `source_ip`, `token_id`, command, exit code per attempt (rotated at 10 MB). |
| Body-size DoS on the auth endpoint | LAN edge caps the request body at 64 KB; oversize → 413. |
| Symlink swap on auth.json or fleet.json | `save_*` refuses to write through a symlink. |
| Concurrent token CRUD corrupting auth.json | `fcntl.flock` cross-process lock around every read-modify-write. |

### Limits that are explicit non-goals for Phase 2

- **No TLS** between orchestrator and nodes. Phase 2 is for trusted
  LANs (or LANs glued together by a VPN). If you need confidentiality
  on the wire, route through Tailscale / WireGuard / SSH tunnel.
- **No mTLS.** Token-only auth.
- **No multi-user RBAC.** Every token has the same capabilities — the
  whole whitelist. Splitting into "read-only" vs "operator" tokens is
  a Phase 3 candidate if the use case emerges.
- **No off-host audit shipping.** The JSONL stays on the node; ship
  it elsewhere with `fluent-bit`/`vector` if you need centralized
  storage. Rotation discards the previous backup after 10 MB.

## Backup & restore

The fleet config is a single file: `~/.config/asiai/fleet.json` (0o600).
Back it up with a regular file copy:

```sh
cp ~/.config/asiai/fleet.json ~/Documents/asiai-fleet-backup.json
```

To move a fleet declaration to another Mac, copy the same file across
and `chmod 600` it on the target.

## How does this compare to LM Link / Ollama / Exo?

asiai fleet is **engine-agnostic observability** for an Apple Silicon
home lab. It sits at a different layer than the alternatives:

- **LM Studio "LM Link"** (Tailscale-based, since Feb 2026): makes one
  LM Studio model on a remote Mac reachable via local `localhost:1234`.
  Solves "use my Mac Studio's model from my MacBook". Single engine,
  single model at a time. asiai fleet shows you what is running on N
  Macs across **all engines simultaneously**.
- **Ollama**: no native multi-host mode in 2026. Third-party
  load-balancers (e.g. OLOL) exist for Ollama clusters specifically.
- **Exo** (exo-explore/exo): distributed inference — shards one large
  model across N Macs. Different layer entirely; complementary, not
  competing.

The asiai differentiator: **see Ollama + LM Studio + mlx-lm +
llama.cpp + Rapid-MLX/vllm-mlx side-by-side across your Macs**, with
energy and thermal observability via IOReport (Apple Silicon-only,
unique among comparable tools as of May 2026).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `status: DOWN error: ConnectionRefusedError` | Remote `asiai web` not running | `asiai web --host 0.0.0.0` on the remote |
| `status: DOWN error: TimeoutError` | Network reachability or firewall | `curl -v http://<host>:8899/api/v1/status` from the orchestrator |
| `status: DOWN error: HTTP 404` | Remote runs an older `asiai` without the `/api/v1/snapshot` endpoint | Upgrade the remote to the same `asiai` version as the orchestrator |
| All nodes "never" last seen | `fleet status` has never run since the nodes were added | Run `asiai fleet status` once to populate the `last_seen` field |
