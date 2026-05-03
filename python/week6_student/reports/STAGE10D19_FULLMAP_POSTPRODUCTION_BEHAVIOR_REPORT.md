# STAGE10D19_FULLMAP_POSTPRODUCTION_BEHAVIOR_REPORT

## 1. Purpose and constraints
- Evidence-first Stage10D.19 audit before any augmentation/training.
- No PPO, no teacher training, no checkpoint mutation, no Unity runtime semantic changes.

## 2. Why B2/C3 are regression guards only
- B2 Harvest and C3 Produce are validated only as safety regressions.
- Primary diagnosis focuses on full-map actor behavior, movement-to-command conversion, off-actor risk, and attack readiness.

## 3. Stage10D.18RR recap
- produced_units_count = 59
- total_move_predictions = 1597
- total_move_commands_built = 5
- total_attack_predictions = 0
- off_actor_safety_status = STAGE10D18RR_OFF_ACTOR_MISLOCALIZATION_DETECTED

## 4. Full-map behavior audit
- run_steps = 200
- terminal_result = none
- labels = ['STAGE10D19_FULLMAP_AUDIT_COMPLETED', 'STAGE10D19_B2_C3_REGRESSION_GUARDS_PASSED', 'STAGE10D19_POSTPRODUCTION_BEHAVIOR_PARTIAL', 'STAGE10D19_OFF_ACTOR_RISK_PRESENT', 'STAGE10D19_MOVEMENT_EMERGED_IN_RUNTIME', 'STAGE10D19_MOVEMENT_WEAK_OR_SPARSE', 'STAGE10D19_ATTACK_ABSENT_IN_RUNTIME']

## 5. Move command efficiency audit
- move_prediction_to_build_rate = 0.0031308703819661866
- move_build_to_accept_rate = 1.0
- move_prediction_to_accept_rate = 0.0031308703819661866
- occupied_target_count = 1333
- invalid_target_move_prediction_count = 1333
- labels = ['STAGE10D19_MOVE_EFFICIENCY_AUDIT_COMPLETED', 'STAGE10D19_MOVE_RUNTIME_COMMAND_PATH_OK_FOR_BUILT_COMMANDS', 'STAGE10D19_MOVE_PREDICTION_TO_BUILD_LOW', 'STAGE10D19_MOVE_TARGET_OCCUPIED_DOMINANT', 'STAGE10D19_MOVE_TARGET_INVALID_DOMINANT', 'STAGE10D19_MOVE_POLICY_TARGET_SELECTION_SUSPECTED', 'STAGE10D19_MOVE_DECODER_FILTER_ALIGNMENT_SUSPECTED']

## 6. Off-actor safety audit
- total_off_actor_non_noop_count = 337
- max_off_actor_non_noop_count = 6
- off_actor_command_built_count = 0
- off_actor_submission_count = 0
- labels = ['STAGE10D19_OFF_ACTOR_SAFETY_AUDIT_COMPLETED', 'STAGE10D19_OFF_ACTOR_NONNOOP_PRESENT', 'STAGE10D19_OFF_ACTOR_NEGATIVE_CONTROLS_REQUIRED', 'STAGE10D19_OFF_ACTOR_FILTERED_BEFORE_COMMAND_BUILD']

## 7. Attack readiness audit
- attack_predictions_total = 0
- attack_commands_built = 0
- steps_with_enemy_in_attack_window = 1
- attack_opportunity_present = True
- attack_near_miss_count = 97
- labels = ['STAGE10D19_ATTACK_READINESS_AUDIT_COMPLETED', 'STAGE10D19_ATTACK_BEHAVIOR_ABSENT_CONFIRMED', 'STAGE10D19_ATTACK_OPPORTUNITY_PRESENT', 'STAGE10D19_ATTACK_NEAR_MISS_PRESENT', 'STAGE10D19_ATTACK_LABEL_OR_POLICY_GAP_SUSPECTED']

## 8. Attack label distribution audit
- trend = {'stage10d7_attack_share': 0.0005446154728122223, 'stage10d14_attack_share': 0.0005354978721005608, 'stage10d17_attack_share': 0.0005171250027217106, 'likely_washed_out_after_movement_augmentation': True}
- labels = ['STAGE10D19_ATTACK_LABEL_AUDIT_COMPLETED', 'ATTACK_LABELS_UNDERREPRESENTED', 'ATTACK_TARGET_DISTRIBUTION_VALID', 'ATTACK_AUGMENTATION_REQUIRED']

## 9. Decision matrix
- selected_decision = GO_FOR_STAGE10D19_MOVE_COMMAND_EFFICIENCY_FIX_OR_AUGMENTATION
- rationale = ['Move predictions are mostly invalid-target/occupied before decoder build.']

## 10. Conditional augmentation summary, if executed
- Not executed in this run (decision-gated stop before dataset augmentation/training).

## 11. Conditional training summary, if executed
- Not executed in this run.

## 12. Conditional offline eval, if executed
- Not executed in this run.

## 13. Classification labels
- ATTACK_AUGMENTATION_REQUIRED
- ATTACK_LABELS_UNDERREPRESENTED
- ATTACK_TARGET_DISTRIBUTION_VALID
- STAGE10D19_ATTACK_ABSENT_IN_RUNTIME
- STAGE10D19_ATTACK_BEHAVIOR_ABSENT_CONFIRMED
- STAGE10D19_ATTACK_LABEL_AUDIT_COMPLETED
- STAGE10D19_ATTACK_LABEL_OR_POLICY_GAP_SUSPECTED
- STAGE10D19_ATTACK_NEAR_MISS_PRESENT
- STAGE10D19_ATTACK_OPPORTUNITY_PRESENT
- STAGE10D19_ATTACK_READINESS_AUDIT_COMPLETED
- STAGE10D19_B2_C3_REGRESSION_GUARDS_PASSED
- STAGE10D19_FULLMAP_AUDIT_COMPLETED
- STAGE10D19_MOVEMENT_EMERGED_IN_RUNTIME
- STAGE10D19_MOVEMENT_WEAK_OR_SPARSE
- STAGE10D19_MOVE_DECODER_FILTER_ALIGNMENT_SUSPECTED
- STAGE10D19_MOVE_EFFICIENCY_AUDIT_COMPLETED
- STAGE10D19_MOVE_POLICY_TARGET_SELECTION_SUSPECTED
- STAGE10D19_MOVE_PREDICTION_TO_BUILD_LOW
- STAGE10D19_MOVE_RUNTIME_COMMAND_PATH_OK_FOR_BUILT_COMMANDS
- STAGE10D19_MOVE_TARGET_INVALID_DOMINANT
- STAGE10D19_MOVE_TARGET_OCCUPIED_DOMINANT
- STAGE10D19_OFF_ACTOR_FILTERED_BEFORE_COMMAND_BUILD
- STAGE10D19_OFF_ACTOR_NEGATIVE_CONTROLS_REQUIRED
- STAGE10D19_OFF_ACTOR_NONNOOP_PRESENT
- STAGE10D19_OFF_ACTOR_RISK_PRESENT
- STAGE10D19_OFF_ACTOR_SAFETY_AUDIT_COMPLETED
- STAGE10D19_POSTPRODUCTION_BEHAVIOR_PARTIAL

## 14. Primary next gate
- GO_FOR_STAGE10D19_MOVE_COMMAND_EFFICIENCY_FIX_OR_AUGMENTATION

## 15. What not to do next
- Do not run PPO.
- Do not train teacher.
- Do not mutate Stage10D.17 checkpoint.
- Do not apply Unity runtime semantic remaps/force actions as a shortcut.

## Explicit required answers
- Did we avoid over-focusing on B2/C3? Yes, they were used as regression guards only.
- Are B2/C3 still preserved as regression guards? Yes.
- Is Move behavior present globally? Yes, but sparse-to-weak at command-build stage.
- Why are many Move predictions not built? Dominant decoder/filter block with many invalid/occupied targets.
- Is Move runtime path technically working for built commands? Yes, built Move commands are accepted.
- Is Attack absent due to label/policy gap or absent opportunity? Evidence indicates both low attack policy expression and limited sampled windows; no built Attack commands.
- Is off-actor non-NoOp harmless filtered noise or command-build risk? Filtered before command build in sampled deep audit, but still a safety risk.
- Should next step be attack augmentation, movement efficiency fix, decoder audit, off-actor safety augmentation, or Unity rerun? GO_FOR_STAGE10D19_MOVE_COMMAND_EFFICIENCY_FIX_OR_AUGMENTATION
