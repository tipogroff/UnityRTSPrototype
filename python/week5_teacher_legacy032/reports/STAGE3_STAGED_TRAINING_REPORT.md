# Stage 3 Staged Training Report (legacy032)

Stage name: Stage 3 - Staged teacher training with behavior gates
Date: 2026-04-29

## Summary

- Stage 2 deferred inference warning is closed.
- Evaluator script is implemented and used on Stage 2 smoke checkpoint.
- First staged sanity training run (100k) completed.
- 100k checkpoint behavior gate completed.
- Current Stage 3 status: PASS_WITH_WARNINGS.

Main warning that remains:

- env/action mismatch remains: reference internal 16x16 contract vs preflight target 24x24 contract.

## Stage 2 checkpoint evaluator result

Input checkpoint:

- python/week5_teacher_legacy032/teacher_models/legacy032_smoke_20260429T113844Z/agent_final.pt

Gate artifacts:

- python/week5_teacher_legacy032/reports/stage3_smoke_checkpoint_behavior_gate_20260429T122219Z.json
- python/week5_teacher_legacy032/reports/stage3_smoke_checkpoint_behavior_gate_20260429T122219Z.md

Result:

- checkpoint_load_ok: true
- policy_architecture_load_ok: true
- inference_ok: true
- mask_used_during_eval: true
- gate_decision: PASS_WITH_WARNINGS
- warning: evaluable on reference internal env/action space only, not on target preflight 24x24

## Staged training strategy

Reference script capabilities:

- supports local intermediate checkpoints via --local-save-every
- does not provide robust local non-wandb resume from saved local checkpoints

Strategy chosen for Stage 3:

- Stage 3A executed with 100k sanity run
- behavior gate executed after produced stage checkpoint
- longer stages remain planned and command-ready

## Stages planned

- 100000 (sanity)
- 500000 (early behavior)
- 1000000 (first useful candidate)
- 3000000 (main candidate)
- 5000000 (strong candidate)
- 10000000 (optional if quality continues to improve)

## Stages actually run

- 100000

Run id:

- legacy032_teacher_main_20260429T120524Z

Primary run artifacts:

- python/week5_teacher_legacy032/teacher_models/legacy032_teacher_main_20260429T120524Z/stage_000100000/agent_final.pt
- python/week5_teacher_legacy032/teacher_models/legacy032_teacher_main_20260429T120524Z/stage_000100000/model_metadata.json
- python/week5_teacher_legacy032/teacher_logs/legacy032_teacher_main_20260429T120524Z/stage_000100000/training_stdout.log
- python/week5_teacher_legacy032/teacher_logs/legacy032_teacher_main_20260429T120524Z/stage_000100000/training_stderr.log

## Checkpoint table

| timesteps | checkpoint path | training status | eval status | mean return | non_noop_share | move_share | attack_share | produce_share | mask used | env/mapping warning | gate decision |
|---|---|---|---|---:|---:|---:|---:|---:|---|---|---|
| 100000 | python/week5_teacher_legacy032/teacher_models/legacy032_teacher_main_20260429T120524Z/stage_000100000/agent_final.pt | PASS | PASS | -7.5 | 0.8335067195595856 | 0.16538617227979274 | 0.16553257232297064 | 0.16817924222797928 | true | checkpoint evaluable only on reference internal 16x16 action space, not target preflight 24x24 | PASS_WITH_WARNINGS |

Gate artifact used for the row above:

- python/week5_teacher_legacy032/reports/stage3_gate_000100000_20260429T122246Z.json
- python/week5_teacher_legacy032/reports/stage3_gate_000100000_20260429T122246Z.md

## Best checkpoint so far

- best checkpoint so far: 100k stage checkpoint
- reason:
  - only staged checkpoint run so far
  - behavior gate succeeded with PASS_WITH_WARNINGS
  - policy inference, mask usage, and action distribution recording are all confirmed

## Next recommended stage

- Continue to 500k with behavior gate after checkpoint.
- Keep env mismatch warning explicit in each report until training/eval pipeline is aligned for 24x24 target contract.

## Prepared commands (not auto-executed)

500k:

powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe python/week5_teacher_legacy032/scripts/run_staged_teacher_training_legacy032.py --run-label legacy032_teacher_main --stages 500000 --seed 17 --device cpu --episodes-per-gate 8 --evaluate-after-each --no-wandb

1M:

powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe python/week5_teacher_legacy032/scripts/run_staged_teacher_training_legacy032.py --run-label legacy032_teacher_main --stages 1000000 --seed 17 --device cpu --episodes-per-gate 8 --evaluate-after-each --no-wandb

3M:

powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe python/week5_teacher_legacy032/scripts/run_staged_teacher_training_legacy032.py --run-label legacy032_teacher_main --stages 3000000 --seed 17 --device cpu --episodes-per-gate 8 --evaluate-after-each --no-wandb

5M:

powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe python/week5_teacher_legacy032/scripts/run_staged_teacher_training_legacy032.py --run-label legacy032_teacher_main --stages 5000000 --seed 17 --device cpu --episodes-per-gate 8 --evaluate-after-each --no-wandb
