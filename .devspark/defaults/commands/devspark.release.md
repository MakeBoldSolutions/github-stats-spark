---
source: "DevSpark - (c) 2026 Make Bold Solutions. Source: https://dev.makeboldspark.com"
description: Seal a release from the verified repository delta, sweep .devspark.work retention and archive-eligible work, and keep current knowledge accurate.
handoffs:
  - label: Run Final Audit
    agent: devspark-site-audit
    prompt: Run a final delta and documentation audit before release
scripts:
  sh: .devspark/scripts/bash/release-context.sh $ARGUMENTS --json
  ps: .devspark/scripts/powershell/release-context.ps1 $ARGUMENTS -Json
---

## User Input

```text
$ARGUMENTS
```

You MUST consider non-empty user input. Load and obey the shared command preamble contract before
step 1.

## Purpose

Release seals the verified delta between the previous release and HEAD, and is the **sole** command
that ever moves anything from `.devspark.work/` into `.archive/{YYYY-MM-DD}/` (or the same dated
folder under the archive root a team has configured; see step 4). `{YYYY-MM-DD}` is
always *this release's own cut date* (today, the date this run tags) — never an individual swept
artifact's own internal date, timestamp, or filename stamp. Every artifact swept in steps 4–5 goes
into the one archive folder for the release being cut right now, regardless of what date it happens
to be stamped with internally. Its sources are code, current `.knowledge/`, tests, verification
results, Git history, merged PR metadata, and existing user-facing documentation.

`/devspark-implement` deliberately leaves every completed spec and quickfix record live in
`.devspark.work/` so the delta can be validated against code, tests, and knowledge for as long as it
stays there, which can span more than one sprint. Release is what eventually archives it, and also
runs the maintenance sweep: work-product
retention, orphaned in-flight state, current-knowledge backstop checks, and leaked-planning-identifier
scans all run here.

## Options

| Option              | Behavior                                                                                     |
| ------------------- | -------------------------------------------------------------------------------------------- |
| `{version}`         | Use the explicit semantic version                                                            |
| `--from <ref>`      | Override the release-window base ref                                                         |
| `--archive-root`    | Archive to this folder instead of `archive.root` (see Archive location in step 4)            |
| `--scope=work`      | Evaluate `.devspark.work/` retention and archiving only; skip the version/CHANGELOG workflow |
| `--scope=knowledge` | Evaluate current-knowledge currentness and code/knowledge consistency only                   |
| `--scope=scan`      | Report candidates only; make no changes                                                      |
| `--dry-run`         | Print the complete plan without writing files                                                |

## Workflow

1. Resolve repository or app scope and run the release-context script. Its JSON output is
   diagnostic input for this run only — never commit it to Git under any name (e.g.
   `release-context-*.json`). Check the script's `STRAY_RELEASE_ARTIFACTS` field: any match is a
   file matching that pattern that was already committed by a prior, interrupted release run that
   never reached step 10's version bump/tag. Treat it as stray, remove it, and do not treat its
   presence as evidence that prior release work exists.
2. Establish the release window from the previous version tag to HEAD. Use commits and merged PR
   metadata to classify the semantic version bump, and fix the release version now (the explicit
   `{version}` argument, else the calculated one). Archival in steps 4–5 is recorded against that
   version, so it must be settled first.
3. Verify the delta:
   - required tests, lint, builds, and declared release gates pass;
   - changed behavior and current `.knowledge/` are complete and mutually consistent;
   - the Knowledge builds (`python3 scripts/build_knowledge_index.py --repo-root . --check`;
     `KNOWLEDGE_BUILDS` in the release context). Derived index files are not compared or regenerated;
   - `.knowledge/` structural completeness and knowledge/code mapping accuracy are clean — require a
     current `/devspark-site-audit` result (full scope, or at least `--scope=knowledge`) covering
     this release window with no open `KNOW1`–`KNOW6` findings. Re-run site-audit's knowledge scope
     now if the most recent result predates the window; release does not duplicate that check
     itself, only confirms it has run and passed;
   - shipped code, tests, and `.knowledge/` contain no planning identifiers.
4. **Archive completed work with the release-archive script** — never move files by hand. This is
   the only place in DevSpark archiving happens, and it covers steps 4 and 5 in one operation:
   - Preview: `.devspark/scripts/bash/release-archive.sh plan --version {version} --json`
     (PowerShell: `.devspark/scripts/powershell/release-archive.ps1 plan --version {version} -Json`).
     `plan` writes nothing. It reports `TO_ARCHIVE`, `IN_FLIGHT`, `NEEDS_DECISION` (orphaned
     bundles, untracked files, uncategorized work areas), `COLLISIONS`, and `STALE_REFERENCES`.
   - **Archive location.** The archive is `.archive/` in this repository unless the team keeps its
     history elsewhere: `archive.root` in `.devspark.work/devspark.json`, or `--archive-root <path>`
     on `plan`, `apply`, and `validate` (the argument wins; `ARCHIVE_SOURCE` reports `argument`,
     `config`, or `default`). The root is `.archive/` itself, a folder inside it, or an **existing**
     folder outside the repository, such as a clone of a separate archive repository. Any other
     folder inside the repository is refused, because scans and Knowledge tooling would read the
     archived history as live content; the script never creates the folder. Keep the same root for
     every run of one release, since its journal lives there. Paths below name the default
     `.archive/`; under another root, read `ARCHIVE_ROOT` in its place. When `ARCHIVE_EXTERNAL` is
     true:
     - reported paths are absolute, and each file is copied, hash-checked against the plan, and only
       then removed from `.devspark.work/`, so an interruption leaves the original in place and
       `apply` resumes the move;
     - the archived files belong to the other folder, so this repository's release commit records
       only their removal. Relay `ARCHIVE_NOTICE` and have the folder's owner commit the archive
       there;
     - a bundle with uncommitted changes is listed in `NEEDS_DECISION` until it is committed, because
       Git could not recover what leaves the repository;
     - `--include-roadmap` leaves the roadmap untouched, and `ROADMAP_NOTICE` says why: a link to a
       file outside the repository would break for everyone else.
   - Show the plan and put every `NEEDS_DECISION` entry to the user. Never archive, delete, or
     reclassify one of them on your own, and never edit a bundle's status to make it
     eligible: eligibility rests on completion evidence that already exists. A spec is complete
     when `spec.md` says `Status: Complete` or `gates/closeout.md` records `status: pass` with
     `decision: complete`.
   - After the user confirms the plan, run the same command with `apply` instead
     of `plan` (`--dry-run` still never writes). It journals every move in
     `.archive/{YYYY-MM-DD}/release/archive-manifest-{version}.json`
     (original path, archived path, sha256, last commit) before moving anything, never overwrites
     an existing archived file (a collision stops the run, exit 2, with nothing moved), stages the
     moves so Git records them as renames, and is safe to rerun after an interruption.
   - Then run `validate --version {version}`. It must report `OK` before the release commit: every
     journaled file is in the archive with its recorded hash and none remains under `.devspark.work/`.
   - Resolve every `STALE_REFERENCES` entry (a tracked file outside `.archive/` that still names a
     moved path) by updating it to the archived path or removing it.
   - **Optional roadmap.** When `ROADMAP_COMPLETED` is non-empty, the repository's roadmap (the
     configured `roadmap.root`, default `.devspark.work/roadmap/`; `ROADMAP_ROOT` names it) has
     resolved Prospective Specs (`complete` or `dropped`) staged in `specs/complete/`. Offer to
     archive them with this release; never archive them without that agreement. When the user
     agrees, add `--include-roadmap` to `plan` and `apply`, which journals them in the same manifest
     under `.archive/{YYYY-MM-DD}/roadmap/specs/complete/` and then rewrites each live roadmap link to
     an archived item so it points at the archived copy (`ROADMAP_RELINK` previews the files,
     `ROADMAP_RELINKED` reports them). Existing prose stays as written apart from moved link targets;
     do not edit these links by hand. Every archived item also gets one permanent `## Delivered` line
     in the selected roadmap overview (normally `roadmap.md`; the roadmap checker reports its
     `ROADMAP_FILE`), with its link and
     explicit `complete;` or `dropped;` status, even if another roadmap file already links to it.
     Supporting files stay in place. A layout that preserves published paths keeps every Prospective
     Spec in place and reports `ROADMAP_NOTICE`. The status is captured from the live item in the release
     journal before the move, so interrupted runs can finish the record without reading archived
     planning content. The checker uses only the live Delivered records: a recorded `complete` item
     still satisfies dependencies, while a dropped or unknown item does not. A bare archive link or
     an older journal without status remains `unknown`; confirm its status from current delivery
     evidence rather than opening the archive. A staged item that is malformed, not
     resolved, a symbolic link, or that would relink a roadmap file with uncommitted changes appears
     in `NEEDS_DECISION` instead and stays in place. Everything else under the roadmap root is live
     planning and stays. A roadmap outside this repository (`ROADMAP_EXTERNAL`) is never read,
     archived, or rewritten here; relay `ROADMAP_NOTICE` and leave its archival to an authorized run
     in the planning repository. `ROADMAP_ERROR` means the roadmap was skipped unchanged. An archive
     outside this repository also leaves the roadmap in place (see Archive location). No
     roadmap, or declining the offer, changes nothing else, and the roadmap never blocks a release.
   - The script reads the archive only to refuse an overwrite and to resume this release's own
     manifest; no command, release included, scans or lists archived history for any other purpose.

   The classification behind `plan` is the release context's: `ARCHIVE_ELIGIBLE` lists the bundles
   that qualify, `ARCHIVE_BLOCKED` lists each remaining bundle with its `blockers`, and
   `ORPHAN_CANDIDATES` lists bundles whose branch no longer exists. Treat those as the decision, and
   spot-check rather than re-derive them:
   - A bundle is **archive-eligible** when its own completion marker reads `Complete` (`spec.md`
     `**Status**`, or the quickfix record's completion marker). Legacy `code_ref`/`knowledge_ref`
     fields, populated or not, are ignored.
   - Every archive-eligible bundle moves into `.archive/{YYYY-MM-DD}/` (preserving its relative path
     minus the `.devspark.work/` prefix, e.g. `.devspark.work/specs/042-foo/` →
     `.archive/{YYYY-MM-DD}/specs/042-foo/`), whole and intact — plan, tasks, research, checklists,
     gates, contracts, `context_resolved`, and any other file in the bundle. No copy is left under
     `.devspark.work/`, and nothing moves to `.knowledge/`.
   - A bundle that is **not yet** `Complete` stays exactly where it is — spanning more than one
     release window is normal, not an error. Report it as still in flight; never archive it.
   - Separately, flag a bundle whose branch is stale, merged, or deleted but that never reached
     `Complete` — this is orphaned, abandoned in-flight state, not a normal rollover. Surface it for
     human disposition; never archive it automatically.
5. The same `apply` moves every other categorized `.devspark.work/` artifact — `pr-review/`,
   `audit/`, `metrics/`, `telemetry/` per `.knowledge/taxonomy-registry.json` — into
   `.archive/{YYYY-MM-DD}/` the same way. Every release sweeps all of them unconditionally: there is
   no age, count, or eligibility check for these categories, unlike specs/quickfixes in step 4. A file
   that is not tracked by Git is reported in `NEEDS_DECISION` instead of moved, and nothing is ever
   deleted outright. Operational files stay: `devspark.json`, `devspark.user.json`, `README.md`,
   `commands/`, `scripts/`, `extensions/`, `intake/`, `roadmap/`, and dotfiles. A top-level work area with no
   taxonomy lifecycle is reported for a decision, never guessed at. (`.devspark.work/runs/`
   no longer exists — it was tied to the now-removed CLI; ignore any leftover copy as stray, not a
   category to sweep.)
6. Check `.knowledge/` for obsolete, duplicate, historical, decision-log, rationale-archive,
   lifecycle, or supersession content as a lighter, non-blocking backstop — `/devspark-pr-review` and
   `/devspark-site-audit` are the authoritative checks for this; release only catches what they missed
   between runs. This includes `.knowledge/governance/decisions/` docs: flag any that have drifted
   into a numbered/ADR-style filename, a "superseded by" chain, or a `constrains`/`constrained_by`
   pointer that no longer matches an existing entity — correct in place or delete, never archive.
7. Scan shipped code and `.knowledge/` for leaked spec, task, feature, quickfix, or requirement
   identifiers. Remove the reference; do not rewrite it into another planning reference.
8. Generate user-facing CHANGELOG and release notes from the release delta. Do not mention archived
   spec, task, quickfix, feature, or requirement identifiers.
9. Write operational release output — including a summary of what was archived (cite the manifest),
   what retention swept, and every artifact left for a decision — directly to the archive's
   `{YYYY-MM-DD}/release/` folder (`.archive/{YYYY-MM-DD}/release/` by default; `ARCHIVE_ROOT` names
   it). Release output is never staged under `.devspark.work/`, even temporarily: the archive is the
   only place any of this release's output lives once the run completes.
10. Bump source version files and the `.devspark/VERSION` stamp where applicable.
11. Show the exact commit, version, and tag plan, including the archive already applied in step 4.
    Require explicit confirmation before the release commit, tags, pushes, or publication;
    `--dry-run` never writes.
12. Re-run `release-archive validate` and the release gates (Knowledge build and integrity, package
    checks) against the post-archive workspace. Create the release commit — archive moves, release
    note, version metadata — only after success, create the tag only when authorized, and report
    publication status from the host.

Git is the sole history for `.knowledge/`: release never archives it, only corrects it in place or
deletes it. `.devspark.work/` retained work products and archive-eligible specs/quickfixes are the
one exception — those move to `.archive/{YYYY-MM-DD}/` per steps 4–5 above, never deleted
outright; orphaned planning bundles wait for an explicit owner decision. No DevSpark command,
release included, reads, lists, or globs the archive (`.archive/` or the configured root) afterward
beyond the script's own scoped reads in step 4; a human decides when an entry there is safe to
remove, outside any DevSpark command.

Where you are: release sealed, `.devspark.work/` swept
Next: monitor for the next release window
