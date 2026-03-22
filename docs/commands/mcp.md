---
description: MCP server exposing 11 tools for AI agents to monitor inference engines, run benchmarks and get hardware-aware recommendations.
---

# asiai mcp

Start the MCP (Model Context Protocol) server, enabling AI agents to monitor and benchmark your inference infrastructure.

## Usage

```bash
asiai mcp                          # stdio transport (Claude Code)
asiai mcp --transport sse          # SSE transport (network agents)
asiai mcp --transport sse --port 9000
```

## Options

| Option | Description |
|--------|-------------|
| `--transport` | Transport protocol: `stdio` (default), `sse`, `streamable-http` |
| `--host` | Bind address (default: `127.0.0.1`) |
| `--port` | Port for SSE/HTTP transport (default: `8900`) |
| `--register` | Opt-in registration with asiai agent network (anonymous) |

## Tools (11)

| Tool | Description | Read-only |
|------|-------------|-----------|
| `check_inference_health` | Quick health check: engines up/down, memory pressure, thermal, GPU | Yes |
| `get_inference_snapshot` | Full system snapshot with all metrics | Yes |
| `list_models` | List all loaded models across engines | Yes |
| `detect_engines` | Re-scan for inference engines | Yes |
| `run_benchmark` | Run a benchmark or cross-model comparison (rate-limited to 1/min) | No |
| `get_recommendations` | Hardware-aware engine/model recommendations | Yes |
| `diagnose` | Run diagnostic checks (like `asiai doctor`) | Yes |
| `get_metrics_history` | Query historical metrics (1-168 hours) | Yes |
| `get_benchmark_history` | Query past benchmark results with filters | Yes |
| `compare_engines` | Compare engine performance for a model with verdict; supports multi-model comparison from history | Yes |
| `refresh_engines` | Re-detect engines without restarting the server | Yes |

## Resources (3)

| Resource | URI | Description |
|----------|-----|-------------|
| System Status | `asiai://status` | Current system health (memory, thermal, GPU) |
| Models | `asiai://models` | All loaded models across engines |
| System Info | `asiai://system` | Hardware info (chip, RAM, cores, OS, uptime) |

## Claude Code integration

Add to your Claude Code MCP config (`~/.claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "asiai": {
      "command": "asiai",
      "args": ["mcp"]
    }
  }
}
```

Then ask Claude: *"Check my inference health"* or *"Compare Ollama vs LM Studio for qwen3.5"*.

## Benchmark cards

The `run_benchmark` tool supports card generation via the `card` parameter. When `card=true`, a 1200x630 SVG benchmark card is generated and `card_path` is returned in the response.

```json
{"tool": "run_benchmark", "arguments": {"model": "qwen3.5", "card": true}}
```

Cross-model comparison (mutually exclusive with `model`, max 8 slots):

```json
{"tool": "run_benchmark", "arguments": {"compare": ["qwen3.5:4b", "deepseek-r1:7b"], "card": true}}
```

CLI equivalent for PNG + sharing:

```bash
asiai bench --quick --card --share    # Quick bench + card + share (~15s)
```

See the [Benchmark Card](../benchmark-card.md) page for details.

## Agent registration

Join the asiai agent network to get community features (leaderboard, comparison, percentile stats):

```bash
asiai mcp --register                  # Register on first run, heartbeat on subsequent runs
asiai unregister                      # Remove local credentials
```

Registration is **opt-in and anonymous** — only hardware info (chip, RAM) and engine names are sent. No IP, hostname, or personal data is stored. Credentials are saved in `~/.local/share/asiai/agent.json` (chmod 600).

On subsequent `asiai mcp --register` calls, a heartbeat is sent instead of re-registering. If the API is unreachable, the MCP server starts normally without registration.

Check your registration status with `asiai version`.

## Network agents

For agents on other machines (e.g., monitoring a headless Mac Mini):

```bash
asiai mcp --transport sse --host 0.0.0.0 --port 8900
```

See the [Agent Integration guide](../agent.md) for detailed setup instructions.
