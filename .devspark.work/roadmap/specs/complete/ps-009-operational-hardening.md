---
id: ps-009
title: Operational hardening and backup
status: complete
order: 55
depends_on: [ps-003]
blockers: []
delivery: ["branch 001-work-ps-009-operational-hardening", "commit ef81314", "commit 001fb11", "commit ccd482c"]
---

# ps-009: Operational hardening and backup

## Outcome

The stack runs unattended for months, its history is protected, and it can be upgraded, rolled back, and
restored by one person from documented steps and validated automatically.

## Current Reality

Basic safety arrives earlier (non-root, atomic publish, status). Once ps-003 creates persistent history,
backup and migration become essential, so this item is sequenced right after history starts, not last.

## Scope and Independence

In scope: healthchecks and staleness detection for web/api/worker, restart policy and resource limits
(including coexistence with other home-server workloads), log rotation, image version tags and release
build, Docker secrets for credentials, SQLite backup (online backup, rotation) and restore, config vs
history backup guidance, upgrade/rollback including database migration, post-deploy smoke script.

Out of scope: external monitoring stacks, HA, public exposure.
Standalone: improves any state of the stack delivered so far.

## Future Health

Backup covers artifacts directories as later items add them. Compose stays portable between local and Portainer.

## Dependencies and Decisions

Open: build on server vs registry; backup destination.

## Completion Expectations

A stalled worker turns health red within one interval; restoring database and secrets on a clean host
reproduces sources and history; an upgrade and rollback are exercised once with data intact.
