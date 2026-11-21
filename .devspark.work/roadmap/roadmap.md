# Roadmap: GitHub Stats Spark → BoldOps (working name) — Digital Operations Platform

> **BoldOps is a provisional name, not an approved rename.** The repository, package, and product names
> stay as they are until a branding decision is made. No separate codebase is planned.

## Direction

MakeBoldSolutions builds software for itself and clients. GitHub Stats Spark already turns GitHub
activity into repository health and attention rankings. This roadmap evolves it, in the same repository,
into a private, self-hosted platform that connects the lifecycle **Define → Plan → Build → Release →
Observe → Improve** into one evidence-backed story per client, project, application, and website.

It connects evidence from other tools; it does not replace them. GitHub stays the authority for source,
PRs, CI, releases, and GitHub security data. DevSpark stays the authority for plans (BoldOps reads, never
edits, roadmaps). Lighthouse, Search Console, GA4, CrUX, and Clarity stay the authorities for their metrics.

The platform should let a single trusted administrator pick a client or project and see: what exists,
which repositories support it, what is planned and shipped, whether it works and is available, whether
it is secure and maintained, how it performs, whether it is found and used, what changed since last
period, and what to do next. No LLM is required for any core capability.

Ecosystem: **MakeBoldSolutions** (umbrella) · **DevSpark** (method/tooling) · **GitHub** (source of
delivery truth) · **GitHub Stats Spark** (this codebase) · **BoldOps** (working name for the unified
experience) · **client applications and websites** (what is measured).

Operating principles: evidence first (store observations, then conclusions; every reported finding
traces to a source observation and timestamp); never hide missing data (distinguish *zero*, *unavailable*,
*unauthorized*, *unsupported*, *stale*); configuration is separate from collected data; keep operation
manageable by one person; add dependencies and services only when demonstrated need exists.

## Current Baseline

Evidence from the repository on `main` (after ps-023 classification domains, merge c9f1770). Rows marked Missing or Partial are
the remaining roadmap.

| Area | Status | Evidence |
| --- | --- | --- |
| Pipeline: `spark unified/generate/analyze/cache/config` CLI, JSON per user | Implemented | `src/spark/cli*.py`, `unified_data_generator.py`, `data/users/<slug>/repositories.json` |
| Collection for users, organizations, and single repositories | Implemented (ps-021) | worker runs `spark unified` per enabled source; `--slug` scopes output; an org collects all public repos regardless of author; repos use `owner--name` |
| Repository metadata, activity, PRs, issues, Actions summary, dependency parsing | Implemented | `fetcher.py`, `dependencies/`, `models/repository.py` |
| Change-driven cache (`pushed_at`), `SPARK_CACHE_DIR`, force refresh | Implemented | `fetcher.py`, `cache*.py`; constitution Principle IV |
| Rate-limit handling and retries | Partial | worker skips a cycle when remaining quota is low; `fetcher.handle_rate_limit` is unused and its naive-datetime comparison unverified |
| Dependabot alert detail, lifecycle, Security view | Implemented (ps-006) | `src/spark/security/`, `worker/security.py`, `SecurityView.jsx`; all pages and states, public repositories, own refresh interval (`SPARK_SECURITY_INTERVAL`) |
| Dependabot summary used by attention scoring | Partial | still `fetcher.py`: open state only, first page of 100, so a repository with more than 100 open alerts is undercounted in the attention view |
| Code-scanning summary, repo security feature flags | Partial | same functions |
| Attention scoring (security/PR/dependency/staleness) | Implemented | `unified_data_generator.py`, `ranker.py` |
| React dashboard: attention view, drill-down, filters, export, offline cache | Implemented | `frontend/src/components/*`, `services/dataService.js` |
| Header source switcher (users, orgs, repositories, grouped) | Implemented | `UserPicker.jsx`, `useUserOptions.js`; listed from `data/portfolio.json`; hidden on Pages |
| Repository "fix score" prompt | Implemented, generic | `FixScorePromptSection.jsx`; no DevSpark dependency; per-signal guidance |
| GitHub Pages publication (public only) and CI | Implemented | `.github/workflows/generate-stats.yml`, `validate.yml` |
| Tests (pytest 572, vitest 169, Lighthouse CI config, a11y audit); CI validation green | Implemented | `tests/`, `frontend/tests`, `frontend/scripts` |
| Docker/Compose, scheduler, long-running worker, status, healthcheck | Implemented (ps-001, 002) | `docker-compose.yml`, `docker/`, `src/spark/worker/`; stack runs under Portainer on 192.168.1.197:8086 |
| SQLite registry, sources, connections, dedupe, discovery, `portfolio.json` | Implemented (ps-003) | `src/spark/registry/` |
| Backend API, admin authentication, encrypted token store, admin UI | Implemented (ps-004) | `src/spark/api/`, `frontend/src/components/Admin/`; Argon2id, server-side sessions, CSRF, Fernet |
| Backup, restore, rotation, resource limits, log rotation, secrets override | Implemented (ps-009) | `src/spark/backup.py`, `docker-compose*.yml`; backups sit on the same host disk |
| Clients/projects/applications model, classification domains | Implemented (ps-023) | managed lists with create/rename/retire/merge and duplicate suggestions; unknown names rejected; administrator-defined domains (Tier, Type, Lifecycle, Stack seeded) assigned by dropdown or in bulk; exported in `portfolio.json` (`registry/catalog.py`, `registry/domains.py`, Lists and Domains tabs). Environments and websites are not modelled until ps-011 |
| Unified operator UI (one scope, shared components, cross-links) | Missing | Security ignores the source switcher, Health and Security count alerts from different sources, patterns are duplicated per view (ps-022) |
| Persistent history, observations, alert lifecycle | Partial | ps-006 keeps every alert record and writes a counts observation per collection; trends and remediation metrics are ps-007 |
| Releases/tags, CI run history, deployments, Dependabot PRs | Missing | Actions *summary* only (ps-010) |
| Website availability, TLS, Lighthouse, synthetic checks | Missing | `screenshot.py` / `web_scraper.py` capture screenshots and page signals for repo sites only |
| Search/analytics integrations, reports (client/PDF), notifications | Missing | markdown/SVG reports for a GitHub user exist |
| Tiering and signal scoring of the portfolio | Missing | recoverable from tag `archive/004-portfolio-intelligence` (ps-020) |
| DevSpark roadmap consumption | Unverified | format is inspectable: `roadmap.md` plus `specs/ps-NNN-*.md` with YAML front matter (`id`, `status`, `depends_on`, `blockers`, `delivery`); read-only parse appears feasible |
| Provider API capabilities (Clarity, GA4 quotas, CrUX coverage, Search Console access) | Unverified | to verify at the start of each item that depends on them |

**Constitution** (`.knowledge/governance/constitution.md`): amended to v1.2.0 on 2026-11-16. The
original conflicts (Principle II forbade private data; Principle IV forbade time-based refresh) are
resolved by the new Principle VII, Self-Hosted Mode, which permits private and client data and
time-based security and monitoring refresh only in an explicit, authenticated, single-administrator
deployment. The public CLI and Pages path stays under the original rules. ps-005 implements the data
boundary that Principle VII requires.

## Target Architecture

```text
              Docker Compose / Portainer on 192.168.1.197:8086 (LAN only, no inbound internet)

  browser ──► web: static React app (existing) + reverse proxy
                         │  /api
                         ▼
              api: FastAPI (admin auth, registry CRUD, validation, report/data endpoints)
                         │            reads/writes
                         ▼
           volume: bold.db (SQLite, WAL)  +  config/secrets  +  artifacts (audits, screenshots, reports)
                         ▲
              worker: Python scheduler + collectors (existing GitHub collectors, then HTTP/TLS,
                      Lighthouse, Playwright, Search/analytics), independent schedules per category
                         │  outbound HTTPS only
                         ▼
        GitHub · client websites · Lighthouse · Search Console · GA4 · CrUX · (Clarity)
```

Containers: start with `web` and `worker` (ps-001/002). The `api` is the same Python image running
FastAPI and may share the web container's proxy; it is added with ps-004 (a third process, not a new
technology). A Chromium-capable `browser` worker image appears only with Lighthouse/Playwright items, with
concurrency capped at 1–2. No Kubernetes, broker, or database server. CPU-heavy work (Lighthouse) is
scheduled weekly and serialized so it coexists with other home-server workloads.

**Persistence decision (recommended): SQLite.** The JSON-only approach cannot cleanly support
relationships (clients/projects/applications/repositories), deduplication, alert lifecycle, time-series
observations, retention, or consistent concurrent reads while the worker writes. SQLite in WAL mode
gives transactions, queries, and one-file backup with no extra service, and fits one administrator. Keep
JSON as an *export* layer: `data/users/<slug>/repositories.json` and the Pages contract continue to be
produced for the CLI and public site. Configuration tables and collected-observation tables are kept
logically separate, with config backed up as authoritative and observations as retained history.
Revisit only for multiple concurrent writers or very large volumes.

## Domain Model (minimal)

```text
Client (or internal portfolio)  1─* Project  1─* Application  1─* Environment (prod/staging/dev, URL)
Client 1─* GitHubSource (org | user | repo)  1─* Repository (deduped by owner/repo)
Repository *─* Application   (many-to-many; also optionally *─* Project)
Application 1─* Check/Integration binding (availability, Lighthouse, smoke, GA4, GSC, CrUX, Clarity)
Integration (credential reference + scope) 1─* bindings
Observation (subject, kind, value, source, observed_at)  ← all collectors write here
Release (repo, tag/sha, built/tested/released/deployed/verified/healthy states, evidence refs)
Report (scope, period, generated_at, observation references)
```

Rules: a GitHub organization is not assumed to equal a client; sources can be unassigned; explicit
repositories outside registered orgs are allowed; a repository reached by several sources is stored once
with all sources recorded; removing a source or association never deletes observations or unrelated
repositories; every record is scoped to a client (or internal) so per-client access can be added later
without a schema rewrite. No tenants, billing, or multi-admin in this roadmap.

## Capability Map

- **Foundation:** container deployment, scheduling, status, persistence, backup (ps-001, 002, 003, 009), delivered.
- **Portfolio and sources:** registry, domain model, admin API/UI, GitHub connections, discovery, per-source dashboards and switching (ps-003, 004, 021 delivered), classification domains and managed lists (ps-023, delivered), tiering (ps-020, open).
- **Unified experience:** one scope selector, fixed sections, shared components, cross-links (ps-022).
- **Access and privacy:** admin authentication (ps-004, delivered), private/client data boundary (ps-005, unblocked: constitution v1.2.0 amended 2026-11-16).
- **GitHub intelligence:** Dependabot detail and lifecycle (ps-006, delivered), alert history, CI/PR/release evidence (ps-007, 010).
- **Website health:** availability/TLS, Lighthouse lab audits (ps-011, 012).
- **Delivery intelligence:** DevSpark roadmap visibility, synthetic smoke checks, release/verification timeline (ps-013, 014, 015).
- **Digital presence:** search visibility, traffic and field performance (ps-016, 017).
- **Communication:** notifications, client/executive reports, optional AI narrative (ps-008, 018, 019).
- **Later, only on demonstrated need:** Trivy/SBOM/OpenSSF Scorecard/OSV, DNS and domain, security headers/TLS
  config, visual regression, application observability, release–regression correlation, Dependency-Track.
  Not specified here; add a PS when a client or project needs one.

## Themes

1. **Self-hosted foundation:**
   [ps-001 Docker foundation](specs/complete/ps-001-docker-foundation.md),
   [ps-002 Scheduled collection and status](specs/complete/ps-002-scheduled-collection-and-status.md)
2. **Portfolio and source management:**
   [ps-003 Source registry and portfolio model](specs/complete/ps-003-source-registry-and-portfolio-collection.md),
   [ps-004 Admin API and management UI](specs/complete/ps-004-admin-api-and-source-management-ui.md),
   [ps-005 Private and client data boundary](specs/ps-005-private-data-boundary.md),
   [ps-020 Portfolio classification and signal scoring](specs/ps-020-portfolio-classification-and-signal-scoring.md),
   [ps-021 Organization and repository dashboards with source switching](specs/complete/ps-021-source-dashboards-and-switching.md),
   [ps-023 Classification domains and managed lists](specs/complete/ps-023-classification-domains.md)
3. **GitHub and security intelligence:**
   [ps-006 Dependabot dashboard and lifecycle](specs/complete/ps-006-dependabot-security-dashboard.md),
   [ps-007 Alert history and remediation metrics](specs/ps-007-alert-history-and-trends.md),
   [ps-010 GitHub delivery evidence](specs/ps-010-github-delivery-evidence.md)
4. **Website health:**
   [ps-011 Website registry and availability](specs/ps-011-website-availability-monitoring.md),
   [ps-012 Lighthouse audits](specs/ps-012-lighthouse-audits.md)
5. **Active development intelligence:**
   [ps-013 DevSpark roadmap visibility](specs/ps-013-devspark-roadmap-visibility.md),
   [ps-014 Synthetic smoke checks](specs/ps-014-synthetic-smoke-checks.md),
   [ps-015 Release timeline and verification](specs/ps-015-release-timeline-and-verification.md)
6. **Digital presence:**
   [ps-016 Search visibility](specs/ps-016-search-visibility.md),
   [ps-017 Traffic and field performance](specs/ps-017-traffic-and-field-performance.md)
7. **Communication and reporting:**
   [ps-008 Notifications](specs/ps-008-critical-alert-notifications.md),
   [ps-018 Client and executive reports](specs/ps-018-client-and-executive-reports.md),
   [ps-019 Optional AI-assisted narrative](specs/ps-019-ai-assisted-narrative.md)
8. **Operations:** [ps-009 Operational hardening](specs/complete/ps-009-operational-hardening.md)
9. **Unified experience:** [ps-022 Unified operator experience](specs/ps-022-unified-operator-experience.md)

### Sequence and dependencies

```text
ps-001 → ps-002 → ps-003 ─┬→ ps-004 → ps-005
                          ├→ ps-006 → ps-007 ──────────┬→ ps-008
                          ├→ ps-011 → ps-012           ├→ ps-018 → ps-019
                          ├→ ps-010 ─┐                 │
                          ├→ ps-013  ├→ ps-015 ←─ ps-014 (needs ps-011)
                          └→ ps-016 → ps-017           │
ps-003 → ps-009 (backup/restore is pulled forward once history exists)
ps-004 → ps-021 (delivered: org/repo dashboards and switching; extends ps-003/004 collection)
ps-003 → ps-020 (tiering; recovered from archive tag archive/004-portfolio-intelligence; feeds ps-018)
ps-004 → ps-023 (classification domains) → ps-022 (unified UI; also needs ps-006, ps-021) → ps-011 and later views
ps-023 → ps-020 (tier overrides come from the Tier domain)
```

Done so far: 001, 002, 003, 004, 006, 009, 021, 023 (021 was added after the original sequence, at the
developer's request; 022 and 023 were added 2026-11-21 after a UI consistency review). Recommended order
for the rest: 022, 011, 007, 010, 005 (before any private or client-owned
data is stored, which is required before client reporting), 012, 013, 020, 014, 015, 008, 016, 017, 018, 019.
`order` values in the items reflect this. History starts accumulating at ps-006, because its value
compounds; note GitHub rate limits cannot be banked, so value comes from retained observations and
incremental requests, not from collecting faster.

**Smallest useful first increment (done): ps-001** (existing dashboard in Docker on port 8086). The smallest
increment that *monitors real things* is ps-001 → 003 → 006, with ps-011 giving an early website view. Of
that path ps-001, ps-003, and ps-006 are delivered; ps-011 (website availability) is the next item that
adds monitoring without waiting on a decision.

## Decisions

**Approved by the developer:**

- **SQLite is the persistent store**; JSON is retained as an export layer for the CLI and Pages.
- **Administrator credentials are stored in SQLite.** Basis: single trusted administrator, no extra
  service. Constraint recorded with the decision: store only a salted, slow password hash (argon2 or
  bcrypt), never the password; stored third-party secrets (GitHub tokens, API keys, test logins) are
  encrypted at rest with a key supplied outside the database (Docker secret or env), so a copied
  database file or backup does not expose them.
- **The constitution is amended for a scoped self-hosted mode** (v1.2.0, 2026-11-16, Principle VII:
  private/client data, time-based security and monitoring refresh). The public CLI/Pages path stays under
  the existing rules.
- **ntfy is the notification channel** (ps-008).
- **Consistency before more views** (approved 2026-11-21): ps-023 then ps-022 come before ps-011. Defaults
  adopted: seeded domains Tier, Type, Lifecycle (single-choice) and Stack (multi-choice), values retired not
  deleted; client is the top level of the scope selector; sections Overview, Health, Security, Sites,
  Delivery, Presence, Admin; the public Pages dashboard is unchanged.
- **GitHub authentication: fine-grained PAT connections first, schema ready for a GitHub App** (approved
  2026-11-16). One connection per owner; expiry is tracked and surfaced; `GITHUB_TOKEN` remains the fallback.
  The App comes forward if a client wants to grant access themselves, owners multiply, or an org blocks tokens.
  No known organization forbids personal tokens.

**Adopted in delivered work, no further decision needed:**

- **FastAPI** for the API (ps-004), served by the same Python image as the worker.
- **Single administrator** signing in against the SQLite-stored credential with a server-side session;
  per-client scoping deferred (ps-004).
- **Organization dashboards** (ps-021): an organization shows all of its public repositories with activity
  from anyone, not one author's commits; a repository source is its own dashboard.

**Recommendations still awaiting developer decision:**

- **DevSpark integration:** parse existing roadmap artifacts read-only; no export contract unless parsing
  proves unreliable. A milestone is "complete" only if the roadmap says so; PR merges are shown as
  linked evidence, never as inferred completion.
- **Lifecycle states** (built, tested, released, deployed, verified, healthy) are separate, evidence-linked
  states; a green workflow is never shown as "deployed".
- **Safety rules for monitors:** only registered targets; SSRF guard blocking private/loopback/link-local
  and metadata addresses (re-checked after DNS resolution and redirects); no destructive synthetic actions;
  test credentials in the secret store only.

Questions for the developer are summarized in the review response and in each item's Dependencies and
Decisions.

## Delivered

All on `main` and running on the home server (stack `github-stats-spark`, Portainer).

| Item | Result |
| --- | --- |
| [ps-001 Docker foundation](specs/complete/ps-001-docker-foundation.md) | Dashboard served from Docker/Compose on port 8086 |
| [ps-002 Scheduled collection and status](specs/complete/ps-002-scheduled-collection-and-status.md) | Worker collects every 6 hours; status banner shows freshness |
| [ps-003 Source registry and portfolio](specs/complete/ps-003-source-registry-and-portfolio-collection.md) | SQLite registry, discovery, de-duplicated `portfolio.json` |
| [ps-004 Admin API and management UI](specs/complete/ps-004-admin-api-and-source-management-ui.md) | Sign-in, add/edit/disable sources, GitHub tokens, refresh now |
| [ps-009 Operational hardening and backup](specs/complete/ps-009-operational-hardening.md) | Verified backups, restore, limits; rollback drill passed |
| [ps-021 Organization and repository dashboards](specs/complete/ps-021-source-dashboards-and-switching.md) | Each enabled user, org, and repo source has a dashboard and appears in the header switcher |
| [ps-006 Dependabot dashboard and lifecycle](specs/complete/ps-006-dependabot-security-dashboard.md) | Security view of every alert (open, dismissed, fixed) with coverage reasons, filters, CSV export, and stored history |
| [ps-023 Classification domains and managed lists](specs/complete/ps-023-classification-domains.md) | Clients, projects, applications, and domain values chosen from managed lists; Lists and Domains admin tabs; bulk classify; classifications in `portfolio.json` |

Smaller changes made outside the roadmap items: a header user picker (later extended by ps-021), a
follow-up fix so a restarted worker keeps reporting the existing backup, and a generic "fix score"
prompt that no longer refers to a DevSpark command.

Known gaps and notes:

- ps-021: a "collect now" for a single source is not built (the existing Refresh now collects
  everything), and a single-repository source is covered by tests but has not been tried on the server.
- ps-009: backups are on the same disk as the data; an off-host copy is the administrator's step
  (a cron example is in the Docker deployment guide).
- Credentials still to tidy: the initial admin password sits in the stack environment and should be
  changed and removed; the Portainer and GitHub token files should be rotated.
- The constitution amendment landed as v1.2.0 (2026-11-16, Principle VII Self-Hosted Mode); ps-005 is unblocked.
- ps-006: the attention view still scores from `fetcher.py`'s first-page summary rather than the new
  collector (the spec's "extract collection from `fetcher.py`" was not done); ps-022 moves Health and the
  drawer onto the stored alerts. Not yet confirmed on the server: a security refresh against real repositories, which
  also settles the spec's open check of Dependabot REST field shapes (tests use fixtures). This repository's
  own open Dependabot alerts (19 on 2026-11-21) are housekeeping, not part of ps-006.
- ps-023: classifications reach `portfolio.json` but not the per-source `repositories.json` (the collector
  writes it without reading the registry); ps-022 picks this up for per-source filtering. Not yet done on
  the server: back up the registry, deploy (migration 4 runs on start), confirm existing clients and
  assignments on the Lists tab, and merge suggested duplicates. The two Low review findings were fixed
  (d7eb401) and await an independent reviewer's confirmation.

## Where we are and what is next

**Current state (2026-11-21).** The dashboard runs as a three-container stack (web, api, worker) on the home
server. It collects every enabled user, organization, and repository source on a schedule, publishes one
dashboard per source with a header switcher, and is managed through a signed-in admin UI backed by SQLite
with encrypted tokens and verified backups. ps-006 adds a Security view of every Dependabot alert with
stored history. ps-023 replaces free-text assignment with managed lists and administrator-defined
classification domains. CI validation on `main` is green (lint, types, tests, dependency audits).

**Next steps, in recommended order** (all unblocked unless noted):

1. **ps-022 Unified operator experience**: one scope selector every view honours, fixed sections later items
   fill, shared components, one source per number, and cross-links, before more views are added.
2. **ps-011 Website availability**, the first new section (Sites) built on ps-022.
3. **ps-007 Alert history and trends** builds on the alert records ps-006 now keeps.
4. **ps-010 GitHub delivery evidence** (releases, CI runs, deployments).
5. **ps-005 Private and client data boundary**, required before any private or client-owned data or
   client reports. Open decisions: LAN HTTP or internal TLS, and whether private names may appear in
   notifications.
6. **ps-013** (read DevSpark roadmaps) and **ps-020** (portfolio tiering, now unblocked by ps-023) can slot in at any
   point.
7. **Blocked on a developer decision:** ps-012 (Chromium host budget), ps-014 (which application first),
   ps-015 (how a deployment is evidenced), ps-016 and ps-017 (provider access), ps-019 (AI provider and
   client-data policy).

**Housekeeping that is not a roadmap item:** back up the registry, redeploy the stack, confirm a security
refresh on real repositories and the ps-023 Lists tab (merge suggested duplicates); work down this repository's open Dependabot alerts; change the admin password and remove it
from the stack environment; rotate the Portainer and GitHub token files; set up an off-host backup copy;
consider a per-source "collect now"; and have the collector count a lint or test script in `package.json`
as tests so static sites are not flagged for missing tests.
