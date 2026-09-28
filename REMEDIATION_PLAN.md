# Validation remediation plan

1. Repair CI output paths using the generator's username normalization, track the frontend lockfile, use reproducible installs, and align supported runtimes.
2. Update compatible frontend dependencies, supply coverage/UI/bundle-analysis tools, and replace vulnerable Lighthouse CI tooling with a maintained local audit runner.
3. Establish explicit Python formatting/lint/type-check settings; fix code defects and typing errors rather than hiding them behind blanket exclusions.
4. Make validation repeatable with a script and CI workflow. Add regression tests for changed behavior.
5. Rerun Python/frontend tests, static checks, clean install/build, dependency audits, PowerShell validation, and browser/Lighthouse checks. Record remaining limitations and results here.

## Execution

- CI paths now use `slugify_username`, and change detection includes untracked outputs. The frontend lockfile is included, installs use `npm ci`, Node 24 is configured, and artifact uploads use user-scoped SVG paths.
- Compatible npm updates are locked. Vitest UI and coverage are installed at matching versions. Bundle analysis uses the current visualizer plugin. The vulnerable Lighthouse CI dependency tree was replaced with current Lighthouse and a local browser runner; npm audit reports zero findings.
- Black formatting was applied, unused code/imports were cleaned up, and Flake8 has an explicit Black-compatible E/F/W policy. Docstring prose rules are not enforced. Mypy now resolves `spark` from `src`, uses third-party stubs, and checks all 48 source modules without blanket application suppressions.
- Fixed report construction and validation, nested report deserialization, AI responses containing non-text blocks, optional date annotations, and several incorrect API/type assumptions. Added seven regression test cases.
- Added `run-validation.ps1`, `VALIDATION.md`, a read-only validation workflow, and a production browser smoke test. Validation output goes to `.validation/site` without changing the published site.
- Lighthouse exposed additional app issues: corrected heatmap ARIA roles, heading order, accessible control names, dark-theme contrast, initial service-worker reload, and loading-related footer layout shift. Lazy charts and removal of manual bundle grouping reduced startup JavaScript to approximately 114 KB transferred. Early data/avatar discovery reduced largest-contentful paint.

## Verification

- Python 3.11 and 3.14: 406 tests pass; Black, Flake8, mypy, dependency consistency, and security audits pass.
- Frontend: 30 tests pass with working coverage; lint, formatting, production build and browser smoke pass. Full npm audit: zero findings.
- Both GitHub workflows pass actionlint 1.7.12 (its optional shellcheck/pyflakes integrations were disabled locally).
- Lighthouse completed three mobile runs and passed the retained budgets: median performance 98, accessibility 96, best practices 100, FCP 1.50 s, LCP 2.16 s, CLS 0, and initial script transfer approximately 114 KB. Reports remain local in `frontend/.lighthouse`.
- Final clean-install validation passed: `./run-validation.ps1 -PythonExecutable .validation/venv311/Scripts/python.exe -Browser`. Log: `.validation/final-validation.log`.
- Vitest UI also passed all 30 tests in noninteractive run mode. `npm run build:analyze` successfully generated `frontend/bundle-stats.html`.
- All five plan steps are complete locally. Publishing and hosted CI verification remain external follow-up steps.

## Limits

- Local verification uses Windows. Python 3.11 matches CI, but the installed Node runtime is 26; CI is configured for Node 24. A hosted Ubuntu Actions run is still needed after publishing the changes.
- No live paid AI generation, deployment, or push was performed by the agent. Vite still emits advisory raw chunk-size warnings; the enforced transferred-script budget passes.
- Python dependency auditing skips this local, unpublished project itself; its installed third-party dependencies are audited.
