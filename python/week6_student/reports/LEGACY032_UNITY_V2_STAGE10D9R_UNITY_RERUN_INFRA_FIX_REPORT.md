# LEGACY032 UNITY V2 STAGE10D9R UNITY RERUN INFRA FIX REPORT

## Scope
- Stage10D.9R focused on Unity rerun infrastructure fix and verified inference artifact capture.
- No retraining, PPO, teacher training, checkpoint mutation, ActionApplier patch, or MatchManager patch.

## Stage10D9 Failure Recap
- Stage10D.9 had checkpoint binding pass but no validated policy verdict due to missing adapter artifact.
- Fallback NoOp in B2/C3 was infra-limited and not treated as model-level evidence.

## Root Cause No Adapter Artifact
- Snapshot was captured with zero inference requests, so no adapter artifact was present at capture time.
- Focus-cell diagnostics fell back to no-adapter-artifact path and empty logits/top3 payload.

## Infra Fix Applied
- Added read-only adapter diagnostics capture in Week6StudentPolicyAdapter.
- Added runner snapshot fields for adapter invocation, inference count, bridge status, raw keys, and artifact-missing reason.
- Added fallback artifact read via last_output_json_path without changing action semantics.

## Checkpoint Binding Recheck
- binding_status=pass
- expected_checkpoint=python/week6_student/runs/legacy032_v2_semantic_bc_stage10d8_20260503T093718Z/student_bc_semantic_best.pt

## Runtime Observation
- observation_shape=[24, 24, 27]
- observation_has_nan=False
- observation_has_inf=False

## Runtime Inference Artifact Verification
- verification_status=pass
- inference_request_count=1
- adapter_invoked=True
- logits_shapes_captured=True

## B2 C3 Focus Cell Results
- B2_predicted_action_type=NoOp
- B2_predicted_action_type_source=model_logits
- B2_action_type_top3=[{'class_id': 0, 'class_name': 'NoOp', 'logit': 1.2370370626449585, 'probability': 0.7851663827896118}, {'class_id': 2, 'class_name': 'Harvest', 'logit': -1.23738694190979, 'probability': 0.06612002849578857}, {'class_id': 4, 'class_name': 'Produce', 'logit': -1.6270983219146729, 'probability': 0.0447799414396286}]
- B2_command_built=False
- C3_predicted_action_type=NoOp
- C3_predicted_action_type_source=model_logits
- C3_action_type_top3=[{'class_id': 0, 'class_name': 'NoOp', 'logit': 3.2165684700012207, 'probability': 0.9946195483207703}, {'class_id': 4, 'class_name': 'Produce', 'logit': -3.441709518432617, 'probability': 0.0012764494167640805}, {'class_id': 3, 'class_name': 'Return', 'logit': -3.51444411277771, 'probability': 0.0011869033332914114}]
- C3_command_built=False

## Decoder Applier Result
- commands_built=0
- commands_submitted=0
- action_applier_reached=False
- apply_command_reached=False

## Old Vs D9 Vs D9R
- stage10r_snapshot=C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10r_noop_collapse_snapshot_step0001.json
- stage10d9_snapshot=C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10d9_unity_stage10r_rerun_snapshot_step0001.json
- stage10d9r_snapshot=C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10d9r_unity_stage10r_rerun_snapshot_step0001.json
- stage10r_B2_pred=NoOp
- stage10d9_B2_pred=NoOp
- stage10d9r_B2_pred=NoOp

## Remaining Risks
- Do not classify policy-level NoOp persistence unless verification status is pass and sources are model_logits.
- If verification fails, continue infrastructure fixes before behavior conclusions.

## Gate Decision
- gate_decision=GO_FOR_RUNTIME_NOOP_PERSISTENCE_DIAGNOSTIC

## Explicit Non Claims
- No fallback NoOp is treated as model NoOp evidence.
- No policy-level success claim is made when inference artifact verification fails.

## Classifications
- CHECKPOINT_BINDING_VERIFIED
- UNITY_RERUN_INFRA_FIX_APPLIED
- INFERENCE_ARTIFACT_CAPTURE_VERIFIED
- UNITY_STAGE10R_RERUN_COMPLETED
- UNITY_RUNTIME_NOOP_PERSISTS_WITH_SEMANTIC_CHECKPOINT
- READY_FOR_RUNTIME_NOOP_PERSISTENCE_DIAGNOSTIC
- DECODER_APPLIER_NOT_REACHED

## Gate
- GO_FOR_RUNTIME_NOOP_PERSISTENCE_DIAGNOSTIC
