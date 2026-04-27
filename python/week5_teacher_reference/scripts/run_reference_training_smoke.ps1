<#
.SYNOPSIS
    Smoke-run of the original gym-microrts-paper training recipe.

.DESCRIPTION
    Runs a SHORT training experiment using the original paper scripts to verify:
      - Dependencies are correctly installed
      - gym-microrts env starts up
      - PPO training loop executes without crash
      - Video/replay and logs are created

    This is NOT a meaningful training run — it is only a dependency and startup check.
    Total timesteps are set very low (10000) by default.

.NOTES
    Prerequisites:
      1. Run create_reference_env.ps1 first.
      2. Activate the reference env:
           python/week5_teacher_reference/.venv_microrts032_reference/Scripts/Activate.ps1
      3. Clone gym-microrts-paper into external/ (done by create_reference_env.ps1).
      4. Set JAVA_HOME to JDK >= 1.8.0.

    Run from repo root:
        .\python\week5_teacher_reference\scripts\run_reference_training_smoke.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
$ScriptDir      = $PSScriptRoot
$RefRoot        = Split-Path $ScriptDir -Parent
$VenvPath       = Join-Path $RefRoot ".venv_microrts032_reference"
$PaperRepo      = Join-Path $RefRoot "external\gym-microrts-paper"
$ArtifactsBase  = Join-Path $RefRoot "artifacts\smoke_runs"

$TOTAL_TIMESTEPS = 10000
$SEED            = 1
$CAPTURE_VIDEO   = $true
$SCRIPT_TO_RUN   = "ppo_gridnet_diverse_encode_decode.py"   # Gridnet: best paper agent
$ALT_SCRIPT      = "ppo_diverse_impala.py"                  # UAS: fallback

# JAVA_HOME — override here or set in your shell before running
if (-not $env:JAVA_HOME) {
    # Common Windows install paths — adjust if needed
    $candidates = @(
        "C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot",
        "C:\Program Files\Eclipse Adoptium\jdk-11.0.18.10-hotspot",
        "C:\Program Files\Java\jdk1.8.0_392",
        "C:\Program Files\Java\jdk-17",
        "C:\Program Files\Microsoft\jdk-17.0.10.7-hotspot"
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) {
            $env:JAVA_HOME = $p
            $env:Path      = "$p\bin;$env:Path"
            Write-Host "  Auto-detected JAVA_HOME: $p" -ForegroundColor DarkYellow
            break
        }
    }
}

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "=== Reference Smoke Training ===" -ForegroundColor Cyan
Write-Host "  Script         : $SCRIPT_TO_RUN (fallback: $ALT_SCRIPT)"
Write-Host "  Total timesteps: $TOTAL_TIMESTEPS"
Write-Host "  Seed           : $SEED"
Write-Host "  Capture video  : $CAPTURE_VIDEO"
Write-Host "  JAVA_HOME      : $($env:JAVA_HOME)"
Write-Host ""

$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "ERROR: Reference venv not found at: $VenvPath" -ForegroundColor Red
    Write-Host "Run create_reference_env.ps1 first." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $PaperRepo)) {
    Write-Host "ERROR: gym-microrts-paper not found at: $PaperRepo" -ForegroundColor Red
    Write-Host "Run create_reference_env.ps1 (it will clone it) or clone manually:" -ForegroundColor Red
    Write-Host "  git clone https://github.com/vwxyzjn/gym-microrts-paper $PaperRepo" -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------------
# Timestamp output directory
# ---------------------------------------------------------------------------
$Timestamp  = (Get-Date -Format "yyyyMMddTHHmmssZ")
$OutDir     = Join-Path $ArtifactsBase $Timestamp
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

Write-Host "Output dir: $OutDir" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
# Build command
# ---------------------------------------------------------------------------
$ScriptPath = Join-Path $PaperRepo $SCRIPT_TO_RUN
if (-not (Test-Path $ScriptPath)) {
    Write-Host "WARNING: $SCRIPT_TO_RUN not found — trying fallback $ALT_SCRIPT" -ForegroundColor DarkYellow
    $ScriptPath = Join-Path $PaperRepo $ALT_SCRIPT
    $SCRIPT_TO_RUN = $ALT_SCRIPT
}

if (-not (Test-Path $ScriptPath)) {
    Write-Host "ERROR: Neither $SCRIPT_TO_RUN nor $ALT_SCRIPT found in $PaperRepo" -ForegroundColor Red
    Write-Host "Available .py files:" -ForegroundColor DarkYellow
    Get-ChildItem $PaperRepo -Filter "*.py" | ForEach-Object { Write-Host "  $($_.Name)" }
    exit 1
}

$Args = @(
    $ScriptPath,
    "--total-timesteps", $TOTAL_TIMESTEPS,
    "--seed", $SEED,
    "--exp-name", "smoke_$Timestamp"
)

if ($CAPTURE_VIDEO) {
    $Args += "--capture-video"
}

# Smoke run uses minimal envs to avoid resource pressure
$Args += @("--num-bot-envs", "1", "--num-selfplay-envs", "0")

# Save command to log
$CmdStr = "$VenvPython $($Args -join ' ')"
$CmdStr | Out-File -FilePath (Join-Path $OutDir "smoke_command.txt") -Encoding utf8
Write-Host "Command: $CmdStr" -ForegroundColor DarkCyan
Write-Host ""

# ---------------------------------------------------------------------------
# Run in paper repo directory (scripts reference relative paths)
# ---------------------------------------------------------------------------
$OriginalDir = $PWD.Path
Set-Location $PaperRepo

try {
    Write-Host "--- Training output begins ---" -ForegroundColor DarkGray
    & $VenvPython @Args 2>&1 | Tee-Object -FilePath (Join-Path $OutDir "smoke_train.log")
    $ExitCode = $LASTEXITCODE
    Write-Host "--- Training output ends ---" -ForegroundColor DarkGray
} finally {
    Set-Location $OriginalDir
}

# ---------------------------------------------------------------------------
# Collect outputs
# ---------------------------------------------------------------------------
Write-Host ""
if ($ExitCode -eq 0) {
    Write-Host "Smoke run COMPLETED (exit 0)" -ForegroundColor Green
} else {
    Write-Host "Smoke run FAILED (exit $ExitCode)" -ForegroundColor Red
    Write-Host "See log: $(Join-Path $OutDir 'smoke_train.log')" -ForegroundColor DarkYellow
}

# Copy any videos/checkpoints created by the paper script (written relative to paper repo cwd)
$VideoSrc = Join-Path $PaperRepo "videos"
if (Test-Path $VideoSrc) {
    Copy-Item $VideoSrc -Destination (Join-Path $OutDir "videos") -Recurse -Force
    Write-Host "Videos copied to: $(Join-Path $OutDir 'videos')" -ForegroundColor Green
}

# Write summary
$Summary = @{
    timestamp       = $Timestamp
    script          = $SCRIPT_TO_RUN
    total_timesteps = $TOTAL_TIMESTEPS
    seed            = $SEED
    exit_code       = $ExitCode
    out_dir         = $OutDir
    java_home       = $env:JAVA_HOME
    python_exe      = $VenvPython
}
$Summary | ConvertTo-Json -Depth 3 | Out-File -FilePath (Join-Path $OutDir "smoke_summary.json") -Encoding utf8

Write-Host ""
Write-Host "Artifacts saved to: $OutDir" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next: Run collect_reference_artifacts.py to aggregate results."
