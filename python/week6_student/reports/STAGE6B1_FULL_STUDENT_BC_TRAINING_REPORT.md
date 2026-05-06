# legacy032_v2_full_bc_stage6b1 Training Summary

- classification: STAGE6B1_FULL_BC_TRAINING_PASS_READY_FOR_UNITY_SANITY
- dataset_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_exports_bc\legacy032_3m_unity_v2_bc_ready_stage5p4_20260506T153632Z
- model_variant: transfer
- device: cpu
- epochs_completed: 10
- best_epoch: 5
- best_validation_total_loss: 1.8362130231139502
- final_validation_total_loss: 1.8372341383180357

## Validation Per-Branch

| branch | val_loss | val_accuracy |
|---|---:|---:|
| action_type | 1.780999 | 0.171332 |
| move_dir | 1.381358 | 0.253829 |
| harvest_dir | 1.387030 | 0.248986 |
| return_dir | 1.387210 | 0.249438 |
| produce_dir | 1.386396 | 0.249624 |
| produce_unit_type | 1.943759 | 0.145126 |
| attack_target_local | 3.893482 | 0.020616 |

## Offline Action-Type Diagnostics

- validation_action_type_distribution: {'0': 850097, '1': 297634, '2': 324354, '3': 729145, '4': 684328, '5': 340618}
- predicted_noop_share: 0.26349988345335157
- predicted_move_share: 0.09225597115594437
- predicted_produce_share: 0.21211737983296633
- predicted_attack_share: 0.10557948481421968
- action_type_entropy_normalized: 0.9513855244859326
- action_type_mean_confidence: 0.17949655023412242

## Safety Notes

- no_teacher_training: true
- no_ppo_finetuning: true
- semantic_parity_claim: false
- direct_weight_transfer_claim: false
- behavior_quality_claim_from_loss_only: false
