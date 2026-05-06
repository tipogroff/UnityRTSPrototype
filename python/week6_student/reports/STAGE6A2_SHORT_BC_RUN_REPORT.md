# Stage6A2 Short BC Run Report

## 1. Executive Summary

Final decision: `STAGE6A2_SHORT_BC_RUN_PASS_READY_FOR_UNITY_BRIDGE_FIX`

Stage6A2 completed a preflight regression and a short bounded BC run using the canonical Stage5P4 dataset and transfer model. Training remained bounded by explicit batch caps, produced finite losses, saved a checkpoint, and passed load-only compatibility validation with transfer architecture and correct head shapes `[6,4,4,4,4,7,49]`.

## 2. Commands Executed

Preflight regression:

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe \
  python/week6_student/scripts/train_student_bc_smoke_legacy032_v2.py \
  --bc-ready-dir python/week5_teacher_legacy032/teacher_exports_bc/legacy032_3m_unity_v2_bc_ready_stage5p4_20260506T153632Z \
  --device cpu \
  --batch-size 16 \
  --seed 17 \
  --output-dir python/week6_student/runs/legacy032_v2_bc_short_stage6a2_preflight \
  --run-label legacy032_v2_bc_short_stage6a2_preflight \
  --contract-check-only true \
  --dry-run-only true
```

Short bounded BC run:

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe \
  python/week6_student/scripts/train_student_bc_smoke_legacy032_v2.py \
  --bc-ready-dir python/week5_teacher_legacy032/teacher_exports_bc/legacy032_3m_unity_v2_bc_ready_stage5p4_20260506T153632Z \
  --device cpu \
  --epochs 3 \
  --batch-size 16 \
  --max-train-batches 200 \
  --max-validation-batches 50 \
  --seed 17 \
  --output-dir python/week6_student/runs/legacy032_v2_bc_short_stage6a2 \
  --run-label legacy032_v2_bc_short_stage6a2 \
  --model-variant transfer \
  --save-checkpoint true \
  --contract-check-only false \
  --dry-run-only false
```

Loader help probe:

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe \
  python/week6_student/load_student_checkpoint.py \
  --help
```

Checkpoint compatibility load-only check was executed via a temporary Python script using `load_student_transfer_checkpoint` and dummy forward on `[1,24,24,27]`, then writing:

- `python/week6_student/runs/legacy032_v2_bc_short_stage6a2/stage6a2_checkpoint_compatibility_report.json`

## 3. Dataset And Contract Summary

Canonical dataset:

- `python/week5_teacher_legacy032/teacher_exports_bc/legacy032_3m_unity_v2_bc_ready_stage5p4_20260506T153632Z`

Contract checks passed:

- `dataset_type = bc_ready_legacy032_unity_v2`
- `target_action_contract = unity_v2_legacy032_gridnet`
- `branch_sizes = [6,4,4,4,4,7,49]`
- `attack_target_semantics = local_7x7_49`
- `semantic_parity_claim = false`
- `direct_weight_transfer_claim = false`

## 4. Preflight Regression Result

Status: `pass`

- No optimizer step.
- No weight updates.
- Forward head shapes confirmed at batch-size 16:
  - `[16,576,6]`
  - `[16,576,4]`
  - `[16,576,4]`
  - `[16,576,4]`
  - `[16,576,4]`
  - `[16,576,7]`
  - `[16,576,49]`

Artifact:

- `python/week6_student/runs/legacy032_v2_bc_short_stage6a2_preflight/legacy032_v2_bc_short_stage6a2_preflight_contract_check_report.json`

## 5. Short BC Run Configuration

- `epochs = 3`
- `batch_size = 16`
- `max_train_batches = 200`
- `max_validation_batches = 50`
- `seed = 17`
- `device = cpu`
- `model_variant = transfer`
- `save_checkpoint = true`

Actual bounded execution:

- `train_batches_executed = 600` (3 x 200)
- `validation_batches_executed = 150` (3 x 50)
- `optimizer_step_count = 600`

## 6. Training Metrics

- `train_total_loss_first = 1.8422220008831738`
- `train_total_loss_last = 1.8380480182920613`
- `train_total_loss_mean = 1.8395045848981049`
- `no_nan_inf_loss = true`

Per-branch train losses:

- `train_action_type_loss = 1.7812571620941162`
- `train_move_dir_loss = 1.384849916267975`
- `train_harvest_dir_loss = 1.386543658334099`
- `train_return_dir_loss = 1.3866232715437563`
- `train_produce_dir_loss = 1.386144718027984`
- `train_produce_unit_type_loss = 1.9432843570080052`
- `train_attack_target_local_loss = 3.8930794881428414`

Per-branch train accuracies:

- `train_action_type_accuracy = 0.17157552083333333`
- `train_move_dir_accuracy = 0.2529988325400593`
- `train_harvest_dir_accuracy = 0.2518864487499713`
- `train_return_dir_accuracy = 0.24987700966212095`
- `train_produce_dir_accuracy = 0.2502908295048997`
- `train_produce_unit_type_accuracy = 0.14570393885022115`
- `train_attack_target_local_accuracy = 0.020446309990326126`

## 7. Validation Metrics

- `validation_total_loss_mean = 1.8386250157253297`

Per-branch validation losses:

- `val_action_type_loss = 1.7838045014275445`
- `val_move_dir_loss = 1.3842286771036407`
- `val_harvest_dir_loss = 1.386941997462141`
- `val_return_dir_loss = 1.3867354560065936`
- `val_produce_dir_loss = 1.3863667319105364`
- `val_produce_unit_type_loss = 1.9428623729588366`
- `val_attack_target_local_loss = 3.893301584221406`

Per-branch validation accuracies:

- `val_action_type_accuracy = 0.16974609375`
- `val_move_dir_accuracy = 0.25149269096149884`
- `val_harvest_dir_accuracy = 0.24864249545317754`
- `val_return_dir_accuracy = 0.25197293512544333`
- `val_produce_dir_accuracy = 0.24828921716147434`
- `val_produce_unit_type_accuracy = 0.14647964724508356`
- `val_attack_target_local_accuracy = 0.021162208459612596`

## 8. Checkpoint Files

- Main run checkpoint:
  - `python/week6_student/runs/legacy032_v2_bc_short_stage6a2/legacy032_v2_bc_short_stage6a2_smoke_checkpoint.pt`
- Main run report JSON:
  - `python/week6_student/runs/legacy032_v2_bc_short_stage6a2/legacy032_v2_bc_short_stage6a2_smoke_training_report.json`
- Main run report MD:
  - `python/week6_student/runs/legacy032_v2_bc_short_stage6a2/legacy032_v2_bc_short_stage6a2_smoke_training_report.md`

## 9. Checkpoint Compatibility/Load-Only Validation

Status: `pass`

Compatibility report:

- `python/week6_student/runs/legacy032_v2_bc_short_stage6a2/stage6a2_checkpoint_compatibility_report.json`

Validation details:

- `loadable_by_transfer_loader = true`
- `model_variant = transfer`
- `state_dict_key_count = 76`
- `missing_keys = []`
- `unexpected_keys = []`
- Dummy input `[1,24,24,27]` forward head shapes:
  - `[1,576,6]`
  - `[1,576,4]`
  - `[1,576,4]`
  - `[1,576,4]`
  - `[1,576,4]`
  - `[1,576,7]`
  - `[1,576,49]`
- `produce_head_size = 7`
- `attack_head_size = 49`
- `v1_regression_detected = false`
- `head_shape_mismatch = {}`

## 10. Warnings

- This is still a short bounded run and not a full optimization campaign.
- Loss movement is modest, which is acceptable for this stage objective.

## 11. Remaining Unity Blockers

Not modified in Stage6A2:

- `Assets/Scripts/ML/Week6StudentPolicyAdapter.cs` checkpoint path / filename gating
- `Assets/Scripts/ML/Week6Day4StudentInferenceDryRun.cs` stale default checkpoint path

## 12. Final Decision

`STAGE6A2_SHORT_BC_RUN_PASS_READY_FOR_UNITY_BRIDGE_FIX`

## 13. Recommended Next Stage

`Stage6R2 — Unity Bridge Checkpoint Path / Filename Gating Fix`
