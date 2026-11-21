---
id: ps-022
title: Unified operator experience
status: proposed
order: 58
depends_on: [ps-006, ps-021, ps-023]
blockers: []
delivery: []
---

# ps-022: Unified operator experience

## Outcome

One consistent self-hosted application: a single scope selector (portfolio, client, source, repository)
that every view honours, a fixed set of sections that later capabilities fill instead of each adding a
top-level tab, shared page building blocks, one source of truth for each number, and views that link to
each other. The public GitHub Pages dashboard keeps its current visitor experience.

## Current Reality

The September 2026 redesign (`.documentation/specs/001-make-bold-solutions-redesign/`) designed a public,
three-view (Overview, Insights, Health) single-profile dashboard with a three-item mobile tab bar. Sources
(ps-004) and Security (ps-006) were then added to the same header, each with its own patterns. Findings
from the 2026-11-21 review:

- **Scope:** the header switcher reloads the page with `?user=<slug>`; Overview, Insights, and Health follow
  it, Security does not (`useDependabot.js` always loads the portfolio-wide file). There is no client or
  project scope, although the registry and API model both.
- **Two numbers for one fact:** Health and the drawer's fix-score prompt count alerts from `fetcher.py`'s
  first-page summary (at most 100 open alerts); Security counts every alert from the ps-006 store.
- **Dead ends:** a Security row links only to GitHub, not to the repository drawer; the drawer has no
  Security panel.
- **Duplicated patterns:** Security has its own CSV export rather than `ExportButton`; its page heading lives
  in `App.jsx` while Sources writes its own; only Security distinguishes zero from unavailable or
  unauthorized, though the roadmap requires that of every collector; two `LoadingState` components; and
  `EmptyState`, `GestureHandler`, `TouchTarget`, `SafeArea`, and the mobile `LoadingState` are not imported.
- **Two refreshes:** the footer "Refresh" clears the browser cache; the admin "Refresh now" asks the worker
  to collect. Nothing on screen distinguishes them.
- **Sprawl ahead:** ps-010, 011, 012, 015, 016, 017, and 020 each describe a new view.

## Scope and Independence

In scope:

- **Scope selector** replacing the source switcher: portfolio, then client (top level, with internal work as
  its own client), then source, then repository. Held in the URL, changed without a page reload, honoured by
  every view including Security, and filterable by ps-023 domains.
- **Sections:** Overview, Health, Security, Sites (ps-011, 012, 014), Delivery (ps-010, 013, 015), Presence
  (ps-016, 017), Admin. A section appears only once it has data; existing hashes keep working. The
  repository drawer gains one panel per section, starting with Security.
- **Shared building blocks:** page header (eyebrow, title, scope, per-category freshness), filter bar
  (including domain filters), data table, export through `ExportButton`, and a coverage/state component that
  shows zero, unavailable, unauthorized, unsupported, and stale distinctly, generalised from the Security
  coverage panel as the contract future collectors report into.
- **One source per number:** Health, the drawer, and the fix-score prompt read alert counts from the ps-006
  store; the `fetcher.py` summary remains only for the public CLI/Pages path.
- **Cross-links:** a Security row opens the repository drawer; the drawer shows that repository's alerts.
- **Clean-up:** adopt or remove the unused components; name the two refresh actions distinctly ("Reload
  data" and "Collect now").
- **Mobile:** the tab bar holds the primary sections with an overflow for the rest.

Out of scope: building the content of sections whose items are not delivered (they stay hidden), visual
rebranding (the BoldOps name is undecided), per-client access control, and changes to the attention-score
model beyond its data source. Public mode: the GitHub Pages build keeps Overview, Insights, Health, and the
drawer as they are; operator sections and the scope selector appear only in the self-hosted deployment.

## Future Health

Each later item adds a panel to an existing section and a drawer panel, uses the shared table, filter, and
coverage components, and inherits scope and domain filtering without its own routing or export code.

## Dependencies and Decisions

Adopted defaults (developer, 2026-11-21): client is the top level of the scope selector; the sections are
as listed; the public Pages dashboard is unchanged. Depends on ps-023 for clean client lists and domain
filters. Open: none.

## Completion Expectations

Choosing a client, source, or repository changes every view, including Security, without a reload, and the
URL restores it; Health, the drawer, and Security show the same open-alert count for a repository with
more than 100 alerts; a Security row opens the drawer; every table exports through `ExportButton`; each
view shows zero and unavailable differently through the shared component; no unused component remains;
the two refresh actions are labelled distinctly; the public Pages build renders the existing three views
unchanged; vitest covers scope switching, cross-links, the shared components, and accessibility; existing
tests pass.
