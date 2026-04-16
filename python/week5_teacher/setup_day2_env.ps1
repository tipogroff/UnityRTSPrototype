[CmdletBinding()]
param(
    [string]$VenvPath = (Join-Path $PSScriptRoot ".venv_day2_py39"),
    [string]$MicroRTSRepoPath = (Join-Path $env:TEMP "MicroRTS-Py-v0.6.1"),
    [string]$Python39Exe = "",
    [string]$JavaHome = "",
    [string]$AntBin = "",
    [switch]$InstallPrerequisites,
    [switch]$RunSmokeCheck,
    [int]$SmokeSeed = 17
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [string[]]$ArgumentList = @()
    )

    Write-Host "> $FilePath $($ArgumentList -join ' ')"
    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($ArgumentList -join ' ')"
    }
}

function Resolve-Python39 {
    param([string]$PreferredPath)

    if ($PreferredPath) {
        if (-not (Test-Path $PreferredPath)) {
            throw "Provided Python39Exe does not exist: $PreferredPath"
        }
        return (Resolve-Path $PreferredPath).Path
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        $resolved = & $pyLauncher.Source -3.9 -c "import sys; print(sys.executable)"
        if ($LASTEXITCODE -eq 0 -and $resolved) {
            return ($resolved | Select-Object -Last 1).Trim()
        }
    }

    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        $majorMinor = & $pythonCmd.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
        if ($LASTEXITCODE -eq 0 -and ($majorMinor | Select-Object -Last 1).Trim() -eq "3.9") {
            return $pythonCmd.Source
        }
    }

    throw "Python 3.9 was not found. Install it first, or pass -Python39Exe explicitly."
}

Write-Host "[Day2 setup] Starting setup_day2_env.ps1"

if ($InstallPrerequisites) {
    Write-Host "[Day2 setup] Installing Python 3.9 and Java 17 via winget"
    Invoke-External -FilePath "winget" -ArgumentList @(
        "install", "-e", "--id", "Python.Python.3.9",
        "--accept-package-agreements", "--accept-source-agreements"
    )
    Invoke-External -FilePath "winget" -ArgumentList @(
        "install", "-e", "--id", "EclipseAdoptium.Temurin.17.JDK",
        "--accept-package-agreements", "--accept-source-agreements"
    )
}

$python39 = Resolve-Python39 -PreferredPath $Python39Exe
Write-Host "[Day2 setup] Python 3.9: $python39"

$week5Root = $PSScriptRoot
$requirementsFile = Join-Path $week5Root "requirements_day2_canonical.txt"
$rolloutScript = Join-Path $week5Root "run_teacher_rollout.py"

if (-not (Test-Path $requirementsFile)) {
    throw "Requirements file not found: $requirementsFile"
}
if (-not (Test-Path $rolloutScript)) {
    throw "Rollout script not found: $rolloutScript"
}

$venvFullPath = (Resolve-Path (Split-Path $VenvPath -Parent) -ErrorAction SilentlyContinue)
if (-not $venvFullPath) {
    New-Item -ItemType Directory -Path (Split-Path $VenvPath -Parent) -Force | Out-Null
}

Invoke-External -FilePath $python39 -ArgumentList @("-m", "venv", $VenvPath)
$venvPython = Join-Path $VenvPath "Scripts/python.exe"
if (-not (Test-Path $venvPython)) {
    throw "Virtual environment python.exe not found: $venvPython"
}

Invoke-External -FilePath $venvPython -ArgumentList @("-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel")
Invoke-External -FilePath $venvPython -ArgumentList @("-m", "pip", "install", "-r", $requirementsFile)

$gitCmd = Get-Command git -ErrorAction SilentlyContinue
if (-not $gitCmd) {
    throw "git is required but was not found in PATH."
}

if (-not (Test-Path $MicroRTSRepoPath)) {
    Write-Host "[Day2 setup] Cloning MicroRTS-Py v0.6.1 into $MicroRTSRepoPath"
    Invoke-External -FilePath $gitCmd.Source -ArgumentList @(
        "clone",
        "--branch", "v0.6.1",
        "--depth", "1",
        "--recurse-submodules",
        "https://github.com/Farama-Foundation/MicroRTS-Py.git",
        $MicroRTSRepoPath
    )
} else {
    Write-Host "[Day2 setup] Reusing existing repository at $MicroRTSRepoPath"
    Invoke-External -FilePath $gitCmd.Source -ArgumentList @("-C", $MicroRTSRepoPath, "fetch", "--tags", "--depth", "1", "origin", "v0.6.1")
    Invoke-External -FilePath $gitCmd.Source -ArgumentList @("-C", $MicroRTSRepoPath, "checkout", "v0.6.1")
    Invoke-External -FilePath $gitCmd.Source -ArgumentList @("-C", $MicroRTSRepoPath, "submodule", "update", "--init", "--recursive")
}

Invoke-External -FilePath $venvPython -ArgumentList @("-m", "pip", "install", "-e", $MicroRTSRepoPath)

if ($JavaHome) {
    $resolvedJavaHome = (Resolve-Path $JavaHome).Path
    $env:JAVA_HOME = $resolvedJavaHome
}

if (-not $env:JAVA_HOME) {
    throw "JAVA_HOME is not set. Pass -JavaHome or set JAVA_HOME before running this script."
}

$javaBin = Join-Path $env:JAVA_HOME "bin"
if (-not (Test-Path $javaBin)) {
    throw "JAVA_HOME/bin was not found: $javaBin"
}

if ($AntBin) {
    $resolvedAntBin = (Resolve-Path $AntBin).Path
    $env:Path = "$javaBin;$resolvedAntBin;$env:Path"
} else {
    $env:Path = "$javaBin;$env:Path"
}

$antCmd = Get-Command ant.bat -ErrorAction SilentlyContinue
if (-not $antCmd) {
    $antCmd = Get-Command ant -ErrorAction SilentlyContinue
}
if (-not $antCmd) {
    throw "Apache Ant was not found in PATH. Install Ant and/or pass -AntBin."
}

$buildXml = Join-Path $MicroRTSRepoPath "gym_microrts/microrts/build.xml"
$builtJar = Join-Path $MicroRTSRepoPath "gym_microrts/microrts/build/microrts.jar"
$targetJar = Join-Path $MicroRTSRepoPath "gym_microrts/microrts/microrts.jar"

if (-not (Test-Path $buildXml)) {
    throw "build.xml was not found: $buildXml"
}

Invoke-External -FilePath $antCmd.Source -ArgumentList @("-f", $buildXml, "export_jar")
if (-not (Test-Path $builtJar)) {
    throw "Built jar was not found after Ant build: $builtJar"
}
Copy-Item -Force -Path $builtJar -Destination $targetJar

if (-not (Test-Path $targetJar)) {
    throw "Target jar copy failed: $targetJar"
}

Write-Host "[Day2 setup] Completed successfully"
Write-Host "[Day2 setup] Venv python: $venvPython"
Write-Host "[Day2 setup] JAVA_HOME: $env:JAVA_HOME"
Write-Host "[Day2 setup] microrts.jar: $targetJar"

if ($RunSmokeCheck) {
    Write-Host "[Day2 setup] Running smoke rollout check"
    Invoke-External -FilePath $venvPython -ArgumentList @(
        $rolloutScript,
        "--episodes", "1",
        "--env-id", "MicrortsSelfPlayShapedReward-v1",
        "--map-path", "maps/24x24/basesWorkers24x24.xml",
        "--seed", "$SmokeSeed",
        "--allow-random-policy-smoke-fallback",
        "--rollout-step-limit", "64"
    )
}
