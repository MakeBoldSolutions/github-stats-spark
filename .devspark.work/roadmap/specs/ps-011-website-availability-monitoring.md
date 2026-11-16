---
id: ps-011
title: Website registry and availability monitoring
status: proposed
order: 60
depends_on: [ps-003]
blockers: []
delivery: []
---

# ps-011: Website registry and availability monitoring

## Outcome

The administrator registers applications' environments (production, staging, dev) with URLs and sees
availability, response time, redirect behavior, TLS expiry, uptime percentages, and incidents, per
application, client, and portfolio.

## Current Reality

No uptime or TLS monitoring exists. `web_scraper.py` and `screenshot.py` inspect repository websites for
display signals only. The domain model has no environment/URL records until this item.

## Scope and Independence

In scope: environment and endpoint registration (via the ps-004 UI/API once available; seed via
configuration before); a worker check using `httpx` (default five-minute interval, configurable, bounded
concurrency, timeouts); recorded status code, timing, redirect chain, TLS expiry, and failure class
(DNS, connect, TLS, timeout, HTTP error); consecutive-failure, recovery, and observed-uptime derivation;
a website health view; retention with compaction.

Safety: only registered targets; an SSRF guard rejecting private, loopback, link-local, and metadata
addresses, re-validated after DNS resolution and every redirect; no credentials sent.

Out of scope: Lighthouse, authenticated flows, notifications beyond ps-008.
Standalone: early, high-value monitoring for real sites.

## Future Health

Check configuration is per application so later check types (Lighthouse, smoke) bind to the same entity.
Uptime is labelled "observed from this host", not an SLA.

## Dependencies and Decisions

Open: probe vantage point (home network only); default timeout and expected status; whether monitoring
interval needs the ps-005 amendment (yes if private, else time-based refresh amendment already needed).

## Completion Expectations

A stopped test site is reported as down with the correct failure class and recovers; registering
`http://localhost` or an internal IP is rejected, including via redirect; expiring certificates are
flagged; pytest covers classification, uptime math, and the SSRF guard.
