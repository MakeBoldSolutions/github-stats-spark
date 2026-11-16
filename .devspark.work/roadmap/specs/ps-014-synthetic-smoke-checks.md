---
id: ps-014
title: Synthetic smoke checks
status: proposed
order: 110
depends_on: [ps-011, ps-012]
blockers: ["Developer decision: which application first, and test-credential handling"]
delivery: []
---

# ps-014: Synthetic smoke checks

## Outcome

For selected actively developed applications, scheduled and on-demand non-destructive browser checks
confirm the site loads, key pages and content appear, and a login with a dedicated test account works,
with failures captured as evidence.

## Current Reality

`screenshot.py` already uses Playwright for screenshots; no functional checks exist. The browser image
arrives with ps-012.

## Scope and Independence

In scope: per-application declarative checks (URL, expected text/selector, navigation, console errors,
failed requests, mobile viewport); optional login using test credentials from the secret store; screenshot
and trace on failure with retention; scheduled runs and a manual "run now"; results as observations.

Out of scope: a regression suite, destructive or transactional actions (checks restricted to read-only
journeys), recording user behavior.
Standalone: adds functional status to registered sites.

## Future Health

Run-now is reusable for post-release verification (ps-015). Same SSRF and registered-target rules as ps-011.

## Dependencies and Decisions

Open: check definition format (YAML in the registry vs UI-built); test accounts per client; CAPTCHA/MFA
sites are out of scope.

## Completion Expectations

A broken page or failed login yields a failed result with screenshot; passing runs store no sensitive
data; credentials never appear in logs or artifacts; pytest uses a local fixture site.
