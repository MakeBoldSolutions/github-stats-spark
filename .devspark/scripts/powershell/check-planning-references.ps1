#!/usr/bin/env pwsh
# DevSpark - (c) 2026 Make Bold Solutions. Source: https://dev.makeboldspark.com
#requires -Version 7.0
#
# Deterministic backstop for command-preamble-contract.md §0: durable code, tests, and
# .knowledge/ must never reference the ephemeral planning bundle that produced them. Prose
# instructions in implement.md/pr-review.md/site-audit.md ask the agent to self-check this on
# every run; this script makes it a real, repeatable gate instead of relying on the agent
# remembering, since a leaked reference (a spec/task/quickfix ID, or the branch name itself) has
# kept recurring even with the prose instruction in place.

[CmdletBinding()]
param(
    [string]$RepoRoot = '.',
    [string]$Branch = '',
    [switch]$IncludeTests,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Roots this rule never applies to: the ephemeral planning roots themselves, the installed
# framework payload, vendor/build output, and two meta-documents whose entire purpose is to
# summarize active/historical work by design (AGENTS.md's rolling "Recent Changes", CHANGELOG.md's
# release notes) -- excluded from both tiers below.
$script:AlwaysExcluded = @(
    '.devspark.work/', '.archive/', '.devspark/', '.git/', '.venv/', 'node_modules/',
    'site/_site/', '.pytest_cache/'
)
$script:AlwaysExcludedFiles = @('AGENTS.md', 'CHANGELOG.md')
# templates/, .github/ (shims generated from templates/), and tests/ legitimately document or
# exercise the ID conventions themselves (e.g. tasks-template.md's illustrative task/requirement IDs,
# a generated shim's example command invocation, or this repo's own tests asserting spec/task/
# quickfix numbering and parsing behavior) -- excluded only from the generic-ID-pattern tier
# below, never from the exact-branch-name tier, since a real feature's own branch name should
# never legitimately appear in either. A tests/ directory at any depth is excluded by default to keep the
# routine gate low-noise; pass -IncludeTests for a stricter, human-reviewed audit pass, since a
# real leak can hide in a test file's own comment/docstring rather than its fixture data.
$script:GenericIdExcludedBase = $script:AlwaysExcluded + @('templates/', '.github/', 'site/src/')
$script:GenericIdExcluded = if ($IncludeTests) { $script:GenericIdExcludedBase } else { $script:GenericIdExcludedBase + @('tests/') }
$script:IdPattern = '\bFR-\d{3}\b|\bT\d{3}\b|\bQF-\d{4}-\d{3}\b'

function Test-ExcludedPath {
    param([string]$Path, [string[]]$Prefixes)
    foreach ($prefix in $Prefixes) {
        if ($Path.StartsWith($prefix)) { return $true }
    }
    return $false
}

$root = (Resolve-Path $RepoRoot).Path
Push-Location $root
try {
    if (-not $Branch) {
        $Branch = (git branch --show-current 2>$null)
    }
    if ($Branch -in @('main', 'master', 'trunk', 'develop', 'HEAD')) {
        $Branch = ''
    }

    $files = git ls-files
    $branchFindings = [System.Collections.Generic.List[object]]::new()
    $idFindings = [System.Collections.Generic.List[object]]::new()

    foreach ($file in $files) {
        if (Test-ExcludedPath -Path $file -Prefixes $script:AlwaysExcluded) { continue }
        if ($script:AlwaysExcludedFiles -contains $file) { continue }
        $inGenericScope = -not (Test-ExcludedPath -Path $file -Prefixes $script:GenericIdExcluded)
        if (-not $IncludeTests -and $file.Contains('/tests/')) { $inGenericScope = $false }

        try {
            $lines = Get-Content -LiteralPath $file -ErrorAction Stop
        } catch {
            continue  # binary or unreadable; skip rather than fail the gate on encoding noise
        }

        $lineNumber = 0
        foreach ($line in $lines) {
            $lineNumber++
            if ($Branch -and $line.Contains($Branch)) {
                $branchFindings.Add([PSCustomObject]@{ path = $file; line = $lineNumber; match = $Branch })
            }
            if ($inGenericScope) {
                foreach ($m in [regex]::Matches($line, $script:IdPattern)) {
                    $idFindings.Add([PSCustomObject]@{ path = $file; line = $lineNumber; match = $m.Value })
                }
            }
        }
    }

    $ok = ($branchFindings.Count -eq 0 -and $idFindings.Count -eq 0)

    if ($Json) {
        [PSCustomObject]@{
            contract        = 1
            branch          = $Branch
            branch_findings = $branchFindings
            id_findings     = $idFindings
            ok              = $ok
        } | ConvertTo-Json -Depth 6
    } else {
        foreach ($f in $branchFindings) {
            Write-Host "PLANNING-REF: $($f.path):$($f.line) references the current branch name '$($f.match)'"
        }
        foreach ($f in $idFindings) {
            Write-Host "PLANNING-REF: $($f.path):$($f.line) references planning identifier '$($f.match)'"
        }
        if ($ok) {
            Write-Host 'No planning-artifact references found.'
        }
    }

    if ($ok) { exit 0 } else { exit 1 }
} finally {
    Pop-Location
}
