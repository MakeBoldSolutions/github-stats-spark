# Tasks: Make Bold Solutions Dashboard Redesign

**Input**: Design artifacts in `.documentation/specs/001-make-bold-solutions-redesign/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [ui-contract.md](contracts/ui-contract.md), and [quickstart.md](quickstart.md)

**Tests**: Automated tests are required by the specification for filters, backend health metrics, keyboard behavior, mobile navigation, exports/toasts, and recovery states.

**Organization**: Tasks are grouped by independently testable user story. All product tasks target `frontend/`; no task may change the repository-data schema or public-only filtering behavior.

## Phase 1: Setup

**Purpose**: Establish assets and dependency support for the approved visual system.

- [ ] T001 Add `lucide-react` and its lockfile entry in `frontend/package.json` and `frontend/package-lock.json`
- [ ] T002 [P] Copy supplied font files and logo assets to `frontend/public/fonts/`, `frontend/public/favicon.svg`, and the public metadata-image location
- [ ] T003 [P] Copy supplied token styles into `frontend/src/styles/brand/` and add font URL declarations for locally served assets
- [ ] T004 Update metadata, theme color, preload behavior, and browser icon references in `frontend/index.html`
- [ ] T005 Add brand-layer imports before global styles in `frontend/src/main.jsx`

**Checkpoint**: The frontend can load the supplied fonts, peak mark, and brand tokens locally.

---

## Phase 2: Foundational

**Purpose**: Build shared primitives and state contracts that all redesigned views require.

- [ ] T006 Create Button, Badge, Card, and Eyebrow primitives with CSS modules in `frontend/src/components/Brand/`
- [ ] T007 Replace legacy color, typography, radius, shadow, and dark-theme variables with approved token mappings in `frontend/src/styles/global.css`
- [ ] T008 Create pure display helpers for sanitized excerpts, relative push time, language colors, tier tones, and source-health fallbacks in `frontend/src/utils/repositoryPresentation.js`
- [ ] T009 [P] Add unit coverage for display helpers in `frontend/tests/repositoryPresentation.test.jsx`
- [ ] T010 Extract shared view, selected-repository, active-result-list, toast, export, refresh, and public `?user=` profile-selection ownership into `frontend/src/hooks/useDashboardShell.js`; keep `frontend/src/App.jsx` primarily compositional
- [ ] T011 Update route and app-shell interaction coverage in `frontend/tests/App.test.jsx`, including direct non-default public `?user=` loading with loaded-profile identity labels and totals while retaining Make Bold Solutions defaults

**Checkpoint**: Shared brand controls and shell state are ready; the drawer can navigate the visible ordered list that opened it.

---

## Phase 3: User Story 1 - Browse A Branded Repository Portfolio (Priority: P1) MVP

**Goal**: Deliver the branded Overview with accurate portfolio totals, heatmap, catalog controls, and repository-card navigation.

**Independent Test**: Load the MakeBoldSolutions fixture, exercise search, language/tier filters, all sorts, clear filters, empty state, export trigger, card keyboard activation, and filtered-list drawer navigation.

- [ ] T012 [P] [US1] Update hero behavior and styling for approved copy, actions, portfolio statistics, and no-avatar presentation in `frontend/src/components/ProfileHero/ProfileHero.jsx` and `frontend/src/components/ProfileHero/ProfileHero.module.css`
- [ ] T013 [P] [US1] Rework the contribution calendar end date, thresholds, card header, titles, legend, and responsive scrolling in `frontend/src/components/Visualizations/ContributionHeatmap.jsx` and `frontend/src/components/Visualizations/ContributionHeatmap.module.css`
- [ ] T014 [P] [US1] Update heatmap fixture coverage for generated-at boundaries, thresholds, labels, and keyboard-accessible descriptions in `frontend/tests/ContributionHeatmap.test.jsx`
- [ ] T015 [US1] Replace maturity filtering, legacy language colors, emoji quality badges, and inline SVG controls with the tier-based branded repository catalog in `frontend/src/components/RepositoryGrid/RepositoryGrid.jsx` and `frontend/src/components/RepositoryGrid/RepositoryGrid.module.css`
- [ ] T016 [US1] Wire Overview active results, catalog count, and selected repository callbacks through `frontend/src/App.jsx`
- [ ] T017 [US1] Add catalog tests for search, tier filtering, sorting, sanitized excerpts, empty state, and keyboard card activation in `frontend/tests/RepositoryGrid.test.jsx`

**Checkpoint**: Overview independently delivers the approved portfolio discovery flow and passes its interaction tests.

---

## Phase 4: User Story 2 - Interpret Portfolio Insights (Priority: P1)

**Goal**: Deliver branded repository Insights with actionable activity and quality comparisons.

**Independent Test**: Open Insights through header and compatible hash routes, verify six summary values and all analytical views, then activate a repository from each clickable view.

- [ ] T018 [P] [US2] Update summary-card content and styling for the six prescribed Insight measures in `frontend/src/components/Visualizations/StatCards.jsx` and its CSS module
- [ ] T019 [US2] Recompose Insight data shaping and page layout for commit bars, language distribution, recent activity, and clickable rows in `frontend/src/components/Visualizations/DashboardView.jsx`
- [ ] T020 [US2] Implement the branded weekly activity timeline and quality coverage matrix in `frontend/src/components/Visualizations/ActivityTimeline.jsx`, `frontend/src/components/Visualizations/ActivityTimeline.module.css`, and a new focused quality-matrix component under `frontend/src/components/Visualizations/`
- [ ] T021 [US2] Restyle retained chart components for language colors, ink gridlines, approved typography, and no legends in `frontend/src/components/Visualizations/BarChart.jsx`, `frontend/src/components/Visualizations/PieChart.jsx`, `frontend/src/components/Visualizations/HealthChart.jsx`, and related styles
- [ ] T022 [US2] Add Insight route, value, and repository-activation coverage in `frontend/tests/DashboardView.test.jsx` and `frontend/tests/ActivityTimeline.test.jsx`

**Checkpoint**: Insights independently renders all required analytics and opens detail for a selected repository.

---

## Phase 5: User Story 3 - Prioritize Repository Health (Priority: P1)

**Goal**: Deliver a trustworthy Health view using pipeline-produced attention data.

**Independent Test**: Load repositories with varied source scores, tiers, and components; validate every summary tile and sort column against source data; open a ranked repository.

- [ ] T023 [P] [US3] Add source-attention fixtures and interaction assertions in `frontend/tests/AttentionView.test.jsx`
- [ ] T024 [US3] Remove client-side attention-score derivation and map Health ranking, tiles, tier badges, score bars, and methodology to source attention fields in `frontend/src/components/Attention/AttentionView.jsx`
- [ ] T025 [US3] Implement the responsive Health table, methodology aside, and branded summary presentation in `frontend/src/components/Attention/AttentionView.module.css`
- [ ] T026 [US3] Wire Health ordered results and exports through `frontend/src/App.jsx` and `frontend/src/components/Common/ExportButton.jsx`

**Checkpoint**: Health independently ranks repositories without a competing browser-side formula.

---

## Phase 6: User Story 4 - Investigate A Repository Without Losing Context (Priority: P1)

**Goal**: Convert repository detail to an accessible right-side drawer while retaining existing detail and remediation data.

**Independent Test**: Open detail from filtered Overview and sorted Health, use Escape and left/right navigation, test Previous/Next boundaries, expand/copy the prompt, and activate external actions.

- [ ] T027 [P] [US4] Update drawer interaction and section-toggle behavior for focus, keyboard navigation, and copy feedback in `frontend/src/components/DrillDown/RepositoryDetail/hooks/`
- [ ] T028 [US4] Replace the centered modal shell with the approved right-side drawer, header, footer, and result-position display in `frontend/src/components/DrillDown/RepositoryDetail.jsx`, `frontend/src/components/DrillDown/RepositoryDetail.module.css`, and `frontend/src/components/DrillDown/RepositoryDetail/sections/`
- [ ] T029 [US4] Reorder and restyle summary, statistics, quality, health breakdown, fix prompt, signals, dependencies, and website preview sections in `frontend/src/components/DrillDown/RepositoryDetail/sections/`
- [ ] T030 [US4] Preserve fix-score blocker and prompt generation while applying the collapsible branded presentation and copy state in `frontend/src/components/DrillDown/RepositoryDetail/sections/FixScorePromptSection.jsx`
- [ ] T031 [US4] Update fix-prompt coverage and add drawer keyboard/navigation coverage in `frontend/tests/FixScorePromptSection.test.jsx` and `frontend/tests/RepositoryDetail.test.jsx`

**Checkpoint**: Detail works as an accessible drawer with correct context-preserving navigation.

---

## Phase 7: User Story 5 - Use The Dashboard On Mobile And Offline (Priority: P2)

**Goal**: Ensure the branded experience remains complete on small screens and explains cached/offline state clearly.

**Independent Test**: At less than 768px, navigate all three views, open detail, scroll dense content, simulate offline/online state, and inspect toast placement above the tab bar.

- [ ] T032 [P] [US5] Restyle and relabel the mobile Overview, Insights, and Health tab bar with approved icons and safe-area handling in `frontend/src/components/Mobile/TabBar/TabBar.jsx` and `frontend/src/components/Mobile/TabBar/TabBar.css`
- [ ] T033 [P] [US5] Rebuild the offline banner and toast variants, actions, placement, and dismissal behavior in `frontend/src/components/Mobile/OfflineIndicator/` and `frontend/src/components/Mobile/Toast/`
- [ ] T034 [US5] Add mobile layout, fixed-tab-bar spacing, dense-content scrolling, and responsive shell rules in `frontend/src/styles/global.css` and affected component CSS modules
- [ ] T035 [US5] Update mobile navigation, offline-banner, and toast coverage in `frontend/tests/ThemeToggle.test.jsx`, `frontend/tests/TabBar.test.jsx`, `frontend/tests/OfflineIndicator.test.jsx`, and `frontend/tests/Toast.test.jsx`

**Checkpoint**: Mobile and offline behavior remains usable without obscured controls or lost state.

---

## Phase 8: User Story 6 - Export Current Results And Refresh Data (Priority: P2)

**Goal**: Export the user’s active list and expose cache-clearing refresh feedback without browser alert dialogs.

**Independent Test**: Export filtered Overview and sorted Health lists as CSV and JSON, confirm current CSV columns, then test refresh success and failure toast messages.

- [ ] T036 [US6] Replace export alerts and legacy menu treatment with the accessible branded current-list export menu in `frontend/src/components/Common/ExportButton.jsx` and a new CSS module
- [ ] T037 [US6] Add the footer source timestamp and refresh control while retaining force-refresh behavior in `frontend/src/App.jsx` and `frontend/src/styles/global.css`
- [ ] T038 [US6] Add export-menu, filtered/ranked payload, click-outside, refresh-success, and refresh-failure tests in `frontend/tests/ExportButton.test.jsx` and `frontend/tests/App.test.jsx`

**Checkpoint**: Export and refresh actions report outcomes through branded toasts and preserve existing data behavior.

---

## Phase 9: User Story 7 - Recover From Loading And Failure States (Priority: P2)

**Goal**: Present clear branded loading, data-error, and unexpected-error recovery paths.

**Independent Test**: Force loading, empty, data-load-error, and render-boundary error states; confirm retry, reload, auto-retry, and development-details behavior.

- [ ] T039 [P] [US7] Apply the branded loading and empty-state treatments in `frontend/src/components/Common/LoadingState.jsx` and `frontend/src/components/Mobile/EmptyState/`
- [ ] T040 [P] [US7] Apply the approved data-error and unexpected-error recovery experience in `frontend/src/App.jsx`, `frontend/src/components/ErrorBoundary/ErrorBoundary.jsx`, and `frontend/src/components/ErrorBoundary/ErrorBoundary.css`
- [ ] T041 [US7] Add loading, empty, retry, and error-boundary coverage in `frontend/tests/LoadingState.test.jsx`, `frontend/tests/EmptyState.test.jsx`, and `frontend/tests/ErrorBoundary.test.jsx`

**Checkpoint**: All recoverable application states remain actionable and branded.

---

## Phase 10: Polish And Required Gates

**Purpose**: Remove retired theme surfaces, validate the finished experience, and run required feature gates before implementation approval.

- [ ] T042 Remove the user-facing theme-toggle entry points and retire obsolete theme-specific assertions in `frontend/src/components/Common/ThemeToggle.jsx`, `frontend/src/contexts/ThemeContext.jsx`, and `frontend/tests/ThemeToggle.test.jsx`; replace the retired browser-smoke assertion in `frontend/scripts/smoke.mjs` with permanent-light-shell, navigation, mobile-tab-bar, and no-theme-toggle coverage before T044
- [ ] T043 Audit rendered UI for legacy GitHub-blue colors, Octocat branding, emoji UI, focus contrast, reduced motion, and keyboard traps across `frontend/src/`
- [ ] T044 Run formatting, lint, unit, build, and smoke validation from `frontend/package.json` and record results in `.documentation/specs/001-make-bold-solutions-redesign/quickstart.md`
- [ ] T045 Capture and compare desktop and mobile Overview, Insights, Health, drawer, offline, and error states against `.documentation/design-handoffs/githubspark-redesign/design_handoff_githubspark_redesign/design/GitHubSpark.dc.html`
- [ ] T046 Run `/devspark.analyze` and record resolution of any cross-artifact findings in `.documentation/specs/001-make-bold-solutions-redesign/gates/analyze.md`
- [ ] T047 Run `/devspark.critic` and resolve or explicitly acknowledge risk findings in `.documentation/specs/001-make-bold-solutions-redesign/gates/critic.md`

## Dependencies And Execution Order

- Phase 1 precedes Phase 2.
- Phase 2 blocks all user-story work because it establishes brand primitives, app-shell ownership, and display helpers.
- US1, US2, US3, and US4 are P1 delivery slices. US2 and US3 can proceed after Phase 2; US4 begins after the active-result-list ownership in T010.
- US5, US6, and US7 build on the shared shell and may proceed after Phase 2, but should follow the P1 slices for integrated visual verification.
- Phase 10 runs after all intended user stories. T046 and T047 are required gates before implementation approval.

## Parallel Opportunities

- T002 and T003 can proceed independently after the package dependency is selected.
- T012, T013, and T014 touch distinct Overview surfaces after Phase 2.
- T018 and the first test work for US3 can proceed in parallel with distinct files.
- T027 and section styling work can proceed in parallel once the drawer contract is stable.
- T032 and T033 touch distinct mobile components; T039 and T040 touch distinct recovery components.

## Implementation Strategy

### MVP First

1. Complete Phases 1 and 2.
2. Complete Phase 3 and demonstrate Overview with filters, export trigger, and drawer entry.
3. Validate the independent Overview walkthrough before continuing.

### Incremental Delivery

1. Add Insights, Health, and drawer behavior in the P1 phases.
2. Add mobile/offline, export/refresh, and recovery slices.
3. Complete visual, accessibility, functional, and required-gate validation before approval.
