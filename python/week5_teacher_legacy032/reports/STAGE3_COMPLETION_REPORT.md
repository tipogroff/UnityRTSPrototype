# Stage 3 Completion Report (legacy032)

Date: 2026-04-29
Stage name: Stage 3 - Staged teacher training with behavior gates

## Files created or updated

Created:

- python/week5_teacher_legacy032/scripts/evaluate_teacher_legacy032.py
- python/week5_teacher_legacy032/scripts/run_staged_teacher_training_legacy032.py
- python/week5_teacher_legacy032/reports/STAGE3_PRETRAINING_AUDIT.md
- python/week5_teacher_legacy032/reports/STAGE3_STAGED_TRAINING_REPORT.md
- python/week5_teacher_legacy032/reports/STAGE3_COMPLETION_REPORT.md
- python/week5_teacher_legacy032/reports/stage3_smoke_checkpoint_behavior_gate_20260429T122219Z.json
- python/week5_teacher_legacy032/reports/stage3_smoke_checkpoint_behavior_gate_20260429T122219Z.md
- python/week5_teacher_legacy032/reports/stage3_gate_000100000_20260429T122246Z.json
- python/week5_teacher_legacy032/reports/stage3_gate_000100000_20260429T122246Z.md
- python/week5_teacher_legacy032/reports/stage3_training_20260429T120524Z.json
- python/week5_teacher_legacy032/reports/stage3_training_20260429T120524Z.md

Updated:

- python/week5_teacher_legacy032/LEGACY032_TEACHER_TRAINING_PLAN.md
- python/week5_teacher_legacy032/scripts/README.md

## Commands run

1) Stage 2 smoke checkpoint behavior gate (deferred inference closure):

powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe python/week5_teacher_legacy032/scripts/evaluate_teacher_legacy032.py --checkpoint-path python/week5_teacher_legacy032/teacher_models/legacy032_smoke_20260429T113844Z/agent_final.pt --model-metadata-path python/week5_teacher_legacy032/teacher_models/legacy032_smoke_20260429T113844Z/model_metadata.json --run-label stage3_smoke_checkpoint_behavior_gate --episodes 8 --seed 101 --device cpu --output-dir python/week5_teacher_legacy032/reports --eval-mode both --env-mode auto --require-mask true --max-steps-per-episode 2000

2) Stage 3A 100k staged training sanity run:

powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe python/week5_teacher_legacy032/scripts/run_staged_teacher_training_legacy032.py --run-label legacy032_teacher_main --stages 100000 --seed 17 --device cpu --episodes-per-gate 8 --evaluate-after-each --no-wandb

3) Explicit 100k behavior gate refresh with final evaluator:

powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe python/week5_teacher_legacy032/scripts/evaluate_teacher_legacy032.py --checkpoint-path python/week5_teacher_legacy032/teacher_models/legacy032_teacher_main_20260429T120524Z/stage_000100000/agent_final.pt --model-metadata-path python/week5_teacher_legacy032/teacher_models/legacy032_teacher_main_20260429T120524Z/stage_000100000/model_metadata.json --run-label stage3_gate_000100000 --episodes 8 --seed 17 --device cpu --output-dir python/week5_teacher_legacy032/reports --eval-mode both --env-mode auto --require-mask true --max-steps-per-episode 2000

## Outcome

- Stage 3 successfully started.
- Policy inference warning from Stage 2 is closed.
- 100k sanity staged checkpoint produced.
- Behavior gate executed for Stage 2 smoke checkpoint and Stage 3A 100k checkpoint.
- Stage 3 current status: PASS_WITH_WARNINGS.

## Mandatory checks

- 100k checkpoint produced: YES
- behavior gate passed: YES (PASS_WITH_WARNINGS)
- deferred policy inference warning closed: YES
- action_type_distribution recorded: YES
- mask usage during eval confirmed: YES
- env/map mismatch remains: YES

Mismatch details:

- training/eval compatible env/action space: reference internal 16x16
- preflight target env/action space: 24x24 global single action
- consequence: checkpoint is evaluable on reference internal contract only, not directly on preflight 24x24 contract

## Exact next action

Continue to 500k staged run and behavior gate while preserving explicit env mismatch warning in reports.
