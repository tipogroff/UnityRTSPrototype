
<# Stage7B-9.1: PPO smoke rerun with native exit code preservation #>
param(
    [string]$LogDir = "python/stage7b_teacher_replay",
    [string]$StdoutFile = "stage7b_9_1_ppo_trainer_native_exit_stdout.log",
    [string]$StderrFile = "stage7b_9_1_ppo_trainer_native_exit_stderr.log"
)

$StdoutPath = Join-Path $LogDir $StdoutFile
$StderrPath = Join-Path $LogDir $StderrFile

"Stage7B-9.1 PPO smoke native exit code preservation rerun" | Out-Host
"Stdout: $StdoutPath" | Out-Host
"Stderr: $StderrPath" | Out-Host
"---" | Out-Host

$trainerExe = "python/stage7b_mlagents/.venv_mlagents/Scripts/mlagents-learn.exe"
$configPath = "config/stage7b_ppo_finetune_smoke.yaml"

# Use Start-Process to preserve native exit code
$proc = Start-Process -FilePath $trainerExe `
    -ArgumentList @($configPath, "--run-id", "Stage7B_PPOFineTuneSmoke_002", "--initialize-from", "Stage7B_ImitationSmoke_010_PostKickConfirm", "--force") `
    -NoNewWindow `
    -PassThru `
    -RedirectStandardOutput $StdoutPath `
    -RedirectStandardError $StderrPath

$proc | Wait-Process
$nativeExitCode = $proc.ExitCode

"---" | Out-Host
"Trainer process exited with code: $nativeExitCode" | Out-Host

# Report captured output sizes
if (Test-Path $StdoutPath) {
    $stdoutSize = (Get-Item $StdoutPath).Length
    "Stdout size: $stdoutSize bytes" | Out-Host
}
if (Test-Path $StderrPath) {
    $stderrSize = (Get-Item $StderrPath).Length
    "Stderr size: $stderrSize bytes" | Out-Host
}

exit $nativeExitCode
