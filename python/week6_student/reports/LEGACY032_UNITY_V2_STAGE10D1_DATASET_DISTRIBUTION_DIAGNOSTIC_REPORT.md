# LEGACY032 UNITY V2 STAGE10D1 DATASET DISTRIBUTION DIAGNOSTIC REPORT

## Scope
- Read-only diagnostic only.
- No behavior fix, no retraining, no PPO, no checkpoint/dataset/contract mutation.
- Runtime authority remains ActionApplier/MatchManager.

## Contract Compatibility
- target_action_contract: unity_v2_legacy032_gridnet
- branch_sizes: [6, 4, 4, 4, 4, 7, 49]
- observation_shape_per_sample: [576, 27]
- action_shape_per_sample: [576, 7]
- unity_v2_compatible: True

## Dataset Action-Type Distribution (Combined)
| Group | Total | NoOp | Move | Harvest | Return | Produce | Attack |
|---|---:|---:|---:|---:|---:|---:|---:|
| all_576_cells | 50783040 | 50608730 | 0 | 86570 | 0 | 87645 | 95 |
| own_actor_cells | 174310 | 0 | 0 | 86570 | 0 | 87645 | 95 |
| own_worker_cells | 86570 | 0 | 0 | 86570 | 0 | 0 | 0 |
| own_base_cells | 87645 | 0 | 0 | 0 | 0 | 87645 | 0 |
| worker_cells_near_resource | 86570 | 0 | 0 | 86570 | 0 | 0 | 0 |
| worker_cells_near_own_base | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| base_cells_with_produce_like_possibility | 87645 | 0 | 0 | 0 | 0 | 87645 | 0 |
| cells_with_non_noop_labels | 174310 | 0 | 0 | 86570 | 0 | 87645 | 95 |
| active_eligible_actor_cells | 174310 | 0 | 0 | 86570 | 0 | 87645 | 95 |

## Unity Focus Cell Detection
- B2 detected as own Worker: True
- C3 detected as own Base: True

## Observation Comparison Flags
- owner_relative_vs_absolute_encoding_mismatch_suspected: True
- row_column_mismatch_suspicion: False
- current_action_mismatch_suspected: True
- abnormal_attack_target_value: {'B2': False, 'C3': False}

## Nearest Neighbors Summary
### B2
- l2/train: best distance=3.162278, action_type=Harvest, owner=Neutral, unit=Resource
- l2/validation: best distance=3.162278, action_type=Harvest, owner=Neutral, unit=Resource
- cosine/train: best distance=1.000000, action_type=Harvest, owner=Neutral, unit=Resource
- cosine/validation: best distance=1.000000, action_type=Harvest, owner=Neutral, unit=Resource

### C3
- l2/train: best distance=2.828427, action_type=Produce, owner=Player1, unit=Resource
- l2/validation: best distance=2.828427, action_type=Produce, owner=Player1, unit=Resource
- cosine/train: best distance=0.800000, action_type=Produce, owner=Player1, unit=Resource
- cosine/validation: best distance=0.800000, action_type=Produce, owner=Player1, unit=Resource

## Training Objective Audit
- loss_computed_on_all_576_cells_or_not: True; evidence=action_type branch uses all-ones active_mask in compute_branchwise_loss
- actor_cell_mask_used: False; evidence=No explicit actor-cell masking logic found in training objective path
- class_weights_used: False; evidence=No class weight tensor passed into cross_entropy
- action_type_weighted_ce_used: False; evidence=No weighted CE invocation found for action_type
- non_noop_oversampling_used: False; evidence=No oversampling sampler path found
- actor_cell_accuracy_logged: False; evidence=Branch-wise accuracies logged; no dedicated actor-cell aggregate accuracy metric
- validation_metrics_could_be_dominated_by_empty_cell_noop: True; evidence={'val_action_type_active_count_epoch1': 7617600, 'val_produce_dir_active_count_epoch1': 13165, 'val_attack_target_local_active_count_epoch1': 13, 'dominance_ratio_actiontype_vs_produce_plus_attack': 578.0543329792077}

## Root-Cause Classification
- primary: OBSERVATION_ENCODING_MISMATCH
- secondary: none

## Gate Decision
- GO_FOR_OBSERVATION_ENCODING_REMEDIATION

## Honesty Notes
- High aggregate NoOp share over all 576 cells is expected in sparse RTS grids and is not, by itself, a failure signal.
- Target condition is actor-cell NoOp collapse on Unity own actor cells (B2/C3 context).