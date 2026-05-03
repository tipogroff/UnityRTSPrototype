# Stage10D.9R Unity Stage10R Rerun Report

- generated_at_utc: 2026-05-03T10:51:44.702002+00:00
- scene: Assets/Scenes/Week6_StudentVisualInspection.unity
- checkpoint: python/week6_student/runs/legacy032_v2_semantic_bc_stage10d8_20260503T093718Z/student_bc_semantic_best.pt
- binding_status: pass
- inference_artifact_verification: pass

## Runtime Inference
- inference_request_count: 1
- adapter_invoked: True
- logits_shapes_captured: True
- checkpoint_path_used_at_inference: python/week6_student/runs/legacy032_v2_semantic_bc_stage10d8_20260503T093718Z/student_bc_semantic_best.pt

## Focus Cells
### B2
- predicted_action_type: NoOp
- predicted_action_type_source: model_logits
- action_type_top3: [{'class_id': 0, 'class_name': 'NoOp', 'logit': 1.2370370626449585, 'probability': 0.7851663827896118}, {'class_id': 2, 'class_name': 'Harvest', 'logit': -1.23738694190979, 'probability': 0.06612002849578857}, {'class_id': 4, 'class_name': 'Produce', 'logit': -1.6270983219146729, 'probability': 0.0447799414396286}]
- command_built: False
- command_not_built_reason: predicted_noop
### C3
- predicted_action_type: NoOp
- predicted_action_type_source: model_logits
- action_type_top3: [{'class_id': 0, 'class_name': 'NoOp', 'logit': 3.2165684700012207, 'probability': 0.9946195483207703}, {'class_id': 4, 'class_name': 'Produce', 'logit': -3.441709518432617, 'probability': 0.0012764494167640805}, {'class_id': 3, 'class_name': 'Return', 'logit': -3.51444411277771, 'probability': 0.0011869033332914114}]
- command_built: False
- command_not_built_reason: predicted_noop

## Decoder/Applier
- commands_built: 0
- commands_submitted: 0
- action_applier_reached: False
- apply_command_reached: False

## Decision
- CHECKPOINT_BINDING_VERIFIED
- UNITY_RERUN_INFRA_FIX_APPLIED
- INFERENCE_ARTIFACT_CAPTURE_VERIFIED
- UNITY_STAGE10R_RERUN_COMPLETED
- UNITY_RUNTIME_NOOP_PERSISTS_WITH_SEMANTIC_CHECKPOINT
- READY_FOR_RUNTIME_NOOP_PERSISTENCE_DIAGNOSTIC
- DECODER_APPLIER_NOT_REACHED
- gate: GO_FOR_RUNTIME_NOOP_PERSISTENCE_DIAGNOSTIC
