# Work: ps-022 Unified operator experience

**Status**: Complete (implemented and validated locally 2026-11-22, not yet committed)
**Branch**: 002-work-ps-022-unified-operator (from main 54a09ef)
**Source**: roadmap item ps-022 (`.devspark.work/roadmap/specs/ps-022-unified-operator-experience.md`)

## Intended outcome

One consistent self-hosted app: a single scope selector (portfolio → client → source → repository, plus
domain filters) that every view honours, fixed sections, shared page building blocks, one source per
number, and views that link to each other. The public GitHub Pages dashboard is unchanged. The whole
item ships in one PR (developer decision, 2026-11-22, chose this over splitting).

## Acceptance evidence

- Choosing a client, source, or repository changes every view, Security included, with no page reload,
  and the URL restores it. The old `?user=<slug>` links and the existing hashes keep working.
- Health, the drawer, and the fix-score prompt show the same open-alert count as Security for a
  repository with more than 100 alerts. All three read the ps-006 store in self-hosted mode.
- A Security row opens the repository drawer, and the drawer has a Security panel with that repository's
  alerts.
- Every table exports through `ExportButton`. Security drops its own CSV code.
- One shared coverage/state component shows zero, unavailable, unauthorized, unsupported, and stale
  distinctly, and every view uses it.
- There is one shared page header, filter bar (including domain filters), and data table.
- Sections: Overview, Health, Security, Sites, Delivery, Presence, Admin. A section appears only when it
  has data. The mobile tab bar holds the primary sections and puts the rest behind an overflow.
- No unused component remains. `EmptyState`, `GestureHandler`, `TouchTarget`, `SafeArea`, and the mobile
  `LoadingState` are each either adopted or removed, and the two `LoadingState`s become one.
- The refresh actions are labelled "Reload data" (browser cache) and "Collect now" (worker).
- The public Pages build renders Overview, Insights, Health, and the drawer unchanged.
- vitest covers scope switching, cross-links, the shared components, and accessibility. Existing tests
  pass, and `./run-validation.ps1` exits 0.

## Material exclusions

- No content for undelivered sections: Sites, Delivery, and Presence stay hidden.
- No rebranding.
- No per-client access control.
- No change to the attention-score model beyond its data source.

## Operating assumptions

- Self-hosted mode is detected by the existing data files. `portfolio.json` and
  `security/dependabot.json` are present only on the self-hosted server. The admin API is optional.
- The decision owner is the developer, a single administrator.

## Facts verified at start (main 54a09ef)

- `useDependabot.js` always loads the portfolio-wide `data/security/dependabot.json`. Security ignores
  `?user=`.
- `dataService.js` loads `data/users/<slug>/repositories.json` for the `?user=` source. Choosing a source
  calls `window.location.reload()`.
- `FixScorePromptSection.jsx` reads `security.dependabot.total_open`, the fetcher's first-page summary.
- The per-source `repositories.json` is written by `worker/loop.py` without reading the registry, so it
  has no classifications. Client, project, application, and domain values exist only in `portfolio.json`.
- The unused mobile/layout components listed in the spec exist under `components/Mobile` and
  `components/Layout`.

## Open design point (decide during implementation, from evidence)

- **Portfolio and client scope span several sources**, but repository data is stored per source.
  - Option A: the frontend loads the needed per-source files and de-duplicates them by `full_name`.
  - Option B: the worker writes one portfolio-wide repositories file.
  - Prefer A unless loading many sources is measurably slow.
  - Classifications are joined from `portfolio.json` by `full_name`, which fills the per-source gap
    recorded at ps-023 closeout.

## Invariants

- Domain invariant: a repository is identified by its case-insensitive `full_name` in every scope and
  view, so the same repository shows the same counts everywhere.
- Architectural constraint: public mode never requests the admin API or self-hosted-only files in a way
  that breaks or changes the Pages build.

## Verification expectations

- Public Pages build: `verify:snapshot-neutral`. The Overview, Insights, Health, and drawer output must be
  unchanged in public mode.
- If the worker export changes (Option B, or added fields): `verify:end-to-end` against a real worker
  run. Checking it on the server after deploy is a `stage: post-deploy` item, not pre-merge proof.

## Material decisions (implementation)

- Open design point resolved as Option A. The browser loads the per-source files the scope needs and
  joins classifications from `portfolio.json`; no worker change.
- Insights is kept as a section (the public view requires it), alongside the listed sections.
- Stored alert counts replace the collected counts everywhere they are shown. The attention score is
  still computed at collection time; recomputing it would change the score model, which is out of scope.

## Known differences (not defects of this change)

- On server data (2026-11-22), the per-source files hold 38 repositories while the portfolio and
  Security list 45. The collector writes fewer records than discovery finds, so Overview and Security
  can list different repository sets.

## Next action

Commit, then `/devspark-create-pr`. After deploy: pick a client and a domain filter on the server,
and confirm that Security and Health follow the choice and show the same alert counts.
