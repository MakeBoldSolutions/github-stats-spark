---
source: "DevSpark — © 2026 Make Bold Solutions. Source: https://dev.makeboldspark.com"
description: Optional lightweight WHAT/WHY/HOW record for a defect you have already diagnosed, with targeted constitution checks. /devspark-specify handles fixes too, without a record.
handoffs:
  - label: View Quickfix History
    agent: devspark-quickfix
    prompt: Show me previous quickfixes with /devspark-quickfix list
  - label: Review a Material Concern
    agent: devspark-critic
    prompt: Challenge only the specific material concern discovered on this quickfix, then return to the fix
    send: false
scripts:
  sh: .devspark/scripts/bash/quickfix-context.sh $ARGUMENTS --json
  ps: .devspark/scripts/powershell/quickfix-context.ps1 $ARGUMENTS -Json
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Workflow Position

Optional entry for a defect you have already diagnosed and want recorded as WHAT/WHY/HOW: `[diagnosed defect] → quickfix → implement → verify`. `/devspark-specify` handles fixes too, without a record, and never routes to this command or asks you to choose; use quickfix when the product-owner record is useful.

Also accepts **Code First** work: `[existing diff] → quickfix review and reconciliation → existing
implementation finalization`. A completed or partially completed change needs no prior spec,
plan, or tasks. Both entries use the same quickfix record and existing assurance mechanisms.

- **Owns**: classification, targeted constitution check, a dedicated quickfix branch (`NNN-fix-<slug>`), a temporary product-owner change record (`NNN-fix-<slug>` with WHAT/WHY/HOW), a minimal `## Context Resolution` (whatever `.knowledge/` content the fix touches — flat documents, entities, entity layers, or decisions — if any), and the Validation Checklist. Update the affected production code, tests, and current `.knowledge/` content in the same change; never reference the temporary quickfix record from a durable file.
- **Does NOT own**: multi-file architectural changes, new user-facing features, or API/schema changes (→ `/devspark-specify`); interactive ambiguity resolution (→ `/devspark-clarify`); design artifacts (→ `/devspark-plan`); story-organized task lists (→ `/devspark-tasks`); adversarial risk review (→ `/devspark-critic`, `/devspark-analyze`) — quickfix runs neither as a default gate; when a material concern justifies one, invoke it on this quickfix (it reviews the record in `QUICKFIX-ONLY` scope) and continue the fix.
- **If scope expands during implementation**: surface the scope decision to the developer (see Route Escalation on Discovered Scope) rather than stretching the quickfix silently. The quickfix keeps its route; it gains only the assurance the concern justifies.

## Constitution Authority

`/.knowledge/governance/constitution.md` is **required** — if missing, halt and direct the user to `/devspark-constitution`. The targeted constitution check (§5) loads only principles relevant to the detected classification, but they remain non-negotiable: a FAIL must be surfaced and acknowledged in writing, never silently ignored.

Load and obey the shared preamble contract core at `/.devspark/templates/command-preamble-contract.md` (installed repos) or `templates/command-preamble-contract.md` (source repos) before step 1 — in particular §9 (Genuine Fix Discipline) when the quickfix originates from a linter/test/code-smell finding. Preamble modules: `finding-fix`, `provenance`, `configuration`.

## Overview

This command enables rapid fixes without full-spec overhead. Its record lives under
`.devspark.work/quickfixes/` for as long as it takes to reach `/devspark-implement`, which updates
code, affected tests, and current knowledge, and passes required verification. The record then stays
live in `.devspark.work/quickfixes/`
— `/devspark-release` is the only command that later archives it to `.archive/{YYYY-MM-DD}/quickfixes/`
once it's Complete.

**Use Cases:**

- Bug fixes (runtime errors, UI glitches, data issues)
- Small features (< 4 hours estimated work)
- Production hotfixes requiring rapid deployment
- Configuration changes
- Documentation updates

**IMPORTANT**: This command creates minimal documentation and still performs constitution-aware gate checks.

Lightweight route advice is advisory, not permission to waive a mandatory requirement. Surface
blocking concerns; failed verification, constitution violations, missing required independent
assurance, and missing authorization cannot be reported as passing or Complete. A recorded risk
acknowledgement is not a test result or an approval from the required authority.

## Prerequisites

- Project constitution at `/.knowledge/governance/constitution.md` (REQUIRED)
- Git repository with working branch

## Actions

Parse `$ARGUMENTS` for action type:

| Action     | Trigger                                   | Description                |
| ---------- | ----------------------------------------- | -------------------------- |
| `create`   | Default (description provided)            | Create new quickfix record |
| `complete` | Legacy compatibility only | Route unfinished records through `/devspark-implement` |
| `list`     | `/devspark-quickfix list`                 | Show recent quickfixes     |

## Definition of Done

Done when (for `create`): the quickfix branch `BRANCH_NAME` is checked out when approved, the
temporary record exists at `QUICKFIX_DIR/NEXT_ID.md` with WHAT/WHY/HOW and constitution compliance,
and the final summary routes to `/devspark-implement`. `list` is read-only. `complete` must not retain
a completion claim here; route to implementation finalization. Release alone owns archiving.
For Code First, reconcile the existing diff, then use the existing Quickfix Route and Finalize Every
Route instructions in `/devspark-implement` with the explicit record path. Complete means the
actual delta and all required evidence pass, not merely that code or a record exists.

## Outline

Multi-app scope and the 2-tier override check for scripts are defined by the shared preamble contract already loaded above.

### 1. Initialize Quickfix Context

Run `{SCRIPT}` to gather context and parse JSON output for:

- `REPO_ROOT`: Repository root path
- `CONSTITUTION_PATH`: Path to constitution file
- `CONSTITUTION_EXISTS`: Whether constitution exists
- `QUICKFIX_DIR`: Directory for quickfix records
- `CURRENT_BRANCH`: Current git branch
- `NEXT_ID`: Next quickfix ID (unified `NNN-fix-<slug>` format; legacy records remain readable as `QF-YYYY-NNN`)
- `BRANCH_NAME`: Branch to create for this quickfix (matches `NEXT_ID`)
- `NUMBER`: The allocated 3-digit index (pass through to `new-branch.{ps1,sh} -Number`/`--number` for an exact match)
- `SLUG`: The normalized short-name (pass through to `new-branch.{ps1,sh} -ShortName`/`--short-name` for an exact match)
- `HAS_GIT`: Whether a git repository is available (gates branch creation and commit)
- `GIT_USER`: Git username for attribution
- `TIMESTAMP`: Current UTC timestamp
- `ACTION`: Determined action (create/complete/list)
- `CLASSIFICATION`: Auto-detected classification
- `RISK_LEVEL`: Assessed risk level
- `MAX_EFFORT`: Maximum recommended effort

**Error Handling:**

If constitution doesn't exist:

- **STOP** and inform user that constitution is required
- Provide guidance: "Run `/devspark-constitution` to create project principles first"
- Do not proceed with quickfix creation

### 2. Handle Action

#### Action: `list`

If ACTION is "list":

1. Read all files from QUICKFIX_DIR
2. Parse metadata from each file
3. Display summary table:

```markdown
## Recent Quickfixes

| ID          | Date       | Classification | Status    | Description                     |
| ----------- | ---------- | -------------- | --------- | ------------------------------- |
| QF-2026-003 | 2026-02-01 | bug-fix        | Completed | Fix null pointer in UserService |
| QF-2026-002 | 2026-01-28 | hotfix         | Completed | Payment timeout fix             |
| QF-2026-001 | 2026-01-25 | config-change  | Completed | Update rate limits              |
```

1. Stop execution (no record creation)

#### Action: `complete`

If ACTION is "complete" and QUICKFIX_ID is provided:

1. Read the quickfix record from `QUICKFIX_DIR/QUICKFIX_ID.md`.
2. If it does not exist, report that it was already finalized or never existed.
3. If it exists, do not mark it as completed here. Route to `/devspark-implement`, which owns
  verification and current-knowledge consistency; `/devspark-release` owns archiving the record
  under `.archive/` once it's Complete.
4. Stop execution.

#### Action: `create` (Default)

Continue to step 3. When code already exists, apply the Code First entry below before assessing
scope or creating the same quickfix record.

### Code First Entry: Inspect and Reconcile an Existing Diff

1. **Establish the actual change boundary.** Inspect `git status --short`,
   `git diff --no-ext-diff`, and `git diff --cached --no-ext-diff`; read relevant changed code,
   callers, and tests, including relevant untracked files. For committed work, establish the
   intended base and inspect `git diff --no-ext-diff <base>...HEAD`. Ask only when the base or
   ownership is ambiguous; do not silently treat all dirty files as this change or alter unrelated
   work. Do not create or switch a branch merely to inspect the diff.
2. **Establish intent from evidence.** Use the conversation, diff, surrounding code, existing
   tests, and current Knowledge. Distinguish observed behavior from inferred intent and unknown
   root cause. Ask the developer only when an important intent, required guarantee, or authorization
   cannot be established. Do not invent a requirement to justify the code.
3. **Review scope and correctness before completion.** Apply steps 3-5 and the existing Route
   Escalation guidance to the actual delta, not just description keywords. Check boundary cases,
   caller compatibility, regressions, and relevant existing tests. Material risk requires the
   applicable independent assurance, organizational requirements, and authorization even if code
   is already written. Use existing review/verification mechanisms; halt completion or escalate
   when required assurance is missing. If the developer splits separate work out, document remaining
   work and current decisions prospectively, never fabricate an earlier specification or approval.
4. **Close validation gaps.** Run the smallest relevant existing tests, add or update appropriate
   regression/edge-case coverage, and rerun after corrections. Use the existing verification
   contract and `/devspark-verify` when applicable. Record exact commands, observed results,
   failures, and limitations in the record's Implementation Notes; not-run and blocked checks
   remain unproven. A failing required check prevents a passing result and finalization.
5. **Reconcile lasting Knowledge only when needed.** Inspect applicable `.knowledge/` owners and
   determine whether the diff changes a durable claim, contract, or operational guidance. Update
   the owning document when necessary; create Knowledge only for lasting engineering value, never
   to satisfy a documentation checkbox. If no update is needed, explain why in Context Resolution.
6. **Preserve chronology in the existing record.** Create or update the quickfix record now,
   stating that implementation preceded this review, what was already done, and what remains.
   Describe HOW as the observed implementation plus any prospective corrections. Use actual
   timestamps, test results, and approvals; never backdate a planning decision or human approval.
   Name the inspected paths in the record, and check items only after evidence
   supports them. Reuse a matching existing record rather than generating another for the same work.
7. **Finalize through the existing route.** Apply steps 7-9 with branch confirmation and staging
   safety below, then load `/devspark-implement`'s Quickfix Route and Finalize Every Route using
   this record's explicit path, including when staying on the current branch. Validate already-done
   items instead of reimplementing them; finish authorized remaining work. Produce the step-10
   summary from actual evidence, distinguishing Quickfix's own review from any independent review
   performed or still required. Do not request fictional `spec.md`, `plan.md`, or `tasks.md`.

### 3. Validate Scope

Based on CLASSIFICATION from script:

| Classification  | Keywords Detected                       | Max Effort | Risk   |
| --------------- | --------------------------------------- | ---------- | ------ |
| `hotfix`        | urgent, critical, emergency, production | 2 hours    | HIGH   |
| `bug-fix`       | fix, bug, error, crash, broken, issue   | 4 hours    | MEDIUM |
| `config-change` | config, setting, environment, flag      | 1 hour     | LOW    |
| `docs-update`   | doc, readme, comment, documentation     | 2 hours    | LOW    |
| `minor-feature` | (default)                               | 4 hours    | LOW    |

**Scope Warning:**

If the description suggests work beyond the classification limits, warn:

```markdown
Scope Warning: This appears to be a larger change than a typical {CLASSIFICATION}.

- If it is one small change, continue with this quickfix
- If it is new or broader work, start it with `/devspark-specify {description}` instead
```

### 4. Load Constitution (Targeted)

Read `/.knowledge/governance/constitution.md` and extract only principles relevant to the change type:

| Classification  | Relevant Principles                 |
| --------------- | ----------------------------------- |
| `hotfix`        | Security, Observability, Deployment |
| `bug-fix`       | Testing, Code Quality, Security     |
| `config-change` | Security, Documentation             |
| `docs-update`   | Documentation                       |
| `minor-feature` | All MUST principles                 |

Build a targeted validation checklist from these principles only.

### 5. Constitution Compliance Check

For each relevant principle:

- **PASS**: Proposed solution (or inspected existing change) complies or principle not applicable
- **CONDITIONAL**: Needs specific action to comply (document the action)
- **FAIL**: Cannot proceed without violating principle

**Compliance Decision:**

- If any FAIL: Surface the blocking concern, explain why it matters, and ask whether to correct,
  switch workflows, or stop. **Never auto-bypassed**, even under `--auto`; continuing investigation
  does not authorize a violation, a passing result, or completion.
- If CONDITIONAL: Document required actions in the quickfix record. Under `--auto` (or a standing autonomy instruction), this is auto-documented and the run proceeds without asking — CONDITIONAL is not a blocker, it's a recorded follow-up.
- If all PASS: Proceed with quickfix creation.

Record explicit decisions about FAIL or CONDITIONAL findings under `## Gate Acknowledgements`.
An acknowledgement does not satisfy an unmet mandatory requirement.

### 6. Extract Quickfix Details (Product Owner TLDR — WHAT / WHY / HOW)

Use the **entire conversation thread** as input — not just the `$ARGUMENTS` string. Troubleshooting quickfixes are usually invoked mid-investigation, so mine the preceding turns (the reported bug, error messages, files inspected, root-cause discussion, and the fix that was agreed on) to populate a crisp product-owner-friendly summary:

- **WHAT (the problem)**: What is the current problem / observed behavior — what is broken from the user's or reporter's perspective (1-2 sentences).
- **WHY (the root cause)**: Why is this happening in the code — the underlying technical cause identified during troubleshooting (1-2 sentences). If the trigger was an automated finding (lint rule, test failure, code-smell metric), state the behavioral intent it is a proxy for, not just the raw message — see command-preamble-contract.md §9 (Genuine Fix Discipline).
- **HOW (the fix)**: How are we going to fix it — the concrete change plan agreed on in the thread (1-2 sentences). The plan must address the root cause above, not merely satisfy the check mechanically.
- **Affected Components**: Files/modules likely impacted (infer from the conversation and code already inspected).

For Code First, use the inspected delta: HOW describes what was implemented and any remaining
correction, not a fictional earlier plan. Record uncertain root cause as unknown rather than fact.

Keep each entry plain-language and reviewable by a non-engineer product owner. If any of WHAT/WHY/HOW cannot be determined from the thread, state the open question explicitly rather than inventing an answer.

### 7. Confirm, Then Create the Quickfix Branch

Working on an isolated branch keeps the record and the fix together — but **DevSpark must never create or switch branches without explicit confirmation** (see the Branch Safety rule in the preamble contract). Branch creation for every DevSpark route (including quickfixes) funnels through the single `new-branch.{ps1,sh}` script (spec 001-unified-new-branch) — never run `git checkout -b` directly here.

If `HAS_GIT` is false, skip branching entirely, note it in the summary, and write the record on the current working tree.

Otherwise:

1. If the working tree is already on a `NNN-fix-*` (or legacy `QF-*`) branch from a prior run, **stay on it** (no new branch, no switch) and continue.
   Reuse its matching quickfix record and ID if present instead of the newly allocated NEXT_ID.
2. If the working tree has **uncommitted changes**, warn the developer first — switching would carry those changes onto the new branch. Let them commit, stash, or decide before proceeding.
3. Show exactly what will happen and ask: **"Create and switch to branch `{BRANCH_NAME}` from `{CURRENT_BRANCH}`? (yes / stay on current branch)"**
   - **Wait for an explicit yes.** This confirmation is **required even under `--auto`** — creating/switching a branch is a working-context change that must be a human decision.
   - On **yes**: run `new-branch.{ps1,sh}` with `-Type fix -Number {NUMBER} -ShortName {SLUG} -Yes -Json` (bash: `--type fix --number {NUMBER} --short-name {SLUG} --yes --json`) — reusing the exact `NUMBER`/`SLUG` already shown so the created branch matches `{BRANCH_NAME}` precisely. `-Yes`/`--yes` is safe here because the confirmation above already satisfied Branch Safety; the script performs the audited `git checkout -b` and scaffolds a placeholder record at its `ARTIFACT_PATH`, which step 8 immediately overwrites with the full record.
   - On **no / stay**: do not create or switch; write the record on the current branch and note that choice in the summary.

Do **not** create the branch before the constitution compliance check (§5) resolves — a blocking FAIL must be surfaced first.

### 8. Generate Quickfix Record

Ensure directory exists: Create `/.devspark.work/quickfixes/` if missing.

Create record at `QUICKFIX_DIR/NEXT_ID.md`:

For Code First, fill Implementation Notes with the actual chronology and observed review/test
evidence rather than leaving it blank. Adapt the HOW and checklist wording to already-done work;
leave unresolved items unchecked and Completion blank until existing finalization succeeds.

```markdown
---
classification: one-off-fix
risk_level: { RISK_LEVEL }
target_workflow: quickfix
required_artifacts: quickfix-record
recommended_next_step: implement
required_gates: { Leave blank for low risk; otherwise checklist }
---

# Quickfix Record: {NEXT_ID}

## Metadata

- **ID**: {NEXT_ID}
- **Created**: {TIMESTAMP}
- **Author**: {GIT_USER}
- **Branch**: {CURRENT_BRANCH}
- **Classification**: {CLASSIFICATION}
- **Risk Level**: {RISK_LEVEL}
- **Max Effort**: {MAX_EFFORT}

## TLDR (Product Owner)

- **WHAT (the problem)**: {Plain-language description of the current problem / observed behavior — what is broken}
- **WHY (the root cause)**: {Why this is happening in the code — the underlying technical cause}
- **HOW (the fix)**: {How we are going to fix it — the agreed change plan}

## Affected Components

- {Inferred file/module 1}
- {Inferred file/module 2}

## Context Resolution

{One line per `.knowledge/` item this fix touches — a flat document, an entity, an entity layer, or a `governance/decisions/` doc, e.g. `- token-service (entity, direct)` or `- azure-devops-work-tracking (knowledge, direct)`. Flat documents count exactly as much as entities here. Leave as "None — no existing knowledge touched" if genuinely none apply; do not fabricate entries.}

## Constitution Compliance

| Principle              | Status           | Notes                  |
| ---------------------- | ---------------- | ---------------------- |
| {Relevant Principle 1} | PASS/CONDITIONAL | {Notes if conditional} |
| {Relevant Principle 2} | PASS/CONDITIONAL | {Notes}                |

## Validation Checklist

- [ ] Change addresses stated problem
- [ ] No unintended side effects identified
- [ ] Relevant tests updated/added (if applicable)
- [ ] Documentation updated (if applicable)

## Gate Acknowledgements

{Leave blank unless the user explicitly proceeds past a blocking or conditional concern}

## Implementation Notes

{Space for developer notes during implementation - leave blank initially}

## Completion

- **Completed**: {Leave blank - filled by implement's Finalize Every Route}
- **Commit**: {Leave blank - filled by implement's Finalize Every Route}
- **PR**: {Leave blank - filled by create-pr once the PR is opened}

---

Generated by /devspark-quickfix v1.0.
```

### 9. Commit Quickfix Record

If `HAS_GIT` is true, stage and commit the new record on the quickfix branch so the fix starts from a clean, traceable checkpoint. Compose the commit message from the WHAT/WHY/HOW summary captured in §6 (not a generic message):

For Code First this is a reconciliation checkpoint, not a pre-implementation checkpoint. Before
committing, inspect the index. If unrelated changes are already staged, leave the index untouched
and report the record as uncommitted; do not commit, unstage, or overwrite the developer's work.

1. Stage only the record: `git add {QUICKFIX_DIR}/{NEXT_ID}.md`.
2. Commit with a message of the form:

   ```text
   quickfix({NEXT_ID}): {one-line WHAT summary}

   WHY: {root cause in the code}
   HOW: {planned fix}
   ```

3. If `HAS_GIT` is false, skip the commit and tell the user the record was written but not committed (no git available).

Do not stage unrelated working-tree changes — commit the record only. The actual code fix is committed later by the user as they iterate.

### 10. Output Summary

Display to user:

For Code First, adapt the summary and next steps to what actually happened: report inspected
scope, remaining work, Knowledge update or justified no-update, executed verification and review,
and unresolved failures/assurance. Never print the sample PASS or a completed claim by default.
For traditional entry, creation is not verification: keep the implementation handoff below.

````markdown
Quickfix Record Created: {NEXT_ID}

- **Classification**: {CLASSIFICATION}
- **Risk Level**: {RISK_LEVEL}
- **Constitution Check**: PASS ({N} principles validated)
- **Branch**: {BRANCH_NAME} (created & checked out) | current branch (git unavailable)

Record saved: /.devspark.work/quickfixes/{NEXT_ID}.md
Record committed: {commit SHA} | not committed (git unavailable)

## TLDR

- **WHAT**: {problem}
- **WHY**: {root cause}
- **HOW**: {fix}

## Gate Result

```yaml
gate: quickfix
devspark_version: "<installed version, or `unknown`>"
generated: "<ISO-8601 timestamp of this run>"
status: pass | warn | fail
blocking: true | false
severity: info | warning | error | showstopper
summary: "Targeted constitution check complete"
```

## Next Steps

1. Iterate on the fix on branch `{BRANCH_NAME}` — apply the change described in HOW, then commit as you go
2. Run tests to verify the fix
3. Update the record's Implementation Notes as the fix evolves; if WHAT/WHY/HOW change, keep the TLDR accurate
4. Mark record complete: `/devspark-quickfix complete {NEXT_ID}`
5. Create PR — prefer `/devspark-create-pr` so the PR reflects quickfix context and any recorded gate acknowledgements
6. If creating manually, verify `{BRANCH_NAME}` is in sync with the target branch (usually `main`) before opening the PR

If scope expands beyond {MAX_EFFORT}:

- Follow Route Escalation on Discovered Scope: add only the assurance a material concern justifies on this quickfix, and let the developer decide whether separate work starts with `/devspark-specify`
````

## Guidelines

### Scope Creep Detection

If during implementation the user mentions scope expansion:

- "Also need to change..."
- "This is more complex than expected..."
- "Need to refactor..."
- Multiple files/modules affected

Surface it without converting the route:

```markdown
Scope Expansion Detected

Your quickfix may be growing beyond the {CLASSIFICATION} classification.
  - Same fix, larger than expected: continue here and keep the record accurate
  - A separate change: finish or set aside this fix, then start that work with /devspark-specify
```

### Route Escalation on Discovered Scope

A lightweight route may legitimately begin lightweight. What it may not do is carry architectural or governance-weight work through quickfix ceremony because the route was chosen before the scope was known.

The signals above are about effort and what the developer *says*. These are about what the work turns out to **be** — surface the escalation decision when the fix is discovered to require any of:

- a new architectural contract or interface
- a new cross-subsystem dependency
- a governance or constitution change
- a public contract change (API, CLI, schema, or published output shape)
- a persistent schema change with semantic effect on existing data
- a security or trust-boundary issue
- several unrelated remediation concerns bundled into one fix

One signal is enough, but only when it is **material** — a genuinely new contract, not a renamed helper. Do not convert routinely; most quickfixes exhibit none of these and finish as quickfixes.

A signal never converts the route. It asks for the one activity that resolves its concern, added to this quickfix: `/devspark-critic` to challenge the concern against the real system, `/devspark-analyze` to check the record's internal soundness, or a decision from whoever holds the authority. Then the fix continues. When one fires, state the evidence and hand the decision over:

```markdown
Route Escalation Check

This change has outgrown the assumptions of the quickfix route.
Signal: {which signal, and the specific evidence for it}

Add the needed assurance and continue, or split out separate work?
  - Continue: {the one activity this concern needs, e.g. /devspark-critic}, then /devspark-quickfix complete {ID} when done
  - Split:    keep this fix to its original problem; start the separate change with /devspark-specify
```

The developer owns that decision. Record the outcome in the record's Implementation Notes so a later reader can see the route was examined and chosen, not merely inherited.

For either entry, choosing to continue does not waive material-risk assurance or authorization.
Record missing obligations as unresolved and do not finalize until applicable requirements pass.

### Quickfix vs New Work Decision Guide

Choose at the start. Once a quickfix is under way, discovered scope follows Route Escalation above instead.

| Scenario                             | Recommendation                     |
| ------------------------------------ | ---------------------------------- |
| Single file change, < 50 lines       | Quickfix                           |
| Bug with clear root cause            | Quickfix                           |
| Production issue needing rapid fix   | Quickfix (hotfix)                  |
| Multiple files, architectural impact | New work with `/devspark-specify` |
| New user-facing feature              | New work with `/devspark-specify` |
| Database schema changes              | New work with `/devspark-specify` |
| API contract changes                 | New work with `/devspark-specify` |

### Error Handling

**Constitution missing:**

```markdown
Cannot perform quickfix - Constitution required

The project constitution defines validation criteria. Create one first:

1. Run: /devspark-constitution
2. Define your project's core principles
3. Then retry: /devspark-quickfix {description}

Learn more: https://github.com/MarkHazleton/DevSpark
```

**High Risk Classification:**

For `hotfix` classification with HIGH risk:

```markdown
High-Risk Quickfix Warning

This has been classified as a hotfix with HIGH risk level.

Before proceeding:

- [ ] Confirm this is truly urgent
- [ ] Identify rollback plan if fix fails
- [ ] Notify team of incoming production change

Proceed with caution. Consider pair review for critical fixes.
```

### ID Format

Quickfix IDs follow the unified branch-creation format (spec 001-unified-new-branch): `NNN-fix-<slug>`

- `NNN`: The repo-wide derived index, shared with spec/quick-spec branches and zero-padded to 3 digits (001, 002, ... 999) — never a stored counter.
- `fix`: Fixed type tag identifying this as a quickfix.
- `<slug>`: A normalized short-name derived from the description (up to 4 words).

Example: `042-fix-null-guard-on-parse`.

Legacy `QF-YYYY-NNN` records (year-scoped, reset annually) created before this change remain readable and are still counted by the allocator so new indexes never collide with them.

## Context

$ARGUMENTS
