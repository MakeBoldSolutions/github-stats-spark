#!/usr/bin/env pwsh
<#
.SYNOPSIS
Run app validation without changing the published docs directory.
#>
[CmdletBinding()]
param([switch]$Lighthouse)

$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = 'python' }
$previousBuildDir = $env:SPARK_BUILD_DIR
Push-Location $PSScriptRoot
try {
    $env:SPARK_BUILD_DIR = '.validation/site'
    $checks = @(
        @('-m', 'pip', 'check'),
        @('-m', 'black', '--check', 'src', 'tests', 'setup.py'),
        @('-m', 'flake8', 'src', 'tests', 'setup.py'),
        @('-m', 'mypy'),
        @('-m', 'pytest', 'tests', '-q'),
        @('-m', 'spark.cli', 'config', '--validate'),
        @('-m', 'pip_audit')
    )
    foreach ($arguments in $checks) {
        & $python @arguments
        if ($LASTEXITCODE -ne 0) { throw "Python check failed: $arguments" }
    }
    foreach ($file in @(git ls-files '*.ps1') + @('run-validation.ps1')) {
        $tokens = $null
        $parseErrors = $null
        [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $file), [ref]$tokens, [ref]$parseErrors) | Out-Null
        if ($parseErrors) { throw "PowerShell parse failed: $file - $parseErrors" }
    }
    Push-Location frontend
    try {
        foreach ($arguments in @(@('ci'), @('run', 'validate'), @('run', 'build'), @('audit'))) {
            & npm @arguments
            if ($LASTEXITCODE -ne 0) { throw "Frontend check failed: $arguments" }
        }
        if ($Lighthouse) {
            npm run lighthouse
            if ($LASTEXITCODE -ne 0) { throw 'Lighthouse checks failed; see frontend/.lighthouse' }
        }
    } finally { Pop-Location }
} finally {
    $env:SPARK_BUILD_DIR = $previousBuildDir
    Pop-Location
}
