# BMAD asiai — pilotage allégé multi-projets

**Statut** : activé 2026-05-07 par JMN, format allégé conforme [ADR BMAD pilote](../../../claude-shared-wiki/wiki/decisions/bmad-pilot-mon-impot-v2.md).

**Périmètre BMAD étendu** (décision JMN 2026-05-07 14:08, override partiel claude-config Q4) :

**Pile build (sprints classiques)** : 3 projets liés mais découplés
- `asiai` (CLI principal v1.5.0, monitoring/bench)
- `asiai-inference-server` (fleet manager v0.1, sub-CLI `asiai engine`)
- `asiai-api` (PHP, leaderboard public)

**Pile R&D bench** (sprints custom Bench-X parallèles) :
- Bench M5/M4/M1 (cascade hardware)
- Choix Qwen 3.6 dense vs A3B (modèles/moteurs)
- Optimisations futures (thermal, KV cache, etc.)

**Trade-off conscient** : extension du canon BMAD, à valider/affiner dans le retex final.

## Format allégé (héritage ADR mon-impot V2 + retex claude-config 2026-05-07 + extension R&D bench 2026-05-07 14:08)

### Pile build (séquentielle)

| Sprint | Rôle | Livrables |
|---|---|---|
| **0** | analyst seul | Cartographie 3 backlogs, dépendances cross-projets, user stories candidates, audit dette (.env legacy, désynchros, bugs prod) |
| **0.5** | PM court (1 sprint) | Validation roadmap consolidée avec JMN — escalade décisions ouvertes Sprint 0 |
| **1** | architect software | Décisions transverses build (cascade fleet, integration asiai↔aisrv↔api, secrets process) |
| **2-3** | dev (instance asiai) | Implémentation user stories priorisées par sprint |
| **4** | QA | Critères acceptation cross-projets + retex format BMAD allégé |

### Pile R&D bench (parallèle, sprints Bench-X)

| Sprint | Rôle | Livrables |
|---|---|---|
| **Bench-0** | **Architect bench/LLM** (dépositaire constant, transverse à toutes campagnes) | Protocole méthodologique : prompts standards, métriques, conditions (warmup, thermal, cool-down), critères qualité, anti-biais |
| **Bench-1** | Benchmarker(s) | Matrice campagne X (modèles × moteurs × hardware) appliquant protocole Bench-0 |
| **Bench-1.5** | PM (JMN) | Validation explicite matrice + protocole AVANT exécution |
| **Bench-2** | Benchmarker(s) // par hardware | Exécution + données brutes + logs |
| **Bench-3** | **Architect bench/LLM** (validation méthode) | Audit méthodologique : protocole respecté ? biais ? variance ? prompts représentatifs ? — pas audit des résultats |
| **Bench-4** | Benchmarker | Rapport final + recommandations |

**Architect bench/LLM = constant**, supervise plusieurs campagnes (Phase 1 M5, Phase 2 thermal, etc.). Multi-benchmarkers parallélisables (1 par hardware).

**Règles** :
- **SM banni** (1 dev = moi, vélocité/cérémonies/facilitation sans valeur)
- **PM court 1 sprint** entre Analyst et Architect (recommandation claude-config Q2)
- Chaque rôle libre des templates BMAD canoniques de sa phase
- Pas d'auto-activation de rôles supplémentaires (escalade JMN si blocage réel)
- Retex JMN régulier (chaque sprint)

## Sprints

- [Sprint 0 — Analyst](sprint-0-analyst/) : en cours (démarré 2026-05-07)
- Sprint 0.5 — PM court : pending (post-analyst, validation JMN)
- [Sprint 1 — Architect](sprint-1-architect/) : pending
- [Sprint 2 — Dev](sprint-2-dev/) : pending
- [Sprint 3 — Dev](sprint-2-dev/) : pending
- [Sprint 4 — QA](sprint-3-qa/) : pending

## Coordination

- **Wiki transverse** : [bmad-asiai.md](../../../claude-shared-wiki/wiki/decisions/) (à créer post-sprint 0)
- **claude-config** : whisper validation processus secrets OVH (msg-1778150391, 2026-05-07 12:38)
- **Hors scope BMAD asiai** :
  - mon-impot (BMAD séparé, pilote initial Epic 6)
  - openclaw/Hermes (pivot ADR-010, pas de coordination BMAD)
