# Dependency map — projets asiai

**Sprint 0 Analyst** — 2026-05-07

## Vue d'ensemble

```
                    ┌──────────────────────────────┐
                    │  asiai (CLI v1.5.0, public)  │
                    │  ~/projets/asiai/            │
                    └──────────────┬───────────────┘
                  monitor / bench  │
                  ┌────────────────┼────────────────┐
                  ▼                ▼                ▼
          ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
          │   moteurs    │  │  asiai-api   │  │  aisrv plugin│
          │   d'inférence│  │   (PHP, prod │  │  (sub-CLI    │
          │  (Ollama,    │  │   leaderboard│  │  asiai engine)│
          │  LM Studio…) │  │   public OVH)│  │              │
          └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
                 │                 │                 │
                 │  HTTP /api/...  │                 │
                 │                 │  POST /bulk-import │
                 │                 │  GET /leaderboard  │
                 │                 │                 │
                 ▼                 ▼                 ▼
          ┌──────────────────────────────────────────────────┐
          │    asiai-inference-server (aisctl, public)       │
          │    ~/projets/asiai-inference-server/             │
          │    install / start / stop / unload / purge       │
          │    + entry points asiai.subcommands              │
          └──────────────────────────────────────────────────┘
                              │
                              │  manifests + sudoers + plist
                              ▼
                    /Library/LaunchDaemons/com.asiai.*
                    /etc/sudoers.d/asiai-inference
                    /var/log/<engine>/
```

## Dépendances build (intra-asiai)

### asiai (CLI principal)

**Dépend de** :
- Aucune dépendance code dur sur les autres repos
- Détecte et appelle les moteurs d'inférence via HTTP (port 11434/1234/...)
- Soumet bench results à `asiai-api` (https://api.asiai.dev/bulk-import.php)
- Découvre asiai-inference-server via Python entry-points `asiai.subcommands` (lazy import, fail-soft)

**Consommé par** :
- Utilisateur final (CLI `asiai detect`, `asiai monitor`, `asiai bench`, `asiai engine` sub-CLI)
- agents Claude Code (futur MCP server v1.0+ aisrv)

### asiai-inference-server (aisrv)

**Dépend de** :
- Python stdlib uniquement (engagement v0.1)
- asiai (optional) : si présent, le plugin `engine` est chargé dans `asiai engine` sub-CLI
- moteurs d'inférence sous le capot (Ollama, LM Studio, oMLX, TurboQuant) — installés via `aisctl install`
- macOS launchctl + sudoers `/etc/sudoers.d/asiai-inference` (com.asiai.* scope strict)
- pfctl pour firewall (optionnel)

**Consommé par** :
- Utilisateur via `aisctl <command>` standalone
- Utilisateur via `asiai engine <command>` sub-CLI (entry point)
- Futur agent MCP (v1.0+ write tools)

### asiai-api (PHP backend OVH)

**Dépend de** :
- MySQL OVH mutualisé (table `asiai_benchmarks`, schema v3)
- FTP OVH cluster102 pour deploy
- API OVH pour OPcache toggle (deploy workflow)

**Consommé par** :
- `asiai bench --share` (POST /bulk-import.php depuis CLI)
- `asiai community --leaderboard` (GET /api/v1/leaderboard)
- Web public asiai.dev (leaderboard view)
- WebMCP `query_asiai_leaderboard` tool (homepage)

## Dépendances opérationnelles (cross-environnement)

### Hardware/cascade

| Mac | Rôle (ADR ouvertu pivot Hermes) | Endpoints inférence |
|---|---|---|
| **M4 Pro Mini 64 GB** (`192.168.0.16`) | Endpoint principal partagé Hermes-prod + asiai monitoring | Ollama :11434, LM Studio :1234 |
| **M5 Max 128 GB** (`192.168.0.47` actuel session) | Burst dev/heavy + asiai bench R&D + Hermes-dev éphémère | À installer (Ollama OK, LM Studio en attente) |
| **M1 Max 64 GB** | Archive 60j Phase H, retrait progressif | OpenClaw figé, pas de cascade |

**Décision openclaw 2026-05-07** : LM Studio :1234 partagé Hermes-prod + asiai. Cohabitation possible (LM Studio gère concurrent), à monitor charge.

### Secrets management

| Item 1P | Vault | Scope | Usage |
|---|---|---|---|
| OVH API Personal | Private | claude-config (transverse) | OPcache toggle ovhConfig (deploy asiai-api) |
| FTP OVH | JMN-SH | partagé asiai/charvet/ouvamonimpot | Upload PHP via lftp |
| phpmyadmin.hosting.ovh.net | Private | asiai-api uniquement | DB cleanup web UI |
| asiai-api Production | Private | asiai-api | Application.seed_key |

### Mémoire Claude Code asiai

`~/.claude/projects/-Users-jmn-projets-asiai/memory/` (32 fichiers)
- `MEMORY.md` (index, à jour 5 mai 2026)
- `asiai-product.md` (source vérité produit)
- `project-asiai-inference-server-plan.md` (plan v0.1 livré + audit fixé)
- `bench-qwen36-results.md` (parité Qwen 3.5 ↔ 3.6 sur Ollama MLX NVFP4 du 17 avril)
- `hardware-m5-max.md` (M5 spec + impact cascade)
- ... (28 autres incluant lessons / décisions / feedback)

## Dépendances externes (non-asiai)

### Wiki transverse claude-shared-wiki

- `wiki/decisions/bmad-asiai.md` — ADR BMAD activé (créé 2026-05-07)
- `wiki/decisions/bmad-pilot-mon-impot-v2.md` — ADR pilote initial
- `wiki/decisions/m5-max-bascule.md` — contexte bascule M5
- `wiki/conventions/secrets-management-op-run.md` — workflow OVH validé claude-config
- `wiki/infrastructure/macbook-m5-max.md` — fiche M5

### Instances Claude Code peer

- **claude-config** (transverse, dépositaire sécurité) : whisper validation OVH + BMAD
- **openclaw** (archivage M1 + PR upstream Synology Chat) : whisper coordination cascade pré-Hermes
- **merlin** (nouvelle, prend relais Hermes) : sync future Hermes ↔ LM Studio :1234
- **mon-impot** (BMAD pilote initial) : indépendant
- **PRISM** (Collège peer review) : si besoin ADR critiques

## Cycles de dépendance — analyse

### Cycle 1 : asiai ↔ aisrv
- aisrv déclare entry-point `asiai.subcommands`
- asiai charge le plugin via importlib lazily
- Pas de cycle dur (lazy import + fail-soft)
- **Risque** : si aisrv casse l'API entry-point (PLUGIN_API_VERSION mismatch), asiai logue un warning mais continue

### Cycle 2 : asiai ↔ asiai-api
- asiai POST bench results → asiai-api stocke
- asiai GET leaderboard ← asiai-api agrège
- Couplage faible (HTTP REST avec validation payload)
- **Risque actuel** : bug agrégation API rend leaderboard obsolète côté CLI consumer

### Cycle 3 : aisrv ↔ moteurs
- aisrv install moteurs via brew + manifests TOML
- aisrv supervise daemons via launchctl
- aisrv unload via API moteur native + restart fallback
- Couplage manifest-driven (4 manifests bundled)
- **Risque** : nouveau moteur = nouvelle PR (pas dynamique)

## Risques de dépendance identifiés (input architect)

1. **Hermes ↔ LM Studio :1234 cohabitation** : Hermes-prod va consommer le port à temps plein. asiai bench ou aisctl unload pendant un appel Hermes → 500/timeout côté Synology Chat. **Mitigation** : aisrv v0.3 fleet manager doit savoir détecter "endpoint occupé prod" et basculer M5 burst.

2. **Bug leaderboard public** : 34/38 entrées avec médiane 0 = première impression terrible pour visiteur asiai.dev. **Mitigation** : US-001 patch PHP avant 2026-05-09 (avant retex Sprint 0).

3. **Sudoers `aisctl bootstrap` non-TTY** : empêche dogfood automatisé en CI ou dans agent Claude. **Mitigation** : Sprint 1 architect tranche entre askpass GUI / instructions claires / NOPASSWD pré-provisionné.

4. **Memory Claude Code partagée fragile** : si transfert via rsync brisé (ex: bascule M5), perte d'historique. **Mitigation** : claude-config gère, hors scope asiai mais à monitorer.

5. **Wiki transverse async** : décisions transverses peuvent dériver entre instances. **Mitigation** : `/wiki-query` réflexe avant redécouverte (règle CLAUDE.md asiai déjà en place).
