# STAGE10D18R_CHECKPOINT_BINDING_FIX_REPORT

## 1. Purpose and constraints
- Stage10D.18R fixes checkpoint binding/bridge start only; no PPO/training/checkpoint mutation/runtime semantics changes.

## 2. Stage10D.18 failure recap
- Stage10D.18 failed before real logits: bridge_start_failed and fallback_no_adapter_artifact.

## 3. Pre-fix git/artifact snapshot
- See stage10d18r_pre_fix_git_and_failure_snapshot.json.

## 4. Root cause diagnostics
- See stage10d18r_bridge_start_failure_diagnostics.json.
- root_cause_labels: ['STAGE10D18R_ROOT_CAUSE_FILENAME_GATE']

## 5. Implemented minimal fix
- Week6StudentPolicyAdapter filename allowlist now includes student_bc_stage10d17_movement_augmented_best.pt.

## 6. Manual checkpoint verification
- manual_load_status: ok
- manual_forward_status: ok
- manual_logits_shapes_valid: True

## 7. Unity minimal rerun verification
- checkpoint_binding_status: STAGE10D18R_CHECKPOINT_BINDING_CONFIRMED
- model_loaded: True
- adapter_invoked: True
- parsed_logits_available: True
- predicted_source: model_logits
- fallback_used: False
- logits_shapes_valid: True
- B2: action=Harvest p_noop=9.74388083990954e-29 p_harvest=0.9899958372116089 p_move=0.00653872499242425
- C3: action=Produce p_noop=4.746975427548096e-26 p_produce=0.9871749877929688 p_move=0.010416160337626934

## 8. Classification labels
- STAGE10D18R_UNITY_CHECKPOINT_BINDING_CONFIRMED
- STAGE10D18R_UNITY_MODEL_LOADED
- STAGE10D18R_UNITY_REAL_MODEL_LOGITS_CONFIRMED
- STAGE10D18R_UNITY_LOGITS_SHAPES_VALID
- STAGE10D18R_UNITY_FALLBACK_NOT_USED
- STAGE10D18R_UNITY_BINDING_FIX_PASS
- STAGE10D18R_ROOT_CAUSE_FILENAME_GATE

## 9. Primary next gate
- GO_FOR_STAGE10D18_RUNTIME_BC_REDEPLOY_EVAL_RERUN

## 10. What not to do next
- Do not run PPO.
- Do not train teacher/student.
- Do not mutate checkpoints.
- Do not change decoder/applier/match manager semantics.
- Do not infer movement behavior conclusions until full Stage10D.18 rerun.

## Explicit answers
- Did the Stage10D.17 checkpoint file exist? True
- Was the basename accepted? True
- Was any filename gate changed? yes
- Did manual strict load pass? True
- Did manual forward pass produce valid logits shapes? True
- Did Unity bridge start successfully after fix? True
- Did Unity receive real model logits? True
- Was fallback avoided? True
- Are logits shapes valid? True
- Is Stage10D.18 now ready to rerun as behavior evaluation? True
