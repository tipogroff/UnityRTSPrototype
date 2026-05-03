# LEGACY032 Unity v2 Stage10D.4 Observation Semantic Remediation Report

## 1. Scope
- Stage10D.4 defines a versioned canonical observation semantic contract and explicit adapter remediation workflow.
- No retraining, PPO, checkpoint mutation, or in-place dataset mutation were performed.
- Adapter output is written to a new directory only.

## 2. Stage10D.3 Recap
- Stage10D.3 report: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/LEGACY032_UNITY_V2_STAGE10D3_GYM_TO_UNITY_OBSERVATION_MAPPING_TRACE_REPORT.md
- raw shape: [88165, 24, 24, 27]
- owner [2..4] share(sum==1): 0.003472222222222222
- unit_type [5..11] share(sum==1): 0.025731404622395832
- current_action [12..17] share(sum==1): 0.9742685953776041
- direction [18..21] share(sum==1): 0.9829966227213541

## 3. Canonical Target Observation Semantics
- Canonical target selected: Unity v2 runtime semantics.
- owner_mode_target: perspective_friendly_enemy
- Rationale: student BC inference executes in Unity, so Unity runtime semantics are canonical deployment semantics.

## 4. Legacy032 Raw Observation Semantics
- Inference output: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10d4_inferred_legacy032_raw_channel_semantics.json
- Legacy032 raw semantics are empirical and partially unresolved for owner/unit_type channel identities.
- Stage10D.4 preserves explicit uncertainty instead of implicit remap.

## 5. Mapping Spec
- mapping file: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_legacy032/observation_semantics/legacy032_to_unity_v2_observation_mapping.json
- mapping_spec_version: stage10d4_v1
- observation_semantics_version: unity_v2_runtime_stage10d4
- Current_action/direction/produce/attack_target use explicit derived rules.
- Unknown owner/unit_type channels are explicit unavailable mappings with zero-fill fallback and audit flags.

## 6. Mapping Spec Validation
- validation file: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10d4_mapping_spec_validation.json
- status: pass
- mapping_complete_for_critical_groups: False
- critical_unavailable_channels: [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

## 7. Semantic Adapter Output
- conversion report: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_legacy032/teacher_adapted/legacy032_3m_unity_v2_semantic_adapted_20260503T082111Z/observation_semantic_conversion_report.json
- status: success
- output_dir: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_adapted\legacy032_3m_unity_v2_semantic_adapted_20260503T082111Z
- unavailable_channels: [0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
- critical_unavailable_channels: [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

## 8. Semantic Adapted Dataset Validation
- validation report: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10d4_semantic_adapted_dataset_validation.json
- status: fail
- worker proxy compatible: False
- base proxy compatible: False

## 9. Remaining Gaps
- Owner channel mapping from legacy032 raw to Unity perspective owner remains unresolved.
- Unit_type channel mapping from legacy032 raw to Unity unit_type one-hot remains unresolved.
- Spec reconciliation is still required between ObservationContract absolute-owner docs and UnityMvpTransfer runtime owner semantics.

## 10. Gate Decision
- classifications: ['OBSERVATION_SEMANTIC_MAPPING_SPEC_INCOMPLETE', 'SEMANTIC_ADAPTER_REBUILD_READY', 'UNITY_SPEC_RECONCILIATION_REQUIRED']
- gate: NO_GO_RETRAINING_UNTIL_SEMANTIC_ADAPTER_VALIDATED

## 11. Explicit Non-Claims
- No claim of exact semantic parity between Gym-microRTS raw observations and Unity runtime observations.
- No claim that retraining is authorized in Stage10D.4.
- No runtime mutation in ActionApplier or MatchManager.

## Metadata
- commit: 6f4bdd983d62158e86e55035623f9427feab79fa
