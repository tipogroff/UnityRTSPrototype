# STAGE10D20_UNITY_MASKED_VALID_MOVE_RERUN_REPORT

## 1. Purpose and constraints
- Stage10D.20 runs Unity masked movement rerun only.
- No PPO, no teacher/student training, no checkpoint/dataset mutation.
- Legal mask is pre-selection only; ActionDecoder/ActionApplier/MatchManager remain authoritative.

## 2. Why Stage10D.19C checkpoint is rejected and Stage10D.19B is selected
- selected_checkpoint: python/week6_student/runs/legacy032_v2_stage10d19b_valid_move_augmented_bc_20260503T192454Z/student_bc_stage10d19b_valid_move_best.pt
- Stage10D.19C checkpoint is explicitly rejected by evidence-based override from Stage10D.19C.

## 3. Binding and mask toggle verification
- binding_ok: True
- active_checkpoint: python/week6_student/runs/legacy032_v2_stage10d19b_valid_move_augmented_bc_20260503T192454Z/student_bc_stage10d19b_valid_move_best.pt
- stage10d19c_avoided: True
- model_loaded: True
- parsed_logits_available: True
- fallback_used: False
- mask_enabled: True
- mask_shapes_valid: True

## 4. Runtime masked move efficiency
- total_raw_unmasked_move_predictions: 12
- total_masked_move_predictions: 4
- total_masked_valid_target_moves: 0
- total_masked_invalid_or_occupied_target_moves: 4
- total_move_commands_built: 4
- total_move_commands_accepted: 4
- total_units_that_changed_position_after_move: 0
- build_rate_masked: 1.000000
- build_rate_stage10d18rr: 0.003131

## 5. Off-actor safety
- total_off_actor_raw_non_noop: 171
- total_off_actor_masked_non_noop: 0
- off_actor_command_built_count: 0
- off_actor_submission_count: 0

## 6. Mask action delta audit
- number_of_actions_changed_by_mask: 314
- invalid_move_to_noop: 8
- off_actor_non_noop_to_noop: 171
- mask_causes_action_starvation: False

## 7. Visual behavior summary
- B2_harvest_preserved_initial: True
- C3_produce_preserved_initial: True
- production_preserved: True
- movement_visible: False
- behavior_progress_beyond_production: False

## 8. Comparison to Stage10D.18RR baseline
- baseline_move_predictions: 1597
- baseline_move_commands_built: 5
- baseline_move_commands_accepted: 5
- baseline_units_changed_position_after_move: 1
- baseline_off_actor_non_noop_total: 337

## 9. Attack watch-only notes
- attack_predictions_total: 0
- attack_commands_built: 0
- attack_commands_accepted: 0

## 10. Classification labels
- STAGE10D20_ATTACK_ABSENT
- STAGE10D20_B2_HARVEST_PRESERVED
- STAGE10D20_C3_PRODUCE_PRESERVED
- STAGE10D20_CHECKPOINT_BINDING_CONFIRMED
- STAGE10D20_FALLBACK_NOT_USED
- STAGE10D20_MASKED_INVALID_MOVES_REDUCED
- STAGE10D20_MASKED_MOVE_COMMANDS_ACCEPTED
- STAGE10D20_MASKED_MOVE_COMMAND_BUILD_RATE_IMPROVED
- STAGE10D20_MASK_CHANGES_INVALID_ACTIONS_ONLY_OR_MOSTLY
- STAGE10D20_MASK_DELTA_AUDIT_COMPLETED
- STAGE10D20_MASK_ENABLED_CONFIRMED
- STAGE10D20_MASK_PRESERVES_ECONOMY_GUARDS
- STAGE10D20_MASK_PRESERVES_PRODUCTION
- STAGE10D20_MASK_SHAPES_VALID
- STAGE10D20_MOVE_EFFICIENCY_AUDIT_COMPLETED
- STAGE10D20_MOVE_SUPPRESSED_BY_MASK
- STAGE10D20_OFF_ACTOR_MASKED_SAFE
- STAGE10D20_OFF_ACTOR_MASK_REDUCED_NONNOOP
- STAGE10D20_OFF_ACTOR_SAFETY_AUDIT_COMPLETED
- STAGE10D20_PRODUCTION_PRESERVED
- STAGE10D20_REAL_MODEL_LOGITS_CONFIRMED
- STAGE10D20_STAGE10D19B_CHECKPOINT_CONFIRMED
- STAGE10D20_STAGE10D19C_CHECKPOINT_REJECTED
- STAGE10D20_UNITS_PRODUCED
- STAGE10D20_VISUAL_SUMMARY_COMPLETED

## 11. Primary next gate
- GO_FOR_STAGE10D20_MASK_LOGIC_FIX

## 12. What not to do next
- Do not run PPO.
- Do not train teacher/student.
- Do not mutate checkpoint.
- Do not mutate datasets.
- Do not add runtime remap/current_action-direction shortcuts.
- Do not force movement/attack or heuristic fallback.
