# Validation remediation plan

1. Repair CI output paths using the generator's username normalization, track the frontend lockfile, use reproducible installs, and align supported runtimes.
2. Update compatible frontend dependencies, supply coverage/UI/bundle-analysis tools, and replace vulnerable Lighthouse CI tooling with a maintained local audit runner.
3. Establish explicit Python formatting/lint/type-check settings; fix code defects and typing errors rather than hiding them behind blanket exclusions.
4. Make validation repeatable with a script and CI workflow. Add regression tests for changed behavior.
5. Rerun Python/frontend tests, static checks, clean install/build, dependency audits, PowerShell validation, and browser/Lighthouse checks. Record remaining limitations and results here.

## Execution

- Initial plan recorded. Work in progress.
