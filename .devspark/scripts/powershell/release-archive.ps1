#!/usr/bin/env pwsh
# DevSpark - (c) 2026 Make Bold Solutions. Source: https://dev.makeboldspark.com
#requires -Version 7.0
param(
    [Parameter(Position = 0, ValueFromRemainingArguments)]
    [string[]]$Arguments,
    [switch]$Json,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$engine = Join-Path (Split-Path $PSScriptRoot -Parent) 'release-archive.py'
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    [Console]::Error.WriteLine('Python is required to run the release-archive engine.')
    exit 2
}
$engineArgs = @()
if ($Json) { $engineArgs += '--json' }
if ($DryRun) { $engineArgs += '--dry-run' }
$engineArgs += $Arguments
& python $engine @engineArgs
exit $LASTEXITCODE
