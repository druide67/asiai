---
description: "MTPLX benchmark on Apple Silicon: MLX server with native MTP speculative decoding, OpenAI-compatible API."
---

# MTPLX

MTPLX is an MLX-based inference server for Apple Silicon (youssofal upstream) built around native MTP (multi-token prediction) speculative decoding. It exposes an OpenAI-compatible API and reports rich runtime state (generation mode, draft depth, session cache) on its `/health` endpoint.

## Setup

```bash
brew tap youssofal/mtplx
brew install mtplx
```

## Details

| Property | Value |
|----------|-------|
| Default port | Set at launch (`--port`) |
| API type | OpenAI-compatible |
| VRAM reporting | No (asiai measures GPU power/VRAM via ioreg) |
| Model format | MLX |
| Detection | `owned_by: "mtplx"` in `/v1/models`, version via `brew list --versions mtplx` |
| Requirements | Apple Silicon (M1+), macOS, Homebrew |

## Authentication

When the server is started with an API key, it requires `Authorization: Bearer <key>` on all routes — an unconfigured asiai then sees only 401s and cannot detect or monitor it. Point the engine's config entry at a file containing the key (the key itself never lives in the config):

```bash
asiai config add mtplx http://localhost:8080 --api-key-file ~/.config/asiai/keys/mtplx.key
```

asiai attaches the Bearer header to every request to this engine only (detection, monitoring, benchmarks). A missing or empty key file simply drops the header — no key material is ever logged. See [config](../commands/config.md#engine-api-keys---api-key-file) for details.

## Notes

- MTPLX has no fixed default port; asiai finds it on any scanned port through the `owned_by` field of `/v1/models`, and on non-standard ports through process discovery (`python -m mtplx.server.openai`).
- Its `/health` endpoint returns rich JSON (`{"ok": true, "generation_mode": "mtp", ...}`) rather than llama.cpp's `{"status": "ok"}`, so the two are never confused during detection.
- Generation runs through the standard streaming benchmark path; MTP speculative decoding is server-side and transparent to the OpenAI-compatible client.

## See also

Compare engines with `asiai bench --engines mtplx` --- [learn how](../benchmark-llm-mac.md)
