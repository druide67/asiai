# Fleet mode — multi-host observability

`asiai` started as a single-host observability and benchmarking tool.
**Fleet mode** lets you declare several hosts that all run `asiai web`
and view their state side-by-side from one machine — without re-running
`asiai monitor` on every Mac you own.

Phase 1 (current) is **read-only**: list nodes, poll each one's
snapshot in parallel, render a CLI table and an HTML grid. Phase 2 will
add cross-host engine management commands; Phase 3 will add mDNS Bonjour
auto-discovery and (optional) authentication for non-LAN deployments.

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

## What is NOT in Phase 1

- **Cross-host writes** (start/stop/install/purge engines on remote
  Macs) — Phase 2 will land this through `aisctl` with required
  Bearer-token authentication.
- **Auto-discovery** (Bonjour/mDNS) — Phase 3.
- **TLS** between the orchestrator and the nodes — Phase 3.
- **TUI fleet panel** — likely Phase 3.
- **Authentication required** — Phase 2. The `auth_token` field in the
  schema is reserved but currently unused.

## Security notes for Phase 1

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
