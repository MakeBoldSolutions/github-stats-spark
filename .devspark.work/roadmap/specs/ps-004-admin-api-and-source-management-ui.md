---
id: ps-004
title: Admin API and management UI
status: proposed
order: 40
depends_on: [ps-003]
blockers: ["Developer decision: initial GitHub authentication strategy (PAT vs GitHub App)"]
delivery: []
---

# ps-004: Admin API and management UI

## Outcome

An administrator signs in to the web interface, registers a GitHub organization and an individual
repository, validates access, saves, and sees those repositories in the next collection run. They can also
create clients, projects, and applications and associate repositories with them; sources can be edited,
enabled, disabled, removed, and individual repositories included or excluded.

## Current Reality

The app is static and anonymous; nothing can write configuration. ps-003 provides the registry, domain
tables, and access validation.

## Scope and Independence

In scope: a small FastAPI service (existing Python stack) for registry/domain CRUD, access validation,
"refresh now", and status, with admin authorization on every write and on sensitive reads; named GitHub
connections (`kind: pat` first, schema ready for `kind: app`); credentials server-side only, never
returned by the API, in frontend assets, logs, or reports; validation distinguishing public metadata access
from permission to read Dependabot alerts; Sources and Portfolio pages in the existing React app reusing
current components and accessibility patterns; CSRF/origin protection, security headers, LAN-only binding.

Out of scope: multiple administrators/roles, GitHub App implementation (model only), websites and
integrations beyond GitHub (added by their own items), private-data policy (ps-005), a separate database server.
Standalone: replaces file/DB editing with a secure UI. Until ps-005 ships, the UI manages only
public-data collection.

## Future Health

Thin handlers over the ps-003 modules (SRP); the API is removable without affecting CLI or Pages. Resource
design leaves room for per-client authorization. The worker is triggered through the database, not RPC.

## Dependencies and Decisions

Approved: the administrator credential lives in SQLite (salted slow hash, server-side session); stored
third-party secrets are encrypted with a key kept outside the database. Open: PAT scopes (org policy may block PATs
from org alerts, which would bring the GitHub App forward); client/project naming conventions.

## Completion Expectations

Unauthenticated writes are rejected; a nonexistent org or a token without access shows an actionable error
and saves nothing; credentials never appear in responses, logs, or built assets; sources persist across
`compose down/up`; a saved source is collected on the next run; vitest covers the pages including keyboard
and screen-reader use, pytest covers authorization and validation.
