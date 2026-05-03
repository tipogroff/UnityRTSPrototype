# LEGACY032 UNITY V2 STAGE10D9 UNITY STAGE10R RERUN REPORT

## 1. Scope
- Stage10D.9 rerun only; no retraining/PPO/teacher continuation.
- No checkpoint mutation and no ActionApplier/MatchManager behavioral patch.

## 2. Stage10D.8 Recap
- stage10d8_gate: GO_FOR_UNITY_STAGE10R_RERUN
- stage10d8_authorized_unity_rerun: True
- known_risk_carried: Stage10D.8 sparse snapshot probe had B2/C3 near NoOp-only.

## 3. Checkpoint Binding
- new_checkpoint: python/week6_student/runs/legacy032_v2_semantic_bc_stage10d8_20260503T093718Z/student_bc_semantic_best.pt
- verification_status: pass
- verification_report: python/week6_student/reports/stage10d9_checkpoint_binding_verification.json

## 4. Unity Scene / Runner
- scene: Assets/Scenes/Week6_StudentVisualInspection.unity
- runner: RTS.ML.Week6VisualInspectionRunner
- execution_mode: full Unity runtime observation (not sparse offline tensor)

## 5. Runtime Observation Check
- observation_shape: [24, 24, 27]
- shape_ok_[24,24,27]: True

## 6. Runtime Inference Check
- inference_request_count: 0
- checkpoint_path_used_by_bridge: python/week6_student/runs/legacy032_v2_semantic_bc_stage10d8_20260503T093718Z/student_bc_semantic_best.pt
- logits_shapes_captured: False
- logits_shape_lines: []

## 7. B2/C3 Focus Cell Result
- B2_predicted_action_type: NoOp
- B2_top3: []
- B2_command_built: False
- B2_reason_if_no_command: no_adapter_artifact
- C3_predicted_action_type: NoOp
- C3_top3: []
- C3_command_built: False
- C3_reason_if_no_command: no_adapter_artifact

## 8. Decoder/Applier Result
- commands_built: 0
- commands_submitted: 0
- action_applier_reached: False
- apply_command_reached: False

## 9. Old vs New Stage10R Comparison
- old: {'snapshot': 'python/week6_student/reports/stage10r_noop_collapse_snapshot_step0001.json', 'B2_predicted_action_type': 'NoOp', 'C3_predicted_action_type': 'NoOp', 'B2_command_built': False, 'C3_command_built': False}
- new: {'snapshot': 'python/week6_student/reports/stage10d9_unity_stage10r_rerun_snapshot_step0001.json', 'B2_predicted_action_type': 'NoOp', 'C3_predicted_action_type': 'NoOp', 'B2_command_built': False, 'C3_command_built': False}
- comparison_note: Old Stage10R remained NoOp-only. New rerun missing bridge logits payload at step0001, so policy-level comparison is infra-limited.

## 10. Remaining Risks
- Stage10D.8 offline sparse snapshot probe failed (B2/C3 near NoOp-only); carried forward as known risk.
- Stage10D.9 rerun step0001 has bridge payload missing, so B2/C3 top-3 probabilities are unavailable in this run.
- Do not claim policy-level success until Unity runtime rerun with full bridge logits capture passes.

## 11. Gate Decision
- gate_decision: GO_FOR_UNITY_RERUN_INFRA_FIX

## 12. Explicit Non-Claims
- No retraining performed in Stage10D.9.
- No PPO or teacher training performed in Stage10D.9.
- No checkpoint mutation performed.
- No ActionApplier or MatchManager behavioral patch applied.
- No forced non-NoOp fallback added.
- No policy-level success claim is made in this stage.

## Classifications
- CHECKPOINT_BINDING_VERIFIED
- UNITY_STAGE10R_RERUN_INFRA_FAILURE
- DECODER_APPLIER_NOT_REACHED
- NOT_READY_FOR_UNITY_ANALYSIS
