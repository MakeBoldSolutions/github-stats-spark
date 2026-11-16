---
source: "DevSpark — © 2026 Make Bold Solutions. Source: https://dev.makeboldspark.com"
description: Address open PR review findings with enforced commit isolation between code fixes and review-file updates
handoffs:
  - label: Re-Review Updated PR
    agent: devspark-pr-review
    prompt: Run /devspark-pr-review UPDATE for this PR after fixes are committed
scripts:
  sh: .devspark/scripts/bash/address-pr-review.sh --pr-id $ARGUMENTS --json
  ps: .devspark/scripts/powershell/address-pr-review.ps1 -PrId $ARGUMENTS -Json
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Overview

Load and obey the shared preamble contract core at `/.devspark/templates/command-preamble-contract.md` (installed repos) or `templates/command-preamble-contract.md` (source repos) before Phase 0 — in particular §9 (Genuine Fix Discipline) during the Phase 2 fix loop. Preamble modules: `finding-fix`, `convergence`, `configuration`.

This command is the **author-side companion** to `/devspark-pr-review`. It helps you address open findings in `/.devspark.work/pr-review/pr-{PR_ID}.md` while enforcing commit isolation:

1. Commit code fixes first.
2. Commit review-file updates second.

**IMPORTANT**: The staging gates are mechanical and mandatory. Do not bypass them.

## Prerequisites

- Existing PR review file at `/.devspark.work/pr-review/pr-{PR_ID}.md`
- Git repository with the PR source branch checked out
- PowerShell 7+ (`pwsh`) on Windows, or Bash on macOS/Linux, for the gate helper script

## Definition of Done

Done when: every selected finding is fixed and committed (Phase 4), the review file is updated and committed separately (Phase 6), the two commits are verified disjoint, and the handoff message is printed (Phase 7). If validation (Phase 3) can't be made to pass, stop and report which finding is blocking — don't keep retrying silently.

## Outline

### Phase 0 — Load context

> **Script Resolution**: Before running `{SCRIPT}`, apply the 2-tier override check — if `.devspark.work/scripts/powershell/address-pr-review.ps1` (PowerShell) or `.devspark.work/scripts/bash/address-pr-review.sh` (Bash) exists on disk, run that file instead, preserving all arguments. Team overrides in `.devspark.work/scripts/` always take priority over `.devspark/scripts/`.

1. Run `{SCRIPT}` with the PR id and JSON output enabled (`-PrId {PR_ID} -Json` on PowerShell, `--pr-id {PR_ID} --json` on Bash).
2. Fail fast if `/.devspark.work/pr-review/pr-{PR_ID}.md` is missing.
3. Consume the helper's authoritative projections. Preserve canonical IDs and aliases; distinguish
   actionable findings from `pending_verification`, and use its `blocking`, `route`,
   `auto_eligible`, and `reason` values rather than inferring from an ID prefix.
4. Confirm current branch equals the PR source branch. Refuse if mismatched.
5. Capture `git status --short`.
6. **Refuse to proceed** if any staged path matches `.devspark.work/pr-review/pr-*.md`.

If no actionable findings remain but `pending_verification` is non-empty, report that reviewer
verification is pending and identify the missing permitted reviewer/proof; do not say the review is
complete. Print `Nothing to address.` only when the report is truly empty or has no unresolved
actionable or pending work.

### Phase 1 — Plan

1. Render open findings as a checklist with severity badges.
2. Honor an explicit finding ID or `all` in the user's input. If exactly one finding is already
   `auto_eligible`, select it without a redundant selection question; if several are eligible,
   request the smallest necessary selection unless `--auto` applies. Under `--auto`, select only
   `auto_eligible: true`. Report other findings with their supplied `reason` and leave them
   untouched; optional/nonblocking findings, risk acceptance, ambiguous recovery, and constitution
   routing retain their existing authorization requirements.
3. Build an internal todo list with one item per selected finding. Freeze those finding IDs and
   their required outcomes for this invocation: `all` means the actionable findings selected now,
   not every concern discovered later. Necessary supporting edits and regressions caused by the
   selected corrections stay within the existing authorization; the file list is not a hard limit.
   Do not add adjacent refactors or newly discovered unrelated findings to the batch. Report them
   briefly only when useful, and obtain explicit authorization before adding separate work.

### Phase 2 — Fix loop (per finding)

For each selected finding:

1. Read the cited file/lines and confirm the issue. Investigate only questions needed to settle
   that finding's original expectation. Do not reopen a settled disposition without the new
   evidence required by convergence §10.
2. If the finding cites a lint rule, complexity metric, or code smell, state in one sentence the behavioral intent behind it (command-preamble-contract.md §9) before writing the fix — do not react to the bare metric alone.
3. A finding's suggested fix is evidence, not an architecture mandate. Choose the lightest sufficient remediation, in this order: clarify, remove, reuse something that exists, change an operational detail, make a small local change, and only then add machinery. If the fix needs something beyond the approved Plan's shape (a new state, endpoint, persisted record, cache, dependency, runtime setting, pattern or rollback design), stop and ask for explicit authority; `--auto` never grants it. Show the diff for any alternative to the suggested fix, and confirm the fix addresses that intent (e.g., genuinely lowers branching/responsibility, genuinely names and surfaces an error) rather than merely satisfying the check mechanically.
4. **Rule 1 check**: the fix stays subject to the same one-way reference gate `/devspark-pr-review` §6 enforces — do not introduce a spec ID, task ID, plan reference, or PR-thread ID into code or `.knowledge/` to "explain" what review comment this addresses. A commit message or the review file itself is the right place for that context, never a durable comment.
5. Stage **only** code paths touched by that fix.
6. Never run `git add .`.
7. Never stage `/.devspark.work/pr-review/pr-{PR_ID}.md` during this phase.

### Phase 3 — Validate

1. After the selected fixes are ready, validate the batch once. Use the review's recorded commands
   as evidence of prior coverage, not a permanent minimum scope. Select the narrowest checks that
   cover the corrections and directly affected contracts, subject to explicit repository policy.
   Apply verification-contract.md §4.1 before running: reuse valid evidence, and let a qualifying
   broader run satisfy narrower checks without executing both. Record the reason for changed scope.
2. Include project-specific validators explicitly recorded in the review file; either cite valid
   evidence or run them. Replacing test scope does not silently drop a required validator.
3. If validation fails, return to Phase 2 only for a failure attributable to the selected fixes.
   Otherwise report the baseline debt, environment failure, or unresolved attribution and the
   unmet gate; do not expand remediation or retry silently.
4. Do not continue until required validations pass. Author validation does not replace the
   independent verification of the original concern in Phase 5.

### Phase 4 — Commit code fixes (isolation gate #1)

1. Run gate script with code-only mode before commit (`-Gate code-only` on PowerShell, `--gate code-only` on Bash).
2. If the gate fails, **abort** and print offending staged paths.
3. Review staged diff and commit with:

```text
fix(pr-{PR_ID}): address {M-02,M-04,M-05}
```

1. Capture the resulting short hash as `{FIX_SHA}`.

### Phase 5 — Record remediation and submit for independent verification

After the code-only commit and required author validation:

1. Inspect the latest record and capture its digest.
2. Create one temporary event input outside tracked source paths with
   `operation: remediate-and-submit`, the canonical finding ID, correction commit SHA, author
   execution context, explanation tied to the original expectation, actual author validation (or
   explicit absence and reason), and the remaining independent proof obligation.
3. Apply it with `scripts/pr-review-state.py apply ... --expected-digest ... --repo-root .`.
   Never set `status: resolved`, edit derived checkboxes/tables/counters directly, or claim that
   author proof is independent confirmation.
4. The engine writes `remediated`/`awaiting-verification`, rendered views, counts, and local
   recommendation together. Verify that the blocker remains until a distinct reviewer confirms it.
5. Run `scripts/pr-review-validate.py` against the resulting revision. Remove the temporary event
   input after use, then stage only the review file.

If the finding is already pending verification, do not reapply remediation. Hand off to the existing
`/devspark-pr-review UPDATE` for bounded independent evaluation. A missing distinct evaluator or
required proof leaves it pending; it does not start another address/review reconciliation cycle.

### Phase 6 — Commit review file (isolation gate #2)

1. Run gate script with review-only mode before commit (`-Gate review-only` on PowerShell, `--gate review-only` on Bash).
2. If the gate fails, **abort** and print offending staged paths.
3. Commit with:

```text
review(pr-{PR_ID}): rev {N} — {X} fixed, {Y} remaining
```

1. Verify commit disjointness:

```bash
git log HEAD~2..HEAD --name-only
```

Parse the two commits and assert they share zero file paths.

### Phase 7 — Handoff

1. Print both new commit hashes (`fix` and `review`).
2. Suggest focused re-review:

```text
Run `/devspark-pr-review UPDATE {PR_URL}` for bounded independent evaluation of the pending correction.
```

## Guidelines

### Commit Discipline (MUST)

- A commit touching `/.devspark.work/pr-review/pr-{PR_ID}.md` MUST NOT include any other path.
- Code fixes and review-file updates MUST be separate commits.
- Do not amend/squash these two commits together.

### Gate Execution (MUST)

- Use the helper script as the source of truth for staging gates.
- If a gate exits non-zero, stop and resolve staging before retrying.

### Edit Scope (MUST)

Do not hand-edit finding statuses, derived tables, counts, gate summaries, or recommendation.
The state engine updates the structured record and its marked derived regions in one digest-guarded
operation. Preserve report narrative and source evidence outside those regions.

## Context

$ARGUMENTS

<!-- DIVERGENT: pr-review-state -->
## Shared Review Resolution Contract Output

Use `templates/pr-review-state-contract.md` and `scripts/pr-review-state.py` as the PR-only
authority. Preserve the shared base finding fields for all other review stages.
The shared `execution_mode` values remain `auto`, `selective`, and `manual`; this PR workflow adds
no new execution mode.

```yaml
review_state:
  format_version: 1
  findings:
    - finding_id: H-01
      aliases: []
      severity: high
      category: general
      blocking: true
      description: "[Original concern]"
      expected_outcome: "[Observable expected correction]"
      evidence: ["[Original evidence]"]
      recommended_action: "[Actionable step]"
      execution_mode: manual
      status: open
      outcome: ""
      provenance: {kind: native}
      remediation: null
      verification: null
      disposition: null
      reopen_reason: null
  conditions: []
  last_change: {}
```

Only independent reviewer confirmation can resolve a new correction. Keep author remediation pending,
preserve dispositions and prior outcomes, and never treat a local recommendation as hosted approval
or merge authorization.
