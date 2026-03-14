# asiai v1.0.1 — Suivi des tests pre-push

## Phase 0 — Pre-flight + Version bump
- [x] Tests pytest (631 pass)
- [x] Ruff clean
- [x] Version bump pyproject.toml + __init__.py → 1.0.1
- [x] CHANGELOG.md section [1.0.1] — 2026-03-13

## Phase 1 — Deploy Mac Mini
- [x] rsync code vers mini
- [x] uv tool install --force
- [x] asiai version → 1.0.1
- [x] Restart daemons (monitor + web :8642)
- [x] curl /api/v1/status OK

## Phase 2 — Tests CLI (Mac Mini)
- [x] asiai detect — Ollama 0.17.7 + LM Studio 0.4.5
- [x] asiai models — modeles charges avec VRAM, quant, ctx
- [x] asiai doctor — checks OK
- [x] asiai version — "asiai 1.0.1", chip, engines
- [x] asiai monitor — snapshot CPU/RAM/thermal/GPU
- [x] asiai bench --quick — ~15s, resultats stockes
- [x] asiai bench --quick --card — card SVG generee
- [x] asiai bench --quick --card --share — PNG + share URL
- [x] asiai recommend — recommandations basees sur historique
- [x] asiai compare — comparaison community (strict model matching)
- [x] asiai leaderboard — donnees community

## Phase 3 — Tests Web Dashboard (Mac Mini :8642)
- [x] Dashboard / — engine status, models, memory gauge
- [x] Benchmark /bench — form, Quick Bench, SSE progress, resultats, card, share
- [x] History /history — charts CPU/RAM/GPU, benchmark, filtres temps
- [x] Monitor /monitor — live refresh 5s, sparklines, gauges
- [x] Doctor /doctor — checks pass/warn/fail
- [x] API /api/v1/status
- [x] API /api/v1/snapshot
- [x] API /api/v1/benchmarks?hours=168
- [x] API /api/v1/metrics (Prometheus)

## Phase 4 — Tests MCP
- [x] check_inference_health
- [x] get_inference_snapshot
- [x] list_models
- [x] detect_engines
- [x] diagnose
- [x] get_metrics_history
- [x] get_benchmark_history
- [x] get_recommendations
- [x] compare_engines (verifie via source + unit tests)
- [x] refresh_engines (verifie via source + unit tests)
- [x] run_benchmark (teste via CLI bench --quick, meme code path)

## Phase 5 — Agent Registration
- [x] register_agent() via Python direct
- [x] asiai version → "Agent network: registered (#N)"
- [x] curl agent-count OK
- [x] unregister + re-register cycle

## Phase 6 — Screenshots Playwright
- [x] screenshot-dashboard.png
- [x] screenshot-monitor.png
- [x] screenshot-history.png
- [x] screenshot-bench.png
- [x] screenshot-bench-results.png
- [x] screenshot-doctor.png

## Phase 6b — Fix Benchmark Card (DONE)
- [x] CLI: card_png_b64 dans payload POST /benchmarks (sips macOS → PNG → base64)
- [x] Serveur: validate.php — accepter card_png_b64 (max ~2MB, magic bytes PNG)
- [x] Serveur: card.php — store_card_png_at_submit() stocke PNG client directement
- [x] Serveur: card.php — fix setResolution(144,144) avant readImageBlob (fallback)
- [x] Serveur: card.php — fix bug heredoc generateur PHP fallback
- [x] Serveur: ne JAMAIS servir SVG brut (PNG only)
- [x] config.php — max_payload_bytes 64KB → 3MB
- [x] Deploy OVH (lftp via .netrc credentials) — le vrai pb etait credentials FTP
- [x] Mode dev OVH pour flush OPcache, puis retour production
- [x] IP bans cleared (3 bans)
- [x] Re-deploy CLI sur Mac Mini (rsync + uv tool install)
- [x] Re-test asiai bench --quick --card --share → carte pixel-perfect 362KB
- [x] Verification visuelle card page api.asiai.dev → OK

## Phase 7 — MkDocs Review (DONE)
- [x] docs/agent.md — 3x "1.0.0" → "1.0.1" (lignes 236, 643, 684)
- [x] docs/architecture.md — "10 tools" → "11 tools" (ligne 67)
- [x] Build mkdocs --strict clean (5.16s, 9 langues)
- [ ] Review visuelle pages (optionnel — screenshots deja pris)

## Phase 8 — Expert Panel Visual Review
- [ ] Dashboard
- [ ] Docs MkDocs
- [ ] Benchmark Card (apres fix)
- [ ] Banner X

## Phase 9 — Checklist finale pre-push (DONE)
- [x] pytest -x -q pass (631 passed, 7 skipped, 26.82s)
- [x] ruff check clean
- [x] Version 1.0.1 partout (pyproject.toml + __init__.py)
- [x] CHANGELOG a jour ([1.0.1] — 2026-03-13)
- [x] Screenshots reels dans docs/assets/ (6 screenshots PNG)
- [x] MkDocs build --strict (clean, 9 langues)
- [x] Pas de secrets
- [x] P0 card fix resolu
- [x] Mac Mini OK (asiai 1.0.1, agent registered #5)
- [x] API community OK (5 agents, 2 active 24h)
