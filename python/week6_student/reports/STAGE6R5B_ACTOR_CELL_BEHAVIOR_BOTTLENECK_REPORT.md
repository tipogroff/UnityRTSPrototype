# Stage6R5B - Actor Cell Behavior Bottleneck Analysis

- generated_at_utc: 2026-05-06T18:50:58.660704+00:00
- stage: Stage6R5B
- classification: STAGE6R5B_BEHAVIOR_BOTTLENECK_ANALYSIS_PASS_NEEDS_TELEMETRY_FIX
- recommended_next_stage: Stage6R5C - Command Apply/Expire Telemetry Fix

## Inputs Analyzed
- C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage6r5a_actor_cell_trace.jsonl
- C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage6r5a_command_lifecycle_trace.jsonl
- C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage6r5a_counter_consistency_report.json
- C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage6r5a_rejection_reason_summary.json
- C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage6r5a_actor_cell_diagnostics_normalization_report.json

## Unit-Type / Action Matrix Summary
| UnitType | Predictions | BeforeMaskTop | AfterMaskTop | MaskedToNoOp | Built | Submitted | AcceptedPending | Confirmed | Applied |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|
| Base | 56 | Move:56 | NoOp:56 | 56 (1.000) | 0 (0.000) | 0 (0.000) | 0 (0.000) | 0 (0.000) | 0 (0.000) |
| Worker | 27 | Move:21 | Move:21 | 4 (0.148) | 23 (0.852) | 23 (0.852) | 23 (0.852) | 0 (0.000) | 0 (0.000) |

## Top-K Action Analysis
- top1_action_type_distribution: {'Move': 77, 'Attack': 6}
- top2_action_type_distribution: {'Attack': 77, 'Move': 6}
- avg_margin_top1_vs_noop_probability: 0.03922518896750915
- avg_margin_top1_vs_noop_logit: 0.20606630715804222
- avg_margin_top1_vs_selected_after_mask_probability: 0.02457029589369327
- avg_margin_top1_vs_selected_after_mask_logit: 0.1299515340147139
- cells_with_selected_before_not_equal_selected_after_count: 60
- most_common_mask_corrections: {'Move->NoOp': 56, 'Attack->NoOp': 4}

## Mask Impact Summary
- actor_cell_masked_to_noop_share: 0.7228915662650602
- unit_type_specific_masked_to_noop_share: {'Base': {'masked_to_noop_count': 56, 'masked_to_noop_share': 1.0, 'total': 56}, 'Worker': {'masked_to_noop_count': 4, 'masked_to_noop_share': 0.14814814814814814, 'total': 27}}
- action_type_specific_masked_to_noop_share: {'Attack': {'masked_to_noop_count': 4, 'masked_to_noop_share': 0.6666666666666666, 'total': 6}, 'Move': {'masked_to_noop_count': 56, 'masked_to_noop_share': 0.7272727272727273, 'total': 77}}
- examples_base_move_to_noop: [{'step': 1, 'flat_index': 50, 'logical_label': 'C3', 'selected_before_mask': 'Move', 'selected_after_mask': 'NoOp'}, {'step': 2, 'flat_index': 50, 'logical_label': 'C3', 'selected_before_mask': 'Move', 'selected_after_mask': 'NoOp'}, {'step': 3, 'flat_index': 50, 'logical_label': 'C3', 'selected_before_mask': 'Move', 'selected_after_mask': 'NoOp'}, {'step': 4, 'flat_index': 50, 'logical_label': 'C3', 'selected_before_mask': 'Move', 'selected_after_mask': 'NoOp'}, {'step': 5, 'flat_index': 50, 'logical_label': 'C3', 'selected_before_mask': 'Move', 'selected_after_mask': 'NoOp'}, {'step': 6, 'flat_index': 50, 'logical_label': 'C3', 'selected_before_mask': 'Move', 'selected_after_mask': 'NoOp'}, {'step': 7, 'flat_index': 50, 'logical_label': 'C3', 'selected_before_mask': 'Move', 'selected_after_mask': 'NoOp'}, {'step': 8, 'flat_index': 50, 'logical_label': 'C3', 'selected_before_mask': 'Move', 'selected_after_mask': 'NoOp'}, {'step': 9, 'flat_index': 50, 'logical_label': 'C3', 'selected_before_mask': 'Move', 'selected_after_mask': 'NoOp'}, {'step': 10, 'flat_index': 50, 'logical_label': 'C3', 'selected_before_mask': 'Move', 'selected_after_mask': 'NoOp'}]
- examples_worker_move_to_move: [{'step': 1, 'flat_index': 26, 'logical_label': 'C2', 'selected_before_mask': 'Move', 'selected_after_mask': 'Move', 'command_built': True, 'command_submitted': True}, {'step': 2, 'flat_index': 27, 'logical_label': 'D2', 'selected_before_mask': 'Move', 'selected_after_mask': 'Move', 'command_built': True, 'command_submitted': True}, {'step': 3, 'flat_index': 28, 'logical_label': 'E2', 'selected_before_mask': 'Move', 'selected_after_mask': 'Move', 'command_built': True, 'command_submitted': True}, {'step': 4, 'flat_index': 29, 'logical_label': 'F2', 'selected_before_mask': 'Move', 'selected_after_mask': 'Move', 'command_built': True, 'command_submitted': True}, {'step': 5, 'flat_index': 30, 'logical_label': 'G2', 'selected_before_mask': 'Move', 'selected_after_mask': 'Move', 'command_built': True, 'command_submitted': True}, {'step': 6, 'flat_index': 31, 'logical_label': 'H2', 'selected_before_mask': 'Move', 'selected_after_mask': 'Move', 'command_built': True, 'command_submitted': True}, {'step': 7, 'flat_index': 32, 'logical_label': 'I2', 'selected_before_mask': 'Move', 'selected_after_mask': 'Move', 'command_built': True, 'command_submitted': True}, {'step': 8, 'flat_index': 33, 'logical_label': 'J2', 'selected_before_mask': 'Move', 'selected_after_mask': 'Move', 'command_built': True, 'command_submitted': True}, {'step': 9, 'flat_index': 34, 'logical_label': 'K2', 'selected_before_mask': 'Move', 'selected_after_mask': 'Move', 'command_built': True, 'command_submitted': True}, {'step': 10, 'flat_index': 35, 'logical_label': 'L2', 'selected_before_mask': 'Move', 'selected_after_mask': 'Move', 'command_built': True, 'command_submitted': True}]

## Accepted Pending Interpretation
- counts: {'submitted': 23, 'accepted_pending': 23, 'accepted_confirmed': 0, 'applied_by_match_manager': 0, 'rejected': 0}
- interpretation: {'accepted_pending_likely_missing_terminal_telemetry': True, 'match_manager_apply_may_exist_but_not_linked': True, 'queued_for_future_frames_possible': True, 'apply_or_expire_events_not_linked_to_command_ids': True}
- recommendation: {'decision': 'add_small_telemetry_for_apply_confirmation', 'minimal_telemetry_additions': ['Export command terminal event stream with command_id and lifecycle status (accepted/applied/expired/rejected).', 'Emit MatchManager.ApplyCommand outcome rows linked by command_id.', 'Emit bounded-run end-of-capture unresolved-command summary keyed by command_id.']}

## Training Implications
- should_full_bc_training_proceed_now: False
- main_bottleneck_likely_undertraining: True
- evidence_of_contract_or_bridge_failure: False
- evidence_of_unit_type_action_semantic_mismatch: True
- checkpoint_selection_recommendation: Use validation loss as primary selector; add actor-cell Unity sanity metrics as promotion gate.

## Constraint Confirmation
- No BC training run in this stage.
- No PPO fine-tuning run in this stage.
- No teacher training run in this stage.
- No semantic parity claim between Gym-µRTS and Unity.
- No direct weight transfer claim.
- No behavior quality claim.
