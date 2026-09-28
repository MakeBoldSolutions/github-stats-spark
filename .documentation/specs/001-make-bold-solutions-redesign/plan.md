# Implementation Plan: Make Bold Solutions Dashboard Redesign

**Branch**: `001-make-bold-solutions-redesign` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)
**Input**: Full specification and extracted visual handoff at `.documentation/design-handoffs/githubspark-redesign/`.

## Summary

Re-theme and restructure the existing repository dashboard around the Make Bold Solutions design system without changing the public-repository data pipeline. The implementation copies approved local visual assets, introduces a small shared brand-component layer, moves route and active-result-list state to the app shell, and restyles the Overview, Insights, Health, repository detail, offline, export, and recovery workflows. The data file remains the authoritative contract; Health consumes its backend-produced attention fields directly.

## Technical Context

**Language/Version**: JavaScript with React 19
**Primary Dependencies**: React, Vite, Chart.js, react-chartjs-2, react-markdown, Workbox, and new `lucide-react`
**Storage**: Static `repositories.json` data plus existing browser cache
**Testing**: Vitest, ESLint, Prettier, build, and smoke script
**Target Platform**: Modern desktop and mobile browsers hosted by GitHub Pages
**Project Type**: Static single-page web application
**Performance Goals**: Preserve current lazy loading and serve the dashboard without additional data requests for unchanged repository data
**Constraints**: Public repositories only; unchanged schema; one approved light theme; WCAG AA text contrast; 44px touch controls; reduced-motion support; 1200px content maximum; no emoji iconography
**Scale/Scope**: One dashboard shell; three primary views; a repository drawer; supplied MakeBoldSolutions portfolio snapshot and up to 500 public repositories

## Constitution Check

_GATE: Passed before research and re-checked after design._

| #   | Question                                                             | Answer | Action                                                                    |
| --- | -------------------------------------------------------------------- | ------ | ------------------------------------------------------------------------- |
| 1   | Privacy: Does this feature touch private repository data?            | No     | Preserve existing public-only data flow.                                  |
| 2   | Testability: Can new logic be unit-tested without external services? | Yes    | Cover pure formatting/filtering and component interactions with fixtures. |
| 3   | Observability: Do failure paths produce actionable error messages?   | Yes    | Retain retry, offline, toast, and error-boundary paths.                   |
| 4   | Efficiency: Does this avoid unnecessary API calls?                   | Yes    | Reuse current cache, service-worker, and refetch behavior.                |
| 5   | Accessibility: Does visual output meet WCAG AA?                      | Yes    | Verify token contrast, focus states, semantics, and keyboard behavior.    |
| 6   | Size: Will a modified module exceed 800 LOC?                         | No     | Split new behavior into brand primitives and focused view helpers.        |
| 7   | Generated Output: Does this add a generated output directory?        | No     | No scan-exclusion update is required.                                     |

## Project Structure

### Documentation

```text
.documentation/specs/001-make-bold-solutions-redesign/
├── plan.md
├── research.md
├── data-model.md
├── contracts/ui-contract.md
├── quickstart.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code

```text
frontend/
├── index.html
├── package.json
├── public/
│   ├── fonts/
│   └── favicon.svg
├── src/
│   ├── App.jsx
│   ├── main.jsx
│   ├── components/
│   │   ├── Brand/
│   │   ├── Common/
│   │   ├── ProfileHero/
│   │   ├── RepositoryGrid/
│   │   ├── Visualizations/
│   │   ├── Attention/
│   │   ├── DrillDown/
│   │   ├── Mobile/
│   │   └── ErrorBoundary/
│   ├── contexts/
│   ├── services/
│   ├── styles/
│   │   ├── brand/
│   │   └── global.css
│   └── utils/
└── tests/
```

**Structure Decision**: Retain the existing frontend structure. Add only `components/Brand/` and `styles/brand/`; keep view logic in its existing ownership area and add narrowly scoped helpers where state or formatting becomes reusable.

## Implementation Approach

1. Establish the brand foundation first: local fonts, supplied tokens, brand primitives, peak assets, icon dependency, global variable remapping, metadata, and dark-mode removal.
2. Make the app shell the owner of the selected repository and active repository list. Overview and Health report their ordered visible lists upward so drawer previous/next always follows the initiating view.
3. Complete the Overview as the first independently usable slice: hero, heatmap, tier-based repository catalog, export menu, sanitized summaries, and empty state.
4. Rebuild Insights and Health against existing source fields, explicitly deleting browser-side attention-score derivation rather than maintaining two score formulas.
5. Convert repository detail from its centered modal layout to an accessible right drawer while preserving its existing remediation prompt, signals, dependency, and website data behavior.
6. Finish cross-cutting offline, toast, mobile navigation, loading/error, and visual/accessibility verification, then run the existing quality and build checks.

## Complexity Tracking

No constitution exceptions are required.
