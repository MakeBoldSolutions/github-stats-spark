---
id: ps-007
title: Alert history and remediation metrics
status: proposed
order: 70
depends_on: [ps-006]
blockers: []
delivery: []
---

# ps-007: Alert history and remediation metrics

## Outcome

The platform shows new, resolved, recurring, and aging alerts, historical security debt, and remediation
turnaround at portfolio, client, and repository level.

## Current Reality

ps-006 stores alert records and per-collection observations; nothing interprets them over time yet.

## Scope and Independence

In scope: lifecycle derivation (opened, fixed, dismissed, reopened/recurring) from stored observations;
security-debt and median/percentile time-to-remediate calculations; trend chart and new/resolved badges
using existing Chart.js components; configurable retention with compaction; source-removed alerts shown
as such, not "resolved"; freshness indicators.

Out of scope: notifications, reports, new scoring models.
Standalone: adds analysis to a working security view.

## Future Health

Deterministic calculations, reusable by reports (ps-018). Retention policy shared with other collectors.

## Dependencies and Decisions

Open: default retention (suggest daily-collapsed beyond 90 days, keep alert lifecycle indefinitely).

## Completion Expectations

A test alert shows new, then resolved with a turnaround time; failed collections do not close alerts;
retention prunes without losing lifecycle facts; pytest covers derivation and edge cases (reopen, source
removed, gaps in collection).
