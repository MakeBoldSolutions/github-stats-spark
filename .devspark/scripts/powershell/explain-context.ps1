#!/usr/bin/env pwsh
# DevSpark - (c) 2026 Make Bold Solutions. Source: https://dev.makeboldspark.com
#requires -Version 7.0
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Topic,
    [switch]$Json
)

$engine = Join-Path (Split-Path $PSScriptRoot -Parent) 'explain-context.py'
$engineArgs = @($Topic)
if ($Json) { $engineArgs += '--json' }
& python3 $engine @engineArgs
exit $LASTEXITCODE
