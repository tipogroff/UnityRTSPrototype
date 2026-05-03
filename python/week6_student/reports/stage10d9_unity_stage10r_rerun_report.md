# Stage10D.9 Unity Stage10R Rerun Report

- generated_at_utc: 2026-05-03T10:30:00.231217+00:00
- scene: Assets/Scenes/Week6_StudentVisualInspection.unity
- checkpoint: python/week6_student/runs/legacy032_v2_semantic_bc_stage10d8_20260503T093718Z/student_bc_semantic_best.pt
- binding_verification_status: pass

## Runtime Observation
- shape: [24, 24, 27]
- shape_ok: True

## Runtime Inference
- inference_request_count: 0
- checkpoint_path_used_by_bridge: python/week6_student/runs/legacy032_v2_semantic_bc_stage10d8_20260503T093718Z/student_bc_semantic_best.pt
- logits_shapes_captured: False

## Focus Cells
### B2
- predicted_action_type: NoOp
- action_type_top3: []
- command_built: False
- reason: no_adapter_artifact
### C3
- predicted_action_type: NoOp
- action_type_top3: []
- command_built: False
- reason: no_adapter_artifact

## Decoder/Applier
- action_applier_reached: False
- apply_command_reached: False
- accepted_meaningful_commands: 0
- rejected_commands: 0

## Terminal
- steps_run: 54
- terminal_reason: Loss

## Old vs New
- old: {'snapshot': 'python/week6_student/reports/stage10r_noop_collapse_snapshot_step0001.json', 'B2_predicted_action_type': 'NoOp', 'C3_predicted_action_type': 'NoOp', 'B2_command_built': False, 'C3_command_built': False}
- new: {'snapshot': 'python/week6_student/reports/stage10d9_unity_stage10r_rerun_snapshot_step0001.json', 'B2_predicted_action_type': 'NoOp', 'C3_predicted_action_type': 'NoOp', 'B2_command_built': False, 'C3_command_built': False}
- note: Old Stage10R remained NoOp-only. New rerun missing bridge logits payload at step0001, so policy-level comparison is infra-limited.

## Classifications
- CHECKPOINT_BINDING_VERIFIED
- UNITY_STAGE10R_RERUN_INFRA_FAILURE
- DECODER_APPLIER_NOT_REACHED
- NOT_READY_FOR_UNITY_ANALYSIS

## Gate
- GO_FOR_UNITY_RERUN_INFRA_FIX

## Explicit Non-Claims
- No retraining performed in Stage10D.9.
- No PPO or teacher training performed in Stage10D.9.
- No checkpoint mutation performed.
- No ActionApplier or MatchManager behavioral patch applied.
- No forced non-NoOp fallback added.
- No policy-level success claim is made in this stage.
