#!/usr/bin/env pwsh
# DevSpark - (c) 2026 Make Bold Solutions. Source: https://dev.makeboldspark.com
#requires -Version 7.0
# Unified branch-creation entry point.
# Work branches establish a safe delivery branch without scaffolding a specification.
[CmdletBinding(PositionalBinding = $false)]
param(
    [string]$Type,
    [string]$ShortName,
    [int]$Number = 0,
    [switch]$Json,
    [switch]$DryRun,
    [switch]$Yes,
    [switch]$Help,
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$Description
)

$ErrorActionPreference = 'Stop'

# Prompts, warnings, and progress go to stderr so stdout carries only JSON.
function Write-Err { param([string]$Message) [Console]::Error.WriteLine($Message) }

# Exit-code table: 0 ok | 1 usage/type | 2 collision | 3 empty slug
function Exit-WithError { param([string]$Message, [int]$Code) Write-Err "[new-branch] $Message"; exit $Code }

if ($Help) {
    Write-Err "Usage: ./new-branch.ps1 -Type <fix|work> [-ShortName <slug>] [-Number N] [-Json] [-DryRun] [-Yes] <description>"
    exit 0
}

. "$PSScriptRoot/common.ps1"

# Branch type is required and explicit (II. Explicit Over Implied). New work never scaffolds a
# full-spec or quick-spec bundle; existing bundles continue on their own branches.
$validTypes = @('fix', 'work')
if (-not $Type -or $validTypes -notcontains $Type.ToLower()) {
    Exit-WithError "type must be one of: fix, work" 1
}
$Type = $Type.ToLower()

$descText = (($Description | Where-Object { $_ }) -join ' ').Trim()
if (-not $ShortName -and -not $descText) {
    Exit-WithError "a description or -ShortName is required" 1
}

# Use the shared normalizer; derive the slug from ShortName or description.
if ($ShortName) {
    $slug = ConvertTo-CleanBranchName -Name $ShortName
} else {
    $slug = ConvertTo-CleanBranchName -Name $descText
    $parts = @($slug -split '-' | Where-Object { $_ } | Select-Object -First 4)
    $slug = ($parts -join '-')
}
if (-not $slug) { Exit-WithError "description did not yield a usable short name" 3 }

$repoRoot = Get-RepoRoot
$hasGit = Test-HasGit
if ($Type -eq 'work' -and -not $hasGit) {
    Exit-WithError "work branches require a Git repository" 1
}

# Derive the global index unless -Number overrides it.
if ($Number -le 0) { $Number = Get-NextUnifiedIndex } 

# Guard against index collisions.
if (Test-IndexCollision -Number $Number -RepoRoot $repoRoot) {
    Exit-WithError "index $('{0:000}' -f $Number) is already in use by an existing branch or spec directory - recompute" 2
}

$featureNum = ('{0:000}' -f $Number)
$branchName = "$featureNum-$Type-$slug"

# 244-byte git/GitHub branch limit.
if ($branchName.Length -gt 244) {
    $keep = 244 - ($featureNum.Length + $Type.Length + 2)
    $slug = ($slug.Substring(0, [Math]::Min($slug.Length, $keep)) -replace '-$', '')
    $branchName = "$featureNum-$Type-$slug"
    Write-Err "[new-branch] branch name truncated to 244 bytes: $branchName"
}

# The composed name must be a valid Git ref.
if ($hasGit) {
    git check-ref-format --branch $branchName *> $null
    if ($LASTEXITCODE -ne 0) { Exit-WithError "composed branch name is not a valid git ref: $branchName" 1 }
}

# Resolve artifact destination by type .
$specsDir = Join-Path $repoRoot '.devspark.work/specs'
$qfDir = Join-Path $repoRoot '.devspark.work/quickfixes'
switch ($Type) {
    'fix'   { $artifactPath = Join-Path $qfDir "$branchName.md" }
    'work'  { $artifactPath = Join-Path (Join-Path $specsDir $branchName) 'work.md' }
}

$switched = $false

if ($DryRun) {
    $artifactPath = ''
} else {
    # Confirm branch safety before moving HEAD.
    if ($hasGit) {
        $current = Get-CurrentBranch
        $proceed = $Yes
        if (-not $proceed) {
            if ([Environment]::UserInteractive -and -not [Console]::IsInputRedirected) {
                Write-Err "[new-branch] Create and switch to '$branchName' from '$current'? (y/N)"
                $answer = [Console]::ReadLine()
                $proceed = ($answer -match '^(y|yes)$')
            } else {
                # Non-TTY without -Yes MUST fail closed .
                Exit-WithError "refusing to switch branches without confirmation (pass -Yes in non-interactive use)" 1
            }
        }
        if (-not $proceed) { Exit-WithError "aborted by user; no branch created" 1 }

        # Create offline with bounded recompute and retry.
        $attempt = 0
        while ($true) {
            git checkout -b $branchName *> $null
            if ($LASTEXITCODE -eq 0) { $switched = $true; break }
            $attempt++
            if ($attempt -ge 3) { Exit-WithError "failed to create branch '$branchName' after $attempt attempts (it may already exist)" 2 }
            # Recompute in case a colliding branch appeared (race / stale fetch).
            $Number = Get-NextUnifiedIndex
            $featureNum = ('{0:000}' -f $Number)
            $branchName = "$featureNum-$Type-$slug"
            if ($Type -eq 'fix') { $artifactPath = Join-Path $qfDir "$branchName.md" }
            else { $artifactPath = Join-Path (Join-Path $specsDir $branchName) 'work.md' }
            Write-Err "[new-branch] retrying with recomputed index: $branchName"
        }
    } else {
        Write-Err "[new-branch] git not detected; scaffolding artifact without a branch"
    }

    if ($Type -eq 'fix') {
        # Minimal quickfix record with the year as metadata; a work branch scaffolds nothing.
        New-Item -ItemType Directory -Path (Split-Path $artifactPath -Parent) -Force | Out-Null
        $year = (Get-Date).Year
        "# Quickfix: $slug`n`n**Created**: $((Get-Date).ToString('yyyy-MM-dd')) - **Branch**: ``$branchName`` - **Year**: $year`n" | Set-Content -Path $artifactPath -Encoding utf8
    }
    if ($hasGit) { $env:DEVSPARK_FEATURE = $branchName }
}

# Emit the JSON contract to stdout only.
$result = [PSCustomObject]@{
    BRANCH_NAME   = $branchName
    NUMBER        = $featureNum
    TYPE          = $Type
    ARTIFACT_PATH = $artifactPath
    HAS_GIT       = $hasGit
    SWITCHED      = $switched
}
if ($Json) {
    $result | ConvertTo-Json -Compress
} else {
    Write-Output "BRANCH_NAME: $branchName"
    Write-Output "NUMBER: $featureNum"
    Write-Output "TYPE: $Type"
    Write-Output "ARTIFACT_PATH: $artifactPath"
    Write-Output "SWITCHED: $switched"
}
