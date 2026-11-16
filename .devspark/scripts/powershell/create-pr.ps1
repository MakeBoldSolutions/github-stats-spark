#!/usr/bin/env pwsh
# DevSpark - (c) 2026 Make Bold Solutions. Source: https://dev.makeboldspark.com
#requires -Version 7.0
[CmdletBinding()]
param(
    [ValidateSet('Preflight','Create','Update')]
    [string]$Mode = 'Preflight',
    [switch]$Json,
    [string]$Title,
    [string]$Body,
    [string]$BodyFile,
    [string]$Base,
    [int]$PrNumber,
    [switch]$Draft,
    [string[]]$Reviewer = @(),
    [string[]]$Label = @(),
    [string[]]$Assignee = @(),
    [string[]]$Issue = @()
)

$ErrorActionPreference = 'Stop'

. "$PSScriptRoot/common.ps1"
. "$PSScriptRoot/platform.ps1"

function Get-JsonError {
    param([string]$Message, [string]$Details = '')
    [PSCustomObject]@{
        error = $true
        message = $Message
        details = $Details
    } | ConvertTo-Json -Depth 10
}

function Get-DefaultBaseBranch {
    if ($DevSparkPlatform.Name -eq 'github' -and (Get-Command gh -ErrorAction SilentlyContinue)) {
        try {
            if (& $DevSparkPlatform.AuthCheck) {
                $branch = gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name' 2>$null
                if ($branch) { return $branch }
            }
        } catch { }
    }
    try {
        $symbolic = git symbolic-ref refs/remotes/origin/HEAD 2>$null
        if ($symbolic) { return ($symbolic -replace '^refs/remotes/origin/', '') }
    } catch { }
    return 'main'
}

function Resolve-PrBody {
    $bodyValue = $Body
    if ($BodyFile -and (Test-Path $BodyFile)) {
        $bodyValue = Get-Content -LiteralPath $BodyFile -Raw -Encoding utf8
    }
    if ($Issue.Count -gt 0) {
        $issueLine = 'Refs: ' + ($Issue -join ', ')
        if ($bodyValue) { $bodyValue += [Environment]::NewLine + [Environment]::NewLine }
        $bodyValue += $issueLine
    }
    return $bodyValue
}

function Get-MarkdownSectionText {
    param(
        [string]$Path,
        [string]$SectionName
    )

    if (-not (Test-Path $Path)) {
        return ''
    }

    $content = Get-Content -LiteralPath $Path -Encoding utf8
    $capture = $false
    $lines = New-Object System.Collections.Generic.List[string]
    foreach ($line in $content) {
        $sectionMatch = [regex]::Match($line, '^##\s+(.+)$')
        if ($sectionMatch.Success) {
            $heading = $sectionMatch.Groups[1].Value.Trim()
            if ($capture -and $heading -ne $SectionName) {
                break
            }
            $capture = $heading -eq $SectionName
            continue
        }
        if ($capture) {
            $lines.Add($line)
        }
    }

    return (($lines -join [Environment]::NewLine).Trim())
}

function Get-GateAcknowledgements {
    param([string]$TasksPath)

    if (-not (Test-Path $TasksPath)) {
        return @()
    }

    $section = Get-MarkdownSectionText -Path $TasksPath -SectionName 'Gate Acknowledgements'
    if (-not $section) {
        return @()
    }

    $entries = New-Object System.Collections.Generic.List[string]
    $current = New-Object System.Collections.Generic.List[string]
    foreach ($line in ($section -split "`r?`n")) {
        $trimmed = $line.Trim()
        if (-not $trimmed) {
            if ($current.Count -gt 0) {
                $entries.Add(($current -join [Environment]::NewLine).Trim())
                $current.Clear()
            }
            continue
        }
        if ($trimmed.StartsWith('- Gate:') -and $current.Count -gt 0) {
            $entries.Add(($current -join [Environment]::NewLine).Trim())
            $current.Clear()
        }
        $current.Add($trimmed)
    }
    if ($current.Count -gt 0) {
        $entries.Add(($current -join [Environment]::NewLine).Trim())
    }
    return @($entries)
}

function Find-QuickfixRecordForBranch {
    param(
        [string]$RepoRoot,
        [string]$BranchName
    )

    $quickfixDir = Join-Path $RepoRoot '.devspark.work/quickfixes'
    if (-not (Test-Path $quickfixDir)) {
        return $null
    }

    $quickfixFiles = Get-ChildItem -Path $quickfixDir -Filter *.md -File -ErrorAction SilentlyContinue |
        Where-Object {
            $content = Get-Content -LiteralPath $_.FullName -Encoding utf8
            $branchLine = $content | Where-Object { $_ -match '^- \*\*Branch\*\*:\s*(.+)$' } | Select-Object -First 1
            $branchLine -and (($branchLine -replace '^- \*\*Branch\*\*:\s*', '').Trim() -eq $BranchName)
        } |
        Sort-Object Name

    if ($quickfixFiles) {
        return ($quickfixFiles | Select-Object -Last 1).FullName
    }
    return $null
}

function Get-QuickfixRecordSummary {
    param([string]$QuickfixPath)

    if (-not $QuickfixPath -or -not (Test-Path $QuickfixPath)) {
        return $null
    }

    $heading = Get-Content -LiteralPath $QuickfixPath -Encoding utf8 | Where-Object { $_ -match '^# ' } | Select-Object -First 1
    $idLine = Get-Content -LiteralPath $QuickfixPath -Encoding utf8 | Where-Object { $_ -match '^- \*\*ID\*\*:\s*(.+)$' } | Select-Object -First 1
    return [PSCustomObject]@{
        path = $QuickfixPath
        id = if ($idLine) { ($idLine -replace '^- \*\*ID\*\*:\s*', '').Trim() } else { [IO.Path]::GetFileNameWithoutExtension($QuickfixPath) }
        title = if ($heading) { $heading -replace '^#\s*', '' } else { '' }
        classification = Get-MarkdownFrontmatterValue -Path $QuickfixPath -Key 'classification'
        risk_level = Get-MarkdownFrontmatterValue -Path $QuickfixPath -Key 'risk_level'
        required_gates = Get-MarkdownFrontmatterValue -Path $QuickfixPath -Key 'required_gates'
        recommended_next_step = Get-MarkdownFrontmatterValue -Path $QuickfixPath -Key 'recommended_next_step'
        problem_statement = Get-MarkdownSectionText -Path $QuickfixPath -SectionName 'Problem Statement'
        gate_acknowledgements = Get-MarkdownSectionText -Path $QuickfixPath -SectionName 'Gate Acknowledgements'
    }
}

function Get-TaskCounts {
    param([string]$TasksPath)
    if (-not (Test-Path $TasksPath)) {
        return [PSCustomObject]@{ total = 0; completed = 0; incomplete = 0 }
    }
    $content = Get-Content -LiteralPath $TasksPath -Encoding utf8
    $taskLines = @($content | Where-Object { $_ -match '^\s*- \[([ xX])\]' })
    $completedLines = @($content | Where-Object { $_ -match '^\s*- \[[xX]\]' })
    return [PSCustomObject]@{
        total = $taskLines.Count
        completed = $completedLines.Count
        incomplete = $taskLines.Count - $completedLines.Count
    }
}

function Get-ChecklistSummary {
    param([string]$ChecklistDir)
    if (-not (Test-Path $ChecklistDir)) {
        return @()
    }
    $results = @()
    Get-ChildItem -Path $ChecklistDir -Filter *.md -File -ErrorAction SilentlyContinue | ForEach-Object {
        $content = Get-Content -LiteralPath $_.FullName -Encoding utf8
        $taskLines = @($content | Where-Object { $_ -match '^\s*- \[([ xX])\]' })
        $completed = @($content | Where-Object { $_ -match '^\s*- \[[xX]\]' })
        $results += [PSCustomObject]@{
            name = $_.Name
            total = $taskLines.Count
            completed = $completed.Count
            incomplete = $taskLines.Count - $completed.Count
            status = if (($taskLines.Count - $completed.Count) -eq 0) { 'pass' } else { 'fail' }
        }
    }
    return $results
}

function Get-GateArtifacts {
    param([string]$FeatureDir)
    $results = @()
    foreach ($gate in @('analyze','critic','checklist')) {
        $candidatePaths = @(
            (Join-Path $FeatureDir "gates/$gate.md"),
            (Join-Path $FeatureDir "$gate.md")
        )
        $path = $candidatePaths | Where-Object { Test-Path $_ } | Select-Object -First 1
        if ($path) {
            $content = Get-Content -LiteralPath $path -Encoding utf8
            $status = (($content | Where-Object { $_ -match '^status:\s*' } | Select-Object -First 1) -replace '^status:\s*', '')
            $blockingRaw = (($content | Where-Object { $_ -match '^blocking:\s*' } | Select-Object -First 1) -replace '^blocking:\s*', '')
            $severity = (($content | Where-Object { $_ -match '^severity:\s*' } | Select-Object -First 1) -replace '^severity:\s*', '')
            $summary = (($content | Where-Object { $_ -match '^summary:\s*' } | Select-Object -First 1) -replace '^summary:\s*', '')
            $results += [PSCustomObject]@{
                gate = $gate
                path = $path
                status = if ($status) { $status } else { 'unknown' }
                severity = if ($severity) { $severity } else { 'info' }
                summary = $summary
                blocking = ($blockingRaw -eq 'true')
            }
        }
    }
    return $results
}

# The engine needs PyYAML and Python 3.11+, so an interpreter that cannot run it is "unavailable",
# never a reason to report the Knowledge as broken.
function Resolve-KnowledgePython {
    foreach ($name in @('python3', 'python')) {
        $command = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $command) { continue }
        & $command.Source -c 'import sys, yaml; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { return $command.Source }
    }
    return $null
}

function New-KnowledgeBlocker {
    param([string]$Kind, $Path, $Message)
    [PSCustomObject]@{
        kind = $Kind
        path = $Path
        message = $Message
    }
}

function New-KnowledgeResult {
    param(
        [string]$Readiness,
        [string]$Summary,
        [string]$Head,
        [object[]]$Blockers = @(),
        [string]$CheckOutput
    )
    [PSCustomObject]@{
        gap_summary = if ($Summary) { $Summary } else { $null }
        readiness = $Readiness
        blockers = @($Blockers)
        checked_head = $Head
        check_output = if ($CheckOutput) { $CheckOutput } else { $null }
    }
}

# Read-only: proves the Knowledge at the committed HEAD still builds. It never regenerates,
# edits, or commits anything, and it does not compare generated files or `last_verified` dates.
function Get-KnowledgeConsistency {
    param([string]$RepoRoot, [string]$Head)

    $engine = Resolve-KnowledgeEngine -RepoRoot $RepoRoot
    if (-not $engine) {
        return New-KnowledgeResult -Readiness 'unknown' -Summary 'build_knowledge_index.py not found' -Head $Head
    }

    $tracked = @(git -C $RepoRoot ls-tree -r --name-only HEAD -- .knowledge 2>$null | Where-Object { $_ })
    if ($tracked.Count -eq 0) {
        return New-KnowledgeResult -Readiness 'not-applicable' -Summary 'no .knowledge content is tracked at HEAD' -Head $Head
    }

    $python = Resolve-KnowledgePython
    if (-not $python) {
        return New-KnowledgeResult -Readiness 'unknown' -Summary 'no usable Python interpreter (python3 or python with PyYAML, 3.11+) found' -Head $Head
    }

    $output = & $python $engine --repo-root $RepoRoot --check 2>&1
    $exitCode = $LASTEXITCODE
    $lines = @($output | ForEach-Object { "$_".TrimEnd() } | Where-Object { $_ })
    $text = $lines -join "`n"

    if ($exitCode -eq 0) {
        return New-KnowledgeResult -Readiness 'ready' -Head $Head -CheckOutput $text
    }

    if ($exitCode -eq 1) {
        $summary = if ($lines.Count -gt 0) { $lines[0] } else { 'knowledge check failed' }
        $blockers = @(New-KnowledgeBlocker -Kind 'build-error' -Path $null -Message $lines[-1])
        return New-KnowledgeResult -Readiness 'blocked' -Summary $summary -Head $Head -Blockers $blockers -CheckOutput $text
    }

    return New-KnowledgeResult -Readiness 'unknown' -Summary "knowledge engine returned an unsupported result (exit $exitCode)" -Head $Head -CheckOutput $text
}

function Get-KnowledgeBlockedError {
    param($Preflight)

    $knowledge = $Preflight.knowledge
    $dash = [string][char]0x2014
    $engineRelative = if (Test-Path (Join-Path $Preflight.repo_root '.devspark/scripts/build_knowledge_index.py')) { '.devspark/scripts/build_knowledge_index.py' } else { 'scripts/build_knowledge_index.py' }
    $message = "CREATE PR BLOCKED $dash KNOWLEDGE CANNOT BE BUILT"
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("Committed HEAD: $($knowledge.checked_head)")
    $lines.Add('Knowledge: BUILD ERROR')
    foreach ($blocker in @($knowledge.blockers)) { $lines.Add("Error: $($blocker.message)") }
    $lines.Add('Required action:')
    $lines.Add('1. Fix the reported source or frontmatter problem.')
    $lines.Add("2. Confirm it builds: python $engineRelative --repo-root . --check")
    $lines.Add('3. Commit the .knowledge/** changes.')
    $lines.Add('4. Push.')
    $lines.Add('5. Rerun /devspark-create-pr.')

    [PSCustomObject]@{
        error = $true
        message = $message
        details = ($lines -join "`n")
        checked_head = $knowledge.checked_head
        blockers = @($knowledge.blockers)
    } | ConvertTo-Json -Depth 10 -EscapeHandling EscapeNonAscii
}

# Reports DevSpark's own lifecycle check (judge.py lifecycle) for the branch's work directory, the
# same check /devspark-next and /devspark-implement use. It only reads; the rules live in judge.py.
# When the check cannot run, the result says why and whether work.md declares mandatory obligations,
# because an obligation that could not be evaluated must never read as one that passed.
function Get-LifecycleReadiness {
    param([string]$FeatureDir)

    $result = { param($Status, $Failures = @(), $Pending = @()) [PSCustomObject]@{ status = $Status; failures = @($Failures); pending_later_phase = @($Pending) } }
    if (-not $FeatureDir -or -not (Test-Path -LiteralPath $FeatureDir -PathType Container)) {
        return & $result 'not-applicable'
    }
    $unavailable = {
        param($Reason)
        $workMd = Join-Path $FeatureDir 'work.md'
        $declared = (Test-Path -LiteralPath $workMd -PathType Leaf) -and
            ((Get-Content -LiteralPath $workMd -Raw -ErrorAction SilentlyContinue) -match '(?im)^##[ \t]+Required Obligations[ \t]*\r?$')
        [PSCustomObject]@{ status = 'unavailable'; reason = $Reason; obligations_declared = [bool]$declared; failures = @(); pending_later_phase = @() }
    }
    $judge = Join-Path $PSScriptRoot '../judge.py'
    if (-not (Test-Path -LiteralPath $judge)) {
        return & $unavailable 'judge-missing'
    }
    $python = Resolve-KnowledgePython
    if (-not $python) {
        return & $unavailable 'python-unavailable'
    }
    try {
        $parsed = ((& $python $judge lifecycle --feature-dir $FeatureDir 2>$null) -join "`n") | ConvertFrom-Json
    } catch {
        return & $unavailable 'invalid-output'
    }
    if (-not $parsed -or $parsed.status -notin @('pass', 'fail')) {
        return & $unavailable 'invalid-output'
    }
    return & $result ([string]$parsed.status) $parsed.failures $parsed.pending_later_phase
}

function Get-LifecycleUnavailableError {
    param($Preflight, [string]$FeatureName)

    $dash = [string][char]0x2014
    $reason = [string]$Preflight.lifecycle.reason
    $cause = switch ($reason) {
        'judge-missing' { 'DevSpark''s judge.py is not installed beside its scripts' }
        'python-unavailable' { 'no Python 3.11+ interpreter with PyYAML is available as python3 or python' }
        default { 'judge.py ran but did not return a lifecycle result' }
    }
    $fix = switch ($reason) {
        'judge-missing' { '1. Restore judge.py by reinstalling or upgrading the DevSpark scripts.' }
        'python-unavailable' { '1. Make Python 3.11+ with PyYAML available as python3 or python.' }
        default { "1. Run judge.py lifecycle --feature-dir .devspark.work/specs/$FeatureName to see the error, and fix it." }
    }
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("Committed HEAD: $($Preflight.remote.local_head)")
    $lines.Add("work.md declares Required Obligations, but DevSpark could not run its lifecycle check: $cause.")
    $lines.Add('An obligation that could not be evaluated is not an obligation that passed, so DevSpark will not publish this PR.')
    $lines.Add('Required action:')
    $lines.Add($fix)
    $lines.Add('2. Rerun /devspark-create-pr.')
    $lines.Add('DevSpark has no override for this. Where organizational policy authorizes a different approval path, follow that path outside DevSpark.')

    [PSCustomObject]@{
        error = $true
        message = "CREATE PR BLOCKED $dash LIFECYCLE CHECK UNAVAILABLE"
        details = ($lines -join "`n")
        reason = $reason
    } | ConvertTo-Json -Depth 10 -EscapeHandling EscapeNonAscii
}

function Get-ObligationBlockedError {
    param($Preflight)

    $failure = @($Preflight.lifecycle.failures | Where-Object { $_.code -eq 'required-obligation-unresolved' })[0]
    $dash = [string][char]0x2014
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("Committed HEAD: $($Preflight.remote.local_head)")
    $lines.Add("Obligation: $($failure.message)")
    $lines.Add('A mandatory obligation is not the developer''s to waive, and no flag or acknowledgement bypasses it.')
    $lines.Add('Required action:')
    $lines.Add('1. Obtain the satisfying evidence, or an explicit decision from the authority the obligation names.')
    $lines.Add('2. Check the entry under ## Required Obligations in work.md and add a reference to that evidence or decision (Evidence: followed by a repository path, commit, review or approval id, or link).')
    $lines.Add('3. Commit.')
    $lines.Add('4. Push.')
    $lines.Add('5. Rerun /devspark-create-pr.')

    [PSCustomObject]@{
        error = $true
        message = "CREATE PR BLOCKED $dash REQUIRED OBLIGATION UNRESOLVED"
        details = ($lines -join "`n")
        obligations = @($failure.obligations)
    } | ConvertTo-Json -Depth 10 -EscapeHandling EscapeNonAscii
}

function Get-CreatePrPreflight {
    $repoRoot = Get-RepoRoot
    $currentBranch = Get-CurrentBranch
    $targetBranch = if ($Base) { $Base } else { Get-DefaultBaseBranch }
    $dirty = [bool](git status --porcelain 2>$null)
    $localHead = ''
    $remoteHead = ''
    $originExists = $false
    $remoteBranchExists = $false
    $branchPushedToRemote = $false
    $branchPushDetails = ''

    try {
        $localHead = (git rev-parse HEAD 2>$null | Select-Object -First 1).Trim()
    } catch { }

    try {
        git remote get-url origin 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $originExists = $true
        }
    } catch { }

    if ($originExists) {
        try {
            $remoteLine = (git ls-remote --heads origin "refs/heads/$currentBranch" 2>$null | Select-Object -First 1)
            if ($remoteLine) {
                $remoteHead = (($remoteLine -split "`t")[0]).Trim()
                $remoteBranchExists = [bool]$remoteHead
            }
        } catch { }
    }

    if (-not $originExists) {
        $branchPushDetails = 'Remote ''origin'' is not configured'
    } elseif (-not $remoteBranchExists) {
        $branchPushDetails = "Branch '$currentBranch' has not been pushed to origin"
    } elseif ($localHead -and $remoteHead -and $localHead -eq $remoteHead) {
        $branchPushedToRemote = $true
        $branchPushDetails = "Branch '$currentBranch' is pushed to origin"
    } else {
        $branchPushDetails = "Push the latest commits from '$currentBranch' to origin before creating a PR"
    }

    $prCli = $DevSparkPlatform.PrCli
    $cliAvailable = [bool](Get-Command $prCli -ErrorAction SilentlyContinue)
    $authOk = $false
    if ($cliAvailable) {
        try { $authOk = & $DevSparkPlatform.AuthCheck } catch { $authOk = $false }
    }
    $creationSupported = $cliAvailable -and ($DevSparkPlatform.Name -in @('github', 'azdo'))

    $featureDir = Find-FeatureDirByPrefix -RepoRoot $repoRoot -BranchName $currentBranch
    $specPath = Join-Path $featureDir 'spec.md'
    $planPath = Join-Path $featureDir 'plan.md'
    $tasksPath = Join-Path $featureDir 'tasks.md'
    $checklistDir = Join-Path $featureDir 'checklists'

    $specExists = Test-Path $specPath
    $planExists = Test-Path $planPath
    $tasksExists = Test-Path $tasksPath

    $specTitle = ''
    $classification = ''
    $riskLevel = ''
    $requiredGates = ''
    $recommendedNextStep = ''
    if ($specExists) {
        $heading = Get-Content -LiteralPath $specPath -Encoding utf8 | Where-Object { $_ -match '^# ' } | Select-Object -First 1
        $specTitle = $heading -replace '^#\s*', ''
        $classification = Get-MarkdownFrontmatterValue -Path $specPath -Key 'classification'
        $riskLevel = Get-MarkdownFrontmatterValue -Path $specPath -Key 'risk_level'
        $requiredGates = Get-MarkdownFrontmatterValue -Path $specPath -Key 'required_gates'
        $recommendedNextStep = Get-MarkdownFrontmatterValue -Path $specPath -Key 'recommended_next_step'
    }

    $taskCounts = Get-TaskCounts -TasksPath $tasksPath
    $checklists = Get-ChecklistSummary -ChecklistDir $checklistDir
    $gateArtifacts = Get-GateArtifacts -FeatureDir $featureDir
    $gateAcknowledgements = Get-GateAcknowledgements -TasksPath $tasksPath
    $quickfixRecordPath = Find-QuickfixRecordForBranch -RepoRoot $repoRoot -BranchName $currentBranch
    $quickfixRecord = Get-QuickfixRecordSummary -QuickfixPath $quickfixRecordPath

    if (-not $specExists -and $quickfixRecord) {
        $specTitle = $quickfixRecord.title
        $classification = $quickfixRecord.classification
        $riskLevel = $quickfixRecord.risk_level
        $requiredGates = $quickfixRecord.required_gates
        $recommendedNextStep = $quickfixRecord.recommended_next_step
        if ($quickfixRecord.gate_acknowledgements) {
            $gateAcknowledgements = @($quickfixRecord.gate_acknowledgements.Trim())
        }
    }

    $diffRef = 'HEAD~1...HEAD'
    try {
        git rev-parse --verify "origin/$targetBranch" 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            git fetch origin $targetBranch 2>$null | Out-Null
            $diffRef = "origin/$targetBranch...HEAD"
        }
    } catch { }
    $linesSummary = (git diff --shortstat $diffRef 2>$null) -join ''
    $fileChanges = @(
        git diff --name-status $diffRef 2>$null |
        ForEach-Object {
            if ($_ -and $_ -match "`t") {
                $parts = $_ -split "`t"
                if ($parts.Count -ge 2) {
                    $st = $parts[0].Substring(0, 1)
                    if ($parts.Count -ge 3) {
                        [PSCustomObject]@{ status = $st; path = $parts[2].Trim(); from = $parts[1].Trim() }
                    } else {
                        [PSCustomObject]@{ status = $st; path = $parts[1].Trim() }
                    }
                }
            }
        } | Where-Object { $_ -ne $null }
    )
    $commitLog = @(
        git log --format="%H`u{001f}%s`u{001f}%an`u{001f}%ai" -n 20 $diffRef 2>$null |
        ForEach-Object {
            $parts = $_ -split "`u{001f}"
            if ($parts.Count -ge 4) {
                [PSCustomObject]@{
                    hash    = $parts[0].Trim()
                    subject = $parts[1].Trim()
                    author  = $parts[2].Trim()
                    date    = $parts[3].Trim()
                }
            }
        } | Where-Object { $_ -ne $null }
    )

    $knowledge = Get-KnowledgeConsistency -RepoRoot $repoRoot -Head $localHead
    $lifecycle = Get-LifecycleReadiness -FeatureDir $featureDir

    $existingPr = [PSCustomObject]@{ exists = $false; number = $null; url = ''; title = ''; state = ''; draft = $false }
    if ($cliAvailable -and $authOk) {
        try {
            if ($DevSparkPlatform.Name -eq 'azdo') {
                $azctx = Get-AzdoRepoContext
                $orgUrl = "https://dev.azure.com/$($azctx.Org)"
                $azList = az repos pr list --organization $orgUrl --project $azctx.Project --repository $azctx.Repo --source-branch $currentBranch --status active --top 1 --output json 2>$null | ConvertFrom-Json
                $pr = @($azList)[0]
                if ($pr -and $pr.pullRequestId) {
                    $existingPr = [PSCustomObject]@{
                        exists = $true
                        number = $pr.pullRequestId
                        url    = "https://dev.azure.com/$($azctx.Org)/$($azctx.Project)/_git/$($azctx.Repo)/pullrequest/$($pr.pullRequestId)"
                        title  = $pr.title
                        state  = $pr.status
                        draft  = [bool]$pr.isDraft
                    }
                }
            } else {
                $existingRaw = gh pr list --head $currentBranch --json number,url,title,state,isDraft --limit 1 2>$null | ConvertFrom-Json
                $pr = @($existingRaw)[0]
                if ($pr) {
                    $existingPr = [PSCustomObject]@{
                        exists = $true
                        number = $pr.number
                        url = $pr.url
                        title = $pr.title
                        state = $pr.state
                        draft = [bool]$pr.isDraft
                    }
                }
            }
        } catch { }
    }

    return [PSCustomObject]@{
        repo_root = $repoRoot
        current_branch = $currentBranch
        target_branch = $targetBranch
        dirty_worktree = $dirty
        prerequisites = [PSCustomObject]@{
            clean_worktree = (-not $dirty)
            branch_pushed_to_remote = $branchPushedToRemote
        }
        remote = [PSCustomObject]@{
            name = 'origin'
            exists = $originExists
            branch_exists = $remoteBranchExists
            branch_pushed_to_remote = $branchPushedToRemote
            local_head = $localHead
            remote_head = $remoteHead
            details = $branchPushDetails
        }
        cli_available = $cliAvailable
        auth_ok = $authOk
        creation_supported = $creationSupported
        feature = [PSCustomObject]@{
            dir = $featureDir
            spec_path = $specPath
            plan_path = $planPath
            tasks_path = $tasksPath
            checklist_dir = $checklistDir
            spec_exists = $specExists
            plan_exists = $planExists
            tasks_exists = $tasksExists
            spec_title = $specTitle
            classification = $classification
            risk_level = $riskLevel
            required_gates = $requiredGates
            recommended_next_step = $recommendedNextStep
            tasks_total = $taskCounts.total
            tasks_completed = $taskCounts.completed
            tasks_incomplete = $taskCounts.incomplete
            checklists = $checklists
            gate_artifacts = $gateArtifacts
            gate_acknowledgements = @($gateAcknowledgements)
        }
        diff = [PSCustomObject]@{
            changed_files_count = $fileChanges.Count
            lines_summary       = $linesSummary
            commit_log          = $commitLog
            file_changes        = $fileChanges
        }
        quickfix_record = $quickfixRecord
        knowledge = $knowledge
        lifecycle = $lifecycle
        existing_pr = $existingPr
    }
}

function Invoke-CreateOrUpdatePr {
    param([ValidateSet('Create','Update')][string]$Action)

    $preflight = Get-CreatePrPreflight
    if (-not $preflight.prerequisites.clean_worktree) {
        return (Get-JsonError -Message 'Working tree has unmanaged changes' -Details 'Commit, stash, or discard all changes before creating or updating a PR')
    }
    if ($preflight.knowledge.readiness -eq 'blocked') {
        return (Get-KnowledgeBlockedError -Preflight $preflight)
    }
    if (-not $preflight.prerequisites.branch_pushed_to_remote) {
        return (Get-JsonError -Message 'Current branch is not pushed to remote' -Details $preflight.remote.details)
    }
    if (@($preflight.lifecycle.failures | Where-Object { $_.code -eq 'required-obligation-unresolved' }).Count -gt 0) {
        return (Get-ObligationBlockedError -Preflight $preflight)
    }
    if ($preflight.lifecycle.status -eq 'unavailable' -and $preflight.lifecycle.obligations_declared) {
        return (Get-LifecycleUnavailableError -Preflight $preflight -FeatureName (Split-Path -Leaf $preflight.feature.dir))
    }
    if (-not $preflight.creation_supported) {
        return (Get-JsonError -Message "Automated PR creation is not supported for platform '$($DevSparkPlatform.Name)'" -Details 'Supported: github (gh), azdo (az). Install and authenticate the platform CLI.')
    }
    if (-not $preflight.auth_ok) {
        $authHint = switch ($DevSparkPlatform.Name) { 'github' { 'Run: gh auth login' } 'azdo' { 'Run: az login' } default { "Authenticate the $($DevSparkPlatform.PrCli) CLI" } }
        return (Get-JsonError -Message "$($DevSparkPlatform.DisplayName) CLI is not authenticated" -Details $authHint)
    }

    $bodyValue = Resolve-PrBody
    if (-not $Title -or -not $bodyValue) {
        return (Get-JsonError -Message 'Title and body are required for create/update mode' -Details 'Pass -Title and -Body or -BodyFile')
    }

    if ($Action -eq 'Create' -and $preflight.existing_pr.exists) {
        return (Get-JsonError -Message 'A PR already exists for this branch' -Details 'Use update mode or pass -PrNumber')
    }

    $baseBranch = if ($Base) { $Base } else { $preflight.target_branch }

    if ($DevSparkPlatform.Name -eq 'azdo') {
        $azctx = Get-AzdoRepoContext
        $orgUrl = "https://dev.azure.com/$($azctx.Org)"
        if ($Action -eq 'Update') {
            $targetPr = if ($PrNumber) { $PrNumber } else { $preflight.existing_pr.number }
            if (-not $targetPr) { return (Get-JsonError -Message 'No PR found to update' -Details 'Create a PR first or pass -PrNumber') }
            az repos pr update --organization $orgUrl --id $targetPr --title $Title --description $bodyValue 2>$null | Out-Null
            foreach ($item in $Reviewer) { az repos pr reviewer add --organization $orgUrl --id $targetPr --reviewers $item 2>$null | Out-Null }
            $show = az repos pr show --organization $orgUrl --id $targetPr --output json 2>$null | ConvertFrom-Json
        } else {
            $azArgs = @('repos','pr','create','--organization',$orgUrl,'--project',$azctx.Project,'--repository',$azctx.Repo,'--source-branch',$preflight.current_branch,'--target-branch',$baseBranch,'--title',$Title,'--description',$bodyValue,'--output','json')
            if ($Draft) { $azArgs += @('--draft','true') }
            foreach ($item in $Reviewer) { $azArgs += @('--reviewers',$item) }
            $show = & az @azArgs 2>$null | ConvertFrom-Json
            if (-not $show -or -not $show.pullRequestId) { return (Get-JsonError -Message 'Failed to create pull request' -Details 'az repos pr create did not return a pull request id') }
        }
        $prId = $show.pullRequestId
        $view = [PSCustomObject]@{
            number  = $prId
            url     = "https://dev.azure.com/$($azctx.Org)/$($azctx.Project)/_git/$($azctx.Repo)/pullrequest/$prId"
            title   = $show.title
            state   = $show.status
            isDraft = [bool]$show.isDraft
        }
    } else {
        if ($Action -eq 'Update') {
            $targetPr = if ($PrNumber) { $PrNumber } else { $preflight.existing_pr.number }
            if (-not $targetPr) {
                return (Get-JsonError -Message 'No PR found to update' -Details 'Create a PR first or pass -PrNumber')
            }
            gh pr edit $targetPr --title $Title --body $bodyValue --base $baseBranch 2>$null | Out-Null
            foreach ($item in $Reviewer) { gh pr edit $targetPr --add-reviewer $item 2>$null | Out-Null }
            foreach ($item in $Label) { gh pr edit $targetPr --add-label $item 2>$null | Out-Null }
            foreach ($item in $Assignee) { gh pr edit $targetPr --add-assignee $item 2>$null | Out-Null }
            $view = gh pr view $targetPr --json number,url,title,state,isDraft 2>$null | ConvertFrom-Json
        } else {
            $ghCreateCommand = @('pr','create','--title',$Title,'--body',$bodyValue,'--base',$baseBranch)
            if ($Draft) { $ghCreateCommand += '--draft' }
            foreach ($item in $Reviewer) { $ghCreateCommand += @('--reviewer',$item) }
            foreach ($item in $Label) { $ghCreateCommand += @('--label',$item) }
            foreach ($item in $Assignee) { $ghCreateCommand += @('--assignee',$item) }
            $created = & gh @ghCreateCommand 2>$null
            $url = ($created | Select-Object -Last 1)
            if (-not $url) {
                return (Get-JsonError -Message 'Failed to create pull request' -Details 'gh pr create did not return a URL')
            }
            $view = gh pr view $url --json number,url,title,state,isDraft 2>$null | ConvertFrom-Json
        }
    }

    return ([PSCustomObject]@{
        status = 'ok'
        action = $Action.ToLower()
        checked_head = $preflight.remote.local_head
        pr_number = $view.number
        url = $view.url
        title = $view.title
        state = $view.state
        draft = [bool]$view.isDraft
    } | ConvertTo-Json -Depth 10)
}

function Write-CreateOrUpdateResult {
    param([string]$Json)

    Write-Output $Json
    # A refused or failed create/update exits non-zero so automation never has to parse the message.
    $failed = $true
    try { $failed = [bool]($Json | ConvertFrom-Json).error } catch { }
    if ($failed) { exit 1 }
}

switch ($Mode) {
    'Preflight' {
        $output = Get-CreatePrPreflight | ConvertTo-Json -Depth 10
        Write-Output $output
        # Preflight always succeeds; its lifecycle probe would otherwise leave a non-zero $LASTEXITCODE.
        exit 0
    }
    'Create' {
        Write-CreateOrUpdateResult (Invoke-CreateOrUpdatePr -Action Create)
    }
    'Update' {
        Write-CreateOrUpdateResult (Invoke-CreateOrUpdatePr -Action Update)
    }
}