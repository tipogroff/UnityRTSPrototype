# STAGE10D19B_VALID_MOVE_EFFICIENCY_REPORT

## 1. Purpose and constraints
- Stage10D.19B focuses on valid-target movement augmentation and safety controls only.
- No PPO, no Gym teacher training, no teacher checkpoint mutation, no Stage10D.17 checkpoint mutation.
- No Unity runtime semantic shortcuts and no decoder/applier/matchmanager semantic changes.
- Attack augmentation remains deferred in this stage.

## 2. Stage10D.19 evidence recap
- Stage10D.19 decision = GO_FOR_STAGE10D19_MOVE_COMMAND_EFFICIENCY_FIX_OR_AUGMENTATION
- Primary issue: move target validity/occupancy mismatch before command build.

## 3. Why Attack augmentation is deferred
- Stage10D.19 gate selected movement efficiency correction first.
- Attack signals are recorded watch-only to avoid conflating failure modes.

## 4. Dataset augmentation design
- Dataset dir: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/bc_ready/legacy032_v2_stage10d19b_valid_move_augmented_bc_ready_20260503T191829Z
- Family counts: {'family_a_valid_move_positive': 256, 'family_b_occupied_negative': 1333, 'family_c_direction_correction': 1333, 'family_d_congestion_rally': 1007, 'family_e_off_actor_negative': 1200, 'family_f_preservation': 841}
- Families used: valid move positives, occupied-target negatives, direction corrections, congestion controls, off-actor negatives, preservation.

## 5. Dataset validation
- Validation status: pass
- Validation labels: ['STAGE10D19B_DATASET_VALID', 'STAGE10D19B_VALID_MOVE_POSITIVES_PRESENT', 'STAGE10D19B_VALID_MOVE_TARGETS_CONFIRMED', 'STAGE10D19B_OCCUPIED_NEGATIVE_CONTROLS_PRESENT', 'STAGE10D19B_OFF_ACTOR_NEGATIVE_CONTROLS_PRESENT', 'STAGE10D19B_NO_LABEL_LEAKAGE_CONFIRMED', 'STAGE10D19B_B2_C3_GUARDS_PRESERVED', 'STAGE10D19B_MOVEMENT_PRESERVATION_CONFIRMED', 'STAGE10D19B_TARGET_DISTRIBUTION_ACCEPTABLE']
- Validation gate: GO_FOR_STAGE10D19B_VALID_MOVE_BC_TRAINING

## 6. Training summary
- Best checkpoint: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/runs/legacy032_v2_stage10d19b_valid_move_augmented_bc_20260503T192454Z/student_bc_stage10d19b_valid_move_best.pt
- Final checkpoint: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/runs/legacy032_v2_stage10d19b_valid_move_augmented_bc_20260503T192454Z/student_bc_stage10d19b_valid_move_final.pt
- Selection epoch: 1

## 7. Offline preservation metrics
- actor_action_accuracy = 1.0
- worker_harvest_recall = 1.0
- base_produce_recall = 1.0

## 8. Valid-target movement metrics
- valid_move_recall = 1.0
- valid_move_dir_accuracy = 1.0
- estimated_prediction_to_build_readiness = 0.9944289693593314

## 9. Occupied-target negative-control metrics
- occupied_target_negative_accuracy = 0.5590277777777778
- predicted_occupied_or_invalid_target_moves = 4

## 10. Off-actor safety metrics
- off_actor_noop_accuracy = 1.0
- off_actor_non_noop_count = 19
- off_actor_command_risk_if_inferable = elevated

## 11. Stage10D.18RR replay/snapshot replay
- Replay proxy: {'total_move_predictions': 718, 'predicted_valid_target_moves': 714, 'predicted_occupied_or_invalid_target_moves': 4, 'estimated_prediction_to_build_readiness': 0.9944289693593314, 'off_actor_non_noop_count': 19, 'off_actor_command_risk_if_inferable': 'elevated', 'b2': {'flat_index': 25, 'predicted_action': 'harvest', 'p_noop': 3.687629634820805e-22, 'p_move': 0.06334275007247925, 'p_harvest': 0.9347254037857056, 'p_return': 1.8407008610665798e-05, 'p_produce': 0.00041369051905348897, 'p_attack': 0.0014996937243267894, 'full_probabilities': [3.687629634820805e-22, 0.06334275007247925, 0.9347254037857056, 1.8407008610665798e-05, 0.00041369051905348897, 0.0014996937243267894]}, 'c3': {'flat_index': 50, 'predicted_action': 'produce', 'p_noop': 2.369201128414166e-15, 'p_move': 0.05498485267162323, 'p_harvest': 0.0016761558363214135, 'p_return': 0.00042824470438063145, 'p_produce': 0.9426979422569275, 'p_attack': 0.00021280725195538253, 'full_probabilities': [2.369201128414166e-15, 0.05498485267162323, 0.0016761558363214135, 0.00042824470438063145, 0.9426979422569275, 0.00021280725195538253]}}
- Snapshot replay summary: {'valid_sum': 12, 'invalid_sum': 0, 'off_actor_non_noop_sum': 2}

## 12. Attack watch-only notes
- {'max_p_attack': 0.21233204007148743, 'true_raw_b2_p_attack': 0.0014996937243267894, 'true_raw_c3_p_attack': 0.00021280725195538253, 'notes': 'Attack is watch-only in Stage10D.19B. No attack optimization performed.'}
- Attack was monitored only; no attack augmentation/training objective was added.

## 13. Classification labels
- STAGE10D19B_DATASET_VALID
- STAGE10D19B_TRAINING_COMPLETED
- STAGE10D19B_ORIGINAL_PERFORMANCE_PRESERVED
- STAGE10D19B_B2_C3_GUARDS_PRESERVED
- STAGE10D19B_MOVEMENT_PRESERVED
- STAGE10D19B_VALID_MOVE_TARGET_SELECTION_IMPROVED_OFFLINE
- STAGE10D19B_NEEDS_AUGMENTATION_REDESIGN
- STAGE10D19B_OFF_ACTOR_RISK_REDUCED_OR_CONTROLLED
- STAGE10D19B_NOT_READY_FOR_UNITY

## 14. Primary next gate
- GO_FOR_STAGE10D19B_AUGMENTATION_REDESIGN

## 15. What not to do next
- Do not run Unity rerun unless gate is GO_FOR_STAGE10D20_UNITY_VALID_MOVE_RERUN.
- Do not start Attack augmentation before movement efficiency gate is satisfied.
- Do not introduce runtime remaps/heuristics/forced movement as shortcuts.

## Explicit answers
- Did we preserve B2/C3 only as regression guards? Yes
- Did we avoid runtime semantic shortcuts? Yes, by stage constraints and artifact trail.
- Did we improve valid-target Move behavior offline? Yes
- Did we reduce occupied/invalid target Move tendency? No
- Did we preserve previous movement ability? Yes
- Did we reduce or control off-actor non-NoOp? Yes
- Did original validation regress? No
- Is model ready for Unity valid-Move rerun? No
- Why are we not doing Attack augmentation yet? Movement-target quality remains the primary unresolved bottleneck by Stage10D.19 gate logic.
- Exact next gate: GO_FOR_STAGE10D19B_AUGMENTATION_REDESIGN
