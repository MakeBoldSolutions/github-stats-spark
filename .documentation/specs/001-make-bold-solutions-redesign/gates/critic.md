---
gate: critic
status: pass
blocking: false
severity: info
summary: "The task plan now replaces the retired theme-toggle smoke assertion before validation and isolates app-shell state in a focused hook."
---

## Technical Risk Assessment

**Analysis Date:** 2026-09-28
**Risk Posture:** YELLOW
**Detected Stack:** JavaScript + React 19/Vite + static JSON/IndexedDB cache

### Executive Summary

The redesign is a contained static-frontend change with public-only data, per-user cache keys, retries, and recovery paths already in place. The task plan now replaces the legacy theme-toggle browser smoke assertion before the required validation run and extracts growing shell state from `App.jsx`.

### Showstopper Risks (Must Fix Before Implementation)

None.

### Critical Risks (High Probability of Costly Issues)

| ID  | Category              | Location                                          | Risk Description                                                                                                                                                                | Likely Impact                                                   | Recommended Action         |
| --- | --------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- | -------------------------- |
| C1  | Validation regression | `frontend/scripts/smoke.mjs`; tasks.md:T042, T044 | T042 now replaces the retired theme-toggle assertion with permanent-light-shell, navigation, mobile-tab-bar, and no-theme-toggle coverage before T044 runs the validation gate. | The required smoke gate remains aligned with the redesigned UI. | Complete T042 before T044. |

### High-Priority Concerns

| ID  | Category             | Location                              | Issue                                                                                                                         | Impact                                                                                    | Suggestion                                       |
| --- | -------------------- | ------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------ |
| H1  | Component complexity | `frontend/src/App.jsx`; tasks.md:T010 | T010 now extracts dashboard-shell state into `useDashboardShell.js` and keeps `App.jsx` compositional before later view work. | Drawer navigation, refresh feedback, and `?user=` behavior have a focused testable owner. | Complete T010 before dependent view integration. |

### Framework-Specific Red Flags

- [x] No new asynchronous backend or database layer is introduced; existing fetch timeout, retry, cache, and per-user cache-key behavior remain the correct pattern.
- [x] No new authentication, CORS, or API-versioning surface is introduced by this static dashboard redesign.
- [x] Browser smoke coverage is explicitly updated for the retired theme control before the required validation run.
- [x] App-shell state is constrained through the planned dashboard-shell hook.

### Architecture Red Flags

- [ ] Over-engineered for stated requirements
- [ ] Under-engineered for implied scale
- [ ] Single point of failure without redundancy
- [ ] Missing standard patterns for problem domain
- [ ] Inadequate async/concurrency handling

The resolved items were bounded frontend integration risks, not availability or data-integrity risks. The static data service already scopes offline cache entries by selected user and handles retry/fallback behavior.

### Missing Critical Tasks

- **Observability:** None beyond preserving existing actionable error paths and browser-console smoke checks.
- **Operations:** None; GitHub Pages deployment and service-worker architecture are intentionally unchanged.
- **Testing:** None; T042 now updates the browser smoke script for fixed-light and mobile-navigation coverage.
- **Documentation:** None; the plan, UI contract, and quickstart cover the intended architecture and verification flow.
- **Security:** None; no new input, credential, private-data, or server endpoint surface is introduced.

### Questionable Assumptions

1. **Existing smoke coverage will remain valid after visual-control removal.** → Addressed by T042's replacement coverage before T044.
2. **App-shell ownership can absorb all redesign state without structural work.** → Addressed by extracting `useDashboardShell.js` in T010.

### Dependencies Risk Assessment

| Dependency              | Concern                                                                                                                       | Alternative to Consider                                                             |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `lucide-react`          | Adds a production dependency, but it replaces scattered inline symbols and emoji UI with the approved accessible icon system. | Retain the dependency; it is justified by the documented design-system requirement. |
| Existing Chart.js stack | Visual restyling could tempt a full chart rewrite and destabilize lazy-loaded analytics.                                      | Keep existing chart dependencies and use semantic CSS-led views where prescribed.   |

### Estimated Technical Debt at Launch

- **Code Debt:** Low when T010 extracts app-shell state before additional view integration.
- **Operational Debt:** None beyond existing static-host and service-worker behavior.
- **Documentation Debt:** None identified.
- **Testing Debt:** Low when T042 replaces the retired theme assertion before T044.

### Metrics

- Showstopper Count: 0
- Critical Risk Count: 0
- High-Priority Concern Count: 0
- Missing Operational Tasks: 0
- Underspecified Security Requirements: 0
- Scale Bottlenecks Identified: 0

## GO/NO-GO RECOMMENDATION

```text
[ ] STOP - Showstoppers present, cannot proceed to implementation
[ ] CONDITIONAL - Fix critical risks first, then reassess
[x] PROCEED WITH CAUTION - Document acknowledged risks, add mitigation tasks
```

## Required Actions Before Implementation

1. Complete T010 before adding further app-shell behavior.
2. Complete T042 before T044 runs the smoke gate.

## Recommended Risk Mitigations

- Preserve browser coverage for the default and non-default public user paths while implementing `useDashboardShell.js`.

## Resolution Contract

```yaml
findings:
  - finding_id: critic-001
    severity: critical
    description: "The required smoke script asserts the theme toggle that T042 removes, so the T044 validation gate will fail after the intended redesign."
    recommended_action: "Add a task to replace the theme-toggle smoke assertion with permanent-light-shell, navigation, and mobile-tab-bar checks before running T044."
    execution_mode: auto
    status: resolved
    outcome: "T042 now replaces the retired theme-toggle assertion before T044 runs smoke validation."
  - finding_id: critic-002
    severity: high
    description: "App.jsx is already 528 lines and is assigned additional cross-cutting state without an explicit extraction boundary."
    recommended_action: "Refine T010 to extract a focused app-shell state hook or controller and keep App.jsx primarily compositional."
    execution_mode: selective
    status: resolved
    outcome: "T010 now extracts dashboard-shell state into useDashboardShell.js before dependent integration work."
```
