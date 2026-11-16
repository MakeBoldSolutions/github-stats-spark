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

Evidence from the repository (branch `001-make-bold-solutions-redesign`, dd322de).

| Area | Status | Evidence |
| --- | --- | --- |
| Pipeline: `spark unified/generate/analyze/cache/config` CLI, JSON per user | Implemented | `src/spark/cli*.py`, `unified_data_generator.py`, `data/users/<slug>/repositories.json` |
| Multi-user collection | Implemented (config-file only) | `users:` in `config/spark.yml` |
| Repository metadata, activity, PRs, issues, Actions summary, dependency parsing | Implemented | `fetcher.py`, `dependencies/`, `models/repository.py` |
| Change-driven cache (`pushed_at`), `SPARK_CACHE_DIR`, force refresh | Implemented | `fetcher.py`, `cache*.py`; constitution Principle IV |
| Rate-limit handling and retries | Partial | `handle_rate_limit` blocks until reset; naive-datetime comparison unverified |
| Dependabot summary (severity counts, availability/reason) | Partial | open state only, first page of 100, no detail/age/advisory/fix/URL (`fetcher.py` ~L1036, ~L1249) |
| Code-scanning summary, repo security feature flags | Partial | same functions |
| Attention scoring (security/PR/dependency/staleness) | Implemented | `unified_data_generator.py`, `ranker.py` |
| React dashboard: attention view, drill-down, filters, export, offline cache | Implemented | `frontend/src/components/*`, `services/dataService.js` |
| GitHub Pages publication (public only) and CI | Implemented | `.github/workflows/generate-stats.yml`, `validate.yml` |
| Tests (pytest, vitest, Lighthouse CI config, a11y audit) | Implemented | `tests/`, `frontend/tests`, `frontend/scripts` |
| Docker/Compose, scheduler, long-running process | Missing | no Dockerfile or compose file |
| Backend API, admin authentication, credential store | Missing | frontend is static and anonymous |
| Source registration, org/repo discovery, dedupe, per-source status | Missing | discovery is `get_user().get_repos()` only |
| Clients/projects/applications/environments model | Missing | — |
| Persistent history, observations, alert lifecycle | Missing | only caches and latest JSON |
| Releases/tags, CI run history, deployments, Dependabot PRs | Missing | Actions *summary* only |
| Website availability, TLS, Lighthouse, synthetic checks | Missing | `screenshot.py` / `web_scraper.py` capture screenshots and page signals for repo sites only |
| Search/analytics integrations, reports (client/PDF), notifications | Missing | markdown/SVG reports for a GitHub user exist |
| DevSpark roadmap consumption | Unverified | format is inspectable: `roadmap.md` plus `specs/ps-NNN-*.md` with YAML front matter (`id`, `status`, `depends_on`, `blockers`, `delivery`); read-only parse appears feasible |
| Provider API capabilities (Clarity, GA4 quotas, CrUX coverage, Search Console access) | Unverified | to verify at the start of each item that depends on them |

**Constitution conflicts** (`.knowledge/governance/constitution.md`): Principle II forbids private
repository data and `exclude_private=True` is the default; Principle IV mandates change-driven caching
with no time-based invalidation; "What We Never Do" bans private data and API calls for unchanged data.
Private data, client data, and time-based security/availability refresh all need developer-approved
amendments, scoped to a self-hosted mode, before the affected items. The public Pages/CLI path stays under
the existing rules.

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

- **Foundation:** container deployment, scheduling, status, persistence, backup (ps-001, 002, 003, 009).
- **Portfolio and sources:** registry, domain model, admin API/UI, GitHub connections, discovery (ps-003, 004).
- **Access and privacy:** admin authentication, private/client data boundary (ps-004, 005).
- **GitHub intelligence:** Dependabot detail and lifecycle, CI/PR/release evidence (ps-006, 007, 010).
- **Website health:** availability/TLS, Lighthouse lab audits (ps-011, 012).
- **Delivery intelligence:** DevSpark roadmap visibility, synthetic smoke checks, release/verification timeline (ps-013, 014, 015).
- **Digital presence:** search visibility, traffic and field performance (ps-016, 017).
- **Communication:** notifications, client/executive reports, optional AI narrative (ps-008, 018, 019).
- **Later, only on demonstrated need:** Trivy/SBOM/OpenSSF Scorecard/OSV, DNS and domain, security headers/TLS
  config, visual regression, application observability, release–regression correlation, Dependency-Track.
  Not specified here; add a PS when a client or project needs one.

## Themes

1. **Self-hosted foundation:**
   [ps-001 Docker foundation](specs/ps-001-docker-foundation.md),
   [ps-002 Scheduled collection and status](specs/ps-002-scheduled-collection-and-status.md)
2. **Portfolio and source management:**
   [ps-003 Source registry and portfolio model](specs/ps-003-source-registry-and-portfolio-collection.md),
   [ps-004 Admin API and management UI](specs/ps-004-admin-api-and-source-management-ui.md),
   [ps-005 Private and client data boundary](specs/ps-005-private-data-boundary.md)
3. **GitHub and security intelligence:**
   [ps-006 Dependabot dashboard and lifecycle](specs/ps-006-dependabot-security-dashboard.md),
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
8. **Operations:** [ps-009 Operational hardening](specs/ps-009-operational-hardening.md)

### Sequence and dependencies

```text
ps-001 → ps-002 → ps-003 ─┬→ ps-004 → ps-005
                          ├→ ps-006 → ps-007 ──────────┬→ ps-008
                          ├→ ps-011 → ps-012           ├→ ps-018 → ps-019
                          ├→ ps-010 ─┐                 │
                          ├→ ps-013  ├→ ps-015 ←─ ps-014 (needs ps-011)
                          └→ ps-016 → ps-017           │
ps-003 → ps-009 (backup/restore is pulled forward once history exists)
```

Recommended order: 001, 002, 003, 004, 006, 009, 011, 007, 010, 005 (before any private or client-owned
data is stored, which is required before client reporting), 012, 013, 014, 015, 008, 016, 017, 018, 019.
`order` values in the items reflect this. History starts accumulating at ps-006, because its value
compounds; note GitHub rate limits cannot be banked, so value comes from retained observations and
incremental requests, not from collecting faster.

**Smallest useful first increment: ps-001** (existing dashboard in Docker on port 8086). The smallest
increment that *monitors real things* is ps-001 → 003 → 006, with ps-011 giving an early website view.
The first release does not need the rest.

## Decisions

**Approved by the developer:**

- **SQLite is the persistent store**; JSON is retained as an export layer for the CLI and Pages.
- **Administrator credentials are stored in SQLite.** Basis: single trusted administrator, no extra
  service. Constraint recorded with the decision: store only a salted, slow password hash (argon2 or
  bcrypt), never the password; stored third-party secrets (GitHub tokens, API keys, test logins) are
  encrypted at rest with a key supplied outside the database (Docker secret or env), so a copied
  database file or backup does not expose them.
- **The constitution will be amended for a scoped self-hosted mode** (private/client data, time-based
  security and monitoring refresh). The public CLI/Pages path stays under the existing rules. The
  amendment itself is made through `/devspark-constitution`, not by this roadmap, and must land before
  ps-005 and ps-006 are delivered.
- **ntfy is the notification channel** (ps-008).

**Recommendations still awaiting developer decision:**

- **FastAPI** for the API.
- **GitHub authentication:** fine-grained PAT connections first, schema ready for GitHub App.
- **Single administrator** signing in against the SQLite-stored credential with a server-side session;
  per-client scoping deferred.
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

None.
