# STAGE6R5A Actor-Cell Diagnostics Normalization Report

- Generated (UTC): 2026-05-06T18:50:58.440705+00:00
- Scene/run used: Assets/Scenes/Week6_StudentVisualInspection.unity | mode=student_live_policy | target_steps=80 | steps_completed=57 | terminal=True | terminal_reason=Loss
- Checkpoint used: python/week6_student/runs/legacy032_v2_bc_short_stage6a2/legacy032_v2_bc_short_stage6a2_smoke_checkpoint.pt
- Classification: STAGE6R5A_DIAGNOSTICS_NORMALIZATION_PASS_READY_FOR_BEHAVIOR_BOTTLENECK_ANALYSIS
- Classification reason: single payload flat size is 44928, actor-cell-only counters are separated from all-grid counters, and lifecycle warnings are explicit.

## Flat Size
- single_payload_action_flat_size: 44928
- expected_single_payload_action_flat_size: 44928
- legacy_stage6r4_reported_action_flat_size: 526848
- corrected interpretation: legacy downstream report value; raw adapter payload remains 44928 and no checked-in runtime adapter path emits 526848

## Scopes
- all_grid_scope.total_cells_evaluated: 32832
- all_grid_scope.all_grid_predicted_noop_count: 110
- all_grid_scope.all_grid_predicted_non_noop_count: 32722
- all_grid_scope.all_grid_non_actor_cell_rejections: 32639
- actor_cell_scope.actor_cells_detected: 83
- actor_cell_scope.controllable_actor_cells_detected: 83
- actor_cell_scope.actor_cell_predictions_count: 83
- actor_cell_scope.actor_cell_predicted_noop_count: 0
- actor_cell_scope.actor_cell_predicted_non_noop_count: 83
- actor_cell_scope.actor_cell_masked_to_noop_count: 60
- actor_cell_scope.actor_cell_command_built_count: 23
- actor_cell_scope.actor_cell_command_not_built_count: 60
- command_lifecycle_scope.commands_built: 23
- command_lifecycle_scope.commands_submitted: 23
- command_lifecycle_scope.commands_accepted_pending: 23
- command_lifecycle_scope.commands_accepted_confirmed: 0
- command_lifecycle_scope.commands_rejected: 0
- command_lifecycle_scope.commands_applied_by_match_manager: 0
- command_lifecycle_scope.commands_not_applied: 23

## Consistency Warnings
| # | warning |
|---|---|
| 1 | 23 submitted commands remain in accepted_pending/unknown state at capture end; no explicit expire/apply terminal event was exported for them. |

## Top Actor Outcomes
| step | flat | label | unit | before_mask | after_mask | status | reason |
|---|---|---|---|---|---|---|---|
| 1 | 26 | C2 | Worker | Move | Move | accepted_pending | none |
| 1 | 50 | C3 | Base | Move | NoOp | accepted_pending | masked_to_noop |
| 2 | 27 | D2 | Worker | Move | Move | accepted_pending | none |
| 2 | 50 | C3 | Base | Move | NoOp | accepted_pending | masked_to_noop |
| 3 | 28 | E2 | Worker | Move | Move | accepted_pending | none |
| 3 | 50 | C3 | Base | Move | NoOp | accepted_pending | masked_to_noop |
| 4 | 29 | F2 | Worker | Move | Move | accepted_pending | none |
| 4 | 50 | C3 | Base | Move | NoOp | accepted_pending | masked_to_noop |

## Safety Gates
- fallback_used: False
- uses_heuristic_policy: False
- fake_policy_or_stub_seen: False
- v1_regression: False
- accepted_event_definition: accepted_confirmed is defined as row.command_event_accepted or row.applier_accepted, i.e. MatchManager acceptance telemetry as exposed through the runner export.

## Explicit Notes
- No BC training was run.
- No PPO fine-tuning was run.
- No teacher training was run.
- No semantic parity claim is made.
- No direct weight transfer claim is made.
- No behavior-quality claim is made.

## Artifacts
- JSON report: python/week6_student/reports/stage6r5a_actor_cell_diagnostics_normalization_report.json
- Actor trace: python/week6_student/reports/stage6r5a_actor_cell_trace.jsonl
- Command lifecycle trace: python/week6_student/reports/stage6r5a_command_lifecycle_trace.jsonl
- Counter consistency report: python/week6_student/reports/stage6r5a_counter_consistency_report.json
- Flat size report: python/week6_student/reports/stage6r5a_flat_size_report.json
- Rejection reason summary: python/week6_student/reports/stage6r5a_rejection_reason_summary.json
