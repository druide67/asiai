# Versions — running vs installed vs available

`asiai versions` answers a question single-host tools usually can't:
**is the engine I have the latest one, and is the process I'm running the
one I have installed?** It lines up three coordinates per engine:

- **running** — the version of the live engine process (read from its HTTP
  endpoint or a `--version` shell-out, the same detection `asiai detect`
  uses).
- **installed** — what is on the machine (Homebrew formula/cask, a pip
  package, or a macOS app bundle).
- **available** — the latest upstream version. Offline by default
  (`brew outdated` against the local Homebrew cache); PyPI/GitHub when you
  pass `--check-upstream`.

From those it derives a status:

| Status | Meaning |
|--------|---------|
| `up-to-date` | installed == available (or no upstream signal and running == installed) |
| `upgrade-available` | a newer version exists upstream |
| `running-stale` | the **running process predates the installed binary** — you upgraded but didn't restart. A restart reconciles it. |
| `not-installed` | nothing installed and nothing running |
| `unknown` | a version string couldn't be parsed, or there's nothing to compare against |

## CLI

```sh
asiai versions                      # offline: running/installed + brew outdated
asiai versions --check-upstream     # also query PyPI / GitHub (network, opt-in)
asiai versions --engine llamacpp    # filter to one engine
asiai versions --json | jq          # machine-readable
```

Example:

```
Engine versions

  ENGINE     RUNNING  INSTALLED  AVAILABLE  STATUS
  ─────────  ───────  ─────────  ─────────  ─────────────────
  llama.cpp  9370     9370       9380       upgrade-available
  Ollama     —        0.24.0     0.24.0     up-to-date
  Rapid-MLX  —        0.6.68     0.6.68     up-to-date

  llama.cpp: https://github.com/ggml-org/llama.cpp/releases
  Ollama:    https://github.com/ollama/ollama/releases

  AVAILABLE is brew-cache only (offline). Pass --check-upstream for PyPI/GitHub.
  1 upgrade(s) available
```

A `running-stale` row is the classic post-upgrade trap: `brew upgrade
llama.cpp` bumped the binary, but the `llama-server` process you started
last week is still the old build. The fix is `aisctl restart llamacpp`
(or whatever your engine is), not another upgrade.

## Web dashboard

`asiai web` gains a **/versions** page: the same three-column table with
status badges and clickable changelog links, auto-refreshed via HTMX.

```sh
asiai web                                # http://127.0.0.1:8899
open http://127.0.0.1:8899/versions
open http://127.0.0.1:8899/versions?upstream=1   # include PyPI/GitHub
```

The JSON API mirrors the CLI:

```sh
curl -s localhost:8899/api/v1/versions | jq
curl -s 'localhost:8899/api/v1/versions?upstream=1' | jq
```

Results are cached (60 s offline, 10 min for the network mode) so opening
the page doesn't hammer brew/PyPI/GitHub on every refresh.

## Doctor recap

`asiai doctor` runs an **offline** version recap under the Engine section
so a single `doctor` pass tells you if anything is behind:

```
  Engine
    ⚠ Versions             1 upgrade(s): llama.cpp
      Fix: asiai versions
```

It never makes a network call (only the local `brew outdated` plus the
reachability probes doctor already does), so `doctor` stays fast.

## Where the engine list comes from

`asiai` ships an internal table mapping each engine to its Homebrew
formula / pip package / GitHub repo, so the feature works standalone. When
[`asiai-inference-server`](https://github.com/druide67/asiai-inference-server)
is installed alongside `asiai`, it contributes a richer table through the
`asiai.version_sources` entry point — adding the engines it manages
(e.g. `turboquant`) and the authoritative formula mapping. The two
packages never import each other; the provider hands over plain data and
`asiai` merges it **field by field over its internal defaults** (a
provider that knows the brew formula but not the app-bundle path won't
erase asiai's own fallback). Rows sourced from the provider are labelled
accordingly in `--json` (`"source": "aisrv"`).

## Upgrading (Phase 2)

Reading versions is read-only by design. Triggering an upgrade is a
**write** and lives in `asiai-inference-server`:

```sh
aisctl upgrade llamacpp        # brew upgrade (formula-whitelisted) + restart
aisctl upgrade llamacpp --dry-run
```

Web-triggered upgrades (a button on the /versions page) ride the same
authenticated `asiai web → aisctl serve` surface as the Phase 2 fleet
write commands — Bearer token, per-token rate limit, audit log. See
[fleet-mode.md](fleet-mode.md) for that security model.

## Caveats

- **`brew outdated` reflects the local cache.** The `available` column is
  only as fresh as your last `brew update`. `asiai versions` never runs
  `brew update` for you (it's slow and mutates state) — run it yourself
  before relying on the offline column.
- **GitHub rate-limits unauthenticated requests** to 60/hour per IP. Set
  `GITHUB_TOKEN` in the environment to lift that to 5000/hour; otherwise
  `--check-upstream` degrades gracefully to `available: —` with a note
  rather than failing.
- **App-bundle engines have no public upstream API** (e.g. LM Studio).
  Their `available` column stays empty; the status is derived from
  running-vs-installed only.
- **pip lookups use the environment `asiai` runs under**
  (`sys.executable -m pip`), which can differ from the venv your engine
  runs in. The reported pip version is asiai's view.
- **mlx-lm can be installed via both brew and pip.** Brew takes
  precedence for the `installed` column, matching `doctor` and the
  upgrade path.
