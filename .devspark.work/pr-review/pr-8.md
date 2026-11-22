---
pr: 8
devspark_version: 9.6.0
reviewed_commit: 6f936707f15f362dbe777bf236957ba5f35226bc
revision: 5
findings: &id001
  critical: 0
  high: 0
  medium: 1
  low: 2
  con: 0
historical_findings: *id001
current_findings:
  critical: 0
  high: 0
  medium: 1
  low: 2
current_state_counts:
  open: 0
  remediated: 0
  awaiting-verification: 3
  reopened: 0
  resolved: 0
unresolved_blockers: 1
recommendation: request-changes
gate_status: pass
max_severity: medium
risk_rating: high
risk_score: 14
risk_escalated: false
review_state:
  format_version: 1
  findings:
  - finding_id: M-01
    aliases: []
    severity: medium
    category: testing
    blocking: true
    description: 'The tests for portfolio detection were removed with UserPicker.test.jsx,
      but the behavior moved to usePortfolio and is now untested. usePortfolio decides
      public versus self-hosted mode (a static host that answers portfolio.json with
      HTML, or a network failure, must yield portfolio null), which sources are listed
      (enabled user/org/repo only), their slugs, and which are ready (HEAD check).
      The self-hosted loading path in useRepositoryData (choose sources for the scope,
      fetch each, merge) is also never exercised: App.test.jsx mocks both hooks. This
      is the switch that keeps the public Pages dashboard unchanged.'
    expected_outcome: Executable tests cover usePortfolio (HTML response and network
      failure give portfolio null; disabled and unsupported sources are dropped; worker
      slug wins, derived slug otherwise; uncollected sources are not ready) and the
      self-hosted branch of useRepositoryData (fetches only the scope's sources and
      merges them; public mode fetches the single profile).
    evidence:
    - frontend/tests/UserPicker.test.jsx deleted; its useUserOptions cases (static
      host HTML, readiness, slug derivation, network failure) have no successor
    - 'frontend/src/hooks/usePortfolio.js:54-105 carries the same logic with no direct
      test (grep: only App.test.jsx references usePortfolio, as a mock)'
    - frontend/tests/App.test.jsx mocks @/hooks/useRepositoryData, so useRepositoryData.js:44-53
      (sourcesForScope + Promise.all + mergeDashboards) never runs under test
    recommended_action: Port the removed cases to a usePortfolio test (renderHook
      with a stubbed fetch), and add a useRepositoryData test that stubs fetchDashboardData
      and asserts the requested users and the merged result for a client scope and
      for public mode.
    execution_mode: manual
    status: awaiting-verification
    outcome: ''
    provenance:
      kind: native
      location: frontend/src/hooks/usePortfolio.js:54
    remediation:
      correction_commit: 41084831851017145a8897a565aad79a2b4bbe4e
      author_context: Claude Code session that authored the PR (same session as the
        review)
      explanation: 'New tests/DataHooks.test.jsx: usePortfolio returns portfolio null
        for an HTML response and for a network failure, keeps only enabled user/org/repo
        sources, uses the worker slug or derives one, and marks uncollected sources
        not ready; useRepositoryData waits for the portfolio, loads the single profile
        in public mode, and in a scope fetches only the needed sources and merges
        them (re-fetching only `me` for the Internal client).'
      author_validation: './run-validation.ps1 exit 0 at 41084831851017145a8897a565aad79a2b4bbe4e:
        pytest 572 passed, vitest 213 passed (23 files), eslint, prettier, build,
        pip-audit and npm audit clean.'
      proof_obligation: A distinct reviewer confirms the tests exercise the real hooks
        (not mocks of them) and would fail if public-mode detection or scope source
        selection regressed.
    verification: null
    disposition: null
    reopen_reason: null
  - finding_id: L-01
    aliases: []
    severity: low
    category: correctness
    blocking: false
    description: 'Merging sources puts repositories from different owners in one list,
      but the list is still keyed and navigated by the short name. Two repositories
      with the same name collide: duplicate React keys in the Health table and Overview
      grid, and drawer Previous/Next and its position counter find the first match.
      Before this PR each list held one owner''s repositories.'
    expected_outcome: Lists and drawer navigation identify a repository by its full
      name.
    evidence:
    - frontend/src/hooks/useDashboardShell.js:133,143 and frontend/src/App.jsx:426
      compare `r.name === selectedRepo.name`
    - frontend/src/components/Attention/AttentionView.jsx:229 `key={repo.name}`; RepositoryGrid.jsx:341
      `key={repo.name}`
    - Server portfolio.json (2026-11-22) lists two repositories named apitestspark
      under different owners; the collected files currently hold only one, so the
      collision is not yet visible
    recommended_action: Compare and key on fullNameOf(repo) (already exported from
      utils/scope.js) in useDashboardShell, App and the list keys.
    execution_mode: manual
    status: awaiting-verification
    outcome: ''
    provenance:
      kind: native
      location: frontend/src/hooks/useDashboardShell.js:133
    remediation:
      correction_commit: 41084831851017145a8897a565aad79a2b4bbe4e
      author_context: Claude Code session that authored the PR (same session as the
        review)
      explanation: 'useDashboardShell exports sameRepo (full-name comparison via fullNameOf);
        drawer Previous/Next and the position counter in App use it, and Health rows,
        Overview cards and QualityMatrix rows are keyed by full name. Regression test:
        in a list with Acme/api and Me/api, Next from Me/api goes to Me/tool (name
        matching would stay on Me/api).'
      author_validation: './run-validation.ps1 exit 0 at 41084831851017145a8897a565aad79a2b4bbe4e:
        pytest 572 passed, vitest 213 passed (23 files), eslint, prettier, build,
        pip-audit and npm audit clean.'
      proof_obligation: A distinct reviewer confirms two repositories sharing a name
        are distinct in lists and drawer navigation, and that single-owner (public)
        lists behave as before.
    verification: null
    disposition: null
    reopen_reason: null
  - finding_id: L-02
    aliases: []
    severity: low
    category: error-handling
    blocking: false
    description: A portfolio or client scope now loads several source files with Promise.all,
      so one failing file replaces every section with 'Error loading data', and the
      message (from fetchDashboardData) does not say which source failed. Principle
      III requires errors to include context and actionable guidance.
    expected_outcome: A failed source file is named in the error shown to the operator.
    evidence:
    - frontend/src/hooks/useRepositoryData.js:48-52 `await Promise.all(slugs.map(...
      fetchDashboardData ...))`
    - 'frontend/src/services/dataService.js:129-130 error text is `Failed to fetch
      dashboard data: ${status} ${statusText}` with no source'
    recommended_action: 'Smallest: wrap each fetch so a rejection is rethrown as `Could
      not load <source>: <message>`. Optional: use Promise.allSettled and show the
      loaded sources with a notice naming the failed one.'
    execution_mode: manual
    status: awaiting-verification
    outcome: ''
    provenance:
      kind: native
      location: frontend/src/hooks/useRepositoryData.js:48
    remediation:
      correction_commit: 41084831851017145a8897a565aad79a2b4bbe4e
      author_context: Claude Code session that authored the PR (same session as the
        review)
      explanation: 'useRepositoryData rethrows each failed source fetch as `Could
        not load the data for source "<slug>": <cause>`. Test asserts the message
        for a 404 on one of two sources.'
      author_validation: './run-validation.ps1 exit 0 at 41084831851017145a8897a565aad79a2b4bbe4e:
        pytest 572 passed, vitest 213 passed (23 files), eslint, prettier, build,
        pip-audit and npm audit clean.'
      proof_obligation: A distinct reviewer confirms the error shown names the failing
        source and keeps the cause.
    verification: null
    disposition: null
    reopen_reason: null
  conditions: []
  last_change:
    operation: remediate-and-submit
    affected:
    - L-02
    event_fingerprint: 5f76b4246051861f35f770ad20b233cfa27d6853b587ddef725ae79692923e3e
    actor_role: ''
    actor_context: ''
    explanation: ''
---
# Pull Request Review: feat(dashboard): unified operator experience with one scope

- **PR**: #8 — 002-work-ps-022-unified-operator → main — OPEN
- **Reviewed Commit**: 6f936707f15f362dbe777bf236957ba5f35226bc
- **Review Date**: 2026-11-22 02:57:14 UTC (last updated 2026-11-22 02:57:14 UTC)
- **Constitution Version**: 1.2.0

## Revision Log

| Rev | Commit | Date | Critical | High | Medium | Low | CON | Test Command | Result |
|-----|--------|------|----------|------|--------|-----|-----|--------------|--------|
| 1 | 6f93670 | 2026-11-22 | 0 | 0 | 1 | 2 | 0 | `npx vitest run` (frontend); reused: CI validate on 6f93670 | pass |

## Test Evidence

- reused: GitHub Actions `validate` on 6f93670 — pass (run 44977744728; full `run-validation` incl. pytest, vitest, lint, build, audits).
- Reviewer run (trigger: author-reported local evidence on a high-risk delta): `npx vitest run` in `frontend/` at 6f93670, clean tree, exit 0, 22 files / 206 tests passed.
- Author evidence cited in the PR (not re-run): HTML diff of the public dashboard against `main` (identical Overview, Insights, Health; footer label only), and a run of the scope/merge/alert helpers on the server's data files. Neither is committed, so neither is reproducible from the repository.

## Stats

| Metric | Value |
|--------|-------|
| Files changed | 62 |
| Commits | 2 |
| Lines | +3439 −2803 |
| Tiers (P0/P1/P2/P3) | 5/48/7/2 |
| Risk | high (14) — p0_files, auth_or_security_path, large_diff; Knowledge absent (live) |

## Executive Summary

**Overall Assessment**: The scope model, stored-count overlay and shared components are small, pure where it matters, and well unit-tested; the public views are unchanged by the author's evidence. One blocking gap: the hooks that decide public versus self-hosted mode and that load a multi-source scope lost or never had tests. The reviewer is the authoring session, so this is not an independent review. Knowledge is `absent` (`.knowledge/` holds only the constitution), so tiers come from path patterns alone.

- Constitution: PASS with one partial (5 applicable principles evaluated) · Durable delta: FAIL (1 open PRD3-class finding, M-01)
- Security: 0 issues · Quality: 2 recommendations · Testing: INADEQUATE (M-01) · Docs: PASS
- Constitution Improvements: 0 CON findings

<!-- PR-REVIEW-DERIVED:ACTION:BEGIN -->
## Action Items

### Immediate Actions (Blocking)

- [ ] **M-01** [Pending independent verification] — The tests for portfolio detection were removed with UserPicker.test.jsx, but the behavior moved to usePortfolio and is now untested. usePortfolio decides public versus self-hosted mode (a static host that answers portfolio.json with HTML, or a network failure, must yield portfolio null), which sources are listed (enabled user/org/repo only), their slugs, and which are ready (HEAD check). The self-hosted loading path in useRepositoryData (choose sources for the scope, fetch each, merge) is also never exercised: App.test.jsx mocks both hooks. This is the switch that keeps the public Pages dashboard unchanged.

### Recommended Improvements

- [ ] **L-01** [awaiting-verification] — Merging sources puts repositories from different owners in one list, but the list is still keyed and navigated by the short name. Two repositories with the same name collide: duplicate React keys in the Health table and Overview grid, and drawer Previous/Next and its position counter find the first match. Before this PR each list held one owner's repositories.
- [ ] **L-02** [awaiting-verification] — A portfolio or client scope now loads several source files with Promise.all, so one failing file replaces every section with 'Error loading data', and the message (from fetchDashboardData) does not say which source failed. Principle III requires errors to include context and actionable guidance.

### Constitution Improvements

- None.
<!-- PR-REVIEW-DERIVED:ACTION:END -->
<!-- PR-REVIEW-DERIVED:DETAIL:BEGIN -->
## Findings Detail

| ID | Status | Severity | Blocking | Issue | Expected outcome | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| M-01 | Pending verification | medium | Yes | The tests for portfolio detection were removed with UserPicker.test.jsx, but the behavior moved to usePortfolio and is now untested. usePortfolio decides public versus self-hosted mode (a static host that answers portfolio.json with HTML, or a network failure, must yield portfolio null), which sources are listed (enabled user/org/repo only), their slugs, and which are ready (HEAD check). The self-hosted loading path in useRepositoryData (choose sources for the scope, fetch each, merge) is also never exercised: App.test.jsx mocks both hooks. This is the switch that keeps the public Pages dashboard unchanged. | Executable tests cover usePortfolio (HTML response and network failure give portfolio null; disabled and unsupported sources are dropped; worker slug wins, derived slug otherwise; uncollected sources are not ready) and the self-hosted branch of useRepositoryData (fetches only the scope's sources and merges them; public mode fetches the single profile). | frontend/tests/UserPicker.test.jsx deleted; its useUserOptions cases (static host HTML, readiness, slug derivation, network failure) have no successor; frontend/src/hooks/usePortfolio.js:54-105 carries the same logic with no direct test (grep: only App.test.jsx references usePortfolio, as a mock); frontend/tests/App.test.jsx mocks @/hooks/useRepositoryData, so useRepositoryData.js:44-53 (sourcesForScope + Promise.all + mergeDashboards) never runs under test |
| L-01 | Pending verification | low | No | Merging sources puts repositories from different owners in one list, but the list is still keyed and navigated by the short name. Two repositories with the same name collide: duplicate React keys in the Health table and Overview grid, and drawer Previous/Next and its position counter find the first match. Before this PR each list held one owner's repositories. | Lists and drawer navigation identify a repository by its full name. | frontend/src/hooks/useDashboardShell.js:133,143 and frontend/src/App.jsx:426 compare `r.name === selectedRepo.name`; frontend/src/components/Attention/AttentionView.jsx:229 `key={repo.name}`; RepositoryGrid.jsx:341 `key={repo.name}`; Server portfolio.json (2026-11-22) lists two repositories named apitestspark under different owners; the collected files currently hold only one, so the collision is not yet visible |
| L-02 | Pending verification | low | No | A portfolio or client scope now loads several source files with Promise.all, so one failing file replaces every section with 'Error loading data', and the message (from fetchDashboardData) does not say which source failed. Principle III requires errors to include context and actionable guidance. | A failed source file is named in the error shown to the operator. | frontend/src/hooks/useRepositoryData.js:48-52 `await Promise.all(slugs.map(... fetchDashboardData ...))`; frontend/src/services/dataService.js:129-130 error text is `Failed to fetch dashboard data: ${status} ${statusText}` with no source |
<!-- PR-REVIEW-DERIVED:DETAIL:END -->

## Constitution Alignment Details

**Passing**: 4 of 5 applicable principles (I Single Responsibility, II Data Privacy, V Accessibility, VII Self-Hosted Mode). IV and VI are not applicable to this frontend-only delta.

| Principle | Status | Evidence | Notes |
|-----------|--------|----------|-------|
| III. Fail Fast, Fail Loud | ⚠️ Partial | frontend/src/hooks/useRepositoryData.js:48 | A failed source file is not named in the error (L-02) |

Notes on passing principles: App.jsx is 444 lines after the split and no new file exceeds 500. No new export, route or file is written; the public build reads no self-hosted file it did not read before. New controls are labelled, the More menu exposes `aria-expanded`/`aria-controls`, tables are captioned with scoped headers.

## Security

No issues. CSV export now neutralises formula starters for every table (it previously did so only for Security alerts); no new dependency; the admin API and its auth are unchanged.

## Testing

**Status**: INADEQUATE — reviewer-run vitest passes (206), but the mode-detection and multi-source loading hooks are untested (M-01).

| File | Changes | Type |
|------|---------|------|
| frontend/tests/RepositoryDetail.test.jsx | +75 -0 | Modified |
| frontend/tests/App.test.jsx | +256 -14 | Modified |
| frontend/tests/AttentionView.test.jsx | +20 -2 | Modified |
| frontend/tests/Scope.test.jsx | +401 -0 | Added |
| frontend/tests/SecurityView.test.jsx | +40 -6 | Modified |
| frontend/tests/SharedComponents.test.jsx | +256 -0 | Added |
| frontend/tests/SourcesView.test.jsx | +2 -2 | Modified |
| frontend/tests/UserPicker.test.jsx | +0 -196 | Deleted |

Removed tests:

- `tests/UserPicker.test.jsx` — **Unjustified (partly)**: the picker UI is gone, but its `useUserOptions` cases cover behavior that still exists in `usePortfolio` → M-01

## Changed Files

| File | Tier | Changes | Type |
|------|------|---------|------|
| frontend/src/components/DrillDown/RepositoryDetail.jsx | P0 | +10 -0 | Modified |
| frontend/src/components/Security/SecurityView.jsx | P0 | +87 -205 | Modified |
| frontend/src/components/Security/SecurityView.module.css | P0 | +16 -84 | Modified |
| frontend/src/components/Security/alertColumns.jsx | P0 | +115 -0 | Added |
| frontend/tests/RepositoryDetail.test.jsx | P0 | +75 -0 | Modified |
| frontend/src/App.jsx | P1 | +271 -309 | Modified |
| frontend/src/components/Admin/SourcesView.jsx | P1 | +12 -10 | Modified |
| frontend/src/components/Attention/AttentionView.jsx | P1 | +19 -1 | Modified |
| frontend/src/components/Common/CoverageState.jsx | P1 | +92 -0 | Added |
| frontend/src/components/Common/DataTable.jsx | P1 | +76 -0 | Added |
| frontend/src/components/Common/DataViews.module.css | P1 | +106 -0 | Added |
| frontend/src/components/Common/ExportButton.jsx | P1 | +120 -104 | Modified |
| frontend/src/components/Common/FilterBar.jsx | P1 | +63 -0 | Added |
| frontend/src/components/Common/PageHeader.jsx | P1 | +59 -0 | Added |
| frontend/src/components/Common/ScopeSelector.jsx | P1 | +133 -0 | Added |
| frontend/src/components/Common/ScopeSelector.module.css | P1 | +26 -0 | Added |
| frontend/src/components/Common/Tooltip.jsx | P1 | +0 -93 | Deleted |
| frontend/src/components/Common/Tooltip.module.css | P1 | +0 -107 | Deleted |
| frontend/src/components/Common/UserPicker.jsx | P1 | +0 -97 | Deleted |
| frontend/src/components/Common/UserPicker.module.css | P1 | +0 -25 | Deleted |
| frontend/src/components/DrillDown/RepositoryDetail/hooks/useSectionToggles.js | P1 | +1 -0 | Modified |
| frontend/src/components/DrillDown/RepositoryDetail/sections/SecuritySection.jsx | P1 | +61 -0 | Added |
| frontend/src/components/Layout/Container/Container.css | P1 | +0 -51 | Deleted |
| frontend/src/components/Layout/Container/Container.jsx | P1 | +0 -44 | Deleted |
| frontend/src/components/Layout/SafeArea/SafeArea.css | P1 | +0 -8 | Deleted |
| frontend/src/components/Layout/SafeArea/SafeArea.jsx | P1 | +0 -33 | Deleted |
| frontend/src/components/Layout/SkipLink/SkipLink.css | P1 | +0 -39 | Deleted |
| frontend/src/components/Layout/SkipLink/SkipLink.jsx | P1 | +0 -18 | Deleted |
| frontend/src/components/Layout/Stack/Stack.css | P1 | +0 -57 | Deleted |
| frontend/src/components/Layout/Stack/Stack.jsx | P1 | +0 -60 | Deleted |
| frontend/src/components/Mobile/BottomSheet/BottomSheet.css | P1 | +0 -146 | Deleted |
| frontend/src/components/Mobile/BottomSheet/BottomSheet.jsx | P1 | +0 -141 | Deleted |
| frontend/src/components/Mobile/GestureHandler/GestureHandler.css | P1 | +0 -149 | Deleted |
| frontend/src/components/Mobile/GestureHandler/GestureHandler.jsx | P1 | +0 -158 | Deleted |
| frontend/src/components/Mobile/LoadingState/LoadingState.css | P1 | +0 -110 | Deleted |
| frontend/src/components/Mobile/LoadingState/LoadingState.jsx | P1 | +0 -87 | Deleted |
| frontend/src/components/Mobile/TabBar/TabBar.css | P1 | +41 -0 | Modified |
| frontend/src/components/Mobile/TabBar/TabBar.jsx | P1 | +104 -39 | Modified |
| frontend/src/components/Mobile/TouchTarget/TouchTarget.css | P1 | +0 -11 | Deleted |
| frontend/src/components/Mobile/TouchTarget/TouchTarget.jsx | P1 | +0 -76 | Deleted |
| ... 22 more P2/P3 files not listed | | | |

## Behavioral Changes

| Change | Before | After | Intentional? | Risk |
|--------|--------|-------|-------------|------|
| Self-hosted landing scope | Default user `makeboldsolutions` | Whole portfolio, merged from every collected source | Yes (PR description) | Overview shows no profile hero until a single source is chosen |
| Health alert cell | `0` when alerts could not be read | Coverage badge (e.g. "No access") | Yes | None; public data normally reads `available` |
| CSV export | Formula starters exported raw; "Dependabot Open Alerts" column always empty (wrong key) | Prefixed with `'`; column filled from `total_open` | Yes | Public CSV output changes for text cells starting with `= + - @` |
| Footer button | "Refresh" / "Force refresh repositories data" | "Reload data" / "Reload data from the published files" | Yes | Public footer text changes |
| Admin hash | `#sources` | `#admin` (`#sources` still resolves) | Yes | None |

## Deployment & Handoff Notes

### Deployment Notes

- After deploy, choose a client and a domain filter on the server and confirm Security and Health follow the scope and show the same alert counts (stated in the PR).

### Handoff Notes

None.

### Observations

- Until the first security collection after a fresh start, stored coverage is `not_checked`, so Health shows "Not checked yet" instead of the collected count. This follows the one-number rule and clears on the first security run (minutes after start).
- On server data the per-source files hold 38 repositories while the portfolio and Security list 45; the collector writes fewer records than discovery finds. Pre-existing and unrelated to this change.
- The attention score is still computed at collection time from the first-page counts; only displayed counts changed. Documented in the PR and the deployment guide.
- A drawer opened from Security for a repository with no collected record shows a minimal record (name and link). Acceptable; noted for the Sites/Delivery panels that will reuse it.
- `get-pr-context.ps1` returns `number`, `title` and `head_sha` as null for this PR; `commit_sha` was used.

<!-- PR-REVIEW-DERIVED:DECISION:BEGIN -->
## Approval Decision

**Recommendation**: REQUEST CHANGES — derived from current blockers and applicable review conditions.

*This local recommendation does not cast a hosted approval vote or authorize merge.*
<!-- PR-REVIEW-DERIVED:DECISION:END -->

---

*Re-review after fixes: `/devspark-pr-review #8 re-review`. Address findings with `/devspark-address-pr-review 8`; commit the review file on its own.*

---

<!-- PR-REVIEW-DERIVED:SUMMARY:BEGIN -->
## Current Review State

- Historical unique findings: 3
- Current unresolved findings by severity: {'critical': 0, 'high': 0, 'medium': 1, 'low': 2}
- Current lifecycle state counts: {'open': 0, 'remediated': 0, 'awaiting-verification': 3, 'reopened': 0, 'resolved': 0}
- Unresolved blockers: 1
- Pending independent verification: 3
- Review conditions: pass
- Local recommendation: request-changes
<!-- PR-REVIEW-DERIVED:SUMMARY:END -->
