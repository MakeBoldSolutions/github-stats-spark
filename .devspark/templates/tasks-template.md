---
source: "DevSpark — © 2026 Make Bold Solutions. Source: https://dev.makeboldspark.com"
description: "Task list template for feature implementation"
devspark_version: "<version that authored this task list; omit if undeterminable>"
plan_semantic_hash: null
participants:
  owner: human
  planner: ai
  implementer: ai
  reviewer: human
  critic: ai
  scribe: ai
---

# Tasks: [FEATURE NAME]

**Input**: Design documents from `/.devspark.work/specs/[###-feature-name]/`
**Prerequisites**: plan.md (required), spec.md (required for user stories); research.md, data-model.md, contracts/ and quickstart.md only when the plan created them

**Tests**: The examples below include test tasks. Every behavior change considers its Tests impact; the delta is add, update, retire or none, so include test tasks for any delta that is not none, and never assume every change adds tests.

**Pre-PR only**: in every derivation, with or without `qa-acceptance.md`, derive only work that can finish before the PR or merge. Never add a task that waits for deployment, runs QA after merge, needs post-deployment sign-off, belongs to a later sprint, or depends on defects not yet found. A specification delivers a releasable change, not the product release itself; tasks must not include release packaging, version publication, or product deployment. **Post-merge capture** applies to all derivations: a `stage: post-deploy` obligation is not a task; it is carried as a deferred requirement with an owner and an existing durable `captured_as` record.

**Organization**: Derive tasks from the Plan's `expected_change_surface`, one per entry or small group of entries that change together. Group by user story only when the spec has independent stories; otherwise use one ordered list with no phase headings or story labels. Include Setup, Foundational or Final groups only when real work needs them.

## Format: `[ID] [P?] [Story?] Description (Implements: FR-###[, FR-###])`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Only when grouped by story (e.g., US1, US2)
- **Implements**: Trailing `(Implements: FR-001, FR-003)` naming the functional requirement ID(s) from `spec.md` that this task satisfies. This makes spec↔task traceability explicit and deterministically checkable by `/devspark-analyze` (coverage gaps + traceability hallucinations). Omit only for pure setup/infrastructure tasks that implement no specific requirement.
- **Linkage**: none. A task states its files in the description. Durable files must never reference `spec.md`, `plan.md`, `tasks.md`, quickfix records, or other temporary work products.
- Include exact file paths in descriptions
- Describe only the implementation or verification delta. Cite requirement and acceptance IDs instead of paraphrasing their text; do not repeat the Spec rationale, research evidence, or Plan decisions.

## Tasks

[One task per `expected_change_surface` entry or group of entries. Reuse the existing tests and fixtures the Plan names; add a test only for behavior no existing test covers. When the spec has independent stories, use one section per story instead, each with a one-line **Goal** and **Independent Test** citing Spec ids. Add a setup or foundational section only for a blocking shared prerequisite, and a final section only for required verification, current-knowledge or linkage work. Omit any section that would be empty.]

- [ ] T001 [Implementation delta and file path] (Implements: FR-001)

---

## Dependencies

List only actual task/story dependencies not already implied by phase order. Mark parallel tasks with `[P]`; omit this section when no additional dependency exists.

## Gate Acknowledgements

Record any explicit human decisions to proceed despite unresolved checklist, analyze, or critic findings.

- Gate: [checklist|analyze|critic]
- Concern: [concise unresolved issue]
- Decision: [proceed/fix later/escalate]
- Recorded By: [name or role]
- Date: [YYYY-MM-DD]

---
