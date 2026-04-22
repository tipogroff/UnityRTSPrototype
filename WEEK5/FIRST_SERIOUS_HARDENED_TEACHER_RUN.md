# FIRST_SERIOUS_HARDENED_TEACHER_RUN.md

Date: 2026-04-21
Scope: First serious teacher-agent training run on the existing hardened Week 5 pipeline.

## Training intent note

This run is intended as the first serious hardened teacher candidate.
It is not a final paper reproduction claim, not a final-best checkpoint claim, and not a BC run.

Evaluation intent:
- complete hardened training end-to-end;
- produce a checkpoint with explicit backend/mask/policy/opponent metadata;
- evaluate downstream quality through Day 3 rollout export, Day 4 adapter, Day 5 validation, and comparison versus current preferred adapted batch.

## Recommended serious run configuration

Selected config:
- run profile: `throughput_tuned`
- policy architecture: `cnn_preferred`
- action mask mode: `auto` (prefers mask-aware path and records fallback reason if needed)
- backend routing: `allow_fallback`
- opponent pool: `coacAI,workerRushAI,lightRushAI,passiveAI`
- opponent sampling: `per_episode`
- device: `cuda` when available
- run label: `day5_teacher_hardened_serious_v2`

Environment used:
- `python/week5_teacher/.venv_day2_py39` (CUDA-ready torch + gym_microrts + sb3_contrib)

## Recommended training command

```powershell
$env:JAVA_HOME='C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME/bin;$env:Path"

python/week5_teacher/.venv_day2_py39/Scripts/python.exe \
  python/week5_teacher/train_teacher_smoke.py \
  --run-profile throughput_tuned \
  --run-label day5_teacher_hardened_serious_v2 \
  --env-id MicrortsSelfPlayShapedReward-v1 \
  --map-path maps/24x24/basesWorkers24x24.xml \
  --policy-architecture cnn_preferred \
  --action-mask-mode auto \
  --backend-mode allow_fallback \
  --opponent-pool coacAI,workerRushAI,lightRushAI,passiveAI \
  --opponent-sampling per_episode \
  --checkpoint-interval 20000 \
  --seed 17 \
  --device cuda
```

## Expected artifacts

Training artifacts:
- checkpoint: `python/week5_teacher/teacher_models/<run_id>/teacher_sb3_ppo.zip`
- interval checkpoints: `python/week5_teacher/teacher_models/<run_id>/checkpoints/teacher_sb3_ppo_step_<timesteps>.zip`
- latest pointer: `python/week5_teacher/teacher_models/LATEST_DAY5_TEACHER_CHECKPOINT.txt`
- training log: `python/week5_teacher/teacher_logs/<run_id>.log`
- training metadata: `python/week5_teacher/teacher_logs/<run_id>.training.json`

## Expected metadata fields to inspect

Mandatory fields to verify (for honesty and diagnosis):
- `training_backend`
- `mask_regime.requested`
- `mask_regime.effective`
- `mask_regime.fallback_reason`
- `backend_routing.backend_mode`
- `backend_routing.actual_backend`
- `backend_routing.backend_role`
- `backend_routing.fallback_trigger_reason`
- `policy_architecture.requested`
- `policy_architecture.effective`
- `policy_architecture.policy_class`
- `opponent_regime.configured_pool`
- `opponent_regime.configured_sampling`
- `opponent_regime.runtime`
- `profiling.shares`
- `profiling.diagnostic_note`

Interpretation notes:
- If `mask_regime.effective` is `non_mask_aware` while requested is `auto`/`mask_aware`, treat this as a controlled degradation and keep it explicit.
- If `backend_routing.actual_backend` is legacy fallback, treat it as a controlled fallback path and keep it explicit.

## Immediate post-training rollout check

```powershell
$env:JAVA_HOME='C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME/bin;$env:Path"

$CKPT = Get-Content python/week5_teacher/teacher_models/LATEST_DAY5_TEACHER_CHECKPOINT.txt

python/week5_teacher/.venv_day2_py39/Scripts/python.exe \
  python/week5_teacher/run_teacher_rollout.py \
  --policy-path $CKPT \
  --policy-algorithm ppo \
  --checkpoint-env-version 0.0.0 \
  --episodes 6 \
  --batch-mode training \
  --batch-label day5_serious_hardened_candidate \
  --env-id MicrortsSelfPlayShapedReward-v1 \
  --map-path maps/24x24/basesWorkers24x24.xml \
  --backend-mode allow_fallback \
  --opponent-pool coacAI,workerRushAI,lightRushAI,passiveAI \
  --opponent-sampling per_episode \
  --seed 17 \
  --rollout-step-limit 256 \
  --write-jsonl never
```

## Post-training handoff path (Day 4 + Day 5)

1. Identify produced raw rollout batch directory under `python/week5_teacher/teacher_rollouts/teacher_raw_training_day5_serious_hardened_candidate_<timestamp>`.
2. Run Day 4 adapter:

```powershell
python/week5_teacher/.venv_day2_py39/Scripts/python.exe \
  python/week5_teacher/adapt_teacher_dataset.py \
  --input-batch-dir <RAW_BATCH_DIR> \
  --write-debug-jsonl
```

3. Run Day 5 validator:

```powershell
python/week5_teacher/.venv_day2_py39/Scripts/python.exe \
  python/week5_teacher/validate_adapted_dataset.py \
  --adapted-batch-dir <ADAPTED_BATCH_DIR> \
  --strict
```

4. Compare against current preferred adapted batch (`teacher_adapted_day5_first_nonrandom_meaningful`):

```powershell
python/week5_teacher/.venv_day2_py39/Scripts/python.exe \
  python/week5_teacher/compare_day5_reports.py \
  --old-batch-dir python/week5_teacher/teacher_exports/teacher_adapted_day5_first_nonrandom_meaningful \
  --new-batch-dir <ADAPTED_BATCH_DIR> \
  --old-label preferred_old \
  --new-label serious_hardened_candidate \
  --output-md python/week5_teacher/teacher_exports/COMPARE_TEACHER_BATCHES_DAY5_SERIOUS.md \
  --output-json python/week5_teacher/teacher_exports/COMPARE_TEACHER_BATCHES_DAY5_SERIOUS.json
```

## Scope guardrails

Not in scope for this run:
- new training framework;
- BC training;
- Unity import;
- large hyperparameter sweep;
- final paper-equivalence claims.
