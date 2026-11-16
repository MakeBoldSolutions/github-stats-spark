<!-- DevSpark — © 2026 Make Bold Solutions. Source: https://dev.makeboldspark.com -->

# DevSpark Context Scripts

Helper scripts invoked by the slash-command prompts in `templates/commands/`.
Installed copies live at `.devspark/scripts/` in consumer repositories; team
overrides in `.devspark.work/scripts/` take precedence at run time (2-tier
script resolution).

## Layout and Parity

- `bash/` — POSIX Bash implementations
- `powershell/` — PowerShell 7+ implementations. Every script declares
  `#requires -Version 7.0`, so Windows PowerShell 5.1 stops with a version
  error instead of a parse error.

Constitution §VI (Platform Parity) requires every `bash/<name>.sh` to have a
matching `powershell/<name>.ps1` with equivalent behavior, and vice versa.
`tests/test_script_parity_contract.py` enforces this.

### Bash version constraint

`bash/*.sh` must stay compatible with **bash 3.2** — the version Apple ships
as `/bin/bash` on every Mac and has not upgraded since 2007 (GPLv3 licensing).
Since every script uses `#!/usr/bin/env bash`, it resolves to whichever
`bash` is first on `PATH`; on a stock Mac (no Homebrew `bash` prepended to
`PATH`) that is the real 3.2 binary. Avoid bash 4+-only constructs such as
`mapfile`/`readarray`, `${var^^}`/`${var,,}` case expansion, `local -n`
namerefs, and associative arrays (`declare -A`). When testing locally on a
Mac, run scripts with `/bin/bash` explicitly (not just `bash`) to catch
regressions even if Homebrew bash is installed and earlier on `PATH`.

## Unified Branch Creation

`new-branch.(sh|ps1)` is the **single** entry point that issues
`git checkout -b` for new DevSpark work. It:

- derives the next global index live (never stores a counter) by scanning
  branches, `.devspark.work/specs/*`, and `.devspark.work/quickfixes/*`
  (both legacy `QF-YYYY-NNN` and unified `NNN-fix-*` records);
- composes `NNN-<type>-<slug>` branch names (`type` ∈ `work`, `fix`);
- validates the composed name with `git check-ref-format --branch` before
  ever creating it;
- enforces the Branch Safety confirmation gate (fails closed — non-zero
  exit — in a non-interactive context without `--yes`/`-Yes`);
- scaffolds nothing for a `work` branch and a minimal quickfix record for a
  `fix` branch, and prints JSON-only to stdout (diagnostics go to stderr).

`/devspark-specify` creates `--type work` branches and `/devspark-quickfix`
creates `--type fix` branches. New work never scaffolds a full-spec or
quick-spec bundle; existing `NNN-spec-*`, `NNN-quick-*`, legacy `NNN-<slug>`
and `QF-YYYY-NNN` branches and records continue to resolve and are counted by
the allocator.

## Standalone Tools

Most scripts are invoked by a command prompt's `scripts:` frontmatter. One is
standalone:

- `generate-atomic-shims.(sh|ps1)` — maintainer tool that regenerates the
  source-repository Agent Skills `.github/skills/devspark-*/SKILL.md` from
  `templates/commands/*.md` (and, for the five source-only commands, the stop
  bodies in `eng/skills/source-stop/`), plus the published consumer skills
  `templates/consumer-skills/devspark-*/SKILL.md`. Run with `--check` / `-Check` as the
  CI drift gate; it also reports orphaned `devspark-*` skill folders, which it
  never deletes.

Release packaging tooling is maintainer-only and lives in `eng/release/`, not
here — nothing under `eng/` ships to consumer repositories.
