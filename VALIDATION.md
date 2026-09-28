# Application validation

Install Python 3.11+ and Node 24 LTS, then install Python dependencies:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt -e .
./run-validation.ps1
```

The command checks Python dependencies, Black, Flake8, mypy, all Python tests,
configuration, PowerShell syntax, a clean `npm ci`, frontend lint/formatting,
Vitest coverage, production build, and security audits. Failures stop validation
with a nonzero exit code. Builds go to `.validation/site`; published `docs` files
are not modified. `-PythonExecutable` selects a separate Python interpreter.

For browser and performance checks, install Chrome (or set `CHROME_PATH` to its
executable), then run:

```powershell
./run-validation.ps1 -Browser -Lighthouse
```

Browser smoke covers loading data, search, repository details, charts, Health,
mobile navigation, and theme switching. Lighthouse runs three mobile audits and
enforces the median against the budgets in `frontend/.lighthouserc.json`. Reports
stay in `frontend/.lighthouse`; nothing is uploaded. Historical FID, interactive,
and PWA assertions were removed because current Lighthouse no longer emits those
audits. The supported timing, transfer-size, accessibility, and performance
budgets are retained.

Individual frontend commands (run inside `frontend`):

```powershell
npm ci
npm run validate
npm run test:ui
npm run build:analyze
```

`build:analyze` produces `frontend/bundle-stats.html` without opening a browser.
Build commands normally publish to `docs`. Set `SPARK_BUILD_DIR=.validation/site`
for a local validation build. Other output paths are rejected before cleanup.

Python policy: Black owns formatting at 88 columns; Flake8 checks E/F/W rules,
excluding wrapping/spacing rules that conflict with Black. Docstring prose rules
are not part of this gate. Mypy checks the entire `spark` package using its `src`
layout, with installed third-party stubs; only untyped `svgwrite` imports are
excluded from import checking. Type errors in application code are not suppressed.

The read-only `Validate application` GitHub Actions workflow runs on pull requests,
main pushes, and manual dispatch. The statistics generation workflow uses the same
Node major and committed npm lockfile. It normalizes filesystem paths using the
same helper as the Python generator and detects newly generated, untracked data.
