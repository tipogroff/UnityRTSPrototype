# STAGE10D18RR_RUNTIME_BC_REDEPLOY_EVAL_RERUN_REPORT

## 1. Purpose and constraints
- Runtime redeploy evaluation only after Stage10D.18R binding fix.
- No PPO, no teacher/student training, no checkpoint mutation, no runtime semantic changes.

## 2. Stage10D.18 failure recap
- Original Stage10D.18 failed due to binding/bridge startup path; runtime behavior evaluation was blocked.

## 3. Stage10D.18R binding fix recap
- Filename gate fix enabled Stage10D.17 checkpoint basename acceptance in Unity adapter.
- Stage10D.18R confirmed real model logits path and no fallback.

## 4. Checkpoint/inference binding verification
- active_checkpoint_path: python/week6_student/runs/legacy032_v2_stage10d17_movement_augmented_bc_20260503T164734Z/student_bc_stage10d17_movement_augmented_best.pt
- active_checkpoint_basename: student_bc_stage10d17_movement_augmented_best.pt
- expected_basename: student_bc_stage10d17_movement_augmented_best.pt
- adapter_invoked: True
- parsed_logits_available: True
- model_loaded: True
- python_request_status: completed
- predicted_source: model_logits
- fallback_used: False
- fake_logits_used: False
- heuristic_policy_path_used: False
- logits_shapes_valid: True

## 5. Run configuration
- scene: Assets/Scenes/Week6_StudentVisualInspection.unity
- target_steps: 200
- steps_completed: 200
- terminal: none

## 6. Initial Harvest/Produce regression check
- B2: {'predicted_action': 'Harvest', 'probabilities': {'noop': 9.74388083990954e-29, 'move': 0.00653872499242425, 'harvest': 0.9899958372116089, 'return': 8.134354720823467e-05, 'produce': 0.0022491835989058018, 'attack': 0.001134936697781086}, 'command_built': False, 'accepted': None}
- C3: {'predicted_action': 'Produce', 'probabilities': {'noop': 4.746975427548096e-26, 'move': 0.010416160337626934, 'harvest': 0.0019502744544297457, 'return': 0.00039386312710121274, 'produce': 0.9871749877929688, 'attack': 6.470976950367913e-05}, 'command_built': True, 'accepted': True}
- actor_cell_predicted_noop_share_step1: 0.0
- off_actor_non_noop_count_step1: 0
- commands_built_step1: 1

## 7. Produced unit lifecycle
- produced_units_count: 59
- produced_units_visible_in_observation: 59
- produced_units_owner_unit_encoding_valid: 59
- produced_units_with_move_prediction_count: 26
- produced_units_with_move_command_built_count: 4
- produced_units_with_move_command_accepted_count: 4
- produced_units_that_moved_count: 36

## 8. Movement command path audit
- total_move_predictions: 1597
- total_move_commands_built: 5
- total_move_commands_submitted_to_action_applier: 5
- total_move_commands_reached_match_manager: 5
- total_move_commands_accepted: 5
- total_units_that_changed_position_after_move: 1
- move_decoder_reject_counts_by_reason: {'not_built_in_decoder_or_filter': 1592}
- move_applier_reject_counts_by_reason: {}
- move_matchmanager_reject_counts_by_reason: {}

## 9. Action distribution over time
- temporal_pattern_labels: ['INITIAL_HARVEST_PRODUCE_PRESERVED', 'MOVEMENT_PREDICTIONS_PRESENT', 'MOVEMENT_COMMANDS_ACCEPTED', 'ATTACK_BEHAVIOR_ABSENT', 'BEHAVIOR_PROGRESS_BEYOND_PRODUCTION']

## 10. Off-actor safety audit
- off_actor_safety_status: STAGE10D18RR_OFF_ACTOR_MISLOCALIZATION_DETECTED
- max_off_actor_non_noop_count: 6
- total_off_actor_non_noop_count: 337

## 11. Visual behavior summary
- run_steps_completed: 200
- terminal_result: none
- primary_failure_or_success_mode: partial_runtime_progress_with_off_actor_risk

## 12. Classification labels
- STAGE10D18RR_CHECKPOINT_BINDING_CONFIRMED
- STAGE10D18RR_REAL_MODEL_LOGITS_CONFIRMED
- STAGE10D18RR_LOGITS_SHAPES_VALID
- STAGE10D18RR_INITIAL_B2_HARVEST_PRESERVED
- STAGE10D18RR_INITIAL_C3_PRODUCE_PRESERVED
- STAGE10D18RR_INITIAL_COMMAND_ACCEPTANCE_CONFIRMED
- STAGE10D18RR_UNITS_PRODUCED_CONFIRMED
- STAGE10D18RR_PRODUCED_UNITS_VISIBLE_IN_OBSERVATION
- STAGE10D18RR_PRODUCED_UNITS_OWNER_UNIT_ENCODING_VALID
- STAGE10D18RR_MOVE_PREDICTIONS_PRESENT
- STAGE10D18RR_MOVE_COMMANDS_BUILT
- STAGE10D18RR_MOVE_COMMANDS_ACCEPTED
- STAGE10D18RR_UNITS_CHANGED_POSITION
- STAGE10D18RR_MOVE_DRIVEN_POSITION_CHANGE_CONFIRMED
- STAGE10D18RR_BEHAVIOR_PROGRESS_BEYOND_PRODUCTION
- STAGE10D18RR_ATTACK_BEHAVIOR_ABSENT
- STAGE10D18RR_OFF_ACTOR_MISLOCALIZATION_DETECTED
- STAGE10D18RR_RUNTIME_REDEPLOY_RERUN_PARTIAL_SUCCESS

## 13. Primary next gate
- GO_FOR_STAGE10D19_ATTACK_BEHAVIOR_AUGMENTATION

## 14. What not to do next
- Do not run PPO.
- Do not train teacher.
- Do not train student.
- Do not mutate checkpoint.
- Do not add force-move/heuristic/random/current_action remap fallbacks.

## Explicit required answers
- Was Stage10D.17 checkpoint loaded? True
- Were logits real model logits? True
- Was fallback avoided? True
- Were logits shapes valid? True
- Did B2 Harvest remain? True
- Did C3 Produce remain? True
- Were units produced? True
- Were produced units visible and correctly encoded? True
- Did Move predictions appear? True
- Did Move commands build? True
- Did Move commands reach ActionApplier? True
- Did Move commands reach MatchManager? True
- Did Move commands get accepted? True
- Did units physically move because of Move commands? True
- Was off-actor safety preserved? False
- Did behavior progress beyond production? True
- Is next blocker policy, decoder, applier, match manager, or attack behavior? attack_behavior
