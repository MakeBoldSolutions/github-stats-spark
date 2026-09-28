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
