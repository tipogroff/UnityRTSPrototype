# STAGE10D15_UNITY_VISUAL_RERUN_WITH_AUGMENTED_STUDENT_REPORT

## 1. Purpose and constraints
- Stage10D.15 is runtime verification only: no PPO, no teacher/student training, no checkpoint mutation, no decoder/applier/match-manager semantic changes.
- Goal: validate live Unity path from model logits to command submission and visible runtime behavior.

## 2. Active checkpoint binding verification
- checkpoint_binding_status: CHECKPOINT_BINDING_STAGE10D14_CONFIRMED
- active_checkpoint_path: python/week6_student/runs/legacy032_v2_stage10d14_unity_like_augmented_bc_20260503T1455Z/student_bc_stage10d14_augmented_best.pt
- active_checkpoint_basename: student_bc_stage10d14_augmented_best.pt
- model_loaded: True
- predicted_source: model_logits
- fallback_used: False

## 3. Unity scene/run configuration
- scene: Assets/Scenes/Week6_StudentVisualInspection.unity
- observation_shape: [24,24,27]
- first_step_snapshot_source: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10r_noop_collapse_snapshot_step0001.json

## 4. First-step observation and logits
- B2 predicted_action: Harvest; p_harvest=0.9916912913; p_noop=6.333e-24
- C3 predicted_action: Produce; p_produce=0.9922326803; p_noop=2.209e-20
- logits_shape_validation: LOGITS_SHAPE_VALID

## 5. Actor-cell predictions
- first_step_actor_cell_predicted_noop_share: 0.0
- first_step_off_actor_non_noop_count: 0

## 6. Decoder command build results
- total_non_noop_actor_predictions: 2
- total_commands_built: 1
- decoder_reject_counts_by_reason: {'not_built_in_decoder_or_filter': 1}

## 7. ActionApplier results
- total_commands_submitted_to_action_applier: 1
- action_applier_reject_counts_by_reason: {}

## 8. MatchManager.ApplyCommand results
- total_commands_reached_match_manager: 1
- total_commands_accepted: 1
- match_manager_reject_counts_by_reason: {}

## 9. Visible behavior summary
- visible_behavior_observed: True
- terminal_result: Loss

## 10. Classification labels
- CHECKPOINT_BINDING_STAGE10D14_CONFIRMED
- INFERENCE_REAL_MODEL_LOGITS_CONFIRMED
- LOGITS_SHAPE_VALID
- UNITY_RUNTIME_B2_HARVEST_CONFIRMED
- UNITY_RUNTIME_C3_PRODUCE_CONFIRMED
- UNITY_RUNTIME_ACTOR_ACTIONS_RESTORED
- UNITY_RUNTIME_OFF_ACTOR_SAFE
- ACTION_DECODER_REACHED
- COMMANDS_BUILT
- ACTION_APPLIER_REACHED
- MATCHMANAGER_APPLYCOMMAND_REACHED
- COMMANDS_ACCEPTED
- VISIBLE_BEHAVIOR_OBSERVED
- UNITY_VISUAL_RERUN_SUCCESS

## 11. Primary next gate
- primary_next_gate: GO_FOR_STAGE10D16_EXTENDED_VISUAL_BEHAVIOR_EVALUATION

## 12. What not to do next
- Do not run PPO or retraining in Stage10D.15 follow-up.
- Do not patch decoder/applier/match-manager semantics before Stage10D.16 gate audits.
- Do not claim full transfer success beyond collected Unity runtime evidence.

## Explicit required statements
- Stage10D.14 checkpoint loaded: True
- Model logits are real: True
- B2 switched to Harvest in live Unity: True
- C3 switched to Produce in live Unity: True
- Commands were built: True
- ActionApplier was reached: True
- MatchManager.ApplyCommand was reached: True
- Visible behavior was observed: True
