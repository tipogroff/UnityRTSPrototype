<#
.SYNOPSIS
    Branch B smoke run for project-compatible Gridnet teacher training.

.DESCRIPTION
    Runs a short 10k-timestep smoke to verify training loop stability and artifact creation.
    This is a no-crash check, not a teacher-readiness claim.
#>

param(
    [switch]$RenderWindow,
    [switch]$RenderDuringTrain,
    [bool]$RenderDuringFinalEval = $true
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\.." )).Path
$ScriptPath = Join-Path $PSScriptRoot "train_teacher_gridnet_project.py"
$PythonCandidate = Join-Path $RepoRoot "python\week5_teacher\.venv_day2_py39\Scripts\python.exe"
$PythonExe = if (Test-Path $PythonCandidate) { $PythonCandidate } else { "python" }

if (-not $env:JAVA_HOME) {
    $Candidates = @(
        "C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot",
        "C:\Program Files\Eclipse Adoptium\jdk-11.0.18.8-hotspot",
        "C:\Program Files\Java\jdk-17"
    )
    foreach ($PathCandidate in $Candidates) {
        if (Test-Path $PathCandidate) {
            $env:JAVA_HOME = $PathCandidate
            $env:Path = "$PathCandidate\bin;$env:Path"
            break
        }
    }
}

$GitBashCandidates = @(
    "C:\Program Files\Git\bin",
    "C:\Program Files\Git\usr\bin"
)
foreach ($GitPath in $GitBashCandidates) {
    if (Test-Path (Join-Path $GitPath "bash.exe")) {
        if (-not ($env:Path -like "*$GitPath*")) {
            $env:Path = "$GitPath;$env:Path"
        }
    }
}

$RunId = "gridnet_smoke_$(Get-Date -Format 'yyyyMMddTHHmmssZ')"
$Args = @(
    $ScriptPath,
    "--run-id", $RunId,
    "--total-timesteps", "10000",
    "--checkpoint-steps", "10000",
    "--num-bot-envs", "6",
    "--num-selfplay-envs", "0",
    "--seed", "1",
    "--device", "cpu"
)

if ($RenderWindow) {
    $Args += "--render-window"
    if ($RenderDuringTrain) {
        $Args += "--render-during-train"
    }
    if ($RenderDuringFinalEval) {
        $Args += "--render-during-final-eval"
    } else {
        $Args += "--no-render-during-final-eval"
    }
}

Write-Host "=== Branch B Gridnet Smoke (10k) ===" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"
Write-Host "Python: $PythonExe"
Write-Host "JAVA_HOME: $($env:JAVA_HOME)"
Write-Host "RunId: $RunId"
Write-Host "RenderWindow: $RenderWindow"
Write-Host "RenderDuringTrain: $RenderDuringTrain"
Write-Host "RenderDuringFinalEval: $RenderDuringFinalEval"
Write-Host ""

Push-Location $RepoRoot
try {
    & $PythonExe @Args
    $ExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}

if ($ExitCode -eq 0) {
    Write-Host "Smoke run completed (exit 0)." -ForegroundColor Green
} else {
    Write-Host "Smoke run failed (exit $ExitCode)." -ForegroundColor Red
}

exit $ExitCode
