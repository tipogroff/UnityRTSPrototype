# Legacy032 Local Resume And Checkpointing

## Scope

This document defines the current local checkpoint and resume behavior for:

- python/week5_teacher_legacy032/scripts/ppo_gridnet_legacy032_24x24_local_save.py
- python/week5_teacher_legacy032/scripts/run_24x24_staged_teacher_training_legacy032.py

## Historical Note (Pre-Resume Checkpoints)

Before full local resume support, local artifacts were weights-only snapshots:

- agent_final.pt
- agent_step_<global_step>.pt

These old checkpoints are valid for inference/eval/export, but they are not complete training checkpoints because optimizer state, RNG state, and update-state were not persisted.

Historical limitation statement:

- If resume was not implemented/validated, treat later stage targets as from-scratch runs.

This statement only applies to pre-resume checkpoints.

## New Behavior

Full local training checkpoints are now supported.

Weights snapshots remain unchanged for inference compatibility:

- agent_final.pt
- agent_step_<global_step>.pt

New full training checkpoint artifacts:

- trainer_state_final.pt
- trainer_state_step_<global_step>.pt
- latest_trainer_state.json

Summary:

- agent_final.pt is the inference/export snapshot.
- trainer_state_final.pt is the training resume checkpoint.

## Full Checkpoint Schema

Schema version:

- legacy032.full_training_checkpoint.v1

Checkpoint kind:

- full_training_state

Full checkpoint payload includes at minimum:

- global_step/update/num_updates_completed
- agent_state_dict
- optimizer_state_dict
- args
- training_config
- environment_contract
- rng_state
- device_info
- source_script
- notes

## Resume Semantics

Resume restores:

- model parameters (strict=True)
- optimizer state
- RNG state (python/numpy/torch, and CUDA RNG when available)
- global_step
- update / num_updates_completed

Important limitation:

- Java environment internal state is not serialized.
- Resume is training-state continuation, not guaranteed bitwise mid-episode replay.

## New Staged Semantics

Stage targets are cumulative totals when local resume is enabled:

- 100k -> 500k -> 3M is a real continuation chain when local-resume-mode is auto or required.

Schedule semantics:

- --schedule-total-timesteps auto uses max(stages).
- LR annealing uses schedule_total_timesteps horizon, not only the current stage target.

## Orchestrator Controls

Key flags in run_24x24_staged_teacher_training_legacy032.py:

- --local-resume-mode none|auto|required
- --full-checkpoint-required true|false
- --save-full-training-state true|false
- --schedule-total-timesteps auto|<int>

Behavior summary:

- local-resume-mode=required: fail if previous full checkpoint is missing.
- local-resume-mode=auto: resume from previous stage full checkpoint; if missing, fail by default (unless full-checkpoint-required=false).
- local-resume-mode=none: from-scratch stages; reports include RESUME_DISABLED_FROM_SCRATCH_STAGE.

## Canonical Training Command (PowerShell)

```powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"

c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
  python/week5_teacher_legacy032/scripts/run_24x24_staged_teacher_training_legacy032.py `
  --run-label legacy032_24x24_teacher_resume_main `
  --stages 100000,500000,3000000 `
  --seed 17 `
  --device cpu `
  --map-path maps/24x24/basesWorkers24x24.xml `
  --training-max-steps 6000 `
  --episodes-per-gate 8 `
  --max-steps-per-gate 6000 `
  --evaluate-after-each `
  --no-wandb `
  --require-contract-check true `
  --local-resume-mode required `
  --save-full-training-state true `
  --schedule-total-timesteps auto
```

## Compatibility For Eval/Export

Evaluation/export scripts support both:

- weights-only checkpoints (agent_final.pt / agent_step_*.pt)
- full checkpoints (trainer_state_final.pt / trainer_state_step_*.pt, via agent_state_dict extraction)

Strict loading default:

- strict=True by default.
- strict=False only with explicit --strict-load false and machine-readable warning STRICT_LOAD_STATUS=STRICT_LOAD_OPT_OUT.

## Legacy Baseline

The old 3M checkpoint remains a historical baseline and may be provably incomplete as a training resume checkpoint if it was produced by the old weights-only save path.
