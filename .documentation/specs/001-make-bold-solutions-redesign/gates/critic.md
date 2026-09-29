---
gate: critic
status: pass
blocking: false
severity: info
summary: "One constitution-level (WCAG AA contrast) showstopper was found by hand-computed luminance analysis and fixed during this pass; remaining risks are acknowledged, non-blocking QA gaps (T045 visual comparison, manual offline/toast exercise, non-text border contrast)."
---

## Technical Risk Assessment

**Analysis Date:** 2026-09-28 (post-implementation, T001-T044 complete)
**Risk Posture:** YELLOW (was RED before this pass's fix — see Showstopper Risks)
**Detected Stack:** JavaScript + React 19/Vite + static JSON/IndexedDB cache + CSS Modules (no backend/async/database risk surface — the checklist below is adapted accordingly)

### Executive Summary

This is a contained static-frontend visual redesign with no new data flow, API surface, or async/concurrency risk. The one real production-impacting risk found — two WCAG AA text-contrast failures baked into the approved design tokens — was verified by hand-computed relative-luminance contrast ratios (not assumed) and fixed in this pass by re-pointing the `--text-muted` semantic alias and two "off-state" quality-indicator colors from `ink-400`/`ink-500` to `ink-600`. All 105 automated tests, lint, format, and the browser smoke check pass after the fix. Remaining risk is confined to QA coverage gaps (visual screenshot comparison, live manual offline/toast exercise) rather than code defects.

### Showstopper Risks (Must Fix Before Implementation)

| ID  | Category      | Location                                                                                                   | Risk Description                                                                                                                                                                                                                                                                          | Likely Impact                                                                                                   | Mitigation Required                                                                                                                                                             |
| --- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| S1  | Accessibility (Constitution V, NON-NEGOTIABLE) | `styles/brand/colors.css` `--text-muted` (was `var(--ink-500)`)                                                                                          | Hand-computed relative luminance: `ink-500` (#76736c) on `--cream` (#f8f6f2) = **4.38:1**, below the WCAG AA 4.5:1 minimum for normal text. `--text-muted` is used pervasively (sublabels, meta text, catalog counts, footer timestamp) directly on the cream page background, not only inside white cards. | Widespread AA contrast failure across nearly every view — an automated axe/Lighthouse accessibility audit (SC-004) would fail immediately. | **FIXED in this pass**: re-pointed `--text-muted` to `var(--ink-600)`, which measures ~7:1 on both `--cream` and `--surface-card`. Verified: 105/105 tests, lint, format all still pass. |
| S2  | Accessibility (Constitution V, NON-NEGOTIABLE) | `RepositoryGrid.module.css:.qualityOff`, `RepositoryDetail.module.css:.qualityBadgeInactive`                                                                                           | The approved design spec (README) literally names `ink-400` text for "off" quality-indicator chips (README/License/CI-CD/Tests). Hand-computed: `ink-400` (#9b988f) on `ink-50`/white = **2.88:1** — fails AA badly (needs 4.5:1). This is a fidelity-vs-accessibility conflict baked into the design system itself, not an implementation slip. | Every repository card's inactive quality chips (a very common state — most repos are missing at least one of README/License/CI-CD/Tests) render with sub-AA text. | **FIXED in this pass**: changed both to `var(--ink-600)` for the text (keeping `ink-300` for the decorative dot, which is not text). |

### Critical Risks (High Probability of Costly Issues)

None remaining after the S1/S2 fixes above.

### High-Priority Concerns

| ID  | Category              | Location                                                                 | Issue                                                                                                                                                                                                 | Impact                                                                                     | Suggestion                                                                                          |
| --- | --------------------- | ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| H1  | QA coverage gap       | `QualityMatrix.module.css:.squareOff` border                              | The "off" square's `1px solid var(--ink-300)` border on white measures ~1.84:1 — below the WCAG 1.4.11 non-text UI-component contrast target (3:1). This is a supporting visual only (the same information is available via row labels and `QualitySection` badges elsewhere), so it was **not** changed in this pass to avoid an unreviewed visual deviation from the approved spec's literal token choice. | Low: information isn't conveyed by color/border alone (rows are labeled), but an automated a11y scanner will still flag it. | Confirm with design whether to darken the off-state border to `ink-500`/`ink-600`, or accept as a documented exception. |
| H2  | QA coverage gap       | Whole app                                                                  | No automated contrast scanner (axe-core, Lighthouse a11y) was run — the two fixes above came from manually computing luminance for the highest-traffic token pairs, not an exhaustive scan. Other pairings (status dot colors, badge tones, focus rings under motion) are unverified. | Unknown additional AA failures could exist in less-common states (e.g. `critical`/`caution` badge text on their soft backgrounds). | Run Lighthouse or axe DevTools against the built app (or add `npm run lighthouse`, already present in `package.json`) before merge. |
| H3  | QA coverage gap       | tasks.md:T045                                                              | Desktop/mobile screenshot capture and visual comparison against `design/GitHubSpark.dc.html` was not executed — see `gates/analyze.md` finding C1. | Visual fidelity (pixel-level spacing/typography match) is unverified beyond structural/behavioral tests. | Run T045 manually before sign-off. |
| H4  | Judgment-call scope   | Implementation only (not in tasks.md)                                      | Several fully-orphaned legacy components were deleted during T043's audit (not explicitly named in any task): `RepositoryTable/`, `Mobile/RepositoryCard/`, `VisualizationControls.jsx`, `ChartTypeSelector.jsx`, `LineGraph.jsx`, plus `HealthChart.jsx`/`ScatterPlot.jsx` from Phase 4 (T021/T019). All were verified to have zero importers before deletion, and a full `vite build` succeeded after each removal. | Low risk of breakage (verified unreachable), but a reviewer scanning the diff will see deletions not called out in tasks.md. | Already documented in `gates/analyze.md` I1/I2; call out explicitly in the PR description. |

### Framework-Specific Red Flags

- [x] No new asynchronous backend, database, or API surface is introduced; existing fetch timeout, retry, cache, and per-user cache-key behavior remain the unmodified pattern.
- [x] No new authentication, CORS, or API-versioning surface.
- [x] Service worker precache manifest regenerates automatically from content-hashed filenames (Workbox pattern, unchanged) — new font/CSS/JS asset hashes will be picked up without extra cache-versioning work.
- [x] `OfflineIndicator` and the branded `Toast` action-button path were previously built but **never rendered anywhere in the app** (dead code) before this pass wired them into `App.jsx`'s header and `useDashboardShell`. This is newly-exercised code, not previously-tested legacy behavior — see H2/QA note below.
- [x] Browser smoke coverage (`test:smoke`) was updated for the retired theme toggle and passes against a fresh production build.

### Architecture Red Flags

- [ ] Over-engineered for stated requirements
- [ ] Under-engineered for implied scale
- [ ] Single point of failure without redundancy
- [ ] Missing standard patterns for problem domain
- [ ] Inadequate async/concurrency handling

None checked — this redesign is a contained visual/presentational change over an already-working data/cache/service-worker architecture.

### Missing Critical Tasks

- **Observability:** None beyond existing console logging in `dataService`/`useRepositoryData` (unchanged).
- **Operations:** None; GitHub Pages deployment and service-worker architecture are intentionally unchanged. Production build was verified against the whitelisted `.validation/site` output directory (not `docs/`) to avoid disturbing the committed production artifact mid-review.
- **Testing:** Automated contrast/accessibility scanning (axe/Lighthouse) — see H2. Visual screenshot comparison — see H3.
- **Documentation:** None; `quickstart.md` was updated with the T044 validation run results.
- **Security:** None; no new input, credential, private-data, or server endpoint surface.

### Questionable Assumptions

1. **"The approved design tokens are accessibility-compliant as specified."** → False for two token pairings (S1, S2 above); the design system's own literal color choices for muted/inactive text fail WCAG AA on the surfaces they're actually used on. Verified by hand-computed relative luminance, not assumed — and fixed.
2. **"OfflineIndicator and Toast action buttons work correctly because they were already built."** → They were built but never wired into any render path before this pass (confirmed via `grep` — zero importers). Their logic is unit-tested now (`OfflineIndicator.test.jsx`, `Toast.test.jsx`) but has only been exercised end-to-end once, via a single automated `test:smoke` run in headless Chrome — not manually verified across real network offline/online transitions.

### Dependencies Risk Assessment

| Dependency      | Concern                                                                                                                        | Alternative to Consider                                                             |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `lucide-react`  | New production dependency; replaces scattered inline SVGs and all emoji iconography across ~15 components.                     | Retain; justified by the documented design-system requirement (FR-005/FR-006).       |
| `@testing-library/react`, `@testing-library/jest-dom` | New dev dependencies, added because no rendering-level component tests existed before this redesign (only pure-function tests). | Retain; required to test the drawer's keyboard behavior, toast dismissal, and export-menu interactions per FR-032. |

### Estimated Technical Debt at Launch

- **Code Debt:** Low. `RepositoryDetail.jsx`'s secondary sections (repo info, languages, commit history/metrics, activity metrics, ranking) are retained below the primary 8 spec-ordered sections rather than fully consolidated — see `gates/analyze.md` "detail-content-order: Partial."
- **Operational Debt:** None beyond pre-existing static-host/service-worker behavior.
- **Documentation Debt:** None identified beyond T045's outstanding manual visual comparison.
- **Testing Debt:** Medium — no automated contrast/accessibility scan (H2), no visual regression tooling (H3). Recommend adding both before the next redesign iteration, not necessarily before this PR merges.

### Metrics

- Showstopper Count: 0 (2 found, both fixed in this pass — see S1/S2)
- Critical Risk Count: 0
- High-Priority Concern Count: 4 (H1-H4, all QA/documentation gaps, none blocking)
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

1. ~~Fix the two WCAG AA contrast failures (S1, S2).~~ Done in this pass.
2. Run T045 (visual screenshot comparison) before final sign-off.

## Recommended Risk Mitigations

- Run an automated accessibility scanner (axe DevTools or `npm run lighthouse`) against the built app to catch any remaining contrast issues beyond S1/S2 (H2).
- Decide whether `QualityMatrix`'s "off" square border needs darkening for WCAG 1.4.11 non-text contrast, or should be documented as an accepted exception (H1).
- Call out the orphaned-component deletions (H4) explicitly in the PR description so reviewers aren't surprised by unscoped deletions.

## Resolution Contract

```yaml
findings:
  - finding_id: critic-2026-09-28-001
    severity: critical
    description: "--text-muted (ink-500 on cream) measured 4.38:1, below WCAG AA's 4.5:1 minimum for normal text (Constitution V, NON-NEGOTIABLE), and was used pervasively across sublabels, meta text, and counts."
    recommended_action: "Re-point the --text-muted semantic alias from ink-500 to ink-600 (measures ~7:1 on cream and white)."
    execution_mode: auto
    status: resolved
    outcome: "styles/brand/colors.css --text-muted now points to var(--ink-600); 105/105 tests, lint, and format all re-verified passing."
  - finding_id: critic-2026-09-28-002
    severity: critical
    description: "The approved design spec's literal ink-400 text color for 'off' quality-indicator chips measured 2.88:1 on its ink-50/white background, failing WCAG AA badly, and affects nearly every repository card (most repos are missing at least one quality signal)."
    recommended_action: "Change the inactive quality-chip text color from ink-400 to ink-600 in both RepositoryGrid.module.css and RepositoryDetail.module.css, keeping ink-300 for the non-text decorative dot."
    execution_mode: auto
    status: resolved
    outcome: "Both .qualityOff and .qualityBadgeInactive now use ink-600 for text; dots unchanged."
  - finding_id: critic-2026-09-28-003
    severity: medium
    description: "No automated contrast/accessibility scanner (axe/Lighthouse) was run; the two fixes above came from manually verifying the highest-traffic token pairs only."
    recommended_action: "Run `npm run lighthouse` or an axe DevTools pass against the built app before merge to catch any remaining AA issues in less-common states."
    execution_mode: manual
    status: open
    outcome: ""
  - finding_id: critic-2026-09-28-004
    severity: low
    description: "QualityMatrix's 'off' square border (ink-300 on white) measures ~1.84:1, below the WCAG 1.4.11 non-text UI-component target of 3:1. Not fixed in this pass since the information isn't conveyed by color alone (rows are labeled) and changing it would deviate from the approved design token without design sign-off."
    recommended_action: "Confirm with design whether to darken the border or accept as a documented exception."
    execution_mode: selective
    status: open
    outcome: ""
```
