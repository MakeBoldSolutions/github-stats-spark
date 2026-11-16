---
id: ps-008
title: Notifications
status: proposed
order: 140
depends_on: [ps-007]
blockers: []
delivery: []
---

# ps-008: Notifications

## Outcome

The administrator is told once about events needing attention: a new critical/high alert and, when
ps-011 exists, a site that stays down or a certificate near expiry, without polling the dashboard.

## Current Reality

No notification mechanism exists; ps-007 supplies "new" detection.

## Scope and Independence

In scope: one optional channel, ntfy (approved), with server URL, topic, and optional access token held
in the encrypted secret store, per-event thresholds,
de-duplication and recovery notices, and delivery failures that never break collection. Disabled by default.

Out of scope: multiple channels, per-client routing, digests (reports cover those).
Standalone: inactive until configured.

## Future Health

One small sender interface with one implementation. Messages contain no secrets or full payloads and
follow ps-005 policy for private/client names.

## Dependencies and Decisions

Open: self-hosted vs public ntfy server (a public server means notification text leaves the LAN, so keep
it free of private/client names unless self-hosted); inclusion of private/client names.

## Completion Expectations

A new critical alert yields exactly one notification across repeated runs; failures are logged and visible
in status; unconfigured sends nothing; pytest covers dedupe, recovery, and failure.
