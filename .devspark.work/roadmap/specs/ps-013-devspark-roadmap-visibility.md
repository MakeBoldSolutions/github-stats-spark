---
id: ps-013
title: DevSpark roadmap visibility
status: proposed
order: 100
depends_on: [ps-003]
blockers: []
delivery: []
---

# ps-013: DevSpark roadmap visibility

## Outcome

For projects managed with DevSpark, the platform shows planned and completed roadmap items, their
statuses, dependencies, blockers, and delivery references, linked to the original artifacts, beside
operational status.

## Current Reality

Installed DevSpark roadmaps are Markdown: `roadmap.md` plus `specs/ps-NNN-*.md` (and `specs/complete/`)
with YAML front matter (`id`, `title`, `status`, `order`, `depends_on`, `blockers`, `delivery`); the
root defaults to `.devspark.work/roadmap/` or `roadmap.root`, and a deterministic checker exists
(`roadmap-check`). This repository's own roadmap is a first test subject. Cross-repository reading
and private-repository access are unverified.

## Scope and Independence

In scope: a read-only parser that fetches roadmap artifacts for a repository (GitHub contents API;
configured path per repository) and stores a versioned snapshot; roadmap view per project with status,
dependencies, blockers, and links; display of `delivery` references as links to PRs/commits; staleness
and parse-error reporting. Statuses are shown exactly as recorded; PR merges are shown as evidence, never
as automatic completion. DevSpark remains the editor and source of truth.

Out of scope: editing or creating roadmaps, status inference, an export contract unless parsing proves
unreliable (then propose a small versioned read-only contract in DevSpark, separately).
Standalone: planning visibility without needing releases or monitoring.

## Future Health

Tolerate format drift (unknown fields, legacy ids, `preserve_paths` layouts). Associates items with
releases later in ps-015 using explicit references only.

## Dependencies and Decisions

Open: where roadmaps live for client projects (their repository vs a planning repository, `EXTERNAL` roots).

## Completion Expectations

This repository's roadmap renders with correct statuses and dependency links; a malformed item is reported,
not hidden; no write call is ever made to the source; pytest covers parsing fixtures including legacy layouts.
