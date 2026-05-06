# Stage6A1 BC Smoke Training Enablement Report

## 1. Executive Summary

Final decision: `STAGE6A1_BC_SMOKE_TRAINING_PASS_READY_FOR_SHORT_BC_RUN`

Stage6A1 successfully enabled a controlled, bounded BC smoke training mode inside the Stage6 wrapper while preserving contract-check-only behavior. The smoke run executed with strict batch caps, transfer architecture, Stage5P4 dataset, finite loss, successful backward/optimizer steps, successful validation pass, checkpoint save, and no v1 branch regression.

## 2. Changed Files

- `python/week6_student/scripts/train_student_bc_smoke_legacy032_v2.py`

Runtime-generated artifacts:

- `python/week6_student/runs/legacy032_v2_bc_smoke_stage6a1/legacy032_v2_bc_smoke_stage6a1_smoke_checkpoint.pt`
- `python/week6_student/runs/legacy032_v2_bc_smoke_stage6a1/legacy032_v2_bc_smoke_stage6a1_smoke_training_report.json`
- `python/week6_student/runs/legacy032_v2_bc_smoke_stage6a1/legacy032_v2_bc_smoke_stage6a1_smoke_training_report.md`
- `python/week6_student/runs/legacy032_v2_bc_smoke_stage6a1_preflight/legacy032_v2_bc_smoke_stage6a1_preflight_contract_check_report.json`

## 3. Training Mode Implementation Summary

Wrapper update in `train_student_bc_smoke_legacy032_v2.py`:

- Added dual-mode gating:
  - preflight mode: `--contract-check-only true --dry-run-only true`
  - controlled smoke training mode: `--contract-check-only false --dry-run-only false`
- Kept contract-check-only behavior intact.
- Added bounded train/validation loops using:
  - `build_day3_student_model` (transfer model)
  - `create_dataloader`
  - `compute_branchwise_loss`
  - `Adam`
- Enforced `--model-variant transfer` for canonical smoke path.
- Enforced strict limits:
  - stop train epoch after `--max-train-batches`
  - stop validation after `--max-validation-batches`
- Added checkpoint save only when `--save-checkpoint true`.
- Added smoke report writers (JSON + MD) for training mode.

## 4. Contract-Check-Only Regression Check

Executed command:

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe \
  python/week6_student/scripts/train_student_bc_smoke_legacy032_v2.py \
  --bc-ready-dir python/week5_teacher_legacy032/teacher_exports_bc/legacy032_3m_unity_v2_bc_ready_stage5p4_20260506T153632Z \
  --device cpu \
  --batch-size 8 \
  --seed 17 \
  --output-dir python/week6_student/runs/legacy032_v2_bc_smoke_stage6a1_preflight \
  --run-label legacy032_v2_bc_smoke_stage6a1_preflight \
  --contract-check-only true \
  --dry-run-only true
```

Result: pass

- Contract preflight still validates manifest/splits/head shapes.
- `optimizer_step_executed = false`
- `weights_updated = false`

## 5. Exact Smoke Training Command Executed

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe \
  python/week6_student/scripts/train_student_bc_smoke_legacy032_v2.py \
  --bc-ready-dir python/week5_teacher_legacy032/teacher_exports_bc/legacy032_3m_unity_v2_bc_ready_stage5p4_20260506T153632Z \
  --device cpu \
  --epochs 2 \
  --batch-size 8 \
  --max-train-batches 20 \
  --max-validation-batches 5 \
  --seed 17 \
  --output-dir python/week6_student/runs/legacy032_v2_bc_smoke_stage6a1 \
  --run-label legacy032_v2_bc_smoke_stage6a1 \
  --model-variant transfer \
  --save-checkpoint true \
  --contract-check-only false \
  --dry-run-only false
```

## 6. Dataset Contract Summary

Canonical package:

- `python/week5_teacher_legacy032/teacher_exports_bc/legacy032_3m_unity_v2_bc_ready_stage5p4_20260506T153632Z`

Manifest checks passed:

- `dataset_type = bc_ready_legacy032_unity_v2`
- `target_action_contract = unity_v2_legacy032_gridnet`
- `branch_sizes = [6,4,4,4,4,7,49]`
- `attack_target_semantics = local_7x7_49`
- `semantic_parity_claim = false`
- `direct_weight_transfer_claim = false`

## 7. Model/Head Shape Summary

Model variant used:

- `transfer`

First batch output head shapes:

- `action_type_logits`: `[8,576,6]`
- `move_dir_logits`: `[8,576,4]`
- `harvest_dir_logits`: `[8,576,4]`
- `return_dir_logits`: `[8,576,4]`
- `produce_dir_logits`: `[8,576,4]`
- `produce_unit_type_logits`: `[8,576,7]`
- `attack_target_local_logits`: `[8,576,49]`

First batch target shape:

- `[8,576,7]`

## 8. Train Smoke Metrics

- `train_total_loss_first`: `1.856973278512174`
- `train_total_loss_last`: `1.8464400354376536`
- `train_total_loss_mean`: `1.8517066569749137`
- `train_batches_executed`: `40` (2 epochs x 20 max)
- `optimizer_step_count`: `40`
- `no_nan_inf_loss`: `true`

Per-branch train losses:

- `train_action_type_loss`: `1.7918933444552951`
- `train_move_dir_loss`: `1.3884160425881664`
- `train_harvest_dir_loss`: `1.3888231924086143`
- `train_return_dir_loss`: `1.3879781446549067`
- `train_produce_dir_loss`: `1.3879625375016484`
- `train_produce_unit_type_loss`: `1.9486354750912815`
- `train_attack_target_local_loss`: `3.9004084035434596`

Per-branch train accuracies:

- `train_action_type_accuracy`: `0.17027994791666667`
- `train_move_dir_accuracy`: `0.24265312599174865`
- `train_harvest_dir_accuracy`: `0.24585327476561988`
- `train_return_dir_accuracy`: `0.25198267244251915`
- `train_produce_dir_accuracy`: `0.2515495186601609`
- `train_produce_unit_type_accuracy`: `0.1458525649479098`
- `train_attack_target_local_accuracy`: `0.021904948171327987`

## 9. Validation Smoke Metrics

- `validation_total_loss_mean`: `1.8361315424501463`
- `validation_batches_executed`: `10` (2 epochs x 5 max)

Per-branch validation losses:

- `val_action_type_loss`: `1.791842312282986`
- `val_move_dir_loss`: `1.3860362916419098`
- `val_harvest_dir_loss`: `1.3864656865642633`
- `val_return_dir_loss`: `1.3871685821429156`
- `val_produce_dir_loss`: `1.3876069511973441`
- `val_produce_unit_type_loss`: `1.9465942226752269`
- `val_attack_target_local_loss`: `3.8931565699313504`

Per-branch validation accuracies:

- `val_action_type_accuracy`: `0.16940104166666667`
- `val_move_dir_accuracy`: `0.2517985611510791`
- `val_harvest_dir_accuracy`: `0.25365478327776353`
- `val_return_dir_accuracy`: `0.23682140047206923`
- `val_produce_dir_accuracy`: `0.23830222449501406`
- `val_produce_unit_type_accuracy`: `0.14446433137305037`
- `val_attack_target_local_accuracy`: `0.02016898337421641`

## 10. Checkpoint Files

Checkpoint requested and saved:

- `python/week6_student/runs/legacy032_v2_bc_smoke_stage6a1/legacy032_v2_bc_smoke_stage6a1_smoke_checkpoint.pt`

## 11. Warnings

- This is a short bounded smoke run (2x20 train batches) and is not a final BC optimization run.
- Loss movement is modest as expected for smoke scale; no instability or non-finite values observed.

## 12. Remaining Unity Blockers

Not modified in Stage6A1:

- `Assets/Scripts/ML/Week6StudentPolicyAdapter.cs` bridge path/filename policy
- `Assets/Scripts/ML/Week6Day4StudentInferenceDryRun.cs` stale default checkpoint path

## 13. Final Decision

`STAGE6A1_BC_SMOKE_TRAINING_PASS_READY_FOR_SHORT_BC_RUN`

## 14. Recommended Next Stage

Proceed to Stage6A2 for a slightly longer, still-bounded BC run policy and artifact selection for downstream Unity bridge integration prep.
