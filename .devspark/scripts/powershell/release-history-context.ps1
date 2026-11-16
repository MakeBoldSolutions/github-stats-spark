#!/usr/bin/env pwsh
# DevSpark - (c) 2026 Make Bold Solutions. Source: https://dev.makeboldspark.com
#requires -Version 7.0
# Compatibility adapter: v4 release history is the durable Git delta.
param(
    [string]$BaseRef = '',
    [string]$From = '',
    [string]$To = 'HEAD',
    [switch]$Json
)

$engine = Join-Path (Split-Path $PSScriptRoot -Parent) 'release-context.py'
$engineArgs = @('--to', $To)
if ($BaseRef) { $engineArgs += @('--from', $BaseRef) }
if ($Json) { $engineArgs += '--json' }
& python $engine @engineArgs
exit $LASTEXITCODE
