# STAGE10D14 TARGETED BC AUGMENTATION REPORT

- generated_at_utc: 2026-05-03T15:02:05Z
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
- best_checkpoint: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/runs/legacy032_v2_stage10d14_unity_like_augmented_bc_20260503T1455Z/student_bc_stage10d14_augmented_best.pt
- final_checkpoint: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/runs/legacy032_v2_stage10d14_unity_like_augmented_bc_20260503T1455Z/student_bc_stage10d14_augmented_final.pt
- true_raw_B2_p_harvest: 0.9916913509368896
- true_raw_C3_p_produce: 0.9922326803207397

## 6. Offline Eval on Original Validation
- sample_count: 8817
- actor_cell_count: 17447
- actor_cell_action_type_accuracy: 1.0
- actor_cell_non_noop_recall: 1.0
- worker_harvest_recall: 1.0
- base_produce_recall: 1.0
- action_type_accuracy_all_cells: 1.0
- predicted_noop_share_all_cells: 0.9965645990069688

## 7. Offline Eval on Augmented Validation
- augmented_validation_eval: {'sample_count': 168, 'actor_cell_count': 328, 'actor_cell_action_type_accuracy': 1.0, 'actor_cell_non_noop_recall': 1.0, 'worker_harvest_recall': 1.0, 'base_produce_recall': 1.0, 'action_type_accuracy_all_cells': 1.0, 'predicted_noop_share_all_cells': 0.9966104497354498}
- augmented_target_success: {'sample_count': 168, 'B2_success_count': 66, 'B2_success_rate': 1.0, 'C3_success_count': 98, 'C3_success_rate': 1.0}

## 8. Strict Replay on True Raw Unity Observation
- B2: {'flat_index': 25, 'predicted_action': 'harvest', 'p_noop': 6.3333634666796515e-24, 'p_move': 0.0010157068027183414, 'p_harvest': 0.9916913509368896, 'p_return': 0.000368968554539606, 'p_produce': 0.004075256641954184, 'p_attack': 0.0028487234376370907, 'full_probabilities': [6.3333634666796515e-24, 0.0010157068027183414, 0.9916913509368896, 0.000368968554539606, 0.004075256641954184, 0.0028487234376370907]}
- C3: {'flat_index': 50, 'predicted_action': 'produce', 'p_noop': 2.2091149112348584e-20, 'p_move': 0.0013776383129879832, 'p_harvest': 0.0046825832687318325, 'p_return': 0.0015342525439336896, 'p_produce': 0.9922326803207397, 'p_attack': 0.00017284687783103436, 'full_probabilities': [2.2091149112348584e-20, 0.0013776383129879832, 0.0046825832687318325, 0.0015342525439336896, 0.9922326803207397, 0.00017284687783103436]}
- off_actor_non_noop_count: 0
- global_predicted_noop_share: 0.9965277777777778
- actor_predicted_noop_share: 0.0
- baseline_deltas: {'B2_delta_p_harvest': 0.9255714192986488, 'B2_delta_p_noop': -0.7851666212081909, 'C3_delta_p_produce': 0.9909562316024676, 'C3_delta_p_noop': -0.9946194887161255}

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

