---
id: ps-012
title: Lighthouse audits
status: proposed
order: 90
depends_on: [ps-011]
blockers: ["Developer decision: accept Chromium/Node image and host resource budget"]
delivery: []
---

# ps-012: Lighthouse audits

## Outcome

Each registered website is audited weekly for mobile and desktop with Lighthouse running locally in
Docker, and the platform shows scores, key lab metrics, history, and regressions.

## Current Reality

Lighthouse CI is configured only for this project's own frontend (`frontend/scripts/lighthouse.mjs`);
nothing audits registered sites.

## Scope and Independence

In scope: a separate browser-capable worker image, serialized audits (concurrency 1), mobile and desktop
profiles; stored performance, accessibility, best-practices, SEO scores, LCP, CLS, TBT, Speed Index;
Lighthouse version, settings, environment, and timestamps; selected full reports retained with a size
budget; regression detection against a rolling baseline; history chart per site. Results are labelled
laboratory data; TBT is not presented as INP.

Out of scope: field data (ps-017), authenticated pages, auto-fixing.
Standalone: adds performance monitoring on top of ps-011.

## Future Health

Browser image is shared with Playwright (ps-014). Reports stored under the artifacts volume with
retention and backup coverage.

## Dependencies and Decisions

Depends on ps-011 targets and SSRF guard. Open: image size on the i7-3770 host, run window, retention.
Lab variance means thresholds should use baselines, not single runs.

## Completion Expectations

A scheduled audit stores both profiles with provenance; two runs on an unchanged site stay within a
documented variance band; a deliberately degraded page triggers a regression flag; audits never run
concurrently; pytest covers parsing and regression logic.
