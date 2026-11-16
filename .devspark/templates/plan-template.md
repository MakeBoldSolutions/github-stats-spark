---
source: "DevSpark — © 2026 Make Bold Solutions. Source: https://dev.makeboldspark.com"
devspark_version: "<version that authored this plan; omit if undeterminable>"
spec_semantic_hash: null
participants:
  owner: human
  planner: ai
  implementer: ai
  reviewer: human
  critic: ai
  scribe: ai
---

# Implementation Plan: [FEATURE]

<!--
  Design the smallest responsible change against the current implementation. First find the
  closest existing implementation by behavior and extend it; introduce a new mechanism only when
  that implementation demonstrably cannot satisfy the requirement. Keep the result understandable,
  testable and easy to change again. Avoid speculative abstractions and extensibility.
-->

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]
**Input**: Feature specification from `/.devspark.work/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/devspark-plan` command. See `.devspark.work/templates/commands/plan.md` for the execution workflow.

## Rationale Summary

### Core Problem

[One concise sentence aligned with the Spec's Core Problem; do not copy its rationale or requirements.]

### Decision Summary

**Closest existing pattern**: [path or symbol found by behavior, and how this change fits it: reused as-is, extended, or does not fit]
**New mechanism**: [none | what is new, the requirement or constraint that the existing implementation cannot meet, and the lighter option rejected]

[Plan-owned decisions that resolve material implementation questions, with the rationale needed to explain each. When a behavior could be integrated at an existing seam or distributed across call sites, record the chosen boundary and why. Point to `research.md` for evidence when it exists.]

### Key Drivers

- [Only a planning constraint or implementation driver not already stated in the Spec or technical context.]

### Reviewer Guidance

[One or two plan-specific assumptions or decisions to verify; omit generic guidance.]

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: [e.g., Python 3.11, Swift 5.9, Rust 1.75 or NEEDS CLARIFICATION]
**Primary Dependencies**: [e.g., FastAPI, UIKit, LLVM or NEEDS CLARIFICATION]
**Storage**: [if applicable, e.g., PostgreSQL, CoreData, files or N/A]
**Testing**: [e.g., pytest, XCTest, cargo test or NEEDS CLARIFICATION]
**Target Platform**: [e.g., Linux server, iOS 15+, WASM or NEEDS CLARIFICATION]
**Project Type**: [e.g., library/cli/web-service/mobile-app/compiler/desktop-app or NEEDS CLARIFICATION]
**Performance Goals**: [domain-specific, e.g., 1000 req/s, 10k lines/sec, 60 fps or NEEDS CLARIFICATION]
**Constraints**: [domain-specific, e.g., <200ms p95, <100MB memory, offline-capable or NEEDS CLARIFICATION]
**Scale/Scope**: [domain-specific, e.g., 10k users, 1M LOC, 50 screens, or how often the operation runs and whether a human drives it; NEEDS CLARIFICATION if unknown]

## Expected Change Surface

<!--
  Orientation for Tasks, Analyze, Implement and owner lookup, not an allow-list. A legitimate
  supporting file outside it is explained, not rejected; new architecture or scope returns to Plan.
  Do not store counts (derive them) or a list of Knowledge nodes to update (owner lookup derives it).
-->

```yaml
expected_change_surface:
  - {path: "[file or bounded area]", change: "[add | modify | remove | inspect]", why: "[reason]"}
```

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

[Gates determined based on constitution file]

## Context Resolution

*The bounded `.knowledge/` working set for this delta, pinned down here so `/devspark-implement` consumes it as already-resolved and never traverses more than one additional hop itself. `/devspark-analyze` validates every entry resolves against the current corpus; `/devspark-critic` judges whether the set is sufficient for the delta.*

This section records **resolved** context, which is a selection from — not a copy of — the
**candidate** context Context Projection returns. Projection is deliberately generous so that
nothing relevant is unreachable; this list is deliberately small. Record an item because the delta
needs it, not because the graph could reach it.

```yaml
context_resolved:
  - id: [knowledge id, e.g. token-service | azure-devops-work-tracking]
    kind: [knowledge | entity | entity-layer | decision]
    via: [relation or match that reached it, e.g. direct | depends-on -> auth-gateway]
    hop: [0|1|2]
    reason: [why this item informs the delta]
```

Flat Knowledge documents are first-class resolved context. A working set made entirely of
`kind: knowledge` entries is valid and complete — never promote a flat document into an entity
just so it can be listed here.

`hop: 0` is a direct lexical match, `hop: 1` is one authoritative relationship away, `hop: 2` is
two. Planning never records a hop greater than 2.

[Leave empty only if this delta touches no existing `.knowledge/` content — state that explicitly rather than omitting the section.]

## Project Structure

List only the directories or files this change adds, removes, or materially reorganizes. If the
layout is unchanged, state that and rely on `expected_change_surface`; do not copy a generic
repository tree into the plan.

<!--
Planning bundle artifacts (created conditionally under FEATURE_DIR/):
├── research.md          # Only if a planning question needed research
├── data-model.md        # Only if persisted/domain shape changes materially
├── quickstart.md        # Only if validation needs a non-routine procedure
├── qa-acceptance.md     # Only if independent acceptance validation is warranted
├── contracts/           # Only if an interface changes materially
├── gates/               # Persisted gate artifacts from analyze/critic/checklist
└── tasks.md             # Phase 2 output (/devspark-tasks command - NOT created by /devspark-plan)
-->

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified, or when repeated integration across call sites is chosen over an existing seam**

| Violation / Complexity | Why Needed | Simpler Alternative Rejected Because |
|------------------------|------------|--------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
