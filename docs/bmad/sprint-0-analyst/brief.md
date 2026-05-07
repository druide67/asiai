# Sprint 0 — Analyst — Cartographie multi-projets asiai

**Démarrage** : 2026-05-07
**Échéance** : 2026-05-09 (2 jours analyst pur)
**Sortie attendue** : `findings.md` + `user-stories-candidates.md` + `dependency-map.md`

## Mission

Cartographier en 48h le backlog complet asiai pour permettre à l'architect (sprint 1) et au dev (sprint 2-3) de prioriser sans deviner. Trois projets en cohabitation, plusieurs niveaux de dette, un bug prod, et de la R&D inférence à arbitrer.

## Inputs

### Code & repos
- `~/projets/asiai/` — CLI principal v1.5.0, monitoring + bench
- `~/projets/asiai-inference-server/` — fleet manager v0.1 (livré 2 mai), 184 tests verts
- `~/projets/asiai-api/` — PHP backend leaderboard
- Wiki transverse : `~/projets/claude-shared-wiki/wiki/`

### Mémoire Claude Code
- `~/.claude/projects/-Users-jmn-projets-asiai/memory/` (32 fichiers)
- En particulier : `asiai-product.md`, `project-asiai-inference-server-plan.md`, `rotation-pending-20apr.md`, `feedback-channels-dead.md`

### État opérationnel observé (audit 2026-05-07 sur M5)
- Bug leaderboard prod : 34/38 entrées avec median_tok_s=0 (bug code + bug data)
- Bug aisrv #1 : `aisctl install <engine> --dry-run` exige binary installé
- Bug aisrv #2 : `aisctl bootstrap --install-sudoers` échoue en non-TTY (sudo ask password)
- Dette legacy : 3 .env / configs à auditer (`asiai/.env.local`, `asiai-api/.env`, `~/.config/asiai/agent.json` perms 644)
- Désynchro `__init__.py` : RÉSOLUE (1.5.0/1.5.0)
- Migration M5 : modèles rapatriés (LM Studio 9.2 GB, metrics 16 MB), Ollama 86 GB rsync en cours
- Cascade M4/M5/M1 : à définir (Hermes pas encore lancé sur M4, M5 dev/heavy, M1 archive)

## Livrables analyst

### 1. dependency-map.md
Carte des dépendances cross-projets :
- aisrv `asiai.subcommands` entry-point dépend d'asiai CLI
- asiai-api leaderboard consomme payloads soumis par asiai bench
- aisrv contrib/turboquant/ dépend de configs openclaw legacy (préservé)
- Hermes (futur, hors scope) consommera LM Studio M4 :1234 (aisrv `aisctl engine status`)

### 2. user-stories-candidates.md
User stories par projet, avec :
- Code (US-001, etc.)
- Type (feature / tech-debt / bug / R&D / ops)
- Projet impacté (asiai / aisrv / asiai-api / bench)
- Effort estimé (heures ou jours)
- Dépendances (autres US ou inputs externes)
- Critère acceptation court

Exemples attendus :
- US-001 (bug, asiai-api) Patch handle_leaderboard PHP filter 0 — 30 min
- US-002 (bug, asiai-api) Cleanup data prod payloads avec median=0 — 1h (dépend secrets OVH validés claude-config)
- US-003 (bug, aisrv) Fix `aisctl install --dry-run` skip resolve — 15 min
- US-004 (bug, aisrv) `aisctl bootstrap` mode non-TTY graceful (instructions claires) — 30 min
- US-005 (feature, aisrv v0.2) Profile switching TOML — 3-4j
- US-006 (feature, aisrv v0.3) Fleet manager — 4-5j ★★★
- US-007 (R&D, bench) Bench M5 Phase 1 (Qwen 3.5 ref + 70B + Qwen 3.6 cross-engine) — 4h
- US-008 (R&D, bench) Investigation Qwen 3.6 dense vs A3B variants — 2h
- US-009 (tech-debt, asiai) Audit .env legacy + cleanup — 1h (dépend secrets OVH)
- US-010 (tech-debt, aisrv) Q1 audit tests intégration mock subprocess — 2h
- US-011 (feature, aisrv v1.0) MCP write tools + packaging — 3-4j
- US-012 (feature, aisrv v0.4) HF Hub cross-engine dedupe ★ — 2-3j
- US-013 (R&D, bench) Reseed leaderboard avec données historiques propres — 2h
- US-014 (ops, asiai) Setup M5 install moteurs via aisctl bootstrap — 30 min (dépend US-004 si non-TTY ou JMN terminal)

### 3. findings.md
Synthèse :
- Forces (aisrv v0.1 livré propre, 184 tests, sécurité auditée)
- Faiblesses (3 bugs concomitants, dette legacy, M5 setup partiel)
- Opportunités (1er tier user M5 Pro 48 GB qwen3.6 — traction publique, BMAD permettra d'amorcer)
- Risques (cascade M4/M5 pas encore stabilisée, Hermes pas lancé, bug leaderboard tier-user-visible)

### 4. recommandation priorisation pour architect

Ordre suggéré sprint 1 (architect) → sprints 2-3 (dev) :
1. P0 immédiat : US-001 + US-003 + US-004 (bugs <30 min, déblocage immediate)
2. P0 secrets-dependent : US-002 + US-009 (attente validation claude-config OVH)
3. P0 ops : US-014 (install M5 moteurs en grandeur nature)
4. P1 R&D : US-007 + US-008 (bench M5 Phase 1, parallèle au reste)
5. P2 features aisrv : US-005 v0.2 → US-006 v0.3 ★★★ (cascade) → US-012 v0.4 → US-011 v1.0
6. P3 tech-debt : US-010 (Q1 tests intégration)

## Méthode analyst

Pure analyse, pas de code. Lit les repos, mémoire, wiki. Produit les 3 livrables ci-dessus en markdown.
Ne préemptive pas les décisions architecture (= sprint 1).

## Hand-off architect

Sprint 0 → Sprint 1 = transition explicite avec :
- Les 3 livrables ci-dessus
- Question(s) ouverte(s) listées pour l'architect (max 5)
- Pas d'engagement sur les implémentations (sprint 2-3 décide de l'ordre exact)
