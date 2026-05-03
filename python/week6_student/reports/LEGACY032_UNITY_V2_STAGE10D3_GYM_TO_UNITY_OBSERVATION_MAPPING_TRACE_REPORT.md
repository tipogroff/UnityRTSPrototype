# LEGACY032 Unity v2 Stage 10D.3 Gym-to-Unity Observation Mapping Trace Report

## 1. Scope
- Read-only trace audit only.
- No retraining, no PPO.
- No dataset/checkpoint mutation.
- No runtime semantics change.
- No ActionApplier/MatchManager modifications.

## 2. Inputs
- commit hash: 5c86551f7429ddfdea6385f9b5da55fd0eaa7010
- raw probe: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10d3_raw_gym_observation_channel_probe.json
- adapter trace: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10d3_adapter_observation_transform_trace.json
- permutation search: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10d3_channel_permutation_search.json
- source-code audit: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10d3_source_code_mapping_audit.json
- Stage10D.1R comparison: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10d1r_observation_channel_comparison_corrected.json

## 3. Stage10D.1R Recap
- B2 (Unity abs): owner=player1, unit_type=Worker, current_action=NoOp, direction=South
- C3 (Unity abs): owner=player1, unit_type=Base, current_action=NoOp, direction=South
- Stage10D.1R already confirmed non-owner mismatch persists after owner-mode correction.

## 4. Raw Gym Observation Empirical Channel Map
- raw observation shape: [88165, 24, 24, 27]
- owner [2..4] one-hot share(sum==1): 0.003472222222222222
- unit_type [5..11] one-hot share(sum==1): 0.025731404622395832
- current_action [12..17] one-hot share(sum==1): 0.9742685953776041
- direction [18..21] one-hot share(sum==1): 0.9829966227213541
- Raw gym observation appears internally structured as a stable 27-channel tensor.

## 5. Adapter Transform Trace
- raw->adapted equal: True
- raw->adapted delta: {'l2': 0.0, 'max_abs': 0.0, 'nonzero_count': 0}
- adapter transform flags: {'channel_copy': True, 'channel_reorder': False, 'channel_truncation': False, 'channel_semantic_rewrite': False, 'perspective_conversion': False, 'notes': 'Legacy032 adapter path reshapes observation_t to [N,576,27] without explicit channel remap.'}
- No explicit observation channel remap was detected in Legacy032 adapter path.

## 6. BC-ready Observation Channel Map
- adapted->bc sampled all equal: True
- sampled mismatch count: 0
- BC-ready packager preserves adapted observation channels for sampled keyed joins.

## 7. Unity Runtime Observation Channel Map
- source-code owner semantics conflict detected: True
- ObservationContract documents absolute owner channels; ObservationBuilder UnityMvpTransfer path documents perspective owner channels.
- This semantic split is consistent with Stage10D.2/10D.1R conflict findings.

## 8. Channel Permutation / Shift Analysis
- permutation findings: {'worker_appears_as_resource_ranged_explained_by_permutation': False, 'base_appears_as_resource_ranged_explained_by_permutation': False, 'noop_vs_attack_return_produce_explained_by_permutation': True, 'south_vs_west_explained_by_permutation': True, 'diagnostic_only': True, 'note': 'Search checks if simple channel permutations/group shifts can explain observed mismatch; no remap is applied.'}
- Simple within-group permutation does not fully explain worker/base/action/direction mismatch patterns.

## 9. Source Code Mapping Audit
- files audited: 7
- owner conflict in declarations: True
- unit_type declared across core sources: True
- current_action declared across core sources: False
- direction declared across core sources: False

## 10. Root-Cause Classification
- primary: UNITY_AND_BC_USE_INCOMPATIBLE_OBSERVATION_SEMANTICS
- first layer where mismatch appears: unity_runtime_observationbuilder_semantics_vs_teacher_raw_semantics

## 11. Patch Plan
- Freeze runtime behavior during audit closure.
- Define canonical cross-pipeline observation semantics (owner/unit_type/current_action/direction) as a versioned contract.
- Add explicit observation semantic adapter (or explicit rejection) rather than implicit reshape-only bridging.
- Rebuild adapted + BC-ready artifacts only after mapping spec is approved.
- Re-run Stage10D.1R/10D.3 on regenerated artifacts before any retraining decision.

## 12. Gate Decision
- NO_GO_RETRAINING_UNTIL_OBSERVATION_FIXED

## 13. Explicit Non-Claims
- This report does not claim semantic parity between Gym-μRTS and Unity.
- This report does not authorize retraining or PPO.
- This report does not mutate runtime semantics, dataset files, or checkpoints.