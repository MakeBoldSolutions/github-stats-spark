---
pr: 7
devspark_version: 9.6.0
reviewed_commit: 62933a48d8811aaf43c0719e4ee40372b5b72a46
revision: 4
findings: &id001
  critical: 0
  high: 0
  medium: 0
  low: 2
  con: 0
historical_findings: *id001
current_findings:
  critical: 0
  high: 0
  medium: 0
  low: 2
current_state_counts:
  open: 0
  remediated: 0
  awaiting-verification: 2
  reopened: 0
  resolved: 0
unresolved_blockers: 0
recommendation: approve
gate_status: pass
max_severity: low
risk_rating: high
risk_score: 8
risk_escalated: false
review_state:
  format_version: 1
  findings:
  - finding_id: L-01
    aliases: []
    severity: low
    category: correctness
    blocking: false
    description: PATCH /api/repositories commits an `excluded` change before validating
      the assignment names, so a request that carries both and is rejected for an
      unknown or retired name still changes the repository. The same ordering was
      fixed for sources in this PR; this PR makes the assignment step reject far more
      input than before (unknown names used to be created).
    expected_outcome: A rejected repository PATCH leaves the repository unchanged,
      matching edit_source.
    evidence:
    - src/spark/api/app.py:340-348 — `set_repository_excluded(...)` runs before `associate_repository(...)`,
      which now raises UnknownNameError for unknown/retired names
    - 'Consumer trace: the admin UI sends `excluded` and `assign` in separate requests
      (RepositoriesPanel.jsx), so no current caller combines them; unconfirmed risk,
      Low'
    recommended_action: 'Resolve the client/project/application before writing: validate
      the assignment first (for example call associate_repository before set_repository_excluded,
      or resolve the names up front as edit_source does), and add a test that a combined
      PATCH with an unknown client leaves `excluded` unchanged.'
    execution_mode: manual
    status: awaiting-verification
    outcome: ''
    provenance:
      kind: native
      location: src/spark/api/app.py:340
    remediation:
      correction_commit: d7eb4019d785b085c9ac0225459faf63b0b19292
      author_context: Claude Code session that authored the PR (same session as the
        review)
      explanation: 'edit_repository now calls associate_repository, which resolves
        and rejects unknown or retired names, before set_repository_excluded, so a
        rejected combined PATCH writes nothing. Regression test: a PATCH with excluded=true
        and an unknown client returns 422 and leaves excluded false.'
      author_validation: './run-validation.ps1 exit 0 at d7eb4019d785b085c9ac0225459faf63b0b19292:
        black, flake8, mypy (76 files), pytest 572 passed, vitest 169 passed, build,
        audits.'
      proof_obligation: A distinct reviewer confirms that a combined excluded+assign
        PATCH that fails validation leaves the repository unchanged, and that the
        valid combined path still applies both changes.
    verification: null
    disposition: null
    reopen_reason: null
  - finding_id: L-02
    aliases: []
    severity: low
    category: accessibility
    blocking: false
    description: Each domain's <h3> contains the Rename button, and while renaming
      it contains a <form> with an input. A form is not permitted inside a heading
      (headings allow phrasing content only), and the heading's accessible name becomes
      'Tier Rename Tier', which also names the <article> through aria-labelledby.
    expected_outcome: Domain headings contain only the domain label; the rename control
      sits beside the heading.
    evidence:
    - frontend/src/components/Admin/DomainsPanel.jsx:215-226 — `<h3 id={`domain-${domain.id}-title`}><Renamable
      .../></h3>`
    - frontend/src/components/Admin/DomainsPanel.jsx:92 — Rename button `aria-label={`Rename
      ${label}`}` rendered inside the heading
    recommended_action: Render the label alone in the <h3> and place Renamable's button/form
      after it (for example a header row div containing the h3 and the control), keeping
      aria-labelledby pointed at the h3.
    execution_mode: manual
    status: awaiting-verification
    outcome: ''
    provenance:
      kind: native
      location: frontend/src/components/Admin/DomainsPanel.jsx:215
    remediation:
      correction_commit: d7eb4019d785b085c9ac0225459faf63b0b19292
      author_context: Claude Code session that authored the PR (same session as the
        review)
      explanation: 'Renamable takes a headingId; the h3 now holds only the domain
        label and the Rename button or rename form renders beside it in a title row.
        The article stays labelled by the h3. Regression test: the heading and article
        are named exactly ''Tier'' and the rename input is not inside the heading.'
      author_validation: './run-validation.ps1 exit 0 at d7eb4019d785b085c9ac0225459faf63b0b19292:
        black, flake8, mypy (76 files), pytest 572 passed, vitest 169 passed, build,
        audits.'
      proof_obligation: A distinct reviewer confirms that each domain heading's accessible
        name is the label alone, both before and while renaming, and that no form
        sits inside a heading.
    verification: null
    disposition: null
    reopen_reason: null
  conditions: []
  last_change:
    operation: remediate-and-submit
    affected:
    - L-02
    event_fingerprint: 8633007bc3088c024a30850c3ef2dad9361dbd7867617ebfa37acc74c271349c
    actor_role: ''
    actor_context: ''
    explanation: ''
---
# Pull Request Review: feat(registry): managed lists and classification domains

- **PR**: #7 — 001-work-ps-023-classification-domains → main — @markhazleton — OPEN
- **Reviewed Commit**: 62933a48d8811aaf43c0719e4ee40372b5b72a46
- **Review Date**: 2026-11-21 21:39:28 UTC (last updated 2026-11-21 21:39:28 UTC)
- **Constitution Version**: 1.2.0

## Revision Log

| Rev | Commit | Date | Critical | High | Medium | Low | CON | Test Command | Result |
|-----|--------|------|----------|------|--------|-----|-----|--------------|--------|
| 1 | 62933a4 | 2026-11-21 | 0 | 0 | 0 | 2 | 0 | reused: CI `validate` run 44951807850 on 62933a4; local `./run-validation.ps1` | pass |

## Test Evidence

- reused: GitHub Actions `validate` (run 44951807850, job 136991190205) on commit 62933a4 — pass in 1m34s. It runs `run-validation.ps1`: pip check, black, flake8, mypy, pytest, config validate, pip-audit, npm ci, lint, format check, vitest with coverage, build, npm audit.
- reused: local `./run-validation.ps1` on the same tree before commit — exit 0; pytest 572 passed, vitest 168 passed, pip-audit and npm audit clean. No rerun was triggered: the reviewed commit is the one CI validated.

## Stats

| Metric | Value |
|--------|-------|
| Files changed | 26 |
| Commits | 1 |
| Lines | +3842 −325 |
| Tiers (P0/P1/P2/P3) | 2 / 17 / 6 / 1 |
| Risk | high (8) — p0_files, large_diff; Knowledge absent (live) |

## Executive Summary

**Overall Assessment**: A sound, well-tested change. Managed lists and domains are enforced in the store, so the API, the CLI and the UI all apply the same rules, and the migration keeps existing data. Two Low, nonblocking findings. Knowledge status is `absent` (`.knowledge/` holds no claims), so file tiers came from path patterns alone. I reviewed `db.py` (schema), `store.py` (data access) and `catalog_routes.py`/`app.py` (routes) at P0 depth although the script placed them in P1. **Independence:** this review was produced by the same agent session that wrote the change, so it is not an independent review; a human or separate reviewer should still read it before merging.

- Constitution: PASS (6 applicable principles evaluated) · Durable delta: PASS (0 open PRD findings)
- Security: 0 issues · Quality: 2 recommendations · Testing: PASS · Docs: PASS
- Constitution Improvements: 0 CON findings

<!-- PR-REVIEW-DERIVED:ACTION:BEGIN -->
## Action Items

### Immediate Actions (Blocking)

- None found.

### Recommended Improvements

- [ ] **L-01** [awaiting-verification] — PATCH /api/repositories commits an `excluded` change before validating the assignment names, so a request that carries both and is rejected for an unknown or retired name still changes the repository. The same ordering was fixed for sources in this PR; this PR makes the assignment step reject far more input than before (unknown names used to be created).
- [ ] **L-02** [awaiting-verification] — Each domain's <h3> contains the Rename button, and while renaming it contains a <form> with an input. A form is not permitted inside a heading (headings allow phrasing content only), and the heading's accessible name becomes 'Tier Rename Tier', which also names the <article> through aria-labelledby.

### Constitution Improvements

- None.
<!-- PR-REVIEW-DERIVED:ACTION:END -->
<!-- PR-REVIEW-DERIVED:DETAIL:BEGIN -->
## Findings Detail

| ID | Status | Severity | Blocking | Issue | Expected outcome | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| L-01 | Pending verification | low | No | PATCH /api/repositories commits an `excluded` change before validating the assignment names, so a request that carries both and is rejected for an unknown or retired name still changes the repository. The same ordering was fixed for sources in this PR; this PR makes the assignment step reject far more input than before (unknown names used to be created). | A rejected repository PATCH leaves the repository unchanged, matching edit_source. | src/spark/api/app.py:340-348 — `set_repository_excluded(...)` runs before `associate_repository(...)`, which now raises UnknownNameError for unknown/retired names; Consumer trace: the admin UI sends `excluded` and `assign` in separate requests (RepositoriesPanel.jsx), so no current caller combines them; unconfirmed risk, Low |
| L-02 | Pending verification | low | No | Each domain's <h3> contains the Rename button, and while renaming it contains a <form> with an input. A form is not permitted inside a heading (headings allow phrasing content only), and the heading's accessible name becomes 'Tier Rename Tier', which also names the <article> through aria-labelledby. | Domain headings contain only the domain label; the rename control sits beside the heading. | frontend/src/components/Admin/DomainsPanel.jsx:215-226 — `<h3 id={`domain-${domain.id}-title`}><Renamable .../></h3>`; frontend/src/components/Admin/DomainsPanel.jsx:92 — Rename button `aria-label={`Rename ${label}`}` rendered inside the heading |
<!-- PR-REVIEW-DERIVED:DETAIL:END -->

## Constitution Alignment Details

**Passing**: 6 of 6 applicable principles — I Single Responsibility (new modules all under 500 LOC; `store.py` at 521 now carries the required size justification), II Data Privacy (no private data; classifications are administrator-entered and exported only to the self-hosted data root), III Fail Fast, Fail Loud (unknown/retired names and refused deletes return messages that say what to do), V Accessibility First (labelled controls, fieldsets for multi-choice, existing colour tokens), VII Self-Hosted Mode (every new route requires a session, writes require CSRF; covered by tests), Governance (no new dependencies). IV and VI not applicable.

## Testing

**Status**: ADEQUATE — new pytest and vitest suites cover the new behavior, including a migration from the previous schema; CI passed on the reviewed commit.

| File | Changes | Type |
|------|---------|------|
| frontend/tests/Classification.test.jsx | +426 -0 | Added |
| frontend/tests/SourcesView.test.jsx | +46 -1 | Modified |
| tests/unit/test_api.py | +25 -9 | Modified |
| tests/unit/test_classification.py | +351 -0 | Added |
| tests/unit/test_classification_api.py | +168 -0 | Added |
| tests/unit/test_registry.py | +4 -1 | Modified |

No tests were removed. Two existing tests changed expectations to match the intended behavior (unknown names are now rejected): `test_disable_edit_and_remove_a_source_keeps_repositories` and `test_exclude_and_assign_repositories_and_build_the_portfolio` — justified; they now also assert the rejection.

## Changed Files

| File | Tier | Changes | Type |
|------|------|---------|------|
| frontend/src/components/Admin/RepositoriesPanel.jsx | P0 | +212 -118 | Modified |
| frontend/src/components/Admin/RepositoryEditor.jsx | P0 | +184 -0 | Added |
| frontend/src/components/Admin/Admin.module.css | P1 | +106 -0 | Modified |
| frontend/src/components/Admin/BulkClassify.jsx | P1 | +109 -0 | Added |
| frontend/src/components/Admin/DomainsPanel.jsx | P1 | +373 -0 | Added |
| frontend/src/components/Admin/ListEntry.jsx | P1 | +146 -0 | Added |
| frontend/src/components/Admin/ListsPanel.jsx | P1 | +253 -0 | Added |
| frontend/src/components/Admin/SourcesPanel.jsx | P1 | +22 -3 | Modified |
| frontend/src/components/Admin/SourcesView.jsx | P1 | +19 -2 | Modified |
| frontend/src/components/Admin/portfolioOptions.js | P1 | +84 -0 | Added |
| frontend/src/services/adminApi.js | P1 | +29 -1 | Modified |
| src/spark/api/app.py | P1 | +17 -54 | Modified |
| src/spark/api/catalog_routes.py | P1 | +245 -0 | Added |
| src/spark/registry/__main__.py | P1 | +47 -2 | Modified |
| src/spark/registry/catalog.py | P1 | +356 -0 | Added |
| src/spark/registry/db.py | P1 | +70 -0 | Modified |
| src/spark/registry/domains.py | P1 | +446 -0 | Added |
| src/spark/registry/export.py | P1 | +16 -0 | Modified |
| src/spark/registry/store.py | P1 | +72 -132 | Modified |
| frontend/tests/Classification.test.jsx | P2 | +426 -0 | Added |
| frontend/tests/SourcesView.test.jsx | P2 | +46 -1 | Modified |
| tests/unit/test_api.py | P2 | +25 -9 | Modified |
| tests/unit/test_classification.py | P2 | +351 -0 | Added |
| tests/unit/test_classification_api.py | P2 | +168 -0 | Added |
| tests/unit/test_registry.py | P2 | +4 -1 | Modified |
| .documentation/guides/DOCKER_DEPLOYMENT.md | P3 | +16 -2 | Modified |

## Behavioral Changes

| Change | Before | After | Intentional? | Risk |
|--------|--------|-------|-------------|------|
| Assigning an unknown client/project/application (`PATCH /api/repositories`, `POST`/`PATCH /api/sources`, CLI `add`/`assign`) | Name created on first use | 422 `unknown_name` (CLI exit 2; `--create` restores the old behavior on purpose) | Yes (PR description) | Scripts that relied on implicit creation must create names first or pass `--create` |
| `POST /api/clients` and the project/application create routes with an existing name | Returned the existing entry (idempotent) | 422 `invalid` ("already an existing client here") | Yes (names are unique per scope) | No in-repo caller relied on idempotency |
| `Registry.create_client/create_project/create_application/portfolio_tree` | Methods on `Registry` | Functions in `spark.registry.catalog` | Yes (refactor) | Only `app.py` called them; updated |
| `GET /api/portfolio`, `GET /api/repositories`, `portfolio.json` | — | Additive fields: `retired`, usage counts, `classifications`, `domains` | Yes | Additive; `schema_version` stays 1 |
| `PATCH /api/sources/{id}` with an invalid client | `enabled` change saved, then failed | Nothing saved; 422 | Yes (fix) | None |

## Deployment & Handoff Notes

### Deployment Notes

- Migration 4 runs on first start against the server registry; the existing pre-migration copy (`registry.db.pre-v3.bak`) is written automatically. After deploy, the administrator should check the Lists tab for existing clients and suggested duplicates (already listed in the PR description).

### Handoff Notes

- DevSpark tooling — owned by the DevSpark framework — `.devspark/scripts/bash/get-pr-context.sh` emits invalid JSON when the PR body has CRLF line endings (it splits the string on `\r`); the PowerShell script works. Not a defect of this PR.

### Observations

- Bulk selection is kept after an apply and across filter changes, so a later bulk action can include rows the current filter hides; the "N selected" count states this. It matches "changes exactly the selected repositories"; clearing the selection after a successful apply would be a reasonable follow-up, not a defect.
- Saving the repository editor issues one assignment request and one classify request per changed domain; a failure partway leaves earlier requests applied. The panel reports the error and reloads, so the screen shows what was saved. Acceptable for a single administrator.
- After merging a client whose project matches a same-named project under the target, the retired duplicate application rows keep a `client_id` that no longer matches their retired project's client. They are retired and unused, so nothing reads the mismatch.
- Classifications are exported to `portfolio.json` only, not to per-source `repositories.json`; the PR description states this exclusion.

<!-- PR-REVIEW-DERIVED:DECISION:BEGIN -->
## Approval Decision

**Recommendation**: APPROVE — derived from current blockers and applicable review conditions.

*This local recommendation does not cast a hosted approval vote or authorize merge.*
<!-- PR-REVIEW-DERIVED:DECISION:END -->

---

*Re-review after fixes: `/devspark-pr-review #7 re-review`. Address findings with `/devspark-address-pr-review 7`; commit the review file on its own.*

---

<!-- PR-REVIEW-DERIVED:SUMMARY:BEGIN -->
## Current Review State

- Historical unique findings: 2
- Current unresolved findings by severity: {'critical': 0, 'high': 0, 'medium': 0, 'low': 2}
- Current lifecycle state counts: {'open': 0, 'remediated': 0, 'awaiting-verification': 2, 'reopened': 0, 'resolved': 0}
- Unresolved blockers: 0
- Pending independent verification: 2
- Review conditions: pass
- Local recommendation: approve
<!-- PR-REVIEW-DERIVED:SUMMARY:END -->
