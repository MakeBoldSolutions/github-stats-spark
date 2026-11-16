---
id: ps-015
title: Release timeline and verification
status: proposed
order: 120
depends_on: [ps-010, ps-011, ps-014]
blockers: ["Developer decision: how a deployment is evidenced per application"]
delivery: []
---

# ps-015: Release timeline and verification

## Outcome

An application shows a release timeline whose entries distinguish built, tested, released, deployed,
verified, and healthy, each backed by evidence, with before/after operational comparisons and optional
links to roadmap items.

## Current Reality

ps-010 supplies workflow, tag, release, and deployment evidence; ps-011/012/014 supply operational
observations; ps-013 supplies roadmap items. No state model ties them together.

## Scope and Independence

In scope: a release record per repository tag/SHA with independent, evidence-linked state flags;
deployment evidenced by GitHub deployment records or a declared per-application signal (for example a
version endpoint), never by CI success alone; automatic post-release smoke run and window comparison of
availability, response time, and Lighthouse; correlation shown as "changed after release" without
claiming causation; explicit roadmap links only where an item references the release/PR.

Out of scope: triggering deployments, rollback, automatic root-cause analysis.
Standalone: reads existing evidence.

## Future Health

Missing evidence displays as "unknown", never as failure or success.

## Dependencies and Decisions

Open: deployment evidence method per application; comparison window lengths.

## Completion Expectations

A release with green CI but no deployment evidence shows built/tested only; a verified deployment shows
its smoke result; a post-release regression is flagged with before/after values and observation links;
pytest covers state derivation and unknown handling.
