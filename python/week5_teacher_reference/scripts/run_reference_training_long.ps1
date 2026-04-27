<#
.SYNOPSIS
    Long/staged reference training run for gym-microrts 0.3.2.

.DESCRIPTION
    Runs a longer training experiment using the original paper recipe.

    DEFAULT: 1,000,000 timesteps (1M) as the first staged reference run.
    This gives enough signal to verify that movement behavior emerges
    without committing to a full paper-scale run (100M timesteps).

    IMPORTANT:
      - This script does NOT start automatically.
      - Review the configuration section below before running.
      - Do NOT set TOTAL_TIMESTEPS to 100M+ without planning for multi-day compute.
      - This is a REFERENCE run only — not a Unity-compatible checkpoint.

    Paper-scale context:
      The paper uses ~100M timesteps for final results.
      1M is sufficient to see initial movement/combat behavior in most envs.
      10M is a reasonable "staged sanity" run.

.NOTES
    Prerequisites:
      1. Run create_reference_env.ps1 and verify_reference_env.py first.
      2. Smoke run should have passed.
      3. Activate reference venv before running.
      4. Set JAVA_HOME to JDK >= 1.8.0.

    Run from repo root:
        .\python\week5_teacher_reference\scripts\run_reference_training_long.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

# ===========================================================================
# CONFIGURATION — edit before running
# ===========================================================================

# Total environment steps. Start with 1M for a staged sanity check.
# Paper-level runs use ~100M — do NOT set that without explicit intent.
$TOTAL_TIMESTEPS = 1000000   # 1M staged reference run

# Random seed for reproducibility
$SEED = 1

# Capture video of episodes (requires ffmpeg)
$CAPTURE_VIDEO = $true

# Which paper script to use (from external/gym-microrts-paper/)
# Recommended for reference: ppo_gridnet_diverse_encode_decode.py (best Gridnet agent)
# Alternative UAS: ppo_diverse_impala.py
$SCRIPT_TO_RUN = "ppo_gridnet_diverse_encode_decode.py"

# Number of parallel envs (reduce if OOM)
$NUM_BOT_ENVS      = 4
$NUM_SELFPLAY_ENVS = 0

# Output directory (auto-timestamped subfolder is created)
$OUTPUT_BASE = Join-Path $PSScriptRoot "..\artifacts\long_runs"

# ===========================================================================
# END CONFIGURATION
# ===========================================================================

$ScriptDir   = $PSScriptRoot
$RefRoot     = Split-Path $ScriptDir -Parent
$VenvPath    = Join-Path $RefRoot ".venv_microrts032_reference"
$PaperRepo   = Join-Path $RefRoot "external\gym-microrts-paper"

# JAVA_HOME auto-detect (override if needed)
if (-not $env:JAVA_HOME) {
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
            break
        }
    }
}

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "=== Reference Long Training Run ===" -ForegroundColor Cyan
Write-Host "  Script          : $SCRIPT_TO_RUN"
Write-Host "  Total timesteps : $TOTAL_TIMESTEPS"
Write-Host "  Seed            : $SEED"
Write-Host "  Capture video   : $CAPTURE_VIDEO"
Write-Host "  Num bot envs    : $NUM_BOT_ENVS"
Write-Host "  Num selfplay    : $NUM_SELFPLAY_ENVS"
Write-Host "  JAVA_HOME       : $($env:JAVA_HOME)"
Write-Host ""
Write-Host "NOTE: Paper-level runs use ~100M timesteps. This run uses $TOTAL_TIMESTEPS." -ForegroundColor DarkYellow
Write-Host "      This is a STAGED REFERENCE run, not a full paper reproduction." -ForegroundColor DarkYellow
Write-Host ""

$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "ERROR: Reference venv not found at: $VenvPath" -ForegroundColor Red
    Write-Host "Run create_reference_env.ps1 first." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $PaperRepo)) {
    Write-Host "ERROR: gym-microrts-paper not found at: $PaperRepo" -ForegroundColor Red
    exit 1
}

$ScriptPath = Join-Path $PaperRepo $SCRIPT_TO_RUN
if (-not (Test-Path $ScriptPath)) {
    Write-Host "ERROR: Script not found: $ScriptPath" -ForegroundColor Red
    Write-Host "Available .py files:" -ForegroundColor DarkYellow
    Get-ChildItem $PaperRepo -Filter "*.py" | ForEach-Object { Write-Host "  $($_.Name)" }
    exit 1
}

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------
$Timestamp = (Get-Date -Format "yyyyMMddTHHmmssZ")
$OutDir    = Join-Path $OUTPUT_BASE $Timestamp
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

Write-Host "Output dir: $OutDir" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
# Build command
# ---------------------------------------------------------------------------
$Args = @(
    $ScriptPath,
    "--total-timesteps", $TOTAL_TIMESTEPS,
    "--seed",            $SEED,
    "--exp-name",        "long_ref_${Timestamp}",
    "--num-bot-envs",    $NUM_BOT_ENVS,
    "--num-selfplay-envs", $NUM_SELFPLAY_ENVS
)
if ($CAPTURE_VIDEO) { $Args += "--capture-video" }

$CmdStr = "$VenvPython $($Args -join ' ')"
$CmdStr | Out-File -FilePath (Join-Path $OutDir "long_run_command.txt") -Encoding utf8
Write-Host "Command: $CmdStr" -ForegroundColor DarkCyan
Write-Host ""

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
$OriginalDir = $PWD.Path
Set-Location $PaperRepo

try {
    Write-Host "--- Training output begins ---" -ForegroundColor DarkGray
    & $VenvPython @Args 2>&1 | Tee-Object -FilePath (Join-Path $OutDir "long_train.log")
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
    Write-Host "Long run COMPLETED (exit 0)" -ForegroundColor Green
} else {
    Write-Host "Long run FINISHED with exit $ExitCode" -ForegroundColor DarkYellow
    Write-Host "See log: $(Join-Path $OutDir 'long_train.log')"
}

$VideoSrc = Join-Path $PaperRepo "videos"
if (Test-Path $VideoSrc) {
    Copy-Item $VideoSrc -Destination (Join-Path $OutDir "videos") -Recurse -Force
    Write-Host "Videos copied to: $(Join-Path $OutDir 'videos')" -ForegroundColor Green
}

$Summary = @{
    timestamp        = $Timestamp
    script           = $SCRIPT_TO_RUN
    total_timesteps  = $TOTAL_TIMESTEPS
    seed             = $SEED
    num_bot_envs     = $NUM_BOT_ENVS
    num_selfplay_envs = $NUM_SELFPLAY_ENVS
    capture_video    = $CAPTURE_VIDEO
    exit_code        = $ExitCode
    out_dir          = $OutDir
    java_home        = $env:JAVA_HOME
    python_exe       = $VenvPython
    note             = "Staged reference run. Paper uses ~100M timesteps."
}
$Summary | ConvertTo-Json -Depth 3 | Out-File -FilePath (Join-Path $OutDir "long_run_summary.json") -Encoding utf8

Write-Host ""
Write-Host "Artifacts saved to: $OutDir" -ForegroundColor Cyan
Write-Host "Run collect_reference_artifacts.py to aggregate results."
