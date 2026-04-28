#!/usr/bin/env pwsh
# run_gridnet_teacher_fresh_100k_v2.ps1
# Clean fresh Branch B Gridnet teacher training: 0 -> 100k on v2-compatible pipeline.
# No resume checkpoint. No resume metadata. initial_global_step = 0.

$ErrorActionPreference = 'Stop'

# ─── Environment ──────────────────────────────────────────────────────────────
$env:JAVA_HOME = 'C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path      = "$env:JAVA_HOME\bin;$env:Path"

$PY = 'c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/.venv_day2_py39/Scripts/python.exe'
$SCRIPT = 'c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_gridnet/train_teacher_gridnet_project.py'

# ─── Run provenance check ──────────────────────────────────────────────────────
$TIMESTAMP = (Get-Date -Format 'yyyyMMddTHHmmssZ').Replace(':', '')
$RUN_ID    = "gridnet_fresh_100k_v2_$TIMESTAMP"

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "  FRESH 100k Branch B Gridnet Teacher v2" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "  run_id               : $RUN_ID"
Write-Host "  resume_from_checkpoint: none  (FRESH RUN)"
Write-Host "  resume_model_metadata : none  (FRESH RUN)"
Write-Host "  initial_global_step  : 0     (FRESH RUN)"
Write-Host "  total_timesteps      : 100000"
Write-Host "  checkpoint_steps     : 20000,50000,100000"
Write-Host "  seed                 : 1"
Write-Host "  device               : cpu"
Write-Host "====================================================" -ForegroundColor Cyan

# ─── Launch training ──────────────────────────────────────────────────────────
& $PY $SCRIPT `
    --run-id                  $RUN_ID `
    --total-timesteps         100000 `
    --checkpoint-steps        "20000,50000,100000" `
    --initial-global-step     0 `
    --num-bot-envs            6 `
    --num-selfplay-envs       0 `
    --seed                    1 `
    --device                  cpu `
    --eval-after-checkpoint `
    --map-path                "maps/24x24/basesWorkers24x24.xml" `
    --output-root             "WEEK5R/gridnet_teacher_runs"

$EXIT = $LASTEXITCODE
Write-Host ""
if ($EXIT -eq 0) {
    Write-Host "[OK] Training completed successfully. run_id=$RUN_ID" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Training exited with code $EXIT" -ForegroundColor Red
    exit $EXIT
}
