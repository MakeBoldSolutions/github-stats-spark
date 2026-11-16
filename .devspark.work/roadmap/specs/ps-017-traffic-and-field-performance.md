---
id: ps-017
title: Traffic and field performance
status: proposed
order: 135
depends_on: [ps-016]
blockers: ["Developer decision: which providers (GA4, CrUX, Clarity) are in scope"]
delivery: []
---

# ps-017: Traffic and field performance

## Outcome

Sites with the relevant providers show users and sessions, sources, engagement, conversions, landing pages,
organic traffic, device mix, and real-user field performance (Core Web Vitals) with trends, clearly
separated from lab and search metrics.

## Current Reality

No analytics or field-data integration exists. GA4 Data API quotas and property permissions, CrUX
coverage (low-traffic origins have no data), and Microsoft Clarity API scope (not assumed to expose
dashboards, heatmaps, or recordings) are unverified.

## Scope and Independence

In scope: GA4 via the official Data API with a bounded metric set; CrUX API for origins/URLs with data
and an explicit "insufficient data" state; Clarity only for metrics its API actually exposes, added last
and optional; provider metric definitions shown in the UI; daily incremental storage with quota awareness.

Out of scope: a custom visitor tracker or any public ingestion endpoint (separate privacy/consent
decision), session recordings.
Standalone: each provider is independently shippable and optional.

## Future Health

Metrics keep provider and definition metadata so they are not compared across providers. Reuses the
ps-016 integration model.

## Dependencies and Decisions

Open: provider scope; credentials per client; whether client consent is needed to read their analytics.

## Completion Expectations

A configured property shows retained metrics with provider labels; absent CrUX data says "insufficient
data"; quota errors back off and surface in status; pytest covers response mapping and quota handling.
