---
source: "DevSpark — © 2026 Make Bold Solutions. Source: https://dev.makeboldspark.com"
description: Coordinate dependency-ordered work when it is useful. Generates tasks.md for existing specification bundles; on work branches identifies deliverables and persists them only when continuity or coordination requires it.
handoffs:
  - label: Recommend Next Step
    agent: devspark-next
    prompt: Recommend the next step for this branch
    send: false
scripts:
  sh: .devspark/scripts/bash/check-prerequisites.sh --json --require-plan
  ps: .devspark/scripts/powershell/check-prerequisites.ps1 -Json -RequirePlan
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Workflow Position

**Step 4 of 4** in the authoring chain (`specify → clarify → plan → tasks`).

- **Owns**: a complete, dependency-ordered, story-organized temporary `tasks.md` immediately executable by `/devspark-implement`, including affected current-knowledge updates, tests, and verification. A task states the files it changes; `/devspark-implement` records nothing back into it beyond the checkbox.
- **Does NOT own**: revisiting WHAT/WHY (spec is authoritative); redesigning architecture/stack/contracts (→ `/devspark-plan`); resolving `[NEEDS CLARIFICATION]` (→ `/devspark-clarify`); gate artifacts beyond the opt-in `## Gate Acknowledgements` note (→ `/devspark-analyze`, `/devspark-critic`).
- **Pre-flight**: if `plan.md` is missing or `spec.md` still contains `[NEEDS CLARIFICATION]` markers, halt and route back to the appropriate earlier step.
- **Work branches** (`NNN-work-*`, whatever its directory holds): coordination is optional and needs no plan; follow **Work Branch Coordination**. The authoring chain, pre-flight, Derivative Contract and Planning Review handoff above apply only to existing full-spec bundles.

## Work Branch Coordination (no specification)

Tasks here coordinate meaningful deliverables; they are not a workflow stage. Simple or
single-deliverable work needs no decomposition: say so and continue with `/devspark-implement`.

1. **Establish context** from the developer's request, the branch diff and commits, current code and
   tests, relevant `.knowledge/`, and `work.md` or `plan.md` when `AVAILABLE_DOCS` lists them. A plan
   is never required.
2. **Identify deliverables**: a short dependency-ordered list of independently verifiable outcomes
   (behaviour, contract, test or Knowledge change), not one entry per file edit. Name each
   dependency, and the owner when several developers share the branch. A deliverable that needs a
   material decision nobody has made is surfaced to the developer (who may run `/devspark-plan`),
   not invented here.
3. **Coordinate in session** with your agent's built-in task tracking when it exists, and report the
   list in chat. Write nothing to the repository for this.
4. **Persist only when justified**: when the list must survive a new session, spans substantial
   dependencies, or coordinates several developers, record it in `FEATURE_DIR/work.md` under
   `## Remaining Deliverables` as `- [ ] <outcome> (after: <deliverable>)`, following the resume-note
   rules of `/devspark-specify` (`**Status**: In Progress` while work remains). Preserve existing
   entries and check them off rather than regenerating. Do not create `tasks.md`, `spec.md`,
   `plan.md`, a checklist or a gate artifact, and do not copy the in-session list there unless one
   of these needs applies.
5. **Add no process**: no Task IDs, `Implements:` directives or `plan_semantic_hash`; no Analyze,
   Critic, Judge or Planning Review. Open deliverables are coordination, not a completion gate: the
   work is done when `/devspark-implement` establishes its outcome and verification.
6. **Report and hand back**: report the deliverables, where they are tracked, and the next one. The
   next step is `/devspark-implement`.

## Definition of Done

Done when: `tasks.md` is a coherent, dependency-ordered projection of the approved Plan with required checklist fields. Re-runs select re-projection or authorized task remediation from the Plan fingerprint, protect completed work and report the focused-review handoff. A correction need not append a new task or remediation heading. This command stops after writing tasks.md; it does not begin implementation. Chat output: report only the step-6 summary (counts, MVP scope); the task list itself lives in the file.

On a work branch, Done when the developer has a dependency-ordered list of deliverables (or a statement that none is needed) tracked where **Work Branch Coordination** places it.

## Constitution Authority

Load `/.knowledge/governance/constitution.md` before generating tasks. It is **non-negotiable** in one specific way: a principle that requires runtime behavior (observability, logging, accessibility, security baseline, audit logging, test coverage) needs a task when, and only when, the changed behavior triggers it. Principles the change does not touch generate no tasks. If the plan accepted a Constitution Waiver, surface it as a single note rather than silently skipping the principle.

## Outline

Load and obey the shared preamble contract core at `/.devspark/templates/command-preamble-contract.md` (installed repos) or `templates/command-preamble-contract.md` (source repos) before step 1 — it covers multi-app scope resolution and the 2-tier override check for scripts. Preamble modules: `convergence`, `provenance`.

1. **Setup**: Run `{SCRIPT}` from repo root and parse FEATURE_DIR and AVAILABLE_DOCS list. All paths must be absolute. For single quotes in args like "I'm Groot", use escape syntax: e.g 'I'\''m Groot' (or double-quote if possible: "I'm Groot").
   If the branch matches `NNN-work-*`, follow **Work Branch Coordination** above instead of steps 2-6.

2. **Load design documents**: Read from FEATURE_DIR:
   - **Required**: plan.md (tech stack, libraries, structure), spec.md (user stories with priorities)
   - **Required for principle enforcement**: `/.knowledge/governance/constitution.md` (load once; extract mandated principles that imply runtime tasks — observability, accessibility, security baseline, test coverage, audit logging, etc.)
   - **Optional**: data-model.md (entities), contracts/ (interface contracts), research.md (decisions), quickstart.md (test scenarios), qa-acceptance.md (independent acceptance scenarios with a regression disposition each)
   - Note: Not all projects have all documents. Generate tasks based on what's available.

   Before generating tasks, read the YAML frontmatter in `spec.md` and treat it as authoritative for `classification`, `risk_level`, and `required_gates`. If the prose implies a heavier or lighter route than the metadata, flag that mismatch to the user instead of guessing.

   Read `expected_change_surface` from `plan.md` to know which files the design expects to change, and derive the Knowledge owners of those files with `explain-context.py --files <paths>` (`.devspark/scripts/bash/explain-context.sh` or `.devspark/scripts/powershell/explain-context.ps1` in installed repos) rather than keeping a Knowledge list of your own. A task that needs a file outside the surface is explained as justified support (a helper, a test, an affected owner); one that needs new architecture or scope is a PLANNING GAP.

   Before generating tasks, inspect any existing gate artifacts under FEATURE_DIR:
   - `checklists/*.md`
   - `analyze.md`, `critic.md`
   - `gates/*.md`

   Before **Mode detection**, compute the current Plan fingerprint using `judge.py semantic-hash
   --path <FEATURE_DIR/plan.md>` and compare it with Tasks' `plan_semantic_hash`. Missing,
   incompatible or unavailable evidence is unknown, not a matching Plan. Read the current approved
   Plan to establish the projection; do not fabricate a digest or silently restamp existing Tasks.
   Keep that fingerprint: it identifies the Plan content you read and validated, and it is the only
   value you may record, never one recomputed afterward.

   **Mode detection**: absent Tasks uses initial generation (step 4). When the recorded
   `plan_semantic_hash` differs from the fingerprint, first check the task list against the current
   Plan. If the projection is still coherent, report "Plan → Tasks: NO CONTENT CHANGE" in this run's
   output only and update just `plan_semantic_hash`; that restamp never changes the Tasks projection.
   Otherwise (changed Plan semantics) use
   re-projection: update unchecked work and dependencies to reflect the approved design, consume
   authorized `task_work`, and preserve completed tasks and their evidence. If a completed task is
   invalidated, stop and ask the developer; never silently rewrite or uncheck it. Unknown provenance
   requires checking the projection against the Plan before selecting a mode. A genuinely unchanged
   Plan uses step 3 for authorized task remediation, not full regeneration. Record
   `plan_semantic_hash` only after the resulting projection is coherent and checked; omit it if the
   helper cannot produce a valid fingerprint. Finish with one focused Planning Review, not direct
   implementation under the old STOP.

   If required gates exist and contain unresolved blocking findings, or a checklist has incomplete items, summarize the findings and recommend the next action. Ask the user whether to fix first, review findings, or proceed anyway. Do not hard-block. **Autonomy override**: if the invocation includes `--auto` (or the conversation has established a standing autonomy instruction), skip the ask — auto-select "fix first" when `gates/critic.md`/`gates/analyze.md` have open findings (route to step 3) and "proceed" otherwise; either way, record the auto-selected choice under `## Gate Acknowledgements` with `auto-selected: true`. A constitution-violation finding (CRITICAL/SHOWSTOPPER tied to a `§`-coded principle) is never auto-proceeded past, `--auto` or not.

   If the user (or `--auto`) chooses to proceed anyway, record the decision in `tasks.md` under a `## Gate Acknowledgements` section with the gate name, the unresolved concern, and the user's explicit choice.

3. **Gate Remediation Merge** (re-run only, when `tasks.md` already exists — initial generation skips straight to step 4):

   **Judge dispositions govern scope.** > **A finding is evidence, not automatically work.** When `gates/judge.md` exists, run `scripts/judge.py remediation --feature-dir <FEATURE_DIR>` (`.devspark/scripts/bash/judge.sh` or `.devspark/scripts/powershell/judge.ps1` in installed repos). If it validates, do **not** merge raw Analyze/Critic findings into scope — consume its output instead:

   - `task_work` (authorized `require` or `simplify`) is the input to task remediation, one task per concern citing `(resolves: <concern sources>)`. `plan_revisions` routes to Plan revise first. The compatibility aggregate `current_planning_work` is not permission to turn a Plan correction into an execution task. Skip sources already represented by existing tasks; a `simplify` correction reduces machinery rather than adding it.
   - `routed_obligations` stay with their owner (`verify`, `closeout`, `pr-review`, `implement`). They are never appended as tasks and are never deferred; they remain part of this spec's completion.
   - `accepted` (resolution `accept`) creates no task and no future-work promise.
   - `future_work` (resolution `defer`) is **not** a task and never an unchecked item in this spec. Materialize it once, outside the spec, with `scripts/judge.py future-work --feature-dir <FEATURE_DIR> --write`, which writes a Future Work Plan under `.devspark.work/intake/` (existing files are left untouched). DEFER is a disposition, not a task status.
   - `pending_decisions` (`resolution: null`, `needs_authority: true`) are never processed here: no task, no future work, not accepted. Ask the developer the concern's `question`, then have them re-run `/devspark-planning-review --judge-only` to record the decision; only the recorded `require` / `simplify` / `defer` flows on.

   If the helper reports `status: fail`, stop and tell the developer to re-run `/devspark-planning-review --judge-only`. If `gates/judge.md` does not exist, continue with the legacy merge below (unchanged for older routes).

   Legacy merge (no Judge artifact):

   - Load the `findings:` YAML from `gates/critic.md` and `gates/analyze.md` (when present). Both already use the Shared Review Resolution Contract (`finding_id`, `severity`, `description`, `recommended_action`, `execution_mode`, `status`, `outcome`), so they merge directly — no schema translation needed.
   - Merge and dedupe: findings citing the same file:line/section with overlapping descriptions are one row with both `finding_id`s noted (`critic-004 / analyze-009`).
   - Keep only `status: open` findings. Sort by severity: showstopper > critical > high > medium > low (CON findings are out of scope here — those feed `/devspark-evolve-constitution`, not tasks).
   - If the findings carry Analyze/Critic `classification` values and no Judge artifact exists, the route needs Planning Review: recommend `/devspark-planning-review` and stop instead of promoting raw findings to tasks.
   - Present the merged list as one table with an elaborated recommendation per row (not just the stored `recommended_action` one-liner — reason about the actual fix given the current spec/plan/code).
   - Selection: ask which findings to address this round (`all` allowed). **Autonomy override**: under `--auto`/standing autonomy, select only genuinely blocking compatibility work (`blocking-defect`, or `critical`/`showstopper` when no classification exists) and only when the developer's instruction explicitly grants that scope authority. Medium and Low findings are never auto-selected, whatever their `execution_mode`: report them and leave them for the human. A finding's `recommended_action` is evidence, not permission to add machinery beyond the Plan.
   - For each selected finding, append a task under a new `## Gate Remediation` phase (after the last existing phase) in the existing `tasks.md`: `- [ ] T0NN [P?] Fix <one-line description> in <file path> (resolves: <finding_id>[, <finding_id>...])`. Do not touch already-checked `[X]` tasks or existing phases.
   - Report the count of tasks appended and recommend `/devspark-implement` to execute them. After remediation tasks are implemented, re-run `/devspark-planning-review` once: it reuses fresh child artifacts and rechecks only what `judge.py children` says is stale. **Assurance should converge based on unresolved risk, not artifact churn** — a changed hash alone is not a reason to loop; stop after one remediation round and one focused recheck, and ask the developer if a third round seems needed.
   - This step is terminal for a re-run: do not fall through to step 4 afterward.

4. **Execute task generation workflow** (initial generation only):
   - Load plan.md and extract tech stack, libraries, project structure
   - Load spec.md and extract user stories with their priorities (P1, P2, P3, etc.)
   - If data-model.md exists: Extract entities and map to user stories
   - If contracts/ exists: Map interface contracts to user stories
   - If research.md exists: Extract decisions for setup tasks
   - Generate tasks from the change surface (see Task Organization below)
   - **Enforce triggered constitution obligations**: for each loaded principle the changed behavior triggers, ensure a concrete task exists in the relevant group. If a Constitution Waiver was recorded in `plan.md`, add a single annotation task referencing it rather than silently omitting the principle.
   - Validate task completeness (each group has what it needs and is independently testable)

5. **Generate tasks.md**: Use `/.devspark/templates/tasks-template.md` in installed repos, or `templates/tasks-template.md` in source repos, as the structure. Fill with:
   - Correct feature name from plan.md
   - Only the phases or groups the change needs (see Task Organization): setup and foundational work only when a blocking prerequisite exists, story groups only when there are independent stories
   - Each group includes: goal, independent test criteria, tests (if the Tests delta is not `none`), implementation tasks
   - A final group only for required verification, current-knowledge consistency and no-planning-reference validation, plus retention of the complete `FEATURE_DIR` after every required check passes
   - All tasks must follow the strict checklist format (see Task Generation Rules below)
   - Clear file paths for each task
   - Dependencies only where an edge is not already implied by phase order; `[P]` marks parallel tasks
   - `## Gate Acknowledgements` section when the user proceeds with unresolved findings

   **Current knowledge tasks**: for each behavior-bearing change, add a task to update the matching
   `.knowledge/` node selected by `appliesTo`, or create a typed node when durable new behavior has no
   owner. Add affected test tasks in the same story or phase. Do not generate feature, requirement,
   or task nodes under `.knowledge/`. Neither durable output may point back to this task list or
   its plan/spec.

   Keep task descriptions to the implementation or verification delta, exact path, and forcing
   requirement/design/acceptance id. Do not paraphrase requirements, acceptance scenarios, rationale,
   research, or Plan decisions. Story goals and independent tests should be one line and cite Spec ids;
   include extra detail only when a real task dependency or test procedure needs it.

6. **Report**: Output the tasks.md path and a concise readiness summary; do not restate the task list.

Context for task generation: {ARGS}

The tasks.md should be immediately executable - each task must be specific enough that an LLM can complete it without additional context.

## Constraints

**CRITICAL**: Every task traces to the Plan's change surface and a forcing source. When the spec has independent user stories, organize by story so each can be implemented and tested alone.

**Tests are a durable pillar, not an option**: every behavior change considers its Tests impact, and the resulting delta is `add`, `update`, `retire` or `none`. Generate test tasks for a delta that is not `none`; never assume every change adds tests. When `qa-acceptance.md` exists, derive the Tests tasks from its scenarios and their regression dispositions.

**Pre-PR tasks only**: derive only work that can finish before the PR or merge, in every derivation (with or without an acceptance artifact). When an acceptance artifact exists, that is: automated acceptance coverage, regression add/update/retire, a durable manual-regression reference, and source-controlled QA material. Never derive a task that waits for deployment, executes QA after merge, needs post-deployment sign-off, belongs to a later sprint, or depends on defects not yet discovered. **Specification delivers a releasable change; product release packages and distributes completed changes.** Tasks MUST NOT include publishing or deploying a release, version bumping/publishing, or package distribution. A completed specification does not remain open solely because its product release has not occurred. **Post-merge capture** applies to every derivation: a `stage: post-deploy` obligation is not a task. It stays visible as a deferred requirement with its owner and an existing durable `captured_as` record (closeout contract §4.1), and is verified after deployment.

### Checklist Format (REQUIRED)

Every task MUST strictly follow this format:

```text
- [ ] [TaskID] [P?] [Story?] Description with file path (Implements: FR-###[, FR-###])
```

**Format Components**:

1. **Checkbox**: ALWAYS start with `- [ ]` (markdown checkbox)
2. **Task ID**: Sequential number (T001, T002, T003...) in execution order
3. **[P] marker**: Include ONLY if task is parallelizable (different files, no dependencies on incomplete tasks)
4. **[Story] label**: only when the list is grouped by user story; format `[US1]`, `[US2]` (maps to the spec's user stories)
5. **Description**: Clear action with exact file path
6. **Implements directive**: For implementation tasks, append `(Implements: FR-001, FR-003)` naming the functional requirement ID(s) the task satisfies, so `/devspark-analyze` can deterministically detect coverage gaps and traceability hallucinations. Omit for tasks that implement no specific requirement. Every `FR-###` in spec.md SHOULD be referenced by at least one task.
7. **No back-links**: never add a reference from durable code, tests, or `.knowledge/` back to `spec.md`, `plan.md`, `tasks.md`, or any other temporary work product.

**Examples**:

- ✅ CORRECT: `- [ ] T001 Add the singleton GET/PUT pair to src/api/maintenance_routes.py by copying the closest existing pair (Implements: FR-004)`
- ✅ CORRECT: `- [ ] T005 [P] Implement authentication middleware in src/middleware/auth.py`
- ✅ CORRECT: `- [ ] T012 [P] [US1] Create User model in src/models/user.py (Implements: FR-001)`
- ✅ CORRECT: `- [ ] T014 [US1] Implement UserService in src/services/user_service.py (Implements: FR-001, FR-003)`
- ❌ WRONG: `- [ ] Create User model` (missing ID and Story label)
- ❌ WRONG: `T001 [US1] Create model` (missing checkbox)
- ❌ WRONG: `- [ ] [US1] Create User model` (missing Task ID)
- ❌ WRONG: `- [ ] T001 [US1] Create model` (missing file path)

### Derivative Contract (REQUIRED)

The Plan defines the solution; Tasks only operationalizes it. Every generated task cites exactly one of these forcing sources, in its description or an `(Implements: ...)` directive:

1. a requirement in `spec.md`;
2. a design decision or element in `plan.md`;
3. a verification obligation (a declared `verify:<mode>`, or a test the requirement needs);
4. a constitution obligation;
5. a Knowledge ownership update (an affected `.knowledge/` node);
6. approved Judge remediation (`task_work`).

A task that would introduce a state, setting, endpoint, persisted record, cache, dependency, architectural pattern, rollback design, or behavior that the Plan does not establish is a **PLANNING GAP**. Stop generation, report the missing decision and which task needed it, and route to `/devspark-plan` revise. Do not invent the mechanism here, and do not treat the gap as authority: Plan needs an approved Judge correction or explicit human authority before it changes. Ordinary implementation detail (naming, file layout inside the expected change surface, helper functions, tests) is not a gap.

Before reporting, self-check each task: does it cite one forcing source, and does it add nothing the Plan lacks? A task that fails either test is removed or becomes a PLANNING GAP.

### Task Organization

Tasks are derived from the Plan's `expected_change_surface`, not from a fixed phase template.

1. **One task per surface entry** (or per small group of entries that change together): the exact path, the delta, and the forcing source. `inspect` entries produce no task. A file outside the surface is explained as justified support; new architecture or scope is a PLANNING GAP.
2. **Group by user story only when the spec has more than one independently deliverable story.** A single-story or small change is one ordered list with no phase headings and no `[Story]` labels.
3. **Create Setup, Foundational or Final phases only when real work needs them**: a blocking shared prerequisite, or required verification and current-knowledge updates. Never create an empty phase or a filler task to populate one.
4. **Reuse before adding.** Extend the existing tests, fixtures and harnesses the Plan names. Running existing regression is a verification task; add a new test only for behavior that no existing test covers.
5. **Constitution obligations are tasks only when the changed behavior triggers them** (a new endpoint triggers its audit-logging and auth obligations; an unrelated principle does not). An accepted Constitution Waiver is one annotation, not a task per principle.
6. **Map contracts and data-model entities** to the task or story that needs them; add a contract test only when the Tests delta is not `none`.

Within a story or list: tests, then models, services and endpoints, then integration. Each group is an independently testable increment.
