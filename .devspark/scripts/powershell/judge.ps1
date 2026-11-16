#!/usr/bin/env pwsh
# DevSpark - (c) 2026 Make Bold Solutions. Source: https://dev.makeboldspark.com
#requires -Version 7.0
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PassThroughArgs
)

$engine = Join-Path (Split-Path $PSScriptRoot -Parent) 'judge.py'
& python3 $engine @PassThroughArgs
exit $LASTEXITCODE
