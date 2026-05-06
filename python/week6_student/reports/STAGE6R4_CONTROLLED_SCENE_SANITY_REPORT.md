# Stage6R4 Controlled Scene Sanity Report

## Classification
- classification: PASS_WITH_WARNINGS
- reason: Stage6A2 checkpoint binding and v2 branch-shape evidence are present; student run is terminal Loss with decoder non_actor_cell rejection dominance and no accepted/rejected MatchManager events captured in student_live_policy mode.

## Run Context
- scene: Week6_StudentVisualInspection
- mode: student_live_policy
- steps_completed: 57 / 80
- terminal: True
- terminal_reason: Loss

## Pre-Run Verification (Observed)
- checkpoint_used_at_inference: python/week6_student/runs/legacy032_v2_bc_short_stage6a2/legacy032_v2_bc_short_stage6a2_smoke_checkpoint.pt
- uses_student_checkpoint: True
- uses_python_adapter: True
- uses_heuristic_policy: False
- inferred_action_contract_version: v2_gridnet_compatible
- branch_sizes: [6,4,4,4,4,7,49]
- action_flat_size: 526848
- observation_shape: [24,24,27]
- model_input_shape: [24,24,27]
- adapter_response_has_action_contract_version_key: True
- adapter_response_has_branch_sizes_key: True
- adapter_response_has_action_flat_size_key: True
- v1_payload_seen: False
- fake_policy_or_stub_seen: False

## Command Lifecycle Counters (Aggregated from per-cell diagnostics)
- records: 32832
- decision_requests (snapshot inference calls): 1653
- candidate_actor_cells_submitted: 85
- inferred_actor_cell_rows: 83
- predicted_noop_rows: 110
- predicted_non_noop_rows: 32722
- masked_non_noop_rows: 23
- decoder_non_noop_rows: 24
- command_built_rows: 83
- command_submitted_rows: 105
- accepted_events: 22
- rejected_events: 0
- decoder_rejected_rows: 32617
- accepted_pending_rows: 105
- applier_rejected_rows: 0
- predicted_noop_share_all_rows: 0.00335
- predicted_non_noop_share_all_rows: 0.99665
- command_built_share_of_inferred_actor_rows: 1
- command_submitted_share_of_inferred_actor_rows: 1.26506

## Rejection Reasons
- decoder_reject_reason_histogram: {"non_actor_cell":32639}
- applier_reject_reason_histogram: {}

## Constraint Statement
- No training was executed.
- No fallback/heuristic weakening was applied.
- No semantic policy-quality claims are made.

## Artifacts
- stage6r4_controlled_scene_sanity_report.json
- stage6r4_command_lifecycle_trace.jsonl
- stage6r4_scene_sanity_snapshot.json
- stage6r4_rejection_reason_summary.json
- stage6r4_payload_summary.json
