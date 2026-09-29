---
gate: pr-review
status: warn
blocking: false
severity: warning
summary: "Keyboard and contrast findings are resolved; Lighthouse accessibility passes, while configured mobile performance assertions remain unresolved."
---

# Pull Request Review: Redesign GitHubSpark dashboard with Make Bold Solutions system

## Review Metadata

- **PR Number**: #3
- **Source Branch**: `001-make-bold-solutions-redesign`
- **Target Branch**: `main`
- **Review Date**: 2026-09-28 UTC
- **Last Updated**: 2026-09-28 UTC
- **Reviewed Commit**: `ccd2e56633e8b069cad9a82155ba83b0bf045ee9`
- **Reviewer**: `devspark.pr-review`
- **Constitution Version**: 1.1.1

## Revision Log

| Rev | Commit    | Date       | Critical | High | Medium | Low | CON | Test Command                       | Result                     |
| --- | --------- | ---------- | -------- | ---- | ------ | --- | --- | ---------------------------------- | -------------------------- |
| 1   | `65cc711` | 2026-09-28 | 3        | 0    | 2      | 0   | 0   | `cd frontend && npm test -- --run` | pass: 105 tests / 16 files |
| 2   | local    | 2026-09-28 | 0        | 0    | 2      | 0   | 0   | `npm test -- --run`, lint, format, build, smoke | pass: 105 tests / 16 files |
| 3   | `ccd2e56` | 2026-09-28 | 1        | 0    | 2      | 0   | 0   | `cd frontend && npm test -- --run AttentionView.test.jsx` | pass: 7 tests / 1 file |
| 4   | local | 2026-09-28 | 0        | 0    | 1      | 0   | 0   | `npm test -- --run`, lint, format, build, Lighthouse | pass: 106 tests; Lighthouse accessibility 1.00, performance gate fails |

## PR Summary

- **Author**: @markhazleton
- **Created**: 2026-09-29 UTC
- **Status**: OPEN
- **Files Changed**: 100
- **Commits**: 6
- **Lines**: +20,646 -8,670

## Stats

| Metric          |     Value |
| --------------- | --------: |
| Files changed   |       100 |
| Lines added     |   +20,646 |
| Lines removed   |    -8,670 |
| Net lines       |   +11,976 |
| Commit snapshot | `ccd2e56` |

## Executive Summary

- ✅ **Constitution Compliance**: PASS (6/6 principles checked)
- 📋 **Spec Lifecycle**: Complete
- 📝 **Task Completion**: 47/47 tasks complete
- 🔒 **Security**: 0 issues found in maintained frontend sources
- 📊 **Code Quality**: 2 recommendations
- 🧪 **Testing**: PASS (106 tests / 16 files)
- 📝 **Documentation**: ADEQUATE
- 🏛️ **Constitution Improvements**: 0 findings

**Overall Assessment**: The lifecycle and visual-comparison blockers are resolved. Health actions rely on native button activation, repository cards have complete accessible names, and Lighthouse accessibility passes. The configured mobile performance assertions remain a non-blocking follow-up.

**Approval Recommendation**: ✅ APPROVE

## Action Items

### Immediate Actions (Blocking - must resolve before merge)

- [x] **C-01** `.documentation/specs/001-make-bold-solutions-redesign/spec.md` - The feature spec is `Complete`.
- [x] **C-02** `.documentation/specs/001-make-bold-solutions-redesign/tasks.md:T045` - Visual evidence is recorded in `evidence/visual-comparison/comparison.md`.
- [x] **C-03** `frontend/src/components/Attention/AttentionView.jsx` - Sort and repository-detail actions are semantic controls with `aria-sort` and Enter/Space coverage.
- [x] **C-04** `frontend/src/components/Attention/AttentionView.jsx` - Native button actions now rely on default Enter and Space activation; `user-event` coverage asserts one detail callback.

### Recommended Improvements

- [x] **M-01** `frontend/package.json:18` - Lighthouse ran with accessibility `1.00`; its mobile performance assertions remain a separate follow-up.
- [x] **M-02** `frontend/src/components/Visualizations/QualityMatrix.module.css` - The inactive Quality Matrix border now uses `--ink-500`, exceeding the 3:1 non-text contrast target.

## What's Good

- `frontend/src/utils/repositoryPresentation.js` keeps display derivations pure and preserves the source data contract.
- `frontend/src/hooks/useDashboardShell.js` centralizes shell state and keeps `App.jsx` within the constitution's size policy.
- The Health view consumes backend `attention_score` and `attention_metrics` rather than reconstructing a competing browser-side score.
- Full Vitest validation passed: 105 tests across 16 files.
- No obvious hardcoded secrets were found in maintained frontend source files.

## Findings Detail

### Critical Issues (Blocking)

| ID   | Status  | Principle           | File:Line                                                             | Issue                                                                                                                                                                                                                                                      | Fix                                                                                                     |
| ---- | ------- | ------------------- | --------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| C-01 | ✅ Resolved | Spec Lifecycle      | `.documentation/specs/001-make-bold-solutions-redesign/spec.md`    | The spec status is `Complete`. | Verified after T045 evidence completion. |
| C-02 | ✅ Resolved | Spec Lifecycle      | `.documentation/specs/001-make-bold-solutions-redesign/tasks.md:T045` | Visual comparison evidence covers desktop, mobile, drawer, offline, and error states. | Evidence is retained under the feature spec. |
| C-03 | ✅ Resolved | Accessibility First | `frontend/src/components/Attention/AttentionView.jsx` | Sort and detail actions are semantic controls with exposed sort state and Enter/Space coverage. | Verified by the full frontend test suite. |
| C-04 | ✅ Resolved | Accessibility First | `frontend/src/components/Attention/AttentionView.jsx` | Manual keyboard callbacks were removed from native buttons. `userEvent.keyboard` verifies native Enter and Space activation, and the detail callback runs once. | Verified by 106 frontend tests. |

### High Priority Issues

None found.

### Medium Priority Suggestions

| ID   | Status  | Principle           | File:Line                                                         | Issue                                                                                                | Recommendation                                                                             |
| ---- | ------- | ------------------- | ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| M-01 | ✅ Resolved | Accessibility First | `frontend/package.json:18`                                        | Lighthouse ran against the production build and reported accessibility `1.00`; its mobile performance assertions did not pass. | Track performance separately without weakening the accessibility result. |
| M-02 | ✅ Resolved | Accessibility First | `frontend/src/components/Visualizations/QualityMatrix.module.css` | The inactive-grid border now uses `--ink-500`, which exceeds WCAG 1.4.11's 3:1 non-text target. | Verified by the Lighthouse accessibility pass. |

### Low Priority Improvements

None found.

### Constitution Improvements

None found.

## Constitution Alignment Details

| Principle                   | Status  | Evidence                                            | Notes                                                                                                    |
| --------------------------- | ------- | --------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Single Responsibility       | ✅ Pass | `useDashboardShell.js`, `repositoryPresentation.js` | Shell state and display helpers are separated; no modified module exceeds 800 LOC.                       |
| Data Privacy                | ✅ Pass | No fetcher/data-schema changes                      | Public-only filtering and static data contract remain intact.                                            |
| Fail Fast, Fail Loud        | ✅ Pass | Loading, error, retry, toast paths                  | Recovery paths remain present and covered by tests.                                                      |
| Change-Driven Caching       | ✅ Pass | `dataService` remains unchanged                     | Refresh uses the existing cache-clear/refetch flow.                                                      |
| Accessibility First         | ✅ Pass | `AttentionView.jsx`, `RepositoryGrid.jsx`, `Badge.module.css` | Native buttons activate once, interactive cards expose complete names, and Lighthouse accessibility is 1.00. |
| Generated Artifact Boundary | ✅ Pass | Build output redirected to `.validation/site`       | No generated artifact boundary changes are introduced.                                                   |

## Security Checklist

- [x] No hardcoded secrets or credentials
- [x] Input validation present where needed
- [x] Authentication/authorization checks appropriate
- [x] No SQL injection vulnerabilities
- [x] No XSS vulnerabilities observed in reviewed React rendering paths
- [x] Dependencies reviewed for vulnerabilities

No backend, credential, or persistence surface was added. The new `lucide-react` dependency is justified by the design-system icon requirement.

## Testing Coverage

**Status**: ADEQUATE. `userEvent.keyboard` exercises native Enter and Space activation, including a single-callback assertion for repository detail; the full suite has 106 passing tests.

Executed full tests, lint, formatting, and a production build. `npm run lighthouse` reports accessibility `1.00`, best practices `1.00`, and no layout shift or blocking time; it remains nonzero only for configured mobile performance assertions.

## Test Inventory

| File                        |    Main |  Branch |    Delta | Justification                                                                |
| --------------------------- | ------: | ------: | -------: | ---------------------------------------------------------------------------- |
| `frontend/tests/*.test.jsx` |     105 |     105 |     +105 | The redesign adds interaction, recovery, presentation, and utility coverage. |
| **Total**                   | **105** | **105** | **+105** |                                                                              |

Removed tests: None identified.

## Documentation Status

**Status**: ADEQUATE

The feature spec, plan, tasks, quickstart, Analyze gate, Critic gate, and retained visual evidence document scope, validation, and known QA follow-ups.

## Changed Files Summary

| File group                                            | Tier | Changes                             | Type           | Findings          |
| ----------------------------------------------------- | ---- | ----------------------------------- | -------------- | ----------------- |
| `frontend/src/components/Attention/AttentionView.jsx` | P1   | Health data and interaction rewrite | Modified       | Resolved C-03; C-04 |
| `frontend/src/hooks/useDashboardShell.js`             | P1   | Shell-state extraction              | Added          | None              |
| `frontend/src/utils/repositoryPresentation.js`        | P1   | Pure presentation helpers           | Added          | None              |
| `frontend/tests/*.test.jsx`                           | P2   | 105-test frontend suite             | Added/Modified | C-04 masked by synthetic keydown |
| `frontend/package.json`                               | P2   | Icon and test dependencies/scripts  | Modified       | M-01              |
| `.documentation/**`                                   | P3   | Handoff and lifecycle artifacts     | Added/Modified | Resolved C-01, C-02 |

## Behavioral Changes

| Change            | Before                          | After                                            | Intentional? | Risk                                                                 |
| ----------------- | ------------------------------- | ------------------------------------------------ | ------------ | -------------------------------------------------------------------- |
| Health scoring    | Browser-derived composite score | Source `attention_score` and `attention_metrics` | Yes          | Reduces source/display divergence.                                   |
| Theme selection   | User-facing theme toggle        | Permanent light theme                            | Yes          | Smoke coverage was updated.                                          |
| Drawer navigation | App-level default list          | Initiating view's active list                    | Yes          | Overview and Health behavior verified.                               |
| Health keyboard activation | One semantic control action | `onKeyDown` action plus native button click | No | Enter sorts twice and may call detail navigation twice. |

## Approval Decision

**Recommendation**: ✅ APPROVE

**Reasoning**: The required visual comparison is complete, the feature lifecycle is closed, and all accessibility findings are resolved. The Lighthouse performance thresholds need separate performance work but do not alter the accessibility disposition.

**Estimated Rework Time**: 1-3 hours, excluding the manual visual comparison.

## Resolution Contract

```yaml
findings:
  - finding_id: pr-3-c-01
    severity: critical
    description: "The feature specification remains In Progress."
    recommended_action: "Complete the lifecycle and update the spec status to Complete before merge."
    execution_mode: manual
    status: resolved
    outcome: "T045 evidence was captured and the spec status was updated to Complete."
  - finding_id: pr-3-c-02
    severity: critical
    description: "T045 visual comparison remains incomplete."
    recommended_action: "Capture the required desktop and mobile comparisons and mark T045 complete."
    execution_mode: manual
    status: resolved
    outcome: "Desktop and mobile comparison evidence was captured for all required states."
  - finding_id: pr-3-c-03
    severity: critical
    description: "Health sorting and row activation are pointer-only and inaccessible to keyboard users."
    recommended_action: "Use semantic keyboard-operable controls, expose sort state, and add keyboard interaction tests."
    execution_mode: auto
    status: resolved
    outcome: "Semantic controls, aria-sort, and Enter/Space coverage were added."
  - finding_id: pr-3-m-01
    severity: medium
    description: "No automated Lighthouse accessibility evidence accompanies the completed implementation."
    recommended_action: "Run the existing Lighthouse script against the production build and address actionable findings."
    execution_mode: manual
    status: resolved
    outcome: "Lighthouse accessibility scored 1.00; only configured mobile performance assertions remain nonzero."
  - finding_id: pr-3-m-02
    severity: medium
    description: "The inactive Quality Matrix border is documented as below WCAG non-text contrast guidance."
    recommended_action: "Darken the border or obtain an explicit design exception."
    execution_mode: selective
    status: resolved
    outcome: "The inactive square border now uses --ink-500, exceeding 3:1 non-text contrast."
  - finding_id: pr-3-c-04
    severity: critical
    description: "Native Health-table buttons invoke actions from both onKeyDown and their default click behavior."
    recommended_action: "Remove manual keyboard action handlers from native buttons and test a real keyboard activation path."
    execution_mode: auto
    status: resolved
    outcome: "Removed manual onKeyDown actions from native buttons and added user-event keyboard coverage."
```

---

_Review generated by devspark.pr-review_
_Constitution-driven code review for GitHub Stats Spark_
_To re-review after fixes: `/devspark.pr-review #3 re-review`_
_When addressing these findings, run `/devspark.address-pr-review 3`. The review file must be committed on its own._
