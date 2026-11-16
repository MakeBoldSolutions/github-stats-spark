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

- System MUST ONLY process **public repositories**
- Private repository data MUST be explicitly filtered, even if token provides access
- No credentials, tokens, or private activity data MUST persist to cache or output
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

- Public repositories only
- Repositories owned by or contributed to by the specified user
- Maximum 500 repositories per run (configurable)
- Maximum 365 days of commit history for heatmaps

### What We Never Do

- Process private repository data
- Store API tokens or credentials in output
- Fail silently without logging
- Make API calls for unchanged data
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

1. **Privacy**: Does this touch private repository data? → If yes, reject
2. **Testability**: Can this be unit tested without external services? → If no, refactor
3. **Observability**: Does failure produce actionable error messages? → If no, improve
4. **Efficiency**: Does this avoid unnecessary API calls? → If no, add caching
5. **Accessibility**: Does visual output meet WCAG AA? → If no, fix colors
6. **Size**: Does a modified module exceed 800 LOC? → If yes, split before merging
7. **Generated Output**: Does this add a new generated output directory? → If yes, add it to `scan.exclude_paths` in `config/spark.yml`

---

<!-- SYNC IMPACT REPORT
Version change: 1.1.0 → 1.1.1
Modified principles: none
Modified sections: Governance → Documentation Standards (canonical demo account changed from `markhazleton` to `MakeBoldSolutions`; added canonical repository reference `github.com/MakeBoldSolutions/github-stats-spark`)
Added sections: none
Removed sections: none
Templates requiring updates:
  - plan-template.md: No changes required ✅
  - tasks-template.md: No changes required ✅
Follow-up TODOs:
  - Verify README.md, setup.py, source, and .documentation examples reference MakeBoldSolutions, not markhazleton ✅
-->

*Last Amended: 2026-08-16 (v1.1.1 — demo account and GitHub reference migration to MakeBoldSolutions)*
