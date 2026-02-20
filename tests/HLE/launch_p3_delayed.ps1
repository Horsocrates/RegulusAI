# HLE P3 Agent Pipeline - Delayed Launch
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File launch_p3_delayed.ps1
#   powershell -ExecutionPolicy Bypass -File launch_p3_delayed.ps1 -NoWait
#   powershell -ExecutionPolicy Bypass -File launch_p3_delayed.ps1 -DelayHours 1

param(
    [switch]$NoWait,
    [double]$DelayHours = 4,
    [int]$Seed = 200,
    [int]$StartBatch = 4,
    [int]$NBatches = 3,
    [string]$LeadModel = 'claude-opus-4-6',
    [string]$WorkerModel = 'claude-opus-4-6'
)

$ProjectRoot = 'C:\Users\aleks\Desktop\regulusai'
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$HleDir = Join-Path $ProjectRoot 'tests\HLE'

Write-Host '============================================'
Write-Host '  HLE P3 Agent Pipeline - Scheduled Launch'
Write-Host '============================================'
Write-Host ''
Write-Host "  Seed:         $Seed"
$endBatch = $StartBatch + $NBatches - 1
Write-Host "  Batches:      batch_$($StartBatch.ToString('D3')) .. batch_$($endBatch.ToString('D3'))"
Write-Host "  Questions:    $($NBatches * 10)"
Write-Host "  Lead model:   $LeadModel"
Write-Host "  Worker model: $WorkerModel"
Write-Host '  Calls/q:      8 (plan + D1-D6 + assembly)'
Write-Host ''

# --- Timer ---
if (-not $NoWait) {
    $DelaySec = [int]($DelayHours * 3600)
    $launchAt = (Get-Date).AddSeconds($DelaySec).ToString('HH:mm:ss')
    Write-Host "  Waiting $DelayHours hours (launch at $launchAt)..."
    Write-Host '  Press Ctrl+C to cancel.'
    Write-Host ''
    Start-Sleep -Seconds $DelaySec
}

$now = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Write-Host "--- Starting at $now ---"

# --- Step 1: Prepare questions ---
Write-Host ''
Write-Host "Step 1: Preparing questions (seed=$Seed, batches=$NBatches, start=$StartBatch)"
$prepareScript = Join-Path $HleDir 'prepare_questions.py'
& $Python $prepareScript --seed $Seed --n-batches $NBatches --batch-size 10 --start-batch $StartBatch

if ($LASTEXITCODE -ne 0) {
    Write-Host 'ERROR: prepare_questions.py failed!'
    exit 1
}

# --- Step 2: Run P3 on each batch sequentially ---
$p3Script = Join-Path $HleDir 'run_p3_agent.py'

for ($i = 0; $i -lt $NBatches; $i++) {
    $batchNum = $StartBatch + $i
    $batchName = 'batch_' + $batchNum.ToString('D3')

    Write-Host ''
    Write-Host "Step 2.$($i+1): Running P3 on $batchName"
    & $Python $p3Script --batch $batchName --lead-model $LeadModel --worker-model $WorkerModel

    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARNING: $batchName failed, continuing..."
    }
}

# --- Done ---
Write-Host ''
Write-Host '============================================'
$now = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Write-Host "  All batches complete at $now"
Write-Host '============================================'
Write-Host ''
$judgeOnlyDir = Join-Path $HleDir '.judge_only'
$workspaceDir = Join-Path $HleDir 'workspace'
Write-Host "Results:   $judgeOnlyDir\p3_batch_*.json"
Write-Host "Workspace: $workspaceDir\"
Write-Host ''
Write-Host 'Next steps (in a SEPARATE session):'
$judgeScript = Join-Path $HleDir 'judge.py'
$compareScript = Join-Path $HleDir 'compare.py'
Write-Host "  Judge:   $Python $judgeScript --batch batch_XXX --participant p3"
Write-Host "  Compare: $Python $compareScript --all --left p1 --right p3"
