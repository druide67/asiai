# User stories candidates — Sprint 0 Analyst

**Date** : 2026-05-07
**Status** : draft analyst (sera priorisé Sprint 0.5 PM avec JMN)

## Légende

- **Type** : `bug` | `feature` | `tech-debt` | `R&D` | `ops`
- **Projet** : `asiai` | `aisrv` | `asiai-api` | `bench` | `cross`
- **Effort** : minutes / heures / jours
- **Priorité suggérée analyst** : P0 (immédiat) | P1 (semaine) | P2 (mois)
- **Dépendances** : autres US ou inputs externes

## Pile build

### Bugs (urgent)

#### US-001 — Patch handle_leaderboard PHP filtrer 0 dans array_median
- Type : bug
- Projet : asiai-api
- Effort : 30 min
- Priorité : **P0**
- Dépendances : secrets OVH (validés claude-config 2026-05-07)
- Critère : `curl https://api.asiai.dev/api/v1/leaderboard | jq '.results[] | select(.median_tok_s == 0)'` retourne `[]`

#### US-002 — Cleanup data prod : DELETE bench_runs avec median_tok_s=0 anciens
- Type : bug
- Projet : asiai-api
- Effort : 1h
- Priorité : **P0**
- Dépendances : US-001 deployé + JMN valide SQL DELETE explicite + accès phpmyadmin web UI
- Critère : count(*) avec all engines.*.median_tok_s = 0 = 0 post-cleanup

#### US-003 — Fix `aisctl install --dry-run` skip resolve binary
- Type : bug
- Projet : aisrv (v0.1.x patch)
- Effort : 15 min + 1 test
- Priorité : **P0**
- Dépendances : aucune
- Critère : `aisctl install ollama --dry-run` ne lève pas si `/opt/homebrew/bin/ollama` absent

#### US-004 — Fix `aisctl bootstrap` non-TTY graceful (instructions claires)
- Type : bug
- Projet : aisrv (v0.1.x patch)
- Effort : 30 min + 2 tests
- Priorité : **P0**
- Dépendances : aucune
- Critère : `echo "" | aisctl bootstrap --install-sudoers` détecte `not isatty` → affiche commande à exécuter manuellement

#### US-015 — `lifecycle.install()` crée `/var/log/<engine>/` avant launchctl load
- Type : bug
- Projet : aisrv
- Effort : 30 min + 1 test
- Priorité : **P0** (bloquant install moteurs sans intervention manuelle)
- Dépendances : US-016 (sudoers extension)
- Critère : `aisctl install ollama` sans `/var/log/ollama/` pré-existant fonctionne

#### US-016 — Étendre sudoers : `sudo /bin/mkdir -p /var/log/com.asiai.*`
- Type : bug
- Projet : aisrv (sudoers.py)
- Effort : 15 min + visudo validation
- Priorité : **P0**
- Dépendances : aucune
- Critère : `aisctl bootstrap --install-sudoers --dry-run` montre la nouvelle règle ; visudo -cf accepte

#### US-017 — `aisctl status` rapporte état correct (state machine)
- Type : bug
- Projet : aisrv (lifecycle.current_state)
- Effort : 1h investigation + fix
- Priorité : **P1**
- Dépendances : peut-être US-016 (sudoers `launchctl list` ?)
- Critère : `aisctl status ollama` affiche `running` quand le daemon répond healthcheck (pas `stopped`)

### Tech debt

#### US-009 — Audit + cleanup .env legacy
- Type : tech-debt
- Projet : asiai + asiai-api
- Effort : 1h
- Priorité : **P1**
- Dépendances : claude-config validation processus secrets (✅ fait)
- Critère : tous les `.env*` du scope asiai ont perms 600. Contenu vérifié pas obsolète/leak.
- État : **partiellement fait** (chmod 600 sur asiai-api/.env + asiai/.env.local). Reste : vérifier contenu pas obsolète.

#### US-010 — Q1 audit aisrv : tests intégration mock subprocess
- Type : tech-debt
- Projet : aisrv
- Effort : 2h
- Priorité : **P2**
- Dépendances : aucune
- Critère : coverage firewall/plist/lifecycle passe de 28-57% à >70%

#### US-018 — Notifier openclaw `config/.env` perms 644 (HORS scope asiai)
- Type : ops (notification)
- Projet : openclaw
- Effort : 5 min whisper
- Priorité : **P2**
- Dépendances : aucune
- Critère : whisper envoyé openclaw

### Features aisrv (roadmap)

#### US-005 — aisrv v0.2 Profile switching TOML
- Type : feature
- Projet : aisrv
- Effort : 3-4j
- Priorité : **P2**
- Dépendances : Sprint 1 architect tranche schema TOML
- Critère : `aisctl profile apply coder-32b` swap engine + model + config en <30s avec rollback automatique sur health-check fail

#### US-006 — aisrv v0.3 Fleet manager multi-Mac ★★★
- Type : feature
- Projet : aisrv
- Effort : 4-5j
- Priorité : **P1** (devient critique post-cascade M4/M5)
- Dépendances : US-005 + cascade openclaw/merlin stable
- Critère : `aisctl fleet status` agrégé 3 Macs en <3s + `aisctl fleet push engine purge` parallèle

#### US-007 — aisrv v0.4 Web cockpit + agent HTTP + HF Hub dedupe
- Type : feature
- Projet : aisrv
- Effort : 6-8j
- Priorité : **P2**
- Dépendances : US-006 + asiai web (intégration mount FastAPI)
- Critère : `asiai web` montre onglet Engines / Profiles / Fleet ; HF dedupe symlinks Ollama/LM Studio/mlx-lm depuis store central

#### US-008 — aisrv v1.0 MCP write tools + packaging PyPI/Homebrew
- Type : feature
- Projet : aisrv
- Effort : 3-4j
- Priorité : **P2**
- Dépendances : US-006 + US-007
- Critère : `pipx install asiai-inference-server` + 10 MCP write tools fonctionnels depuis Claude Desktop

#### US-019 — aisrv v0.5+ Thermal management M5 Max
- Type : feature
- Projet : aisrv
- Effort : 3-4j
- Priorité : **P3** (post v1.0)
- Dépendances : US-008
- Critère : `aisctl fleet status --thermal` montre throttling SMC + profil "Silent" cap ressources

### Features asiai

#### US-011 — asiai v1.1 alerting webhook
- Type : feature
- Projet : asiai
- Effort : 1j
- Priorité : **P2**
- Dépendances : aucune
- Critère : `asiai monitor --alert-webhook URL` POST sur transitions état moteur

#### US-012 — asiai v1.1 VRAM LM Studio reporting
- Type : feature
- Projet : asiai
- Effort : 0.5j
- Priorité : **P2**
- Dépendances : aucune
- Critère : `asiai monitor` affiche VRAM allouée par LM Studio (actuellement vide ou 0)

#### US-013 — asiai bench `--no-share-on-error` (anti-pollution leaderboard)
- Type : bug → feature
- Projet : asiai
- Effort : 30 min
- Priorité : **P1**
- Dépendances : US-001 (sinon le filtre côté API protège déjà)
- Critère : un run `asiai bench` qui échoue ne POST pas à `bulk-import.php` par défaut

### Ops

#### US-014 — Setup M5 install moteurs grandeur nature
- Type : ops
- Projet : aisrv (dogfood)
- Effort : 1h (avec workarounds bugs US-003/004/015/016)
- Priorité : **P0**
- Dépendances : US-015/016 ou contournement manuel par JMN
- État : **partiellement fait** (Ollama UP via aisctl, LM Studio install pending)
- Critère : Ollama + LM Studio + (oMLX optional) tous installés via aisctl, listés dans `aisctl status`

#### US-020 — Désynchro `__init__.py` vs `pyproject.toml` asiai
- Type : tech-debt
- État : **résolue** (1.5.0/1.5.0 sur M5, mémoire signalait 0.2.0-dev mais c'était périmé)
- Priorité : **closed**

## Pile R&D bench (parallèle, sprints Bench-X)

#### US-R&D-001 — Bench-0 Architect bench/LLM : protocole méthodologique général
- Type : R&D (méthode)
- Projet : bench (transverse)
- Effort : 1-2j
- Priorité : **P1**
- Dépendances : aucune (parallèle Sprint 0/1)
- Critère : Document constant `~/projets/asiai/docs/research/bench-method/protocol.md` couvrant prompts standards, métriques retenues, conditions (warmup, thermal, cool-down), critères qualité, anti-biais

#### US-R&D-002 — Bench-1 M5 Phase 1 : matrice campagne
- Type : R&D (matrice)
- Projet : bench
- Effort : 0.5j
- Priorité : **P1**
- Dépendances : US-R&D-001
- Critère : matrice Qwen 3.5/3.6 × {Ollama, LM Studio, llamacpp} × {M5, M4, M1} avec hypothèses testables et budget temps

#### US-R&D-003 — Bench-2 M5 Phase 1 : exécution // par hardware
- Type : R&D (exécution)
- Projet : bench
- Effort : 4h max
- Priorité : **P1**
- Dépendances : US-R&D-002 validée par PM (toi)
- Critère : données brutes + logs reproductibles dans `~/projets/asiai/docs/research/bench-m5/phase-1/raw/`

#### US-R&D-004 — Bench-3 audit méthode appliquée
- Type : R&D (audit)
- Projet : bench
- Effort : 1h
- Priorité : **P1**
- Dépendances : US-R&D-003
- Critère : rapport audit par Architect bench/LLM identifie biais éventuels, valide variance, recommande retry si besoin

#### US-R&D-005 — Bench-4 rapport final + recommandations
- Type : R&D (rapport)
- Projet : bench
- Effort : 1h
- Priorité : **P1**
- Dépendances : US-R&D-004
- Critère : `~/projets/asiai/docs/research/bench-m5/phase-1/REPORT.md` avec recommandations cascade M4/M5 + choix Qwen 3.6 dense vs A3B

#### US-R&D-006 — Investigation Qwen 3.6 dense vs A3B
- Type : R&D (exploration)
- Projet : bench
- Effort : 2h
- Priorité : **P1**
- Dépendances : aucune (parallèle au bench)
- Critère : inventaire variants disponibles (HF Hub, Ollama Library, mlx-community), critères choix documentés

#### US-R&D-007 — Investigation tier user M5 Pro 48 GB qwen3.6 leaderboard
- Type : R&D (intel)
- Projet : bench
- Effort : 30 min
- Priorité : **P2**
- Dépendances : US-001 (leaderboard fixed)
- Critère : whois + setup identifié = traction publique première à exploiter (témoignage / outreach)

## Question(s) ouverte(s) pour PM (Sprint 0.5)

1. **Ordre exécution P0** : faut-il bloquer Sprint 1 architect tant que tous les bugs aisrv (US-003/004/015/016/017) ne sont pas fixés, ou procéder en parallèle (architect peut écrire les décisions sur le state machine pendant que dev fixe les bugs simples) ?
2. **US-001 patch leaderboard** : court-circuit BMAD (escalade JMN → fix immédiat hors sprint) ou laisser le séquencement Sprint 1 architect → Sprint 2 dev ? Le bug est public et donne une mauvaise image asiai.dev.
3. **Bench-0 vs Sprint 0** : démarrer Bench-0 Architect bench/LLM en parallèle Sprint 0 build (timing favorable, pas de dépendance) ou attendre Sprint 1 ?
4. **Hermes coordination** : quand merlin sera actif, comment synchroniser le scope cascade asiai (US-006) avec leur intégration LM Studio :1234 ? Whisper thread dédié ?
5. **OVH cleanup data prod (US-002)** : tu valides personnellement chaque DELETE SQL via phpmyadmin web UI ? Oui par défaut, claude-config recommande explicitement cette validation manuelle.

## Recommandation priorisation pour PM (Sprint 0.5 → Architect Sprint 1)

**Vague P0 immédiate (recommandée court-circuit BMAD)** :
- US-001 (patch leaderboard) — public-facing critique, 30 min
- US-002 (cleanup data prod) — corollaire US-001, 1h
- US-013 (no-share-on-error CLI) — anti-pollution future, 30 min

**Vague P0 dogfood aisrv (Sprint 1 architect tranche, Sprint 2 dev exécute)** :
- US-003, US-004, US-015, US-016, US-017 (5 bugs aisrv découverts dogfood)
- Effort total : 2-3h

**Vague P0 ops setup M5** :
- US-014 (install moteurs grandeur nature, partiellement fait Ollama)

**Vague P1 R&D bench parallèle Sprint 0** :
- US-R&D-001 → US-R&D-005 (campagne complète Bench M5 Phase 1, ~3-4j si tout va bien)
- US-R&D-006 (Qwen 3.6 variants)

**Vague P1 features critiques** :
- US-006 (aisrv v0.3 fleet ★★★)
- US-005 (aisrv v0.2 profile switching, prérequis fleet)

**Vague P2 features secondaires** :
- US-007, US-008, US-011, US-012

**Vague P2 tech debt** :
- US-009 (audit env legacy contenu)
- US-010 (Q1 tests intégration aisrv)

**Vague P3** :
- US-019 (thermal management)
- US-018 (notification openclaw)
- US-007 (HF dedupe ★ killer feature, mais effort 6-8j)

**Backlog total** : 21 user stories actives (+1 closed). Effort cumulé estimé : ~25-32 jours-personne sur 6 mois.
