<#
.SYNOPSIS
    Creates the isolated reference virtual environment for gym-microrts 0.3.2 reproduction.

.DESCRIPTION
    This script sets up a self-contained Python environment for reproducing the original
    Gym-uRTS paper training recipe. It does NOT touch the main project's .venv_day2_py39
    or any other Week5/Week6 pipeline components.

    Reference: https://github.com/vwxyzjn/gym-microrts-paper
    Paper:     Gym-uRTS: Toward Affordable Deep Reinforcement Learning Research in RTS Games (CoG 2021)

.NOTES
    Requirements:
      - Python 3.8 or 3.9 (via py launcher or on PATH)
      - JDK >= 1.8.0 on PATH (required by gym-microrts / JPype1)
      - Git (optional, for cloning gym-microrts-paper)
      - Run from the repository root:
          C:\Projects\UnityRTSPrototype\UnityRTSPrototype
#>

param(
    [switch]$ForceRecreate
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
$ScriptDir   = $PSScriptRoot
$RefRoot     = Split-Path $ScriptDir -Parent   # python/week5_teacher_reference/
$VenvName    = ".venv_microrts032_reference"
$VenvPath    = Join-Path $RefRoot $VenvName
$ReqFilePy38 = Join-Path $RefRoot "reference_env\requirements_reference.txt"
$ReqFilePy39 = Join-Path $RefRoot "reference_env\requirements_reference_py39_windows.txt"
$FreezeFile  = Join-Path $RefRoot "reference_env\pip_freeze_reference.txt"
$ArtifactsDir = Join-Path $RefRoot "artifacts"
$InstallLog  = Join-Path $ArtifactsDir "reference_env_install.log"
$ExternalDir = Join-Path $RefRoot "external"
$PaperRepo   = Join-Path $ExternalDir "gym-microrts-paper"
$PaperRepoUrl = "https://github.com/vwxyzjn/gym-microrts-paper"

if (-not (Test-Path $ArtifactsDir)) {
    New-Item -ItemType Directory -Path $ArtifactsDir | Out-Null
}

if (Test-Path $InstallLog) {
    Remove-Item $InstallLog -Force
}

function Write-InstallLog {
    param(
        [string]$Message
    )
    $stamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    "[$stamp] $Message" | Out-File -FilePath $InstallLog -Append -Encoding utf8
}

function Invoke-InstallStep {
    param(
        [string]$StepName,
        [string]$Exe,
        [string[]]$CmdArgs,
        [switch]$AllowFail
    )

    Write-Host "  -> $StepName" -ForegroundColor DarkCyan
    Write-InstallLog "STEP_START: $StepName"
    Write-InstallLog ("COMMAND: " + $Exe + " " + ($CmdArgs -join " "))

    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Exe @CmdArgs *>&1 | Tee-Object -FilePath $InstallLog -Append
    } finally {
        $ErrorActionPreference = $prevEap
    }
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        Write-InstallLog "STEP_FAIL: $StepName (exit=$code)"
        if (-not $AllowFail) {
            throw "Install step failed: $StepName (exit $code)"
        }
        return $false
    }

    Write-InstallLog "STEP_OK: $StepName"
    return $true
}

# ---------------------------------------------------------------------------
# Safety check: ensure we are NOT inside the project venv
# ---------------------------------------------------------------------------
$CurrentVenv = $env:VIRTUAL_ENV
if ($CurrentVenv -and ($CurrentVenv -match "venv_day2_py39")) {
    Write-Error @"
ERROR: You appear to be running inside the project venv: $CurrentVenv
Deactivate it first (run 'deactivate') before running this script.
This script must NOT touch the existing project environment.
"@
    exit 1
}

Write-Host ""
Write-Host "=== Reference Environment Setup: gym-microrts 0.3.2 ===" -ForegroundColor Cyan
Write-Host "Target venv  : $VenvPath"
Write-Host "Install log  : $InstallLog"
Write-Host ""

# ---------------------------------------------------------------------------
# Find Python 3.8 or 3.9
# ---------------------------------------------------------------------------
$PythonExe = $null
$PythonArgs = @()
$PythonVersionText = ""
$PythonMajorMinor = ""

Write-Host "[1/6] Searching for Python 3.8 or 3.9..." -ForegroundColor Yellow

# Prefer py launcher if present.
try {
    $ver38 = & py -3.8 --version 2>&1
    if ($ver38 -match "Python 3\.8\.") {
        $PythonExe = "py"
        $PythonArgs = @("-3.8")
        $PythonVersionText = $ver38
        Write-Host "  Found: $ver38  (via 'py -3.8')" -ForegroundColor Green
    }
} catch { }

if (-not $PythonExe) {
    try {
        $ver39 = & py -3.9 --version 2>&1
        if ($ver39 -match "Python 3\.9\.") {
            $PythonExe = "py"
            $PythonArgs = @("-3.9")
            $PythonVersionText = $ver39
            Write-Host "  Found: $ver39  (via 'py -3.9')" -ForegroundColor Green
        }
    } catch { }
}

# Fallback to direct executables on PATH.
if (-not $PythonExe) {
    foreach ($cmd in @("python3.8", "python3.9")) {
        try {
            $ver = & $cmd --version 2>&1
            if ($ver -match "Python (3\.[89]\.)") {
                $PythonExe = $cmd
                $PythonArgs = @()
                $PythonVersionText = $ver
                Write-Host "  Found: $ver  (via '$cmd')" -ForegroundColor Green
                break
            }
        } catch { }
    }
}

if (-not $PythonExe) {
    Write-Host ""
    Write-Host "ERROR: Python 3.8 or 3.9 not found." -ForegroundColor Red
    Write-Host @"

To fix this, install Python 3.8 or 3.9 and make sure the py launcher can find it:
  Option A (recommended): Install from https://www.python.org/downloads/
                          and check 'Add to PATH'.
  Option B (conda):       conda create -n microrts032 python=3.8
                          conda activate microrts032
                          pip install -r reference_env/requirements_reference.txt
  Option C (manual venv): If you have python3.8 on PATH but not via py launcher,
                          run:  python3.8 -m venv "$VenvPath"
                          then: pip install -r "$ReqFile"

After creating the env manually, run verify_reference_env.py to validate it.
"@
    exit 1
}

if ($PythonVersionText -match "Python (3\.[89])") {
    $PythonMajorMinor = $matches[1]
}

if (-not $PythonMajorMinor) {
    $detected = & $PythonExe @PythonArgs --version 2>&1
    if ($detected -match "Python (3\.[89])") {
        $PythonMajorMinor = $matches[1]
        $PythonVersionText = $detected
    }
}

$SelectedReqFile = $ReqFilePy38
if ($PythonMajorMinor -eq "3.9") {
    $SelectedReqFile = $ReqFilePy39
}

if (-not (Test-Path $SelectedReqFile)) {
    Write-Error "Selected requirements file not found: $SelectedReqFile"
    exit 1
}

Write-Host "  Selected Python version : $PythonVersionText" -ForegroundColor Green
Write-Host "  Selected requirements   : $SelectedReqFile" -ForegroundColor Green
Write-InstallLog "Selected Python version: $PythonVersionText"
Write-InstallLog "Selected requirements file: $SelectedReqFile"

# ---------------------------------------------------------------------------
# Create virtual environment
# ---------------------------------------------------------------------------
Write-Host "[2/6] Creating virtual environment at: $VenvPath" -ForegroundColor Yellow

if ((Test-Path $VenvPath) -and $ForceRecreate) {
    Write-Host "  -ForceRecreate enabled: removing existing venv." -ForegroundColor DarkYellow
    Remove-Item -Recurse -Force $VenvPath
}

if (-not (Test-Path $VenvPath)) {
    & $PythonExe @PythonArgs -m venv $VenvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create virtual environment. Check Python installation."
        exit 1
    }
    Write-Host "  venv created." -ForegroundColor Green
} else {
    Write-Host "  venv already exists - reusing existing venv." -ForegroundColor DarkYellow
}

# ---------------------------------------------------------------------------
# Locate pip inside the venv
# ---------------------------------------------------------------------------
$VenvPip    = Join-Path $VenvPath "Scripts\pip.exe"
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"

if (-not (Test-Path $VenvPip)) {
    Write-Error "pip not found at $VenvPip - venv creation may have failed."
    exit 1
}

Write-Host "[3/6] Staged dependency installation..." -ForegroundColor Yellow
Write-Host "  NOTE: gym-microrts==0.3.2 requires JDK >= 1.8.0 on PATH."
Write-Host ""

$TorchInstallMode = "failed"
$FailedStep = ""

try {
    $FailedStep = "bootstrap_tools"
    Invoke-InstallStep -StepName "bootstrap_tools" -Exe $VenvPython -CmdArgs @("-m", "pip", "install", "--upgrade", "pip<24", "setuptools<66", "wheel<0.38") | Out-Null

    $FailedStep = "numpy_first"
    if ($PythonMajorMinor -eq "3.9") {
        Invoke-InstallStep -StepName "numpy_first" -Exe $VenvPip -CmdArgs @("install", "numpy==1.21.6") | Out-Null
    } else {
        Invoke-InstallStep -StepName "numpy_first" -Exe $VenvPip -CmdArgs @("install", "numpy==1.19.2") | Out-Null
    }
    Write-InstallLog "DEBUG: numpy_first completed"

    $FailedStep = "torch_exact_cpu_wheel"
    $exactOk = Invoke-InstallStep -StepName "torch_exact_cpu_wheel" -Exe $VenvPip -CmdArgs @("install", "torch==1.8.0+cpu", "torchvision==0.9.0+cpu", "-f", "https://download.pytorch.org/whl/torch_stable.html") -AllowFail
    if ($exactOk) {
        $TorchInstallMode = "exact_cpu_wheel"
    } else {
        $FailedStep = "torch_fallback_compat"
        Invoke-InstallStep -StepName "torch_fallback_compat" -Exe $VenvPip -CmdArgs @("install", "torch>=1.10,<1.12", "torchvision>=0.11,<0.13") | Out-Null
        $TorchInstallMode = "fallback_compat"
    }

    $FailedStep = "gym"
    Invoke-InstallStep -StepName "gym" -Exe $VenvPip -CmdArgs @("install", "gym==0.17.3") | Out-Null

    $FailedStep = "jpype1"
    if ($PythonMajorMinor -eq "3.9") {
        Invoke-InstallStep -StepName "jpype1" -Exe $VenvPip -CmdArgs @("install", "JPype1>=1.3,<1.5") | Out-Null
    } else {
        Invoke-InstallStep -StepName "jpype1" -Exe $VenvPip -CmdArgs @("install", "JPype1==1.2.1") | Out-Null
    }

    $FailedStep = "gym_microrts"
    Invoke-InstallStep -StepName "gym_microrts" -Exe $VenvPip -CmdArgs @("install", "gym-microrts==0.3.2") | Out-Null

    $FailedStep = "stable_baselines3"
    Invoke-InstallStep -StepName "stable_baselines3" -Exe $VenvPip -CmdArgs @("install", "stable-baselines3==1.0") | Out-Null

    $RequirementLines = Get-Content $SelectedReqFile |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ -and (-not $_.StartsWith("#")) }

    $RemainingPackages = @($RequirementLines | Where-Object {
        $line = $_
        -not (
            $line -match '^numpy([<>=!~].*)?$' -or
            $line -match '^torch([<>=!~].*)?$' -or
            $line -match '^torchvision([<>=!~].*)?$' -or
            $line -match '^gym([<>=!~].*)?$' -or
            $line -match '^gym-microrts([<>=!~].*)?$' -or
            $line -match '^stable-baselines3([<>=!~].*)?$' -or
            $line -match '^JPype1([<>=!~].*)?$'
        )
    })

    if ($RemainingPackages.Count -gt 0) {
        $FailedStep = "remaining_utilities"
        Invoke-InstallStep -StepName "remaining_utilities" -Exe $VenvPip -CmdArgs (@("install") + $RemainingPackages) | Out-Null
    }
} catch {
    Write-Host ""
    Write-Host "ERROR: install failed at step '$FailedStep'" -ForegroundColor Red
    Write-Host "Details are saved in: $InstallLog" -ForegroundColor Red
    Write-InstallLog ("INSTALL_ABORTED_AT_STEP: " + $FailedStep)
    Write-InstallLog ("INSTALL_EXCEPTION: " + ($_.Exception.Message))
    Write-InstallLog ("INSTALL_ERROR_RECORD: " + ($_ | Out-String))
    Write-Host ("Error details: " + ($_ | Out-String)) -ForegroundColor Red
    Write-Host "Torch install mode: $TorchInstallMode" -ForegroundColor DarkYellow
    exit 1
}

Write-Host "  Torch install mode: $TorchInstallMode" -ForegroundColor Yellow
Write-InstallLog "Torch install mode: $TorchInstallMode"

# Try to snapshot installed packages for reproducibility.
Write-Host ''
Write-Host ('[4b/6] Capturing package freeze to: ' + $FreezeFile) -ForegroundColor Yellow
try {
    & $VenvPython -m pip freeze | Out-File -FilePath $FreezeFile -Encoding utf8
    if ($LASTEXITCODE -eq 0) {
        Write-Host '  pip freeze saved.' -ForegroundColor Green
    } else {
        Write-Host '  WARNING: pip freeze command did not exit cleanly.' -ForegroundColor DarkYellow
    }
} catch {
    Write-Host ('  WARNING: Could not write pip freeze file: ' + $_.Exception.Message) -ForegroundColor DarkYellow
}

# ---------------------------------------------------------------------------
# Clone gym-microrts-paper (optional)
# ---------------------------------------------------------------------------
Write-Host "[5/6] Checking for gym-microrts-paper reference scripts..." -ForegroundColor Yellow

if (-not (Test-Path $ExternalDir)) {
    New-Item -ItemType Directory -Path $ExternalDir | Out-Null
}

if (Test-Path $PaperRepo) {
    Write-Host "  gym-microrts-paper already present at: $PaperRepo" -ForegroundColor Green
} else {
    $GitAvailable = $null
    try { $GitAvailable = & git --version 2>&1 } catch { }

    if ($GitAvailable -and $GitAvailable -match "git version") {
        Write-Host "  Cloning $PaperRepoUrl ..."
        git clone $PaperRepoUrl $PaperRepo
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  WARNING: git clone failed. Clone manually:" -ForegroundColor DarkYellow
            Write-Host "    git clone $PaperRepoUrl $PaperRepo" -ForegroundColor DarkYellow
        } else {
            Write-Host "  Cloned successfully." -ForegroundColor Green
        }
    } else {
        Write-Host "  git not found. Clone manually:" -ForegroundColor DarkYellow
        Write-Host "    git clone $PaperRepoUrl $PaperRepo" -ForegroundColor DarkYellow
        Write-Host "  or download ZIP from: $PaperRepoUrl/archive/refs/heads/master.zip" -ForegroundColor DarkYellow
    }
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[6/6] Setup complete." -ForegroundColor Green
Write-Host ""
Write-Host "Selected Python version : $PythonVersionText" -ForegroundColor Cyan
Write-Host "Selected requirements  : $SelectedReqFile" -ForegroundColor Cyan
Write-Host "Torch install mode     : $TorchInstallMode" -ForegroundColor Cyan
if ($TorchInstallMode -eq "fallback_compat") {
    Write-Host "NOTE: compatibility fallback used for torch/torchvision; this is not exact paper pin." -ForegroundColor DarkYellow
}
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Activate the env:"
Write-Host "       $VenvPath\Scripts\Activate.ps1"
Write-Host "  2. Verify the environment:"
Write-Host "       python $ScriptDir\verify_reference_env.py"
Write-Host "  3. Run smoke training:"
Write-Host "       $ScriptDir\run_reference_training_smoke.ps1"
Write-Host "  4. Re-freeze dependencies (optional):"
Write-Host "       $VenvPython -m pip freeze > $FreezeFile"
Write-Host ""
Write-Host "IMPORTANT: Do NOT use this env for the main Week5/Week6 pipeline." -ForegroundColor DarkYellow
Write-Host "           It is ONLY for reference reproduction experiments." -ForegroundColor DarkYellow
