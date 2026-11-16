---
source: "DevSpark — © 2026 Make Bold Solutions. Source: https://dev.makeboldspark.com"
description: Optional roadmap planning. Establish product direction, record and right-size Prospective Specs, review delivery evidence for drift, and keep the roadmap structurally consistent, without touching code, tests, or Knowledge.
handoffs:
  - label: Start Delivery
    agent: devspark-specify
    prompt: Start delivery of the roadmap item I name
scripts:
  sh: .devspark/scripts/bash/roadmap-check.sh check --json
  ps: .devspark/scripts/powershell/roadmap-check.ps1 check -Json
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty). Requests are natural language,
for example:

```text
/devspark-roadmap establish a roadmap for this application
/devspark-roadmap add a Prospective Spec for exporting reports
/devspark-roadmap is ps-004 right-sized?
/devspark-roadmap what is ready to start?
/devspark-roadmap review progress against what we delivered
/devspark-roadmap mark ps-002 complete
/devspark-roadmap check
/devspark-roadmap --root ../planning/roadmap review progress
```

## Purpose

Load and obey the shared preamble contract core at `/.devspark/templates/command-preamble-contract.md`
(installed repos) or `templates/command-preamble-contract.md` (source repos) before proceeding.

A roadmap is **optional shift-left planning**: it records where the application is going and the
right-sized increments that get it there. It is not a project-management system, a second delivery
lifecycle, or a gate. DevSpark works exactly as before without one; no development, fix, experiment, or
release requires a roadmap.

> Roadmap the direction. Deliver through one flow. Measure outcomes. Adapt deliberately.

The structure, Prospective Spec (PS) shape, and status vocabulary are in
`/.devspark/templates/roadmap-template.md` (installed) or `templates/roadmap-template.md` (source).

## Planning Boundary

This command plans. It never delivers.

- **Read anything relevant**: application source, tests, configuration, architecture, `.knowledge/`,
  Git history, branches, and local delivery evidence, to understand current reality.
- **Write only roadmap artifacts, only inside the resolved roadmap root.** Never modify application
  code, tests, configuration, dependencies, deployment artifacts, `.knowledge/`, or any
  `.devspark.work/specs/` record.
- Never run application builds or tests, never execute an implementation command, never apply a quick
  fix discovered while planning, and never reset, overwrite, stash, or clean existing working-tree
  changes. Record a discovered defect or architectural concern in the roadmap as a finding or a
  proposed PS.
- Never invoke `/devspark-specify` or any delivery command. Starting delivery is always an explicit
  developer action.
- Recommend; do not decide. Product priorities, architectural direction, sizing, and status changes
  are written only after the developer approves them in this conversation.

## Locate the Roadmap

Extract only `--root <path>` from the user input, if present, and append that option with its path
quoted to `{SCRIPT}`. Keep the natural-language request out of the CLI arguments; interpret it using
the Requests section below. Run the resulting command once and parse its JSON. It resolves
`ROADMAP_ROOT` in this order:

1. `--root <path>` that the developer gave in this request;
2. `roadmap.root` in `.devspark.work/devspark.json` (a repository-relative or absolute path);
3. the default `.devspark.work/roadmap/`.

An external planning location (a separate planning repository or directory, `EXTERNAL: true`) must be
explicitly given or configured; that explicit selection is the write authorization. Never search for a
nearby planning directory or assume permission to write one. If the developer names a location
without `--root`, rerun the script with `--root <path>` rather than guessing.

When `PRESENT` is `false` and the request is not to establish a roadmap, say that no roadmap exists at
`ROADMAP_ROOT`, note that one is optional, and stop.
When a configured external roadmap is absent, report the missing location and stop even for an
establish request. The developer can explicitly choose that location with `--root` to authorize
establishing it; never recreate a missing shared checkout automatically.

## Requests

Interpret the request and do only what it needs. One request may combine several of these.

**Establish or revise the roadmap.** Create or update `ROADMAP_FILE` under `ROADMAP_ROOT` (normally
`roadmap.md`) from the template: direction, current baseline, themes, and decisions. Assess the
existing application first so the baseline is factual, citing paths, commits, and observed behavior.
Propose the direction and themes; write them once the developer agrees.

**Add a Prospective Spec.** Use `NEXT_ID` from the script output; ids are permanent and never reused.
Create `specs/<id>-<slug>.md` from the template with `status: proposed`, link it from the relevant
theme in `ROADMAP_FILE`, and keep it concise. A PS records the outcome, current reality, scope and
standalone shipping boundary, future health, dependencies and decisions, and completion expectations.
It never contains implementation tasks, file-by-file plans, test inventories, line-level
instructions, or status audits.

**Review and right-size a PS.** Apply the right-sizing test: *if this PS were completed and every
later roadmap item were canceled, would the application remain healthy, complete, and releasable?*
Check that it is:

- **Complete** and **verifiable**: it delivers a whole capability or technical outcome with an
  observable completion boundary;
- **Autonomous** and **shippable**: no unfinished future PS is needed to complete, repair, or activate
  it, and it leaves the application secure, stable, compatible, and releasable (a complete capability
  may ship intentionally inactive);
- **Right-sized**: neither a fragment nor a bundle of independently shippable outcomes;
- **Future-preserving** and **technically responsible**: it keeps credible future options open,
  avoids unnecessary coupling, introduces no unjustified debt, and leaves affected components at least
  as healthy as it found them.

An undersized PS usually depends on unfinished work; propose merging it into the outcome it serves. An
oversized PS combines separately shippable outcomes; propose a decomposition with ids, before
delivery starts. Do not split to meet a size, duration, or repository-count target, and do not turn a
PS into a general cleanup initiative unless cleanup is itself the shippable outcome. Mark a PS `ready`
only when the developer accepts its boundary.

**Evaluate dependencies and future health.** Explain which delivered prerequisites a PS relies on,
which related technical debt it should leave cleaner, and which credible future options it must not
close off. Do not create refactoring quotas, speculative abstractions, architecture scores, or debt
approval gates.

**Recommend what is ready.** `UNBLOCKED` lists `proposed` and `ready` items with no recorded
`blockers` whose dependencies are complete, or recorded as complete in the live overview's Delivered
section (`ARCHIVED` maps historical ids to `complete`, `dropped`, or `unknown`). An archive link alone has unknown status and never
satisfies a dependency. Confirm unknown status from current code and Git delivery evidence, then
record the developer-approved status in Delivered; never read the archived copy.
Combine it with the roadmap's themes and current evidence to recommend a next PS and say why. The
developer chooses.

**Review progress and drift.** Compare each affected PS with delivery evidence: branches, commits,
merged history, code, tests, and current Knowledge. For a shared roadmap, inspect the affected
repository or repositories; if they are unavailable, report the missing evidence. Distinguish:

- **Tracking drift**: recorded status or `delivery` references disagree with the evidence;
- **Product drift**: what was delivered, or what is being prioritized, diverges from the intended
  outcomes and direction.

Present the evidence and a recommended correction for each. Code and Git evidence outrank a stale
planning claim. Merged is not necessarily deployed and deployed is not necessarily activated; record
only what the evidence shows, never invent deployment or activation. Update only the affected items,
replace their current assessment rather than appending review logs, and never rewrite direction,
decisions, or priorities from an automated finding.

**Record a decision.** Add a developer-approved planning decision, with its basis, to the roadmap's
Decisions section (or to the PS it shapes). Record significant decisions and changes of direction
only, not every observation.

**Resolve an item.** With the developer's confirmation, set `status: complete` (citing at least one
`delivery` reference) or `status: dropped` (keeping the reason in the PS), then run the repair below to
stage it under `specs/complete/`, unless the layout preserves paths. Staged items stay there until
`/devspark-release` offers to archive them; archival
repoints this roadmap's links at the archived copies, so never edit them by hand. An external roadmap
is archived only from its own planning repository.

## Structural Check

The script's `FINDINGS` are deterministic: duplicate ids, id and file-name mismatches, unsupported or
malformed metadata, invalid status, missing dependencies, dependency cycles, broken local links,
misplaced items, and obvious tracking disagreements such as a complete item without a delivery
reference. Report errors and warnings plainly. Run the check again after any roadmap edit.

Mechanical findings marked `repairable` (item placement, and links broken by a move) can be fixed with
`roadmap-check repair` using the same resolved script as the check (team override if present), adding
the same `--root` when one was given. It plans the repairs and writes nothing. Show the plan; only after the developer authorizes it,
run it again with `--apply` (`-Apply`). Repair never advances a status, rewrites a decision,
reprioritizes, changes application files, or writes outside the roadmap root. Fix everything else by
hand, with the developer, or leave it reported.

## Handing a PS to Delivery

When the developer wants to start a PS, tell them to run `/devspark-specify <id>` (or the PS path),
optionally with the `--root` they used here. Specify reads the PS as intake context and follows the
normal delivery workflow. Never start it yourself. The PS id is a planning reference: it may appear in
a commit message, pull request description, or `work.md`, but never in shipped code, tests, or
`.knowledge/`. After delivery starts, a later progress review can record the branch or pull request in
`delivery` and set `status: active` once the developer confirms.

## Report

Summarize what changed in the roadmap (paths only), any open findings, the recommendation given, and
the next useful action. When nothing was written, say so.
