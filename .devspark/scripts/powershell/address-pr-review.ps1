#!/usr/bin/env pwsh
# DevSpark - (c) 2026 Make Bold Solutions. Source: https://dev.makeboldspark.com
#requires -Version 7.0
# Helper script for /devspark.address-pr-review
# -PrId: parse review file and emit open findings JSON
# -Gate: enforce staged-path isolation for code-only or review-only commits

param(
    [Parameter()]
    [string]$PrId,

    [Parameter()]
    [ValidateSet('code-only', 'review-only')]
    [string]$Gate,

    [Parameter()]
    [switch]$Json
)

$ErrorActionPreference = 'Stop'

if (-not (Get-Command Get-RepoRoot -ErrorAction SilentlyContinue)) {
    . (Join-Path $PSScriptRoot 'common.ps1')
}

function Get-StagedPaths {
    try {
        $paths = @(git diff --cached --name-only 2>$null | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
        return $paths
    }
    catch {
        return @()
    }
}

function Test-IsReviewPath {
    param([string]$Path)
    return $Path -match '^\.devspark.work/pr-review/pr-.*\.md$'
}

function Write-GateFailure {
    param(
        [string]$Message,
        [string[]]$OffendingPaths
    )

    Write-Error "DevSpark: $Message"
    if ($OffendingPaths.Count -gt 0) {
        Write-Error "Offending staged paths:"
        foreach ($item in $OffendingPaths) {
            Write-Error "  - $item"
        }
    }
    exit 1
}

if ($Gate) {
    $staged = Get-StagedPaths

    if ($Gate -eq 'code-only') {
        $reviewStaged = @($staged | Where-Object { Test-IsReviewPath $_ })
        if ($reviewStaged.Count -gt 0) {
            Write-GateFailure -Message 'Code commit gate failed. Review files must not be staged for code-only commits.' -OffendingPaths $reviewStaged
        }
    }

    if ($Gate -eq 'review-only') {
        $nonReviewStaged = @($staged | Where-Object { -not (Test-IsReviewPath $_) })
        if ($nonReviewStaged.Count -gt 0) {
            Write-GateFailure -Message 'Review commit gate failed. Only PR review markdown files may be staged.' -OffendingPaths $nonReviewStaged
        }
    }

    if (-not $Json) {
        Write-Output "Gate '$Gate' passed."
    }
    exit 0
}

if (-not $PrId) {
    Write-Error 'DevSpark: Provide -PrId <N> or -Gate <code-only|review-only>.'
    exit 1
}

$normalizedPrId = ($PrId -replace '^#', '').Trim()
if ($normalizedPrId -notmatch '^\d+$') {
    Write-Error "DevSpark: Invalid PR id '$PrId'. Expected a positive integer."
    exit 1
}

$repoRoot = Get-RepoRoot
$reviewFile = Join-Path $repoRoot ".devspark.work/pr-review/pr-$normalizedPrId.md"

if (-not (Test-Path -LiteralPath $reviewFile)) {
    Write-Error "DevSpark: Review file not found: $reviewFile"
    exit 1
}

$stateEngine = Join-Path (Split-Path $PSScriptRoot -Parent) 'pr-review-state.py'
$pythonCommand = Get-Command python3, python -ErrorAction SilentlyContinue | Select-Object -First 1
$hasModernState = Select-String -LiteralPath $reviewFile -Pattern '^review_state\s*:' -Quiet
$pythonReady = $false
if ($pythonCommand) {
    $probeOutput = & $pythonCommand.Source -c 'import yaml' 2>&1
    $probeExit = $LASTEXITCODE
    if ($probeExit -eq 0) {
        $pythonReady = $true
    } elseif (($probeOutput -join "`n") -match "No module named ['`"]yaml['`"]") {
        if ($hasModernState) {
            @{ ok = $false; issues = @(@{ code = 'missing-prerequisite'; message = 'Structured review inspection requires Python with PyYAML.'; location = 'review_state'; recovery = 'Install or select the existing Python/PyYAML runtime, then retry.' }) } |
                ConvertTo-Json -Depth 5 -Compress
            exit 1
        }
    } else {
        Write-Error "DevSpark: Python inspection prerequisite check failed: $($probeOutput -join ' ')"
        exit 1
    }
}
elseif ($hasModernState) {
    @{ ok = $false; issues = @(@{ code = 'missing-prerequisite'; message = 'Structured review inspection requires Python 3.11+ and PyYAML.'; location = 'review_state'; recovery = 'Install or select the existing Python/PyYAML runtime, then retry.' }) } |
        ConvertTo-Json -Depth 5 -Compress
    exit 1
}

if ($pythonReady) {
    $engineOutput = & $pythonCommand.Source $stateEngine inspect $reviewFile --pr-id ([int]$normalizedPrId) --json
    $engineExit = $LASTEXITCODE
    $engineOutput | Write-Output
    exit $engineExit
}

$lines = Get-Content -LiteralPath $reviewFile -Encoding utf8
$records = New-Object System.Collections.Generic.List[object]
$section = ''
$tableHeaders = $null
$inTable = $false
$fenced = $false
$idPattern = '(?:CON|PRD\d+|C|H|M|L)-\d{2,}'

function Get-LegacyBlockingClassification([string]$Section) {
    if ($Section -match '(?i)non-blocking|nonblocking|recommended improvement|suggestion|low priority improvement') {
        return 'false'
    }
    if ($Section -match '(?i)blocking|immediate action') { return 'true' }
    return ''
}

for ($i = 0; $i -lt $lines.Count; $i++) {
    $line = $lines[$i]
    if ($line.TrimStart().StartsWith('```')) {
        $fenced = -not $fenced
        continue
    }
    if ($fenced) { continue }
    if ($line -match '^#+\s+(.*)$') {
        $section = $Matches[1]
        $tableHeaders = $null
        $inTable = $false
        continue
    }
    $action = [regex]::Match($line, '^\s*-\s*\[(?<checked>[ xX])\]\s+\*\*(?<label>[^*]+)\*\*\s*(?<rest>.*)$')
    if ($action.Success) {
        $idMatches = [regex]::Matches($action.Groups['label'].Value, $idPattern)
        if ($idMatches.Count -eq 0) {
            @{ ok = $false; issues = @(@{ code = 'malformed-finding'; message = 'Finding-like action has no supported identifier.'; location = "line $($i + 1)"; recovery = 'Correct the identifier or resolve the unsupported entry.' }) } |
                ConvertTo-Json -Depth 5 -Compress
            exit 1
        }
        $ids = @($idMatches | ForEach-Object { $_.Value.ToUpperInvariant() })
        $sectionBlocking = Get-LegacyBlockingClassification $section
        $labelParts = $action.Groups['label'].Value -split '\s*/\s*'
        if ($labelParts.Count -gt 1 -and $ids.Count -ne $labelParts.Count) {
            @{ ok = $false; issues = @(@{ code = 'malformed-finding'; message = 'Combined finding identifier is malformed.'; location = "line $($i + 1)"; recovery = 'Correct the explicit alias pair or resolve the entry manually.' }) } |
                ConvertTo-Json -Depth 5 -Compress
            exit 1
        }
        $records.Add([pscustomobject]@{
            id = $ids[0]; aliases = @($ids | Select-Object -Skip 1)
            checked = $action.Groups['checked'].Value.Trim() -ne ''
            status = if ($action.Groups['checked'].Value.Trim()) { 'resolved' } else { 'open' }
            description = $action.Groups['rest'].Value.Trim(); evidence = @(); blocking = $sectionBlocking
            expected = ''; section = $section; line = $line.Trim(); line_number = $i + 1
            source = 'action'; basis = if ($action.Groups['checked'].Value.Trim()) { 'checked action item' } else { 'unchecked action item' }
        })
    }
    if ($line.TrimStart().StartsWith('|')) {
        $cells = @($line.Trim().Trim('|').Split('|') | ForEach-Object { $_.Trim() })
        if ($null -eq $tableHeaders -and $cells.Count -gt 0 -and $cells[0].ToLowerInvariant() -in @('id', 'finding', 'finding id')) {
            $tableHeaders = @($cells | ForEach-Object { $_.ToLowerInvariant() })
            $inTable = $true
            continue
        }
        if ($line -match '^\s*\|(?:\s*:?-{2,}:?\s*\|)+\s*$') { continue }
        if ($inTable -and $tableHeaders -and $cells.Count -ge 2) {
            $idMatches = [regex]::Matches($cells[0], $idPattern)
            if ($idMatches.Count -gt 0) {
                $ids = @($idMatches | ForEach-Object { $_.Value.ToUpperInvariant() })
                $values = @{}
                for ($cellIndex = 0; $cellIndex -lt [Math]::Min($tableHeaders.Count, $cells.Count); $cellIndex++) {
                    $values[$tableHeaders[$cellIndex]] = $cells[$cellIndex]
                }
                $statusCell = [string]$values['status']
                $description = [string]$values['issue']
                if (-not $description) { $description = [string]$values['description'] }
                $expected = [string]$values['fix']
                if (-not $expected) { $expected = [string]$values['action'] }
                $evidence = @()
                foreach ($key in @('principle', 'file:line', 'file')) {
                    if ($values[$key]) { $evidence += [string]$values[$key] }
                }
                $closed = $statusCell -match '(?i)resolved|closed|withdrawn|legacy\s+resolved'
                $sectionBlocking = Get-LegacyBlockingClassification $section
                $records.Add([pscustomobject]@{
                    id = $ids[0]; aliases = @($ids | Select-Object -Skip 1)
                    checked = $false; status = if ($closed) { 'resolved' } else { 'open' }
                    description = $description; expected = $expected; evidence = $evidence; section = $section
                    blocking = $sectionBlocking
                    line = $line.Trim(); line_number = $i + 1; source = 'table'
                    basis = if ($statusCell) { $statusCell } else { 'detail table' }
                })
            }
        }
    } elseif ($inTable -and $line.Trim()) {
        $tableHeaders = $null
        $inTable = $false
    }
}

$byId = [ordered]@{}
$aliasOwners = @{}
foreach ($record in $records) {
    foreach ($alias in $record.aliases) {
        if ($aliasOwners.ContainsKey($alias) -and $aliasOwners[$alias] -ne $record.id) {
            @{ ok = $false; issues = @(@{ code = 'alias-conflict'; message = "Alias $alias belongs to multiple findings."; location = "line $($record.line_number)"; recovery = 'Choose the canonical finding that owns this alias.' }) } |
                ConvertTo-Json -Depth 5 -Compress
            exit 1
        }
        $aliasOwners[$alias] = $record.id
    }
    if (-not $byId.Contains($record.id)) {
        $byId[$record.id] = $record
        continue
    }
    $prior = $byId[$record.id]
    if ($prior.status -ne $record.status) {
        @{ ok = $false; issues = @(@{ code = 'contradictory-legacy-status'; message = "Finding $($record.id) has conflicting action/table status."; location = "line $($record.line_number)"; recovery = 'Resolve the conflicting legacy status without inferring closure.' }) } |
            ConvertTo-Json -Depth 5 -Compress
        exit 1
    }
    if ($prior.blocking -and $record.blocking -and $prior.blocking -ne $record.blocking) {
        @{ ok = $false; issues = @(@{ code = 'contradictory-legacy-blocking'; message = "Finding $($record.id) has conflicting blocking classifications."; location = "line $($record.line_number)"; recovery = 'Use Python recover-legacy with an authorized, evidence-based interpretation.' }) } |
            ConvertTo-Json -Depth 5 -Compress
        exit 1
    }
    if (-not $prior.blocking -and $record.blocking) { $prior.blocking = $record.blocking }
    if ($record.aliases.Count -gt 0) { $prior.aliases = $record.aliases }
    if ($record.description.Length -gt $prior.description.Length) { $prior.description = $record.description }
    if ($record.expected) { $prior.expected = $record.expected }
    if ($record.evidence.Count -gt 0) { $prior.evidence = $record.evidence }
    if ($record.source -eq 'table' -and $record.status -eq 'resolved') { $prior.basis = $record.basis }
}

$normalizedFindings = New-Object System.Collections.Generic.List[object]
$openFindings = New-Object System.Collections.Generic.List[object]
foreach ($record in $byId.Values) {
    $prefix = $record.id.Split('-')[0]
    $severityCode = if ($prefix -like 'PRD*') { 'PRD' } else { $prefix }
    $severityLevel = switch ($severityCode) {
        'C' { 'critical' } 'H' { 'high' } 'M' { 'medium' } 'L' { 'low' }
        default { 'medium' }
    }
    $category = if ($prefix -like 'PRD*') { $prefix } elseif ($prefix -eq 'CON') { 'constitution' } else { $null }
    if (-not $record.blocking) {
        @{ ok = $false; issues = @(@{ code = 'ambiguous-legacy-blocking'; message = "Finding $($record.id) has no explicit blocking classification."; location = "line $($record.line_number)"; recovery = 'Install Python/PyYAML and use recover-legacy with a complete interpretation and named authorized reviewer.' }) } |
            ConvertTo-Json -Depth 5 -Compress
        exit 1
    }
    $blocking = $record.blocking -eq 'true'
    $status = if ($record.status -eq 'resolved') { 'closed' } else { 'open' }
    $constitutionFinding = $severityCode -eq 'CON'
    $legacyNonauto = $record.description -match '(?i)accepted|deferred|waived|withdrawn|wontfix|won''t fix|already fixed upstream'
    $eligible = $status -eq 'open' -and $blocking -and
        ($severityLevel -in @('critical', 'high') -or $severityCode -eq 'PRD') -and
        -not $constitutionFinding -and -not $legacyNonauto
    $route = if ($constitutionFinding) { 'evolve-constitution' } elseif ($eligible) { 'auto' } else { 'report' }
    $reason = if ($constitutionFinding) { 'Constitution findings route to /devspark-evolve-constitution, not to product code.' }
        elseif ($status -ne 'open') { "Status is $status; a human decides whether it still needs work." }
        elseif ($legacyNonauto) { 'The legacy report records an accepted, deferred or withdrawn disposition.' }
        elseif ($eligible -and $severityLevel -in @('critical', 'high')) { "Open $($severityLevel.Substring(0,1).ToUpperInvariant()) finding." }
        elseif ($eligible) { 'Open blocking PR-delta finding.' }
        else { 'Ordinary Medium or Low findings are report-only.' }
    $finding = [pscustomobject]@{
        finding_id = $record.id; aliases = @($record.aliases); severity = $severityLevel
        category = $category; blocking = [bool]$blocking; description = $record.description
        expected_outcome = $record.expected; evidence = @($record.evidence); recommended_action = $record.expected
        execution_mode = 'manual'; status = $record.status
        outcome = if ($record.status -eq 'resolved') { 'Legacy resolved' } else { '' }
        provenance = @{ kind = 'legacy'; location = "line $($record.line_number)"; section = $record.section; line = $record.line; basis = $record.basis }
        remediation = $null; verification = $null; disposition = $null; reopen_reason = $null
    }
    $normalizedFindings.Add($finding)
    if ($record.status -ne 'resolved') {
        $openFindings.Add([pscustomobject]@{
            id = $record.id; severity = $severityCode; severity_level = $severityLevel
            category = $category; aliases = @($record.aliases); line_number = $record.line_number
            line = $record.line; section = $record.section; status = $status
            lifecycle_state = $record.status; blocking = [bool]$blocking; auto_eligible = [bool]$eligible
            route = $route; reason = $reason
        })
    }
}

$pending = @()
$blockerCount = @($openFindings | Where-Object { $_.blocking }).Count
$autoCount = @($openFindings | Where-Object { $_.auto_eligible }).Count
$result = [PSCustomObject]@{
    ok = $true; pr_id = [int]$normalizedPrId; review_file = $reviewFile
    record = @{ format_version = 1; findings = $normalizedFindings; conditions = @(); last_change = @{ operation = 'legacy-read' } }
    findings = $normalizedFindings; open_findings = $openFindings; open_count = $openFindings.Count
    auto_eligible_count = $autoCount; historical_count = $normalizedFindings.Count
    pending_verification = $pending; pending_verification_count = 0
    unresolved_blockers = $blockerCount
    recommendation = if ($blockerCount -gt 0) { 'request-changes' } else { 'approve' }
    diagnostics = @()
}

if ($Json) {
    $result | ConvertTo-Json -Depth 10
}
else {
    Write-Output "Review file: $reviewFile"
    Write-Output "Open findings: $($openFindings.Count)"
    Write-Output "Auto-eligible findings: $autoCount"
    foreach ($finding in $openFindings) {
        Write-Output "- $($finding.id) [$($finding.route)]"
    }
}
