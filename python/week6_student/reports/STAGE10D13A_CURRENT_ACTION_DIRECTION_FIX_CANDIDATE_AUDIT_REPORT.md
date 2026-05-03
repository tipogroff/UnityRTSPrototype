# STAGE10D13A CurrentAction/Direction Fix Candidate Audit Report

## 1. Inputs and constraints
- Diagnostic-only offline inference on copied observations.
- No teacher/student training; no checkpoint mutation; no runtime action forcing.
- Runtime capture: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week6_student\reports\stage10d12r_full_raw_runtime_observation_step0001.json
- Strict replay report: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week6_student\reports\stage10d12r_strict_replay_probe_results.json
- BC-ready dir: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week6_student\bc_ready\legacy032_3m_unity_v2_semantic_bc_ready_stage10d7_20260503T090659Z
- Student checkpoint: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week6_student\runs\legacy032_v2_semantic_bc_stage10d8_20260503T093718Z\student_bc_semantic_best.pt

## 2. Stage10D.12R evidence recap
- Stage10D.12R established full raw [24,24,27] validity and strict replay validity.
- Baseline B2/C3 were NoOp in Stage10D.12R.
- Prior probes indicated strong sensitivity to current_action/direction channels.

## 3. Baseline confirmation
- Baseline classification: BASELINE_CONFIRMED
- B2 baseline: action=noop, p_noop=0.785167, p_harvest=0.066120
- C3 baseline: action=noop, p_noop=0.994619, p_produce=0.001276

## 4. B2 minimal current_action/direction probes
- Best B2 probe: B2_scalars_plus_current_action_plus_direction_to_BC
- Best B2 result: action=harvest, p_harvest=0.785149, p_noop=0.000000
- B2 labels: B2_CURRENT_ACTION_ONLY_SUFFICIENT, B2_CURRENT_ACTION_DIRECTION_SUFFICIENT, B2_SCALAR_DEPENDENCY_PRESENT, B2_MINIMAL_HARVEST_ENCODING_SUFFICIENT

## 5. C3 local current_action/context probes
- Best C3 probe: C3_5x5_current_action_plus_direction_to_BC
- Best C3 result: action=produce, p_produce=0.893545, p_noop=0.000001
- C3 labels: C3_LOCAL_5X5_CURRENT_ACTION_SUFFICIENT

## 6. Full actor-map candidate probes
- Best full policy: LOCAL_5X5_ACTION_CONTEXT_FROM_BC_AROUND_BASE
- Best full policy B2/C3: B2=harvest (p_harvest=0.802792), C3=produce (p_produce=0.747130)
- Full policy labels: FULL_ACTOR_MAP_POLICY_RESTORES_ACTOR_ACTIONS, FULL_ACTOR_MAP_POLICY_TOO_INVASIVE

## 7. Current_action semantic audit
- Runtime self-actor action_noop share (channel-derived): 1.0
- Runtime empty-cell action-all-zero share: 1.0
- Semantic labels: CURRENT_ACTION_SEMANTIC_MISMATCH_CONFIRMED, RUNTIME_OBSERVATION_REMAP_CANDIDATE_SUPPORTED, RUNTIME_OBSERVATION_REMAP_HIGH_RISK, TARGETED_BC_AUGMENTATION_SUPPORTED
- Safety interpretation: remap can restore logits but is high risk if it injects intent-like action signal into observation semantics.

## 8. Candidate fix decision matrix
- See stage10d13a_candidate_fix_decision_matrix.json for A-H matrix rows.

## 9. Evidence-based classifications
- BASELINE_CONFIRMED, B2_CURRENT_ACTION_ONLY_SUFFICIENT, B2_CURRENT_ACTION_DIRECTION_SUFFICIENT, B2_SCALAR_DEPENDENCY_PRESENT, B2_MINIMAL_HARVEST_ENCODING_SUFFICIENT, C3_LOCAL_5X5_CURRENT_ACTION_SUFFICIENT, FULL_ACTOR_MAP_POLICY_RESTORES_ACTOR_ACTIONS, FULL_ACTOR_MAP_POLICY_TOO_INVASIVE, CURRENT_ACTION_SEMANTIC_MISMATCH_CONFIRMED, RUNTIME_OBSERVATION_REMAP_CANDIDATE_SUPPORTED, RUNTIME_OBSERVATION_REMAP_HIGH_RISK, TARGETED_BC_AUGMENTATION_SUPPORTED

## 10. Primary next gate
- GO_FOR_TARGETED_BC_AUGMENTATION_WITH_UNITY_LIKE_STATES