---
classification: full-spec
risk_level: high
target_workflow: specify-full
required_artifacts: "spec, plan, tasks"
recommended_next_step: plan
required_gates: "checklist, analyze, critic"
---

# Feature Specification: Make Bold Solutions Dashboard Redesign

**Feature Branch**: `001-make-bold-solutions-redesign`
**Created**: 2026-09-28
**Status**: In Progress
**Input**: User-provided GitHubSpark UI redesign handoff extracted to `.documentation/design-handoffs/githubspark-redesign/`.

## Rationale Summary

Rebuild the GitHubSpark dashboard with the approved Make Bold Solutions visual system while preserving existing public-repository analytics, user workflows, cached-data behavior, and the established data contract.

The authoritative visual reference is the extracted handoff's `README.md` and `design/GitHubSpark.dc.html`. The prototype's `heroVariant`, `cardLayout`, `showHeatmap`, and `previewState` switches are design-review controls only and MUST NOT become product controls.

### Scope And Constraints

- The work is confined to the dashboard experience, public visual assets, and its automated checks. Backend calculation, fetcher behavior, public-repository filtering, and the data contract are out of scope.
- Preserve all existing data access, lazy loading, cached-data, offline, refresh, and export behavior.
- Use the supplied Make Bold Solutions tokens, fonts, logo mark, and approved outline icon set. Do not retain emoji as iconography.
- The dashboard has one approved light theme; remove the user-facing dark-mode toggle while retaining compatibility with existing app state.
- Preserve keyboard navigation, reduced-motion handling, and WCAG AA text contrast. A redesigned surface must not regress existing accessibility behavior.
- Keep the data contract unchanged. Health scores and tiers must use analysis-pipeline values rather than a competing browser-derived score.
- Preserve the existing public `?user=` selector. Make Bold Solutions remains the default portfolio and design reference; identity-dependent labels and portfolio totals use the loaded public profile when another user is selected.

## Clarifications

### Session 2026-09-28

- Q: Should the redesign preserve the current public `?user=` selector or become a Make Bold Solutions-only portfolio? → A: Preserve multi-user public-profile support, with Make Bold Solutions as the default and visual reference.

## User Scenarios & Testing

### User Story 1 - Browse A Branded Repository Portfolio (Priority: P1)

A visitor can open the default overview and immediately recognize the Make Bold Solutions portfolio, inspect the portfolio totals, contribution activity, and repository catalog, then search, filter, sort, and open a repository.

**Why this priority**: The overview is the primary route and the core reason users visit the dashboard.

**Independent Test**: Load the supplied MakeBoldSolutions snapshot, apply each catalog control, and open a filtered repository from its card.

**Acceptance Scenarios**:

1. **Given** the overview route and loaded data, **When** a visitor views the page, **Then** they see the approved cream, rust, ember, and ink visual system; the peak mark; the approved hero copy; portfolio totals; contribution heatmap; and repository catalog.
2. **Given** a populated catalog, **When** a visitor searches, filters by language or health tier, sorts, or clears active filters, **Then** the result count and card list reflect the current criteria without changing the underlying data.
3. **Given** a repository card, **When** a visitor activates it with a pointer, Enter, or Space, **Then** the repository detail drawer opens for that repository.

---

### User Story 2 - Interpret Portfolio Insights (Priority: P1)

A visitor can switch to Insights and compare repository activity, language distribution, weekly activity, and quality coverage using the same branded visual language.

**Why this priority**: Insights is a primary navigation destination and converts the source data into the dashboard's analytical value.

**Independent Test**: Navigate to Insights from both the header and hash URL, then verify all six stat cards and analytical views against the fixture data.

**Acceptance Scenarios**:

1. **Given** loaded repository data, **When** a visitor opens Insights, **Then** the dashboard shows the six approved summary cards, repository commit bars, language distribution, recent-commit bars, weekly timeline, and quality coverage matrix.
2. **Given** an insight row representing a repository, **When** the visitor activates it, **Then** its repository detail drawer opens.

---

### User Story 3 - Prioritize Repository Health (Priority: P1)

A maintainer can open Health to find the public repositories requiring attention and understand why they rank that way.

**Why this priority**: Accurate maintenance prioritization is a core product function and must agree with the analysis pipeline.

**Independent Test**: Load fixture records with varied backend attention scores, tiers, and components; sort every maintenance-table column; and compare displayed values with the source records.

**Acceptance Scenarios**:

1. **Given** data containing backend attention metrics, **When** a maintainer opens Health, **Then** the summary tiles, ranking table, tier badges, score bars, and methodology panel use `attention_score`, `attention_metrics.tier`, and `attention_metrics.components` from the data.
2. **Given** the maintenance ranking, **When** the maintainer selects a column header, **Then** the table sorts in the selected direction and communicates the active sort direction.
3. **Given** a ranked repository row, **When** the maintainer activates it, **Then** the detail drawer opens and retains Health's current ranked-list navigation order.

---

### User Story 4 - Investigate A Repository Without Losing Context (Priority: P1)

A visitor can inspect a repository in an accessible side drawer, see quality and health evidence, use the existing remediation prompt, and navigate the current result list with buttons or keyboard shortcuts.

**Why this priority**: The drawer exposes the detailed data that explains cards, tables, and rankings.

**Independent Test**: Open a repository from an active overview filter and navigate previous/next, Escape, left/right arrow keys, the collapsible prompt, copy action, and external links.

**Acceptance Scenarios**:

1. **Given** a selected repository, **When** the detail view opens, **Then** it is a right-side drawer with a focusable close control, a backdrop, source-repository action, optional live-site action, and all available statistics and signals.
2. **Given** the drawer is open, **When** the visitor presses Escape, Left Arrow, or Right Arrow, **Then** it closes or moves through the active list as appropriate, without navigating outside that list.
3. **Given** an available fix-score prompt, **When** the visitor expands and copies it, **Then** existing blocker and prompt logic is retained, the prompt is copied, and the UI shows the approved temporary copied state.

---

### User Story 5 - Use The Dashboard On Mobile And Offline (Priority: P2)

A visitor can use every primary route on a small viewport and understand cached or disconnected data status.

**Why this priority**: The dashboard is expected to remain usable outside desktop conditions and already supports offline caching.

**Independent Test**: Exercise overview, Insights, Health, drawer, filters, and toast behavior at widths below 768px while simulating offline and online transitions.

**Acceptance Scenarios**:

1. **Given** a viewport narrower than 768px, **When** the visitor navigates the application, **Then** the header navigation is replaced with the fixed three-item Overview, Insights, and Health tab bar, without obscuring page content.
2. **Given** the browser is offline, **When** cached data is available, **Then** the header shows the approved offline banner with relative last-sync time and a retry control.
3. **Given** a transient app message or service-worker update, **When** it is raised, **Then** the branded toast is readable above the mobile tab bar and its action and dismissal controls work.

---

### User Story 6 - Export Current Results And Refresh Data (Priority: P2)

A visitor can export exactly the repositories currently being viewed and can request a cache-clearing refresh.

**Why this priority**: Export and freshness are existing utility workflows that must survive the redesign.

**Independent Test**: Apply Overview filters and Health sorting, export each format, validate the existing CSV columns and JSON records, then trigger footer refresh.

**Acceptance Scenarios**:

1. **Given** a filtered Overview or sorted Health list, **When** the visitor selects CSV or JSON from the export menu, **Then** the export contains that current list and the UI confirms success or reports no data with a toast.
2. **Given** a loaded dashboard, **When** the visitor selects Refresh, **Then** the existing cache-clear and force-refresh behavior runs and reports its result through a toast.

---

### User Story 7 - Recover From Loading And Failure States (Priority: P2)

A visitor receives branded, actionable loading, data-error, and unexpected-error experiences instead of a broken or silent page.

**Why this priority**: Clear recovery behavior is required by the constitution and preserves trust when data or rendering fails.

**Independent Test**: Force loading, data-fetch failure, and render-boundary failure states and verify their retry/reload paths and developer-only details.

**Acceptance Scenarios**:

1. **Given** data is loading, **When** the application renders, **Then** it presents the peak mark and approved loading copy.
2. **Given** data loading fails, **When** the error state renders, **Then** it provides the error context and a Retry action.
3. **Given** an unexpected render error, **When** the error boundary renders, **Then** it provides the approved recovery actions, retains the 30-second auto-retry and development details, and does not expose emoji iconography.

### Edge Cases

- A repository has no language, homepage, summary, quality signal, dependency data, screenshot, or AI summary: show the defined fallbacks without broken controls or raw markdown fragments.
- Search and filter combinations return no repositories: show the approved empty state and a functional clear-filters action.
- Data timestamps are absent or invalid: render the existing safe fallback rather than invalid dates or relative-time errors.
- The result list has one repository or the selected item is first/last: disable Previous or Next as appropriate.
- Tables and heatmaps exceed narrow viewport width: preserve readable cell dimensions and enable the prescribed horizontal scrolling rather than clipping content.
- The data set contains no commits in the last 90 days, no activity weeks, or zero health signals: show valid empty visual states without division-by-zero values.

## Requirements

### Visual System And Assets

- **FR-001**: The application MUST import the supplied fonts and token files before global styles and MUST map global variables to the approved Make Bold Solutions system.
- **FR-002**: The application MUST use Be Vietnam Pro for display headings, Inter Tight for body and UI text, and the approved monospace fallback for code-like content.
- **FR-003**: The application MUST use cream page backgrounds, white cards, warm ink neutrals, rust primary actions, and ember accents. It MUST remove the GitHub-blue palette and user-facing dark theme.
- **FR-004**: The application MUST use 4px, 6px, and 8px radii according to control, small-tile, and card/panel roles; only dots may be circular.
- **FR-005**: The header, loading state, error state, favicon, and metadata MUST use the supplied peak logo mark; the app MUST replace the Octocat mark and remove all emoji iconography.
- **FR-006**: The application MUST use the approved outline icon treatment for all controls and status icons.
- **FR-007**: The application MUST consistently present the approved button, badge, card, and eyebrow treatments, including health-tier badge mapping.

### Application Shell And Navigation

- **FR-008**: The desktop header MUST be sticky, branded, and expose Overview, Insights, and Health navigation; it MUST preserve both current and new supported hash routes: `#`, `#visualizations`/`#insights`, and `#attention`/`#health`.
- **FR-009**: The footer MUST show the approved Make Bold Spark attribution, source generation timestamp, refresh control, domain, and location.
- **FR-010**: On viewports below 768px, the application MUST replace header navigation with the approved fixed mobile tab bar and reserve bottom space for it.
- **FR-011**: The application MUST display the prescribed offline header banner when disconnected and reuse current cached-data, relative-sync-time, and retry behavior.

### Overview

- **FR-012**: The overview MUST replace the avatar hero with the specified default copy, external GitHub and Make Bold Spark actions, update date, and a responsive two-by-two portfolio-stat card. When another public user is selected, identity-dependent labels and totals MUST use the loaded profile.
- **FR-013**: The contribution heatmap MUST use the supplied 365-day window ending at `metadata.generated_at`, Sunday-first 53-week layout, five defined color thresholds, accessible date/count titles, legend, and narrow-screen scrolling.
- **FR-014**: The catalog MUST provide 44px search, language, health-tier, sort, clear-filter, and export controls. Health tier MUST replace the existing maturity filter and default sort MUST be recent activity.
- **FR-015**: Repository cards MUST be whole-card keyboard-operable controls that show approved language, tier, recent-activity, sanitized summary, quality, metric, and relative-push-time information.
- **FR-016**: Card summary text MUST select `ai_summary.summary`, then `summary.text`, then `description`, and MUST remove markdown fragments, badges, bare URLs, bracket syntax, and markdown punctuation before display.
- **FR-017**: The catalog MUST render the approved no-results experience when no card matches the active criteria.

### Insights And Health

- **FR-018**: Insights MUST render the six prescribed stat cards and the specified commit, language, recent-activity, weekly-timeline, and quality-matrix views using approved type, colors, and interaction behavior.
- **FR-019**: Insights charts MUST use the approved colors, typeface, gridline treatment, and no chart legends.
- **FR-020**: Health MUST calculate no new attention score in the dashboard. It MUST render the source data's attention score, tier, and component values as the source of truth.
- **FR-021**: Health MUST provide the approved summary tiles, sortable maintenance table, score thresholds, responsive methodology aside, and export of the ranked list.

### Repository Drawer, Export, And States

- **FR-022**: Repository detail MUST be a right-side, full-height drawer with backdrop, focusable close control, accessible keyboard behavior, result-list previous/next controls, and the specified repository actions.
- **FR-023**: The drawer MUST show available repository stats, cleaned markdown summary, five quality indicators, attention breakdown, existing fix-score prompt logic, signals, dependencies, and website preview in the approved order and with defined conditional behavior.
- **FR-024**: The fix-score prompt MUST preserve existing blocker derivation and prompt generation while applying the new collapsible panel, severity badges, copy feedback, and visual treatment.
- **FR-025**: The export menu MUST be an accessible, dismissible menu that exports only the current Overview filtered list or Health ranked list, retains the existing CSV columns, and replaces alert dialogs with toasts.
- **FR-026**: Toasts MUST use the specified branded placement, variants, action support, mobile offset, dismissal behavior, and approved message copy for refresh, update, and export paths.
- **FR-027**: Loading, data-load-error, and unexpected-error states MUST implement the supplied visual treatment and preserve existing retry, reload, auto-retry, and development-details behavior.

### Quality And Compatibility

- **FR-028**: All interactive controls MUST have visible ember focus treatment, semantic names, keyboard operation, and WCAG AA text contrast.
- **FR-029**: Motion MUST use short color transitions only and honor `prefers-reduced-motion`.
- **FR-030**: The dashboard MUST remain responsive from narrow mobile through a 1200px maximum content container without text overlap, clipped controls, or inaccessible horizontal content.
- **FR-031**: Existing data fetching, service-worker updates, offline cache, lazy loading, and public-data-only behavior MUST remain functional.
- **FR-032**: The implementation MUST add or update tests for removed copy/iconography, active filtering, backend health-score rendering, drawer keyboard navigation, mobile tab behavior, toast/export behavior, and failure states.

### Key Entities

- **Portfolio data**: The unchanged `repositories.json` document containing profile totals, repositories, commit history, technology information, attention metrics, and generation metadata.
- **Catalog result set**: The current Overview repository list after search, language, tier, and sort operations. It controls catalog count, export content, and drawer navigation.
- **Health ranking**: The current Health list ordered by a selected backend-backed metric. It controls Health export and drawer navigation.
- **Repository detail selection**: The repository currently displayed in the side drawer, with a position in the active result set.
- **Toast**: A transient or persistent user message with ID, message, variant, duration, and optional action.

### Non-Goals

- Changing backend analytics, attention-score calculation, GitHub API calls, cache invalidation, or the `repositories.json` schema.
- Creating a dark theme, a theme switcher, or a design-preview configuration surface.
- Adding private repository support or displaying private repository data.
- Replacing the current offline/service-worker architecture or export column definitions.

## Success Criteria

### Measurable Outcomes

- **SC-001**: At desktop and mobile reference widths, all top-level routes and core states visually match the authoritative prototype's tokens, typography, layout, assets, copy, and interaction behavior, with no intentional legacy GitHub-blue, Octocat, or emoji UI remaining.
- **SC-002**: All Overview filters, sorts, Health sorts, exports, drawer navigation, refresh, offline retry, and service-worker update flows complete using the existing data contract.
- **SC-003**: Automated quality, functional, production packaging, and smoke checks pass after the redesign.
- **SC-004**: Automated and manual accessibility checks find no WCAG AA contrast failure or keyboard trap in header navigation, filters, export menu, drawer, toast actions, error recovery, or mobile tab navigation.
- **SC-005**: Loading, empty, offline, data-error, and crash states remain actionable and render without console errors for the supplied fixture data.

### Verification Plan

1. Use the extracted HTML prototype and its MakeBoldSolutions data snapshot as the visual comparison source.
2. Run the existing dashboard's quality, formatting, unit, production-package, and smoke checks.
3. Exercise desktop and mobile navigation, filters, exports, drawer keyboard controls, offline retry, service-worker update toast, and refresh against the existing data fixture.
4. Capture desktop and mobile visual comparisons for Overview, Insights, Health, repository drawer, and all recoverable states.
