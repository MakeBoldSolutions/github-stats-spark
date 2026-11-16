---
id: ps-016
title: Search visibility
status: proposed
order: 130
depends_on: [ps-011]
blockers: ["Developer decision: Google/Bing account access and credential approach"]
delivery: []
---

# ps-016: Search visibility

## Outcome

For registered sites the platform tracks search impressions, clicks, CTR, average position, sitemap and
robots.txt health, and basic technical SEO signals, with trends.

## Current Reality

Nothing exists; `web_scraper.py` parses page signals for repository sites only. Provider access
(Search Console property permissions, API scope, data latency and limits, Bing Webmaster API
availability) is unverified.

## Scope and Independence

In scope: a Search Console integration (official API, service-account or OAuth stored server-side),
daily incremental fetch with provider data-delay awareness; Bing only if verification shows a usable API;
public checks with `httpx`/`beautifulsoup4`/`lxml`: sitemap and robots availability, canonical, title/
description completeness, structured data presence (`extruct` only if justified), bounded internal-link
check on registered URLs; SEO regression flags. Search visibility is kept distinct from traffic.

Out of scope: commercial-grade crawling, rank tracking beyond Search Console, keyword research.
Standalone: search insight per site.

## Future Health

Integration/credential model shared with ps-017. Limits and quotas recorded per provider.

## Dependencies and Decisions

Open: which sites have verified Search Console properties; Bing in or out; crawl page limit.

## Completion Expectations

A verified property shows retained daily metrics with correct "data as of" dates; an unverified property
shows an actionable access error; a missing sitemap is flagged; pytest covers parsing and API error mapping.
