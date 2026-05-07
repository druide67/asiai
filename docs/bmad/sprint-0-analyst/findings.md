# Findings Sprint 0 Analyst — synthèse SWOT asiai

**Date** : 2026-05-07
**Périmètre analysé** : asiai (CLI), asiai-inference-server (aisrv), asiai-api (PHP) + R&D bench M5/M4

## Résumé exécutif

Trois projets en bonne santé technique mais **mal articulés** post-bascule M5 (2026-05-06). Un bug prod public (leaderboard 89% entrées corrompues) à corriger immédiatement. Cinq bugs aisrv découverts au premier dogfood. R&D bench à activer en parallèle pour ne pas dériver. BMAD adopté pour reprendre le contrôle.

## Forces

### F1 — asiai-inference-server v0.1 livré propre (2 mai)
- 184 tests verts sur M5 (Python 3.14)
- CI matrix vert (3 Python × 2 macOS) post-fix dropping macos-13
- Audit sécurité fait + 4 fixes appliqués (H1 TOCTOU, H2 process_pattern regex, M2 lock 0o600, Q3 keep-logs supprimé)
- Architecture stdlib-only respectée (zéro dep runtime)
- Code review code-reviewer agent : "184 tests pass, ruff clean, audit clean"

### F2 — aisrv plugin asiai engine fonctionne grandeur nature
- Entry point `asiai.subcommands` discovery OK
- `asiai engine list` montre les 4 manifestes (lmstudio/ollama/omlx/turboquant)
- Cold-start préservé via lazy thunks (skip discovery sur `--version`/`--help`)
- Premier dogfood install Ollama : daemon UP (`health_ok: True`), 9 modèles M1 visibles

### F3 — Migration M5 réussie sans perte
- 95 GB modèles rapatriés depuis M1 SMB (Ollama 86 GB + LM Studio 9.2 GB)
- 16 MB metrics.db (403 runs, 402 valides — propre côté local)
- Vault Obsidian 600 KB stratégie privée préservé
- TurboQuant configs (32 KB) sauvés dans aisrv/contrib/
- Repos GitHub à jour, mémoire Claude Code transférée

### F4 — Sécurité processus mature
- claude-config dépositaire SI transverse, validation OVH avant deploy
- 1Password vault avec items dédiés (OVH API Personal, FTP OVH, phpmyadmin, asiai-api Production)
- Workflow `op read | pipe` sans secrets en clair / argv
- Règle "never Read secrets files" appliquée par hooks
- Sudoers asiai-inference scoped strict `com.asiai.*`

### F5 — Tier user M5 Pro 48 GB qwen3.6 sur leaderboard
- 3 samples cohérents 55.6 tok/s sur llamacpp UD Q5_K_M
- Première traction communautaire publique (à exploiter en outreach)

## Faiblesses

### W1 — Bug leaderboard public visible (urgent moyen → urgent élevé)
- 34/38 entrées avec `median_tok_s = 0`, `median_ttft_ms = 0`
- Cause double : code (handle_leaderboard array_median sans filtre) + data (payloads stockés à 0)
- **Impact réputation** : visiteur asiai.dev voit un leaderboard 89% inutile
- Patch PHP prêt (4 lignes), bloqué par validation processus secrets OVH (✅ validé) + Sprint BMAD

### W2 — Cinq bugs aisrv découverts au premier dogfood
1. `aisctl install --dry-run` exige binary installé
2. `aisctl bootstrap --install-sudoers` non-TTY → password sudo timeout
3. `lifecycle.install()` ne crée pas `/var/log/<engine>/` → launchctl fail
4. Sudoers ne couvre pas `sudo /bin/mkdir /var/log/<engine>`
5. `aisctl status` rapporte `stopped` alors que daemon répond healthcheck
- **Impact** : install moteurs M5 nécessite 4 interventions manuelles JMN au lieu de 1 commande
- Couvert par US-003, US-004, US-015, US-016, US-017 (effort total ~2-3h)

### W3 — Backlog dispersé pré-BMAD
- 21 user stories actives sur 4 projets (asiai/aisrv/asiai-api/bench)
- Pas de priorisation explicite avant aujourd'hui
- Risque procrastination (notamment R&D bench, choix Qwen 3.6)
- BMAD activé pour résoudre, format allégé + extension Architect bench/LLM

### W4 — Cascade M4/M5/M1 instable post-pivot Hermes
- ADR-010 openclaw → Hermes Agent change le scope inférence
- Phase H2 → H3 en cours côté openclaw (semaine)
- Hermes-prod va consommer LM Studio :1234 sur M4 (cohabitation à monitor)
- M5 dev/burst éphémère (pas daemon 24/7)
- M1 retrait progressif Phase H 60j
- **Impact aisrv v0.3 fleet manager** : design doit prendre en compte la réalité finale des Macs (pas simple "3 endpoints")

### W5 — Coverage tests intégration aisrv faible
- firewall.py 28%, plist.py 55%, lifecycle.py 57%
- 184 unit tests OK mais intégration mock subprocess manquante
- Risque bugs futurs en intégration non détectés
- Couvert par US-010 (effort 2h)

### W6 — aisai-api : 1 contributeur, 0 test, 1 environnement
- Pas de CI sur asiai-api
- Pas de tests automatisés (juste tests/test_api_readonly.sh + test_sql_injection.sh manuels)
- Patch PHP en prod = peu sécurisé sans staging (OPcache toggle = seul filet)
- **Pas dans le scope Sprint 1 architect** mais à mentionner pour audit futur

## Opportunités

### O1 — Tier user M5 Pro 48 GB qwen3.6 = première traction
- 3 samples sur llamacpp Q5_K_M = utilisateur réel a soumis bench
- Identification + outreach possible (US-R&D-007)
- Témoignage à exploiter en com (Reddit/HN sont morts mais mention possible dans README/site)

### O2 — Bench M5 Max = donnée exclusive
- M5 Max 40 GPU cores 128 GB = config rare
- Premier asiai bench M5 = data point exclusive sur le leaderboard
- Mise en avant mérité (badge "First M5 Max benchmark" ?)

### O3 — Dogfood aisrv v0.1 = retex précieux
- Les 5 bugs découverts en 30 min = valeur du dogfood réel
- Une fois fixés, aisrv v0.1.x sera robuste pour utilisateurs externes
- Renforce le narratif "premier fleet manager Apple Silicon LLM testé en prod réelle"

### O4 — HF Hub cross-engine dedupe (US-007 v0.4)
- Dette modèles dupliqués actuelle = quasi nulle (juste 1 modèle LM Studio M1)
- Mais à mesure que la cascade grandit, dedupe = killer feature
- 100-200 GB économisables sur multi-Mac à terme

### O5 — Coordination Hermes ↔ asiai
- Hermes-prod sur LM Studio :1234 = consommateur visible en production
- asiai monitoring peut apporter la visibilité métrique à Hermes
- Future intégration possible : `asiai monitor --hermes-aware` qui détecte la charge Hermes

## Risques

### R1 — Cohabitation LM Studio :1234 Hermes-prod + asiai bench
- Charge concurrente possible, LM Studio gère mais latence dégradée
- Bench asiai pendant inférence Hermes = mesure faussée
- **Mitigation** : aisrv v0.3 fleet doit savoir "endpoint occupied prod" et basculer M5 burst

### R2 — Bug leaderboard érode confiance avant fix
- Visiteurs asiai.dev voient leaderboard 89% inutile
- Cumul avec Reddit/HN morts (cf. memory `feedback-channels-dead.md`) = peu de canaux pour récupérer
- **Mitigation** : court-circuit BMAD, fix US-001 immédiat (escalade JMN)

### R3 — Dispersion R&D bench
- Sans pilotage Architect bench/LLM, risque dérive (combien de prompts ? quels modèles ? quand on s'arrête ?)
- **Mitigation** : structure BMAD bench adoptée, time-box explicite par sprint Bench-X

### R4 — Sprint 1 architect bloqué par bugs aisrv
- L'architect Sprint 1 doit décider state machine, sudoers extension, log dir convention
- Si dev Sprint 2 doit ralentir pour fixer 5 bugs concurrents, sprint 2 latence allongée
- **Mitigation** : court-circuit P0 pour bugs simples (US-003 dry-run, US-004 non-TTY) avant Sprint 1

### R5 — claude-config retex BMAD limité (mon-impot pas relancé)
- Pas de pratique BMAD en cours dans l'écosystème instances
- asiai pilote en parallèle de mon-impot = double risque pédagogique
- **Mitigation** : retex JMN régulier après chaque sprint, ajustements format en cours de route

### R6 — M5 setup encore incomplet (LM Studio cask brew bug)
- `brew install --cask lm-studio` plante sur M5 Tahoe 26.4.1
- Workaround : install manuel depuis lmstudio.ai
- Sans LM Studio, bench cross-engine impossible
- **Mitigation** : install GUI manuel par JMN, à faire avant Bench-2

## Décisions ouvertes (input PM Sprint 0.5)

1. **US-001 patch leaderboard** : court-circuit BMAD ou séquencer Sprint 2 ?
2. **US-014 setup M5 install moteurs** : continuer dogfood (LM Studio + oMLX + TurboQuant) ou stop à Ollama et fix bugs aisrv d'abord ?
3. **Bench-0 timing** : démarrer parallèle Sprint 0 ou attendre Sprint 1 architect ?
4. **Hermes coordination** : whisper thread dédié `cascade-inference` ou ad-hoc ?
5. **R&D outreach tier user M5 Pro 48 GB** : prioriser US-R&D-007 ou attendre Bench-2 pour avoir M5 Max résultats à publier en complément ?

## Hand-off PM (Sprint 0.5)

Les 3 livrables Sprint 0 (`findings.md`, `user-stories-candidates.md`, `dependency-map.md`) constituent le pack handoff vers PM/JMN.

**Question structurante PM** : compte tenu de **W1** (bug leaderboard public) et **R2** (érosion confiance), est-ce qu'on préserve le séquencement BMAD pur (analyst → PM → architect → dev) ou on accepte un court-circuit pour les 3 US les plus simples (US-001, US-013, US-018) qui sont des fix < 1h chacun ?

Le format BMAD allégé adopté autorise l'escalade JMN si blocage avéré. **Proposition analyst** : court-circuit oui, en mode "express lane" P0, avec retex documenté dans le retex Sprint 4 QA.
