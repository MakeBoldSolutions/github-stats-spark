# Stats Spark Constitution

## Purpose

This constitution defines **architectural principles and non-negotiable boundaries** for the Stats Spark project. It guides decision-making without prescribing implementation details.

---

## Core Principles

### I. Single Responsibility

Each module MUST have one well-defined purpose. Business logic MUST be testable independently of infrastructure (GitHub Actions, CLI, caching). When a module does "too much," split it.

**Size Guidance:**

- Python modules and React components SHOULD stay under 500 lines of code (LOC).
- Modules exceeding 500 LOC MUST carry an inline comment at the top explaining why the size is justified (e.g., large enum table, generated code, proven-stable utility).
- Modules exceeding 800 LOC are presumed to violate single responsibility and MUST be split before additional feature work is merged — unless a Constitution Check in the plan explicitly justifies the exception.

### II. Data Privacy (NON-NEGOTIABLE)

- The CLI, GitHub Actions, and GitHub Pages path MUST ONLY process **public repositories**
- Private repository data MUST be explicitly filtered, even if token provides access, except
  where Principle VII (Self-Hosted Mode) explicitly permits it
- No credentials, tokens, or private activity data MUST persist to cache or output; in
  self-hosted mode, stored credentials are confined to the encrypted registry as defined in
  Principle VII and MUST NOT appear in any cache, export, log, or published output
- **Privacy violations are grounds for immediate rejection—no exceptions**

### III. Fail Fast, Fail Loud

- Validate configuration before expensive operations (API calls, file generation)
- All errors MUST include context and actionable guidance
- No silent failures—operations log to stdout/stderr with timestamps
- Rate limit handling MUST use exponential backoff

### IV. Change-Driven Caching

- Cache invalidation MUST be content-addressed (based on data change, not time)
- Repository data invalidates when `pushed_at` timestamp changes
- Unchanged data MUST NOT trigger API calls
- Force-refresh flag MUST bypass cache when explicitly requested
- Exception: in self-hosted mode (Principle VII), security and monitoring data MAY refresh on
  a time basis, because findings and availability change without any repository push

### V. Accessibility First

- All visual output MUST meet WCAG AA contrast compliance (4.5:1 for text)
- Themes MUST validate color requirements before generation
- No accessibility regressions allowed

### VI. Generated Artifact Boundary

Repository build outputs and coverage artifacts are **not source code** and MUST be excluded from source-code quality gates.

- The following paths MUST be excluded from all source-level security and quality scans: `docs/assets/`, `docs/data/`, `docs/output/`, `htmlcov/`, `output/`, `MagicMock/`, `preview/`, and any path matching `*.min.js` or `*.map`.
- CI security scanners (pip-audit, npm audit, pattern-based secret detection) MUST target only maintained source trees: `src/`, `frontend/src/`, `config/`, `.github/`.
- Audit reports that surface findings exclusively from generated paths MUST label those findings as `NOISE - generated artifact` rather than code violations.
- Maintain an explicit exclusion list in `config/spark.yml` under a `scan.exclude_paths` key so tooling and humans share a single source of truth.
- When adding new generated output directories, update the exclusion list before the first scan run.

### VII. Self-Hosted Mode

The platform MAY run as a private, self-hosted deployment (for example Docker on a trusted LAN)
under the terms below. Self-hosted mode MUST be explicit and opt-in; the CLI, GitHub Actions, and
GitHub Pages path is unchanged and remains bound by Principles II and IV.

- **Private and client data.** Private repositories, security findings, and client-identifying
  data MAY be stored and shown only to the authenticated administrator. Each source or
  repository MUST opt in to private data; the default is public-only.
- **Boundary.** Private and client data MUST live only under the server data root. The Pages
  build, public exports, Git history, `docs/`, and published reports MUST NOT contain or be able
  to read it, and a test MUST enforce this.
- **Authentication.** When private or client data exists, every route that can reveal it MUST
  require authentication; unauthenticated requests MUST receive 401.
- **Secrets.** Administrator passwords MUST be stored only as salted slow hashes. Third-party
  secrets (GitHub tokens, API keys, test logins) MUST be encrypted at rest with a key held
  outside the database. Secrets MUST NOT appear in logs, images, backups in plaintext, or output.
- **Time-based refresh.** Security and monitoring data MAY refresh on a schedule independent of
  repository pushes, subject to rate-limit awareness and backoff (Principle III). Repository
  metadata remains change-driven under Principle IV.
- **Scope.** The deployment is for a single trusted administrator. Exposing it to the public
  internet, or adding other users, requires a further amendment.

---

## Quality Gates

| Metric | Requirement |
|--------|-------------|
| **Test Coverage** | >80% for core calculation and visualization modules |
| **Execution Time** | <5 minutes for users with <500 repositories |
| **Accuracy** | <1% discrepancy vs GitHub native insights |
| **Determinism** | Same input MUST produce same output |
| **SVG Size** | <500KB per visualization |

---

## Boundaries

### What We Process

- Public repositories only (CLI, Actions, and Pages); self-hosted mode adds opt-in private data
  per Principle VII
- Repositories owned by or contributed to by the specified user, or all public repositories of a
  registered organization
- Maximum 500 repositories per run (configurable)
- Maximum 365 days of commit history for heatmaps

### What We Never Do

- Process private repository data outside self-hosted mode
- Publish private or client data to Pages, Git, or any public output
- Store API tokens or credentials in output
- Fail silently without logging
- Make API calls for unchanged repository data (security and monitoring refresh in self-hosted
  mode excepted)
- Merge code that violates privacy principles

---

## Governance

### Dependency Decisions

- New dependencies MUST replace significant custom code OR provide critical functionality
- Prefer standard library solutions over external packages
- Abstractions MUST solve demonstrated problems (no premature optimization)

### Configuration Philosophy

- Configuration options MUST have clear, documented use cases
- Defaults MUST work for 90% of users without modification
- Invalid configuration MUST fail before any processing begins

### Documentation Standards

- Primary user-facing documentation lives in `/.documentation`
- Approved metadata/framework exceptions are limited to the root `README.md`, `frontend/README.md`, `frontend/public/README.md`, `docs/README.md`, and `output/README.md`
- `/docs` is the GitHub Pages publishing source tree (built site artifacts), not the project documentation corpus; governance and harvest workflows MUST treat it as deployment/source output, not as archival documentation content
- Generated outputs go to `output/` and `data/`
- Examples use canonical demo account: `MakeBoldSolutions`
- Canonical repository reference is `https://github.com/MakeBoldSolutions/github-stats-spark` — no `github.com/markhazleton/*` references

### Versioning

- **MAJOR**: Breaking configuration or output format changes
- **MINOR**: New features, new statistics categories
- **PATCH**: Bug fixes, performance improvements

---

## The Constitution Test

Before merging code, ask:

1. **Privacy**: Does this touch private repository data? → If yes, reject, unless it is confined
   to self-hosted mode under Principle VII
2. **Testability**: Can this be unit tested without external services? → If no, refactor
3. **Observability**: Does failure produce actionable error messages? → If no, improve
4. **Efficiency**: Does this avoid unnecessary API calls? → If no, add caching (time-based
   security and monitoring refresh in self-hosted mode excepted)
5. **Accessibility**: Does visual output meet WCAG AA? → If no, fix colors
6. **Size**: Does a modified module exceed 800 LOC? → If yes, split before merging
7. **Generated Output**: Does this add a new generated output directory? → If yes, add it to `scan.exclude_paths` in `config/spark.yml`

---

<!-- SYNC IMPACT REPORT
Version change: 1.1.1 → 1.2.0 (MINOR: new principle and materially expanded guidance; the
public CLI/Pages path is unchanged, so no backward-incompatible redefinition)
Applied amendments: self-hosted mode, approved by the developer in the roadmap review
  (.devspark.work/roadmap/roadmap.md, Decisions); no CAP files were pending.
Modified principles:
  - II Data Privacy: scoped to the CLI/Actions/Pages path; self-hosted exception and encrypted
    credential storage cross-referenced to VII
  - IV Change-Driven Caching: time-based refresh allowed for security/monitoring data in
    self-hosted mode
Added sections: VII Self-Hosted Mode
Modified sections: Boundaries (What We Process / What We Never Do), The Constitution Test (items 1, 4)
Removed sections: none
Templates requiring updates:
  - plan-template.md: no references to Principles II/IV, no change required ✅
  - spec-template.md: no change required ✅
  - tasks-template.md: no change required ✅
  - .knowledge/governance/decisions/: directory absent, nothing to correct ✅
Follow-up TODOs:
  - ps-005 and ps-006 no longer blocked on this amendment; clear their blockers in the roadmap
  - Delivered ps-004 already stores encrypted tokens and an admin hash in SQLite; VII now covers it
  - Open decision for ps-005: LAN HTTP vs internal TLS; whether private names appear in notifications
-->

*Last Amended: 2026-11-16 (v1.2.0 — scoped self-hosted mode)*
