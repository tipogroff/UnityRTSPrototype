# STAGE10D14 TARGETED BC AUGMENTATION REPORT

- generated_at_utc: 2026-05-03T14:52:34Z
- primary_next_gate: GO_FOR_STAGE10D15_UNITY_VISUAL_RERUN_WITH_AUGMENTED_STUDENT

## 1. Purpose and Constraints
- Targeted supervised adaptation to Unity-like observation distribution only.
- No PPO.
- No teacher checkpoint change.
- No Unity runtime observation remap deployed as a runtime fix.
- No ActionDecoder, ActionApplier, or MatchManager change.

## 2. Evidence from Stage10D.12R and Stage10D.13A
- Stage10D.12R baseline on true raw Unity observation predicted NoOp at B2 and C3.
- Stage10D.13A confirmed current_action/direction patches can restore Harvest/Produce offline but runtime remap is high risk.
- Stage10D.13A selected targeted BC augmentation as the preferred next gate.

## 3. Augmentation Design
- Family 1: exact true raw Unity observation with teacher labels for B2/C3 targets.
- Family 2: positive BC samples converted to Unity-like NoOp-state observations while preserving action labels.
- Family 3: base-centric local context variants for Produce restoration.
- Family 4: negative controls to limit shortcut overgeneralization.

## 4. Dataset Validation
- status: pass
- classification_labels: ['AUGMENTED_DATASET_VALID', 'TRUE_RAW_UNITY_LIKE_SAMPLE_PRESENT', 'B2_UNITY_LIKE_HARVEST_TARGET_PRESENT', 'C3_UNITY_LIKE_PRODUCE_TARGET_PRESENT', 'NO_OBSERVATION_LABEL_LEAKAGE_CONFIRMED', 'BRANCH_BOUNDS_VALID', 'TARGET_DISTRIBUTION_ACCEPTABLE']
- primary_next_gate: GO_FOR_STAGE10D14_AUGMENTED_BC_TRAINING
- label_leakage_pass: True
- target_distribution_acceptable: True

## 5. Training Summary
- best_epoch: 1
- history_length: 1
- best_checkpoint: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/runs/stage10d14_smoke_train_20260503T1436Z_retry/student_bc_stage10d14_augmented_best.pt
- final_checkpoint: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/runs/stage10d14_smoke_train_20260503T1436Z_retry/student_bc_stage10d14_augmented_final.pt
- true_raw_B2_p_harvest: 0.8438246250152588
- true_raw_C3_p_produce: 0.8215343952178955

## 6. Offline Eval on Original Validation
- sample_count: 8817
- actor_cell_count: 17447
- actor_cell_action_type_accuracy: 0.9998280506677366
- actor_cell_non_noop_recall: 1.0
- worker_harvest_recall: 1.0
- base_produce_recall: 1.0
- action_type_accuracy_all_cells: 0.9999994092850932
- predicted_noop_share_all_cells: 0.9965645990069688

## 7. Offline Eval on Augmented Validation
- augmented_validation_eval: {'sample_count': 13, 'actor_cell_count': 24, 'actor_cell_action_type_accuracy': 1.0, 'actor_cell_non_noop_recall': 1.0, 'worker_harvest_recall': 1.0, 'base_produce_recall': 1.0, 'action_type_accuracy_all_cells': 1.0, 'predicted_noop_share_all_cells': 0.9967948717948718}
- augmented_target_success: {'sample_count': 13, 'B2_success_count': 5, 'B2_success_rate': 1.0, 'C3_success_count': 7, 'C3_success_rate': 1.0}

## 8. Strict Replay on True Raw Unity Observation
- B2: {'flat_index': 25, 'predicted_action': 'harvest', 'p_noop': 1.8083903818855163e-10, 'p_move': 0.022225413471460342, 'p_harvest': 0.8438246250152588, 'p_return': 0.0183781236410141, 'p_produce': 0.07221845537424088, 'p_attack': 0.043353453278541565, 'full_probabilities': [1.8083903818855163e-10, 0.022225413471460342, 0.8438246250152588, 0.0183781236410141, 0.07221845537424088, 0.043353453278541565]}
- C3: {'flat_index': 50, 'predicted_action': 'produce', 'p_noop': 4.683917359216139e-05, 'p_move': 0.04665616899728775, 'p_harvest': 0.057442840188741684, 'p_return': 0.06141189858317375, 'p_produce': 0.8215343952178955, 'p_attack': 0.012907864525914192, 'full_probabilities': [4.683917359216139e-05, 0.04665616899728775, 0.057442840188741684, 0.06141189858317375, 0.8215343952178955, 0.012907864525914192]}
- off_actor_non_noop_count: 0
- global_predicted_noop_share: 0.9965277777777778
- actor_predicted_noop_share: 0.0
- baseline_deltas: {'B2_delta_p_harvest': 0.777704693377018, 'B2_delta_p_noop': -0.7851666210273519, 'C3_delta_p_produce': 0.8202579464996234, 'C3_delta_p_noop': -0.9945726495425333}

## 9. Regression / Safety Analysis
- Original BC performance preserved: True
- True raw B2 restored: True
- True raw C3 restored: True
- Off-actor safety acceptable: True

## 10. Primary Next Gate
- GO_FOR_STAGE10D15_UNITY_VISUAL_RERUN_WITH_AUGMENTED_STUDENT

## Final Decision Labels
- STAGE10D14_AUGMENTATION_DATASET_VALID
- STAGE10D14_TRAINING_COMPLETED
- STAGE10D14_ORIGINAL_PERFORMANCE_PRESERVED
- STAGE10D14_TRUE_RAW_ACTOR_ACTIONS_RESTORED
- STAGE10D14_SAFE_FOR_UNITY_VISUAL_RERUN

