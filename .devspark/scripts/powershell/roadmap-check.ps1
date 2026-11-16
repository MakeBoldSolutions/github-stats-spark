#!/usr/bin/env pwsh
# DevSpark - (c) 2026 Make Bold Solutions. Source: https://dev.makeboldspark.com
#requires -Version 7.0
param(
    [Parameter(Position = 0, ValueFromRemainingArguments)]
    [string[]]$Arguments,
    [string]$Root,
    [switch]$Apply,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
$engine = Join-Path (Split-Path $PSScriptRoot -Parent) 'roadmap-check.py'
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    [Console]::Error.WriteLine('Python is required to run the roadmap checker.')
    exit 2
}
$engineArgs = @()
if ($Root) { $engineArgs += @('--root', $Root) }
if ($Apply) { $engineArgs += '--apply' }
if ($Json) { $engineArgs += '--json' }
$engineArgs += $Arguments
& python $engine @engineArgs
exit $LASTEXITCODE
