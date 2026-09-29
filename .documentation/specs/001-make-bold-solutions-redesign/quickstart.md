# Verification Guide: Make Bold Solutions Dashboard Redesign

## Prerequisites

1. Install the frontend dependencies from `frontend/`.
2. Use the existing MakeBoldSolutions repository-data fixture or generated public-data output.
3. Run the dashboard locally through its existing development command.

## Core Walkthrough

1. Open Overview and verify peak branding, hero, portfolio totals, heatmap, and catalog at desktop width.
2. Search, filter by language and health tier, change every sort, clear filters, and confirm the count, empty state, export payload, and drawer navigation follow the visible list.
3. Open Insights by header navigation and legacy/new hash routes. Verify summary cards, repository activation, language distribution, timeline, and quality matrix.
4. Open Health. Confirm source attention scores, tiers, components, each table sort, methodology values, and Health-ranked drawer navigation.
5. Test the drawer close, left/right, Previous/Next, repository and homepage actions, collapsed fix-score prompt, prompt copy feedback, dependencies, and optional website preview.
6. At a viewport below 768px, verify the fixed tab bar, no obscured content, horizontal table/heatmap access, touch targets, and toast placement.
7. Simulate offline mode, refresh success/failure, service-worker update, no exportable data, loading error, and unexpected render error.

## Quality Commands

Run from `frontend/`:

```powershell
npm run lint
npm run format:check
npm test
npm run build
npm run test:smoke
```

## Acceptance Evidence

- Capture desktop and mobile screenshots for Overview, Insights, Health, and the repository drawer against the extracted prototype.
- Record keyboard traversal through all navigation, filters, export menu, drawer, toast actions, and recovery controls.
- Confirm no private data, legacy GitHub-blue controls, Octocat branding, or emoji UI appears in the rendered dashboard.

## T044 Validation Run (2026-09-28)

Executed from `frontend/` (production packaging redirected to the whitelisted
`.validation/site` directory via `SPARK_BUILD_DIR`, so the committed `docs/`
production output was left untouched during validation):

| Command | Result |
| --- | --- |
| `npm run format:check` | ✅ Pass — all files match Prettier style |
| `npm run lint` | ✅ Pass — 0 warnings/errors (`--max-warnings 0`) |
| `npx vitest run` | ✅ Pass — 105/105 tests across 16 files |
| `SPARK_BUILD_DIR=.validation/site npm run build` | ✅ Pass — clean → lint → format:check → vite build → postbuild data copy, exit 0 |
| `SPARK_BUILD_DIR=.validation/site npm run test:smoke` | ✅ Pass — "Browser smoke passed: data, search, details, charts, health, permanent-light-shell, mobile tab bar." |

Notes:

- The smoke script's repository-card title selector was updated from
  `article[role=button] a` to `article[role=button] [data-testid=repo-name]`
  because the redesigned catalog card no longer wraps the repository name in
  an anchor (the external-link icon is now the only anchor, and only renders
  when a homepage is set). A `data-testid="repo-name"` attribute was added to
  `RepositoryGrid.jsx` for this automation hook.
- T045's visual screenshot comparison against the extracted HTML prototype
  was not performed in this session — it requires a person (or a
  screenshot/browser-automation tool) to open both the live app and
  `design/GitHubSpark.dc.html` side by side and judge pixel/visual fidelity,
  which is outside what this implementation pass could execute
  autonomously. All structural/behavioral acceptance criteria (routes,
  filters, sorts, exports, drawer navigation, keyboard behavior, offline
  retry, recovery states) are covered by the automated test suite above.
