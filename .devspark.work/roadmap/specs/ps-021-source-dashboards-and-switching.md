---
id: ps-021
title: Organization and repository dashboards with full source switching
status: proposed
order: 62
depends_on: [ps-003, ps-004]
blockers: []
delivery: []
---

# ps-021: Organization and repository dashboards with full source switching

## Outcome

Every enabled source the administrator registers (user, organization, or single repository) has its own
dashboard, and the header switcher lists all of them. Adding, editing, disabling, or removing a source in
Sources is reflected in the switcher and in collection without editing files or restarting anything.

## Current Reality

Registered sources are stored and discovered (ps-003, ps-004), but only `user` sources are collected into a
dashboard. The worker runs the author-filtered `spark unified` pipeline once per user source and publishes
`data/users/<slug>/`; `org` and `repo` sources produce only metadata in `portfolio.json` and the
Repositories tab. The header picker (merged after ps-009) therefore lists user sources only; the
administrator's organizations (Oatville-Community-Church, ShareSmallBiz, West-Wichita-Rotary-Club) and
any single repositories cannot be switched to. The pipeline's "my activity" filtering is by commit
author, which has no meaning for an organization.

## Scope and Independence

In scope: decide and implement how an organization or repository is collected into a dashboard, reusing
the repositories already discovered and stored for that source rather than listing GitHub again; a
per-source dashboard data folder with a stable slug for every source type; the switcher listing every
enabled source grouped by type, showing collected-versus-pending state; a collected-at and error state per
source visible in the switcher or Sources page; edits (enable/disable, token, client) taking effect on the
next collection, with an optional "collect now" for one source; a clear empty state for a source that has
no data yet; keep the `?user=` URL parameter working (the existing bookmark contract) and add a source
form that does not break it.

Out of scope: per-client access control, new metrics, and the classification model (ps-020). Private data
and client-owned data stay behind ps-005.
Standalone: depends only on the registry and API already delivered.

## Future Health

Keep the data layout additive: `data/users/<slug>/` stays valid; new sources get a sibling location or a
slug scheme that cannot collide with a user login. Do not grow `fetcher.py`; prefer feeding the existing
pipeline a repository list over adding a second collector. Make the dashboard's notion of "subject" a
single concept so ps-018 reports and ps-020 tiers can reuse it.

## Dependencies and Decisions

Open (developer decision): the meaning of an organization dashboard. Options: (a) all repositories in the
organization with activity from anyone (recommended; matches how a client organization is read), or
(b) activity attributed to one chosen user inside it. Also open: whether a repository source is shown as
its own dashboard or only as a member of a group; and whether the switcher should also allow a combined
"All sources" portfolio view. Verify whether the pipeline can take an explicit repository list and
author-less mode before designing; the answer sets the size of this item.

## Completion Expectations

Each enabled user, organization, and repository source appears in the switcher after one collection and
opens a working dashboard; an uncollected source is shown as pending, not broken; disabling a source removes
it from the switcher on the next collection; existing user dashboards and `?user=` links are unchanged;
a failed source does not block the others; pytest covers collection for each source type and slugging, and
vitest covers the switcher.
