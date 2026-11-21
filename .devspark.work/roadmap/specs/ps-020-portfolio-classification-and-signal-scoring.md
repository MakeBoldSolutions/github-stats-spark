---
id: ps-020
title: Portfolio classification and signal scoring
status: proposed
order: 105
depends_on: [ps-003, ps-023]
blockers: []
delivery: []
---

# ps-020: Portfolio classification and signal scoring

## Outcome

Every repository in the portfolio carries an explainable tier (core, supporting, or archive) and signal
score, set by the administrator's overrides first and by transparent automated rules otherwise, and the
dashboard shows the portfolio grouped by tier so it is clear at a glance which repositories matter now.

## Current Reality

A finished, unmerged implementation exists. Branch `004-portfolio-intelligence` (three commits, 2026-04-24)
was archived as tag `archive/004-portfolio-intelligence` (commit df5c065) rather than merged: its spec was
marked complete with 29 of 29 tasks done, but it was 99 commits behind `main`, and a trial merge conflicted
in 11 places across config, CLI, summarizer, unified data generator, and cache refresh code. It predates
the Docker, worker, and registry work. Contents: a rule-based classifier (`src/spark/classifier.py`),
`config/portfolio.yml` name-to-tier overrides with a `"*"` default, PortfolioBreakdown and
SignalDistribution dashboard components, a documented portfolio JSON contract, and 263 lines of classifier
tests. It also carries unrelated changes (cache refresh executor, summarizer, a stray `test_output.txt`)
that should not be ported. Its tests have not been run against current `main`.

Today the portfolio (ps-003) is a flat de-duplicated list; only the attention score ranks repositories.

## Scope and Independence

In scope: recover the classifier, its tests, and its spec/contract from the archive tag as the starting
point and port them onto current `main`; take repository tier overrides from the ps-023 Tier domain (an
administrator-set value always wins) rather than a separate YAML file, keeping `config/portfolio.yml` only if it is still
needed for the public CLI/Pages path; add tier and signal score to the portfolio export and the dashboard
views; keep the rules and each score's reasons visible so a tier is never unexplained; missing or malformed
override input falls back to automated rules with a warning rather than failing.

Out of scope: the cache refresh executor and summarizer changes on the old branch, narrative or AI copy
(ps-019), client-facing report layout (ps-018), and changes to the attention-score model.
Standalone: the portfolio can be classified and viewed without monitoring or reporting items.

## Future Health

Keep classification a pure function of repository facts and overrides so ps-018 reports can reuse it and
history can record tier changes as observations later. Do not grow `fetcher.py`. Preserve existing JSON
contracts; the tier fields are additive.

## Dependencies and Decisions

Open: whether tier overrides live in the registry only or also in a file for the CLI path; whether tier
should feed the attention score (recommend no, keep them independent); and the default tier for new
repositories (recommend automated rules, not archive). Review the archived spec's user stories before
reuse; they were written for a personal-portfolio audience and may need adjusting for client portfolios.

## Completion Expectations

An override beats the automated rule and a wildcard default applies to the rest; every repository in the
portfolio export has a tier, score, and reasons; the dashboard groups by tier on current `main`; a
malformed override input does not fail a run; pytest covers the ported classifier cases and the export;
the public CLI, Pages workflow, and existing JSON contracts are unchanged.
