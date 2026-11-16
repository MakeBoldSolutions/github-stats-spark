---
id: ps-005
title: Private and client data boundary
status: proposed
order: 85
depends_on: [ps-004]
blockers: ["Constitution amendment for self-hosted mode (approved in principle; must be made via /devspark-constitution)"]
delivery: []
---

# ps-005: Private and client data boundary

## Outcome

Private repositories, security findings, and client-identifying data can be stored and viewed in the
self-hosted app by the authenticated administrator on the trusted LAN, and cannot reach GitHub Pages, Git
history, or public reports.

## Current Reality

Constitution Principle II forbids private data; `exclude_private=True` is the default; Actions commits
`data/` and `docs/` publicly. `is_private` is captured per repository. Authentication from ps-004
protects configuration only.

## Scope and Independence

In scope: constitution amendment (private/client data only in explicit self-hosted mode; Pages and CLI
stay public-only; time-based refresh permitted for security and monitoring data); per-source/repo
"include private" off by default; private and client data confined to the server data root, with the Pages
build and public exports unable to read it (enforced by test); the whole app requires authentication when
such data exists; log-redaction and secret-handling checks; least-privilege token guidance; client
data-scope checks on every query so per-client access can be added later.

Out of scope: roles or client logins, internet exposure, public TLS.
Standalone: opt-in; default behavior unchanged. Must ship before client-owned data or reports are stored.

## Future Health

One visibility/scope check at the data boundary rather than scattered filters. Keep internal-CA TLS possible.

## Dependencies and Decisions

Open: LAN HTTP vs internal TLS; whether private names appear in notifications/reports.

## Completion Expectations

A private repository appears only after login; a test and a tracked-file scan show no private or client data
in Git, `docs/`, or the Pages artifact; unauthenticated requests get 401; secrets absent from logs and images.
