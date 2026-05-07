# BMAD asiai — pilotage allégé multi-projets

**Statut** : activé 2026-05-07 par JMN, format allégé conforme [ADR BMAD pilote](../../../claude-shared-wiki/wiki/decisions/bmad-pilot-mon-impot-v2.md).

**Périmètre BMAD (software build)** : 3 projets liés mais découplés
- `asiai` (CLI principal v1.5.0, monitoring/bench)
- `asiai-inference-server` (fleet manager v0.1, sub-CLI `asiai engine`)
- `asiai-api` (PHP, leaderboard public)

**Hors scope BMAD** (claude-config Q4 du 2026-05-07) :
- Bench M5/M4 (R&D exploratoire, format libre — `~/projets/asiai/docs/research/bench-m5/`)
- Choix Qwen 3.6 dense vs A3B (idem R&D)
- BMAD est conçu pour le build (livrables mesurables), pas pour la R&D exploratoire.

## Format allégé (héritage ADR mon-impot V2 + retex claude-config 2026-05-07)

| Sprint | Rôle | Livrables |
|---|---|---|
| **0** | analyst seul | Cartographie 3 backlogs, dépendances cross-projets, user stories candidates, audit dette (.env legacy, désynchros, bugs prod) |
| **0.5** | PM court (1 sprint) | Validation roadmap consolidée avec JMN — escalade décisions ouvertes Sprint 0 |
| **1** | architect seul | Décisions transverses (cascade M4/M5, fleet design, integration asiai↔aisrv↔api, secrets process) |
| **2-3** | dev (instance asiai) | Implémentation user stories priorisées par sprint |
| **4** | QA | Critères acceptation cross-projets + retex format BMAD allégé |

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
