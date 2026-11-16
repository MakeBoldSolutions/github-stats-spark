---
id: ps-019
title: Optional AI-assisted narrative
status: proposed
order: 160
depends_on: [ps-018]
blockers: ["Developer decision: provider, local-model preference, and client-data sharing policy"]
delivery: []
---

# ps-019: Optional AI-assisted narrative

## Outcome

An administrator can optionally generate a draft executive narrative for a report, review and edit it, and
approve it before it is included in anything distributed.

## Current Reality

The project already calls Anthropic for repository summaries (`summarizer.py`, optional, cached). No
report narrative exists.

## Scope and Independence

In scope: a draft generated only from the deterministic report data with source references preserved;
validation that the narrative contains no figures absent from the data; mandatory human review/approval
state; feature disabled when no key is configured; client-data sharing and redaction policy honored.

Out of scope: any AI dependency for collection, monitoring, or the base report; autonomous distribution;
local-model hosting (kept as a future option behind the same interface).
Standalone: removable with no effect on the rest.

## Future Health

Provider behind a small interface so a local model can be swapped in.

## Dependencies and Decisions

Open: provider and data-handling approval for client information.

## Completion Expectations

With no key the feature is absent; a draft cannot be published unreviewed; numeric claims are checked
against report data; pytest covers validation and the disabled path.
