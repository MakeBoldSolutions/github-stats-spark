---
devspark_version: "9.2.0"
---

# PR Review-State Contract

This contract defines the PR-specific extension to the shared review finding representation. The
existing PR review Markdown file is the only persisted authority; Markdown sections and counters are
derived presentation. Other review stages retain their existing lifecycle semantics.

## Record

Modern review frontmatter may contain `review_state`:

```yaml
review_state:
  format_version: 1
  findings: []
  conditions: []
  last_change: {}
```

`format_version` is exactly `1`. Unsupported versions, malformed YAML, invalid field types,
duplicate canonical IDs, and alias collisions are errors. Once a modern marker is present, parsing
or prerequisite failures never fall back to legacy Markdown interpretation.

Each finding has one `finding_id`, explicit `aliases`, full-word `severity`, independent `category`
and `blocking`, original `description` and `expected_outcome`, evidence, recommended action,
`execution_mode` (`auto`, `selective`, or `manual`), lifecycle `status`, outcome, provenance, and
optional remediation, verification, governed disposition, and reopen reason. The lifecycle states are `open`, `remediated`,
`awaiting-verification`, `resolved`, and `reopened`. Aliases name the same finding and never add
another historical finding or blocker.

`conditions` records existing applicable review obligations and their actual results; it does not
create policy gates or erase failed required evidence. `last_change` describes the most recent
accepted operation. Earlier snapshots remain in Git; the frontmatter is not an event ledger.

## Reading and Compatibility

The existing PowerShell and Bash `address-pr-review` entry points preserve their current flags,
staging gates, output keys, and Python-independent gate behavior. When inspecting a review:

1. A valid modern record is interpreted by the shared Python state engine.
2. A legacy Markdown report remains readable without migration. In environments without Python or
   PyYAML, the shell helpers support only the fixture-pinned read-only legacy grammar.
3. A malformed or unsupported modern record, missing structured-operation prerequisite, stale
   write, busy guard, or invalid transition fails explicitly. Errors are not successful empty input.

Legacy intake recognizes finding action checkboxes and finding detail rows, including table-only
and action-only entries. Blocking is taken only from explicit blocking or non-blocking section
classification, never inferred from severity. Findings without an unambiguous classification fail
with a diagnostic rather than becoming silently nonblocking or approved; use an authorized
`recover-legacy` event to record the complete interpretation. Conflicting classifications also fail
unless resolved through that event. The Python-independent shell readers apply the same rule.
The parser ignores examples inside code fences and unrelated tables. An explicit
slash-linked identity such as `H-01 / PRD3-01` uses `H-01` as canonical and records `PRD3-01` as an
alias. Similar descriptions do not establish identity. Conflicting identity, alias, or lifecycle
evidence requires a bounded recovery decision.

Unambiguous historical closures retain `Legacy resolved` provenance without invented reviewer
evidence. A checkbox or author fix reference alone cannot establish a new independently verified
resolution. Contradictory action/table states fail rather than selecting the favorable view.
Description, evidence, source references, and fix text are retained during normalization. A
structured modern write is an explicit review update, not an automatic migration. An authorized
`recover-legacy` event can resolve a located status, blocking-classification, or alias-ownership
conflict by supplying the complete chosen interpretation, rationale, authority, and evidence.
Unaffected canonical findings are retained; malformed identifiers remain an explicit manual
correction rather than a guessed identity.

## Shared Engine Interface

The internal script `scripts/pr-review-state.py` supports:

```text
inspect REVIEW_PATH --json
apply REVIEW_PATH --event EVENT_JSON_PATH --expected-digest HEX --repo-root ROOT --json
render REVIEW_PATH --expected-digest HEX --json
```

`inspect` is read-only and returns the logical record, SHA-256 digest, finding projection, pending
verification subset, unresolved blocker count, recommendation, and diagnostics. `apply` takes a
typed operation (`record`, `remediate`, `submit`, `remediate-and-submit`, `verify`, `reopen`,
`disposition`, or `recover-legacy`). Event data is temporary caller input, never another persistent
authority, and its proof text is not executed. `render` changes presentation only and cannot create
a lifecycle event or verification.

The renderer owns four paired comment boundaries: `ACTION`, `DETAIL`, `SUMMARY`, and `DECISION`,
using `<!-- PR-REVIEW-DERIVED:<NAME>:BEGIN -->` and matching `END` markers. It rewrites only action
items, finding detail, current-state summary, and local recommendation. Reviewer narrative, risk
analysis, observations, and evidence outside these regions remain intact. A malformed, duplicated,
or out-of-order marker pair fails rather than deleting unrecognized content; an older supported
report with no markers is bounded by its known headings before the first generated rewrite.

Success JSON uses `ok: true`, `changed`, `revision`, `record_digest`, and derived disposition fields.
Failure JSON uses `ok: false` and an `issues` array with a stable diagnostic `code`, concise
`message`, `location`, and (when useful) bounded `recovery` guidance. A failed command exits nonzero.
Compatibility projections retain the helper's historical severity codes and status values while
adding normalized severity, category, aliases, and lifecycle state. Pending reviewer work remains
visible and is never author-auto-eligible.

## Transitions and Independence

Author remediation records the full committed correction SHA, author execution context, explanation,
and actual author validation (or its explicit absence). Submission retains the remaining independent
proof obligation. It may be submitted for independent verification in the same operation, but the
unresolved blocker remains active.

Only a distinct permitted reviewer can evaluate the original expectation against the named
correction and directly affected behavior. The evaluation records reviewer context and role,
correction and evaluated commits, proof considered and performed, evidence, conclusion, and rationale.
The state engine checks completeness, distinctness, and context; it cannot prove that a narrative is
genuine. The reviewer must perform the existing required evaluation and proof. If no distinct
reviewer or sufficient proof is available, status stays pending. Confirmation resolves the finding;
incomplete proof reopens the issue; inconclusive proof remains pending.

Reopening a resolved finding requires substantive recurrence or incomplete-correction evidence and
retains its canonical identity and prior decisive evaluation. Administrative rendering, formatting,
counter repair, aliases, and repeat delivery do not reopen findings or invent verification events.
Accepted, deferred, and withdrawn outcomes remain separately governed dispositions with their
existing authority and capture requirements.

## Derived Views and Closeout

Unique canonical findings determine historical totals. Current severity/state totals, actionable and
pending lists, unresolved blockers, gate summary, and local recommendation derive from the record
and applicable condition results. Category or identifier prefix alone does not determine blocking.
Historical totals count canonical identities once. `remediated` and `awaiting-verification` blockers
remain unresolved; only the latter appears in the pending-reviewer subset. `not-applicable`
conditions do not block closeout, while required failing or pending conditions do. A positive local
recommendation is not a hosted approval vote or merge authorization.

The existing PR review `UPDATE` performs bounded evaluation of the original concern, correction, and
directly affected behavior. When evaluation succeeds and all other applicable review conditions
pass, that same update writes the evaluation, derived Markdown, counts, and recommendation together.
It does not require a full rediscovery pass or a later reconciliation-only invocation.

## Write Integrity

State-changing requests provide the digest of the inspected review bytes. The writer takes a
non-waiting exclusive same-directory guard, re-reads and checks the digest, validates the proposed
record and derived views, writes a temporary sibling, and atomically replaces the review file.
Conflicting updates, incompatible correction context, invalid proof binding, or an active writer
fail explicitly without partially updating the record. An identical already-applied event is
unchanged and does not advance revision or fabricate another evaluation.

Review-record commits remain isolated from code, tests, and other documents. No sidecar state,
database, external service, platform write, automatic retry, or cross-stage evidence cache is added.
