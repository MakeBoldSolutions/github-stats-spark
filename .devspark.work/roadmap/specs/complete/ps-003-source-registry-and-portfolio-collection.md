---
id: ps-003
title: Source registry and portfolio model
status: complete
order: 30
depends_on: [ps-002]
blockers: []
delivery: ["branch 005-work-ps-003-source-registry", "commit 801a9b7", "commit 6d2dc18"]
---

# ps-003: Source registry and portfolio model

## Outcome

Collection runs against a durable registry of GitHub sources (organizations, `owner/repo`, optionally
users) and a minimal portfolio model (clients, projects, applications, repositories) instead of a hardcoded
username, producing one de-duplicated repository portfolio with per-source status that explains failures.
Collected data begins accumulating in a persistent store.

## Current Reality

The only source definition is `users:` in `config/spark.yml`; discovery is `get_user().get_repos()` only.
No organization or explicit-repository entries, include/exclude, dedupe, or per-source status. Output is
JSON keyed by user (`data/users/<slug>/`) with no persistent history.

## Scope and Independence

In scope: SQLite database on a persistent volume (WAL, versioned migrations) holding configuration tables
(client, project, application, source, repository, associations, connection references) separately from
collected-data tables; seeded from `users:` on first start; source types `org`, `repo`, `user`; paginated
organization discovery repeated each cycle; dedupe by case-insensitive full name with all contributing
sources recorded; repository include/exclude; optional association of repositories to client/project/
application (unassigned allowed); per-source status (state, repository count, last discovery, actionable
error: not found, no access, SSO required, rate limited); a validate-access function reused by ps-004;
JSON exports unchanged for the CLI and Pages (`data/users/...`) plus a portfolio export for the app.
Removing a source or association never deletes collected data or repositories still reached elsewhere;
pruning is an explicit admin action.

Out of scope: web UI/API, websites and environments (ps-011), credential management UI, private data policy.
Standalone: multi-owner, org-capable collection with CLI and Pages unchanged.

## Future Health

Keep storage, registry logic, and fetcher separate; do not grow `fetcher.py`. Every record carries a
client scope (nullable = internal). Observations use a generic (subject, kind, value, source, observed_at)
shape so later collectors need no schema redesign. JSON remains an export, not a second source of truth.

## Dependencies and Decisions

SQLite is approved. Open: whether `user` sources ship now (recommend yes); archived/fork defaults; orphan
data prune policy (recommend explicit admin action only).

## Completion Expectations

An org plus an explicit repo it also contains yields one repository; a new org repository appears next
cycle; a bad source reports an actionable status; removing a source leaves overlapping repositories intact;
database and registry survive container recreation; pytest covers migrations, dedupe, pagination, error
mapping; CLI, JSON contracts, and Pages workflow unchanged.
