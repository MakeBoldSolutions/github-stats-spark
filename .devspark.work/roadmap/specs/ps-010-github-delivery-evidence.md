---
id: ps-010
title: GitHub delivery evidence
status: proposed
order: 75
depends_on: [ps-003]
blockers: []
delivery: []
---

# ps-010: GitHub delivery evidence

## Outcome

For each registered repository the platform retains CI run results, pull-request flow, releases and tags,
deployment records where GitHub provides them, and Dependabot pull requests, as timestamped evidence.

## Current Reality

`fetcher.py` summarizes issues, PRs, and Actions at a point in time; there are no run-level records, tags,
releases, or deployment events, and nothing retained. Attention scoring already consumes PR signals.

## Scope and Independence

In scope: incremental collection (since last observation) of workflow runs (conclusion, SHA, branch, times),
PR open/merge/age, releases and tags, GitHub deployment/environment statuses when present, and
Dependabot PRs matched to alerts only when GitHub provides a reliable link; stored as observations;
repository view showing recent delivery activity; collection independent of push-based caching.

Out of scope: inferring deployment from CI success, release timeline UI (ps-015), roadmap links (ps-013).
Standalone: richer, retained repository intelligence.

## Future Health

Records keep SHA and URLs as stable identifiers for ps-015. Honor rate limits using conditional requests
(ETag) where supported.

## Dependencies and Decisions

Open: history depth on first collection; which workflow is the "deploy" workflow (per application, later).
Verify GitHub deployment API availability for the repositories in use.

## Completion Expectations

Run, release, and PR records appear without duplicates across repeated collections; a repository without
Actions or releases shows "none" distinctly from "unavailable"; pytest covers incremental collection and
rate-limit behavior.
