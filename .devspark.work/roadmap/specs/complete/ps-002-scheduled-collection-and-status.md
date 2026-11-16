---
id: ps-002
title: Scheduled collection and status
status: complete
order: 20
depends_on: [ps-001]
blockers: []
delivery: ["branch 005-work-ps-002-scheduled-collection", "commit 96fde36", "commit 93c1d2d", "commit 7c104f9"]
---

# ps-002: Scheduled collection and status

## Outcome

The worker refreshes data on a configurable schedule with no manual CLI run, publishes it safely, and the
dashboard shows the last successful refresh and whether the latest run succeeded, partly failed, or failed.

## Current Reality

Collection is a one-shot CLI run (weekly in Actions). `handle_rate_limit` sleeps until reset inside the run
and compares a naive `datetime.now()` with the reset time (verify). A failed run can leave partial files.
No status artifact exists.

## Scope and Independence

In scope: a small scheduler loop in the worker (interval from env, run on start, no overlapping runs);
atomic publication (stage then swap) so `web` never serves a half-written dataset; `status.json` (times,
outcome, failure counts, rate-limit remaining) shown by a small indicator in the existing UI; bounded
handling of rate-limit exhaustion and transient errors (skip, report, resume next cycle); worker
healthcheck/restart policy.

Out of scope: sources, alert detail, history, notifications, a UI redesign. Security-specific cache expiry
is delivered in ps-006.
Standalone: continuously fresh data for today's configured user.

## Future Health

Design the run as "collect for a list of owners/repositories" so ps-003 swaps the input without reworking
the scheduler. Keep the loop out of `cli_handlers.py` (already ~940 lines).

## Dependencies and Decisions

Open: default interval (suggest 6 h); whether AI summaries run in the worker (cost; default off).

## Completion Expectations

Left running, data timestamps advance on schedule; killing the worker mid-run leaves the prior dataset
served intact; an invalid or exhausted token yields visible failed/partial status; pytest covers scheduling,
atomic swap, and status writing.
