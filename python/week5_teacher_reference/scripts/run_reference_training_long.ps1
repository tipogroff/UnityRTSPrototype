<#
.SYNOPSIS
    Staged long reference training run for gym-microrts 0.3.2.

.DESCRIPTION
    Runs a longer training experiment using the original paper recipe.
    Default: 1,000,000 timesteps (1M staged sanity check).
    Paper-level runs use ~100M timesteps -- do NOT set that without planning for
    multi-day compute.

    IMPORTANT:
      - This is a REFERENCE run only -- not a Unity-compatible checkpoint.
      - Do NOT copy artifacts to python/week5_teacher or Unity pipeline.
      - Smoke run must have passed before running this.

.PARAMETER TotalTimesteps
    Total environment steps. Default: 1_000_000.

.PARAMETER Seed
    Random seed. Default: 1.

.PARAMETER NumBotEnvs
    Number of bot envs. Minimum: 6 (required by ai2s formula in paper script).
    Default: 6.

.PARAMETER CaptureVideo
    Capture episode video. Requires ffmpeg on PATH. Default: auto-detect ffmpeg.

.PARAMETER ScriptToRun
    Paper script filename (relative to external/gym-microrts-paper/).
    Default: ppo_gridnet_diverse_encode_decode.py

.PARAMETER LocalSaveModel
    Use the local patched paper script and save model artifacts to the long-run output dir.

.EXAMPLE
    # 100k quick staged test
    .\run_reference_training_long.ps1 -TotalTimesteps 100000 -CaptureVideo:$false

    # 1M staged reference run
    .\run_reference_training_long.ps1 -TotalTimesteps 1000000 -CaptureVideo:$false
#>
param(
    [int]    $TotalTimesteps = 1000000,
    [int]    $Seed           = 1,
    [int]    $NumBotEnvs     = 6,
    [switch] $CaptureVideo,
    [string] $ScriptToRun    = "ppo_gridnet_diverse_encode_decode.py",
    [switch] $LocalSaveModel
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"
$PSNativeCommandUseErrorActionPreference = $false

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
$ScriptDir  = $PSScriptRoot
$RefRoot    = Split-Path $ScriptDir -Parent
$VenvPath   = Join-Path $RefRoot ".venv_microrts032_reference"
$PaperRepo  = Join-Path $RefRoot "external\gym-microrts-paper"
$PatchedPaperRoot = Join-Path $RefRoot "patched_paper_scripts"
$OutputBase = Join-Path $RefRoot "artifacts\long_runs"

# ---------------------------------------------------------------------------
# Auto-detect JAVA_HOME
# ---------------------------------------------------------------------------
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
            Write-Host "  Auto-detected JAVA_HOME: $p" -ForegroundColor DarkYellow
            break
        }
    }
}

# ---------------------------------------------------------------------------
# Auto-detect ffmpeg for CaptureVideo
# ---------------------------------------------------------------------------
$FfmpegAvailable = $false
if ($null -ne (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    $FfmpegAvailable = $true
}
# If -CaptureVideo was explicitly passed, honour it; otherwise follow auto-detect
$UseCaptureVideo = $CaptureVideo.IsPresent
if ($CaptureVideo.IsPresent -and -not $FfmpegAvailable) {
    Write-Host "WARNING: --CaptureVideo requested but ffmpeg not found on PATH. Disabling." -ForegroundColor DarkYellow
    $UseCaptureVideo = $false
}

# Validation: num_bot_envs minimum
if ($NumBotEnvs -lt 6) {
    Write-Host "ERROR: --NumBotEnvs must be >= 6 (ai2s formula requires it). Got: $NumBotEnvs" -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "=== Reference Long Training Run ===" -ForegroundColor Cyan
Write-Host "  Script          : $ScriptToRun"
Write-Host "  Total timesteps : $TotalTimesteps"
Write-Host "  Seed            : $Seed"
Write-Host "  Num bot envs    : $NumBotEnvs"
Write-Host "  Capture video   : $UseCaptureVideo"
Write-Host "  Local save      : $($LocalSaveModel.IsPresent)"
Write-Host "  JAVA_HOME       : $($env:JAVA_HOME)"
Write-Host ""
Write-Host "NOTE: Paper-level runs use ~100M timesteps. This run uses $TotalTimesteps." -ForegroundColor DarkYellow
Write-Host "      This is a STAGED REFERENCE run -- not a Unity-compatible checkpoint." -ForegroundColor DarkYellow
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

$SelectedScriptRoot = $PaperRepo
if ($LocalSaveModel.IsPresent) {
    $SelectedScriptRoot = $PatchedPaperRoot
    if ($ScriptToRun -eq "ppo_gridnet_diverse_encode_decode.py") {
        $ScriptToRun = "ppo_gridnet_diverse_encode_decode_local_save.py"
    }
}

$ScriptPath = Join-Path $SelectedScriptRoot $ScriptToRun
if (-not (Test-Path $ScriptPath)) {
    Write-Host "ERROR: Script not found: $ScriptPath" -ForegroundColor Red
    Write-Host "Available .py files:" -ForegroundColor DarkYellow
    Get-ChildItem $SelectedScriptRoot -Filter "*.py" | ForEach-Object { Write-Host "  $($_.Name)" }
    exit 1
}

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------
$Timestamp = (Get-Date -Format "yyyyMMddTHHmmssZ")
$ExpName   = "long_ref_${Timestamp}"
$OutDir    = Join-Path $OutputBase $Timestamp
$ModelOutDir = Join-Path $OutDir "models"
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

Write-Host "Output dir: $OutDir" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
# Build command
# ---------------------------------------------------------------------------
$TrainArgs = @(
    $ScriptPath,
    "--total-timesteps", $TotalTimesteps,
    "--seed",            $Seed,
    "--exp-name",        $ExpName,
    "--num-bot-envs",    $NumBotEnvs,
    "--num-selfplay-envs", 0
)
if ($UseCaptureVideo) { $TrainArgs += "--capture-video" }
if ($LocalSaveModel.IsPresent) {
    $TrainArgs += @("--local-save-model", "true", "--local-save-dir", $ModelOutDir, "--local-save-every", 0)
}

$CmdStr = "$VenvPython $($TrainArgs -join ' ')"
$CmdStr | Out-File -FilePath (Join-Path $OutDir "long_run_command.txt") -Encoding utf8
Write-Host "Command: $CmdStr" -ForegroundColor DarkCyan
Write-Host ""

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
$StartTime   = Get-Date
$OriginalDir = $PWD.Path
Set-Location $PaperRepo

$ExitCode = 1
try {
    Write-Host "--- Training output begins ---" -ForegroundColor DarkGray
    $env:WANDB_MODE = "disabled"
    $ErrorActionPreference = "Continue"
    & $VenvPython @TrainArgs 2>&1 | Tee-Object -FilePath (Join-Path $OutDir "long_train.log")
    $ExitCode = $LASTEXITCODE
    Write-Host "--- Training output ends ---" -ForegroundColor DarkGray
} finally {
    $ErrorActionPreference = "Continue"
    Set-Location $OriginalDir
}

$EndTime = Get-Date
$DurationSec = [int]($EndTime - $StartTime).TotalSeconds

# ---------------------------------------------------------------------------
# Discover artifacts produced by the paper script
# ---------------------------------------------------------------------------
# Paper script writes (all relative to PaperRepo CWD):
#   runs/<gym_id>__<exp_name>__<seed>__<unix_ts>/ -- TensorBoard event files (always)
#   models/<gym_id>__<exp_name>__<seed>__<unix_ts>/agent.pt -- only with --prod-mode
#   videos/                                       -- only with --capture-video
$ArtifactPaths = @{}
$ModelPaths = @()
$CheckpointPaths = @()
$MetadataPaths = @()

$RunDirPattern = "*__${ExpName}__${Seed}__*"
$TBDir = Get-ChildItem (Join-Path $PaperRepo "runs") -Directory -ErrorAction SilentlyContinue |
         Where-Object { $_.Name -like $RunDirPattern } |
         Sort-Object LastWriteTime -Descending |
         Select-Object -First 1
if ($TBDir) {
    $ArtifactPaths["tensorboard_dir"] = $TBDir.FullName
    Write-Host "TensorBoard events: $($TBDir.FullName)" -ForegroundColor Green
} else {
    $ArtifactPaths["tensorboard_dir"] = $null
}

$ModelsDir = Get-ChildItem (Join-Path $PaperRepo "models") -Directory -ErrorAction SilentlyContinue |
             Where-Object { $_.Name -like $RunDirPattern } |
             Sort-Object LastWriteTime -Descending |
             Select-Object -First 1
$ModelPt = $null
if ($ModelsDir) {
    $ModelPt = Join-Path $ModelsDir.FullName "agent.pt"
}
if ($null -ne $ModelPt -and (Test-Path $ModelPt)) {
    $ArtifactPaths["agent_pt"] = $ModelPt
    Write-Host "Model checkpoint: $ModelPt" -ForegroundColor Green
} else {
    $ArtifactPaths["agent_pt"] = $null
    Write-Host "NOTE: agent.pt not found (expected -- paper script only saves via wandb --prod-mode)." -ForegroundColor DarkYellow
    Write-Host "      To save a checkpoint add --prod-mode or use a custom save wrapper." -ForegroundColor DarkYellow
}

# Copy TensorBoard runs dir into output dir for archival
if ($ArtifactPaths["tensorboard_dir"]) {
    $TBDest = Join-Path $OutDir "tensorboard"
    Copy-Item $ArtifactPaths["tensorboard_dir"] -Destination $TBDest -Recurse -Force
    Write-Host "TensorBoard data copied to: $TBDest" -ForegroundColor Green
}

# Copy videos if captured
$VideoSrc = Join-Path $PaperRepo "videos"
$VideosFound = $false
if (Test-Path $VideoSrc) {
    Copy-Item $VideoSrc -Destination (Join-Path $OutDir "videos") -Recurse -Force
    $VideosFound = $true
    Write-Host "Videos copied to: $(Join-Path $OutDir 'videos')" -ForegroundColor Green
}

# Detect any .pt / .pth / .zip under paper repo (catch non-standard save locations)
$ExtraModels = Get-ChildItem $PaperRepo -Include "*.pt","*.pth","*.zip" -Recurse -ErrorAction SilentlyContinue |
               Where-Object { $_.LastWriteTime -gt $StartTime } |
               Select-Object -ExpandProperty FullName
if ($ExtraModels) {
    $ArtifactPaths["extra_models"] = $ExtraModels
    Write-Host "Extra model files found since run start:" -ForegroundColor Green
    $ExtraModels | ForEach-Object { Write-Host "  $_" }
} else {
    $ArtifactPaths["extra_models"] = @()
}

if (Test-Path $ModelOutDir) {
    $ModelPaths = @(Get-ChildItem $ModelOutDir -Filter "agent_final.pt" -Recurse -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
    $CheckpointPaths = @(Get-ChildItem $ModelOutDir -Include "agent_step_*.pt","*.zip" -Recurse -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
    $MetadataPaths = @(Get-ChildItem $ModelOutDir -Filter "model_metadata.json" -Recurse -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
}
$ArtifactPaths["local_model_paths"] = $ModelPaths
$ArtifactPaths["local_checkpoint_paths"] = $CheckpointPaths
$ArtifactPaths["local_metadata_paths"] = $MetadataPaths

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
Write-Host ""
if ($ExitCode -eq 0) {
    Write-Host "Long run COMPLETED (exit 0)" -ForegroundColor Green
} else {
    Write-Host "Long run FINISHED with exit $ExitCode" -ForegroundColor DarkYellow
    Write-Host "See log: $(Join-Path $OutDir 'long_train.log')"
}

$Summary = [ordered]@{
    timestamp         = $Timestamp
    exp_name          = $ExpName
    script            = $ScriptToRun
    total_timesteps   = $TotalTimesteps
    seed              = $Seed
    num_bot_envs      = $NumBotEnvs
    num_selfplay_envs = 0
    capture_video     = $UseCaptureVideo
    local_save_model  = $LocalSaveModel.IsPresent
    exit_code         = $ExitCode
    start_time        = $StartTime.ToString("o")
    end_time          = $EndTime.ToString("o")
    duration_sec      = $DurationSec
    out_dir           = $OutDir
    log_path          = (Join-Path $OutDir "long_train.log")
    videos_found      = $VideosFound
    checkpoints_found = (($null -ne $ArtifactPaths["agent_pt"]) -or $CheckpointPaths.Count -gt 0 -or $ModelPaths.Count -gt 0)
    model_paths       = $ModelPaths
    checkpoint_paths  = $CheckpointPaths
    metadata_paths    = $MetadataPaths
    artifact_paths    = $ArtifactPaths
    java_home         = $env:JAVA_HOME
    python_exe        = $VenvPython
    notes             = @(
        "Staged reference run. Paper uses ~100M timesteps.",
        "agent.pt only saved with --prod-mode (wandb). Not expected in reference runs.",
        "LocalSaveModel uses a patched local copy under patched_paper_scripts/ and does not modify external/.",
        "TensorBoard data in tensorboard/ subdirectory if training reached at least 1 update.",
        "np.int patched to np.int32 in gym_microrts venv (numpy>=1.24 compatibility)."
    )
}
$Summary | ConvertTo-Json -Depth 5 | Out-File -FilePath (Join-Path $OutDir "long_run_summary.json") -Encoding utf8

Write-Host ""
Write-Host "Artifacts saved to: $OutDir" -ForegroundColor Cyan
Write-Host "Run collect_reference_artifacts.py to aggregate results."
