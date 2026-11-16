#!/usr/bin/env pwsh
# DevSpark - (c) 2026 Make Bold Solutions. Source: https://dev.makeboldspark.com
#requires -Version 7.0
param(
    [Parameter(Position = 0, ValueFromRemainingArguments)]
    [string[]]$Arguments,
    [switch]$Json,
    [switch]$DryRun
)

$engine = Join-Path (Split-Path $PSScriptRoot -Parent) 'release-context.py'
$engineArgs = @()
if ($Json) { $engineArgs += '--json' }
if ($DryRun) { $engineArgs += '--dry-run' }
$engineArgs += $Arguments
& python $engine @engineArgs
exit $LASTEXITCODE
