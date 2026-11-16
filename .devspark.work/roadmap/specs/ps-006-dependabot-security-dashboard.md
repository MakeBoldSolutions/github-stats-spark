---
id: ps-006
title: Dependabot dashboard and lifecycle
status: proposed
order: 50
depends_on: [ps-003]
blockers: ["Constitution amendment for time-based security refresh (approved in principle; must be made via /devspark-constitution)"]
delivery: []
---

# ps-006: Dependabot dashboard and lifecycle

## Outcome

A portfolio, client, and repository view of Dependabot alerts with severity, package/ecosystem, advisory
IDs, vulnerable and fixed versions, created/updated/dismissed/fixed dates, age, and a direct GitHub link,
filterable by severity, repository, client, and state. Alert records are stored persistently from the
first collection, so history starts accumulating immediately.

## Current Reality

`fetcher.py` already calls the alerts endpoint but keeps only open-state counts from one page of 100.
`security_summary` distinguishes availability and reason; `AttentionView` ranks repositories using
`active_alert_counts`. The security cache is tied to `pushed_at`.

## Scope and Independence

In scope: full pagination and retained alert detail, written to the store with a stable key (repository +
alert number) and per-collection observations; independent time-based security refresh; separate state
handling (open, dismissed, fixed); an explicit "unavailable / unauthorized / disabled / zero" distinction
with a coverage panel; permission reporting separating public metadata access from Dependabot read
permission; Security view reusing table, filter, export, and accessibility patterns; copy stating that
alerts are not proof of exploitable vulnerabilities and no alerts is not proof of security. Attention
scoring unchanged unless a defect is shown. Collection extracted from the 1400-line `fetcher.py`.

Out of scope: trend/turnaround analysis (ps-007), notifications, Dependabot PR matching (ps-010).
Standalone: works on public data; private data after ps-005.

## Future Health

Alert records are lifecycle-ready for ps-007; security refresh interval is configurable per category.

## Dependencies and Decisions

Open: default state filter (recommend open); retention of dismissed/fixed detail. Verify Dependabot REST
fields and org-level permission behavior against GitHub documentation before delivery.

## Completion Expectations

A repository with over 100 alerts lists all; rows link to GitHub; disabled/unauthorized/failed show
distinct reasons; a quiet repository's alerts refresh on the security interval; pytest covers pagination,
partial failure, 403/404; vitest covers filters and accessibility; existing views and exports unchanged.
