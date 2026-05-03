# STAGE10D16_EXTENDED_VISUAL_BEHAVIOR_EVALUATION_REPORT

## 1. Purpose and constraints
- Stage10D.16 is evaluation/audit only: no PPO, no teacher/student training, no checkpoint mutation, no runtime semantic changes.
- Objective: localize blocker for post-production movement/action progression in Unity runtime.

## 2. Stage10D.15 evidence recap
- Stage10D.15 established binding to Stage10D.14 augmented checkpoint and real model logits with fallback disabled.
- Initial B2 Harvest and C3 Produce were confirmed in Unity runtime.

## 3. Git/artifact cleanup note
- Working tree was clean before Stage10D.16 execution (no staged/unstaged/untracked files).
- Raw per-step captures were generated in tmp only: python/week6_student/tmp/stage10d16_extended_runtime
- Final Stage10D.16 artifacts are written to python/week6_student/reports/.

## 4. Run configuration
- scene: Assets/Scenes/Week6_StudentVisualInspection.unity
- target_steps: 200
- steps_completed: 200
- terminal: False (none)
- checkpoint_binding: STAGE10D16_CHECKPOINT_BINDING_CONFIRMED
- inference_status: STAGE10D16_INFERENCE_REAL_MODEL_LOGITS_CONFIRMED
- logits_shapes_status: STAGE10D16_LOGITS_SHAPES_VALID

## 5. Initial Harvest/Produce confirmation
- initial_harvest_detected: True
- initial_produce_detected: True
- initial_command_acceptance_detected: True

## 6. Produced unit lifecycle
- units_produced_count: 10
- produced_units_visible_in_observation: True
- produced_units_owner_unit_encoding_valid: True
- first_step_with_new_unit: 5

## 7. Movement diagnostics
- total_move_predictions: 0
- total_move_commands_built: 0
- total_move_commands_accepted: 0
- total_units_that_moved: 1
- first_move_prediction_step: None
- first_move_command_built_step: None
- first_move_command_accepted_step: None
- move_decoder_reject_counts_by_reason: {}
- move_applier_reject_counts_by_reason: {}
- move_matchmanager_reject_counts_by_reason: {}

## 8. Action distribution over time
- temporal_pattern_labels: ['INITIAL_HARVEST_PRODUCE_ONLY', 'ECONOMY_ONLY_BEHAVIOR']
- economy_only_behavior: True
- produce_loop_no_movement: False

## 9. Decoder/Applier/MatchManager movement path
- move_predicted: False
- move_decoder_built_command: False
- move_reached_action_applier: False
- move_reached_match_manager: False
- move_command_accepted: False

## 10. Visual behavior summary
- visible_behavior_observed: True
- harvest_commands_accepted: 0
- produce_commands_accepted: 11
- move_commands_accepted: 0
- attack_commands_accepted: 0
- units_that_changed_position_count: 1
- enemy_engagement_observed: False

## 11. Classification labels
- STAGE10D16_CHECKPOINT_BINDING_CONFIRMED
- STAGE10D16_INFERENCE_REAL_MODEL_LOGITS_CONFIRMED
- STAGE10D16_LOGITS_SHAPES_VALID
- STAGE10D16_INITIAL_HARVEST_CONFIRMED
- STAGE10D16_INITIAL_PRODUCE_CONFIRMED
- STAGE10D16_INITIAL_COMMAND_ACCEPTANCE_CONFIRMED
- STAGE10D16_UNITS_PRODUCED_CONFIRMED
- STAGE10D16_PRODUCED_UNITS_VISIBLE_IN_OBSERVATION
- STAGE10D16_PRODUCED_UNITS_OWNER_UNIT_ENCODING_VALID
- STAGE10D16_MOVE_PREDICTIONS_ABSENT
- STAGE10D16_MOVE_COMMANDS_NOT_BUILT
- STAGE10D16_UNITS_CHANGED_POSITION
- STAGE10D16_ECONOMY_ONLY_BEHAVIOR_CONFIRMED
- STAGE10D16_ATTACK_BEHAVIOR_ABSENT
- STAGE10D16_OFF_ACTOR_MISLOCALIZATION_DETECTED

## 12. Primary next gate
- primary_next_gate: GO_FOR_STAGE10D17_MOVEMENT_LABEL_AUGMENTATION

## 13. What not to do next
- Do not run PPO.
- Do not train teacher/student.
- Do not mutate checkpoint.
- Do not change runtime semantics or force movement.
- Do not add heuristic/random fallback.

## Explicit required answers
- Did the agent produce units? True
- Were produced units visible in observation? True
- Did produced units receive non-NoOp predictions? True
- Did any unit get Move prediction? False
- Did any Move command build? False
- Did any Move command reach ActionApplier? False
- Did any Move command reach MatchManager? False
- Did any Move command get accepted? False
- Did any unit physically change position? True
- Is current blocker model policy, decoder branch semantics, action applier validation, match manager acceptance, or observation encoding? model_policy
