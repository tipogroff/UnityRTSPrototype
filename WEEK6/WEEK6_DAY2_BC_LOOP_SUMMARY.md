# Week 6 Day 2 - Minimal Student BC Loop Summary

Date: 2026-04-22

## Scope and Honesty

- This day implements a minimal supervised Behavior Cloning (BC) training loop only.
- This is not RL training.
- This is not PPO fine-tuning.
- This is not Unity-side inference integration.
- This is not the final Week 6 student architecture.
- Loss improvement here does not prove transfer correctness.

## 1. Pinned BC-ready source path used

- `python/week5_teacher/teacher_exports_bc/day6_bc_ready_teacher_adapted_day5_hardened_v2_teacher_candidate_corrective_sl2000_ep8_cpu_20260422T085809Z`

Day 2 uses this BC-ready lineage as canonical student input source.
No raw or adapted artifacts are consumed directly by the Day 2 training loop.

## 2. Model input used

- Primary input key: `input_tensor`
- Shape per sample: `[24, 24, 27]`
- Dtype: `float32`
- Model uses spatial input only (no mandatory global features, no metadata input)

## 3. Target branches supervised

- Target key: `target_action_branches`
- Shape per sample: `[576, 7]`
- Branches supervised:
  - `action_type` (size 6)
  - `move_dir` (size 4)
  - `harvest_dir` (size 4)
  - `return_dir` (size 4)
  - `produce_dir` (size 4)
  - `produce_unit_type` (size 4)
  - `attack_target_local` (size 9)

## 4. Always-active losses

- `action_type` cross-entropy is always active for all spatial positions.

## 5. Conditionally-active losses

Conditional branch losses are activated by target `action_type`:

- `move_dir` active only when `action_type == 1` (Move)
- `harvest_dir` active only when `action_type == 2` (Harvest)
- `return_dir` active only when `action_type == 3` (Return)
- `produce_dir` active only when `action_type == 4` (Produce)
- `produce_unit_type` active only when `action_type == 4` (Produce)
- `attack_target_local` active only when `action_type == 5` (Attack)

## 6. Inactive branch handling rule

- Inactive branches are not penalized.
- No unconditional CE is applied over inactive positions.
- If a batch/epoch has zero active examples for a branch:
  - branch loss is reported as `0.0`
  - active count is reported as `0`
  - no NaN/inf is produced by branch-wise objective code path

## 7. Optional mask policy

Current pinned lineage has no optional mask.

- Training loop is mask-agnostic.
- Missing optional mask is not interpreted as runtime all-valid truth.
- No synthetic mask generation is performed.
- Optional mask is not required and is not used in Day 2 loss logic.

## 8. First-level train/validation metrics produced

Per epoch, loop emits and stores:

- `train_total_loss`, `val_total_loss`
- `train_action_type_loss`, `val_action_type_loss`
- Conditional per-branch losses for both train and val:
  - `*_move_dir_loss`
  - `*_harvest_dir_loss`
  - `*_return_dir_loss`
  - `*_produce_dir_loss`
  - `*_produce_unit_type_loss`
  - `*_attack_target_local_loss`
- `*_action_type_accuracy`
- Conditional per-branch accuracies over active positions only
- Per-branch active counts (`*_active_count`)
- Learning rate and epoch time

Outputs:

- Latest checkpoint: `student_bc_minimal_latest.pt`
- Best validation checkpoint: `student_bc_minimal_best.pt`
- Metrics history JSON: `day2_minimal_metrics_history.json`

## 9. Carry-over risks for Day 3

- Action class imbalance can dominate optimization and bias reported aggregate loss.
- Semantic weakening and remap-to-noop pressure remain unresolved by this minimal loop.
- Teacher data quality drift is still a direct risk.
- Branches with low active counts can show noisy or unstable conditional metrics.
- BC loss decrease alone is insufficient evidence of transfer quality in runtime semantics.
- Architecture here is a temporary baseline and may be inadequate for final transfer objectives.
