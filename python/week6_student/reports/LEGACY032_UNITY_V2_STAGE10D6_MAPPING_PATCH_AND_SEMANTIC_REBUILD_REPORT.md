# Legacy032 → Unity V2  Stage 10D.6  Mapping Patch and Semantic Adapter Rebuild Report

_Generated: 2026-05-03T08:56:02Z_

## 1. Scope

Stage 10D.6 patches the official observation mapping spec with the owner/unit_type channel assignments recovered in Stage 10D.5, runs a full semantic adapter rebuild with the patched spec, validates the resulting adapted dataset, and re-runs the Stage 10D.1R observation compatibility diagnostics on the new data.

**Strict constraints this stage:**
- No retraining / PPO / checkpoint mutation.
- No overwrite of old raw rollout, adapted datasets, or BC-ready datasets.
- No silent channel remap.
- No BC-ready dataset rebuild authorised here.

## 2. Stage 10D.5 Recap

- Authoritative encoder: `gym_microrts/envs/vec_env.py` num_planes=[5,5,3,len(unitTypes)+1,6]
- Owner mapping (player0 perspective): neutral←raw10, friendly←raw11, enemy←raw12
- Unit type mapping: resource←14, base←15, barracks←16, worker←17, light←18, heavy←19, ranged←20
- raw 13 = empty/no-unit slot; intentionally not mapped to any Unity unit_type channel
- Candidate dry-run: worker_harvest_proxy peak at index 3 ✓, base_produce_proxy peak at index 1 ✓
- Gate from Stage10D.5: `GO_FOR_STAGE10D4_MAPPING_SPEC_PATCH`

## 3. Mapping Spec Patch

- Status: **success**
- New mapping_spec_version: `stage10d6_v1`
- New observation_semantics_version: `unity_v2_runtime_stage10d6`
- Archive: `observation_semantics/archive/legacy032_to_unity_v2_observation_mapping.stage10d4_before_stage10d6_patch.json`

| target | name | raw_index |
|--------|------|-----------|
| 2 | owner_neutral | 10 |
| 3 | owner_friendly | 11 |
| 4 | owner_enemy | 12 |
| 5 | unit_type_resource | 14 |
| 6 | unit_type_base | 15 |
| 7 | unit_type_barracks | 16 |
| 8 | unit_type_worker | 17 |
| 9 | unit_type_light | 18 |
| 10 | unit_type_heavy | 19 |
| 11 | unit_type_ranged | 20 |

## 4. Mapping Spec Validation

- Status: **pass**
- mapping_complete_for_critical_groups: True
- critical_unavailable_channels: []

## 5. Full Semantic Adapter Rebuild

- Status: **success**
- output_dir: `C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_adapted\legacy032_3m_unity_v2_semantic_adapted_stage10d6_20260503T085218Z`
- sample_count: 88165
- unavailable_channels: [0]
- critical_unavailable_channels: []
- adapted_has_nan: False
- adapted_has_inf: False
- adapted_min: 0.0
- adapted_max: 1.0

## 6. Semantic Adapted Dataset Validation

- Status: **pass**
- worker_harvest_proxy compatible: True
  - unit_type_mean: [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
  - expected_unity_peak_index: 3
- base_produce_proxy compatible: True
  - unit_type_mean: [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
  - expected_unity_peak_index: 1
- group `owner`: share_sum_eq_1=1.000  share_sum_eq_0=0.000  share_sum_le_1=1.000
- group `unit_type`: share_sum_eq_1=0.056  share_sum_eq_0=0.944  share_sum_le_1=1.000
- group `current_action`: share_sum_eq_1=1.000  share_sum_eq_0=0.000  share_sum_le_1=1.000
- group `direction`: share_sum_eq_1=0.003  share_sum_eq_0=0.997  share_sum_le_1=1.000
- group `produce`: share_sum_eq_1=0.002  share_sum_eq_0=0.998  share_sum_le_1=1.000

## 7. Stage 10D.1R Rerun on Semantic Adapted Dataset

- all_steps_passed: True
  - obs_compat_check_all_outputs: pass

- B2 (Worker) unit_type compatible: True
- C3 (Base) unit_type compatible: True
- owner/unit_type hard-failure mismatch found: False

## 8. Remaining Risks

- hit_points (channel 0) remains unavailable from legacy032 raw observation.
- Gym-microRTS environment perspective for player0 is assumed; cross-game rollout validation not performed.
- BC-ready dataset has NOT been rebuilt in this stage.
- Semantic compatibility of observations does not guarantee policy-level behavior parity.

## 9. Gate Decision

**Gate: `GO_FOR_SEMANTIC_BC_READY_REBUILD`**

Classifications:
- `MAPPING_SPEC_PATCHED_FROM_STAGE10D5_SOURCE_EVIDENCE`
- `MAPPING_SPEC_VALIDATED_COMPLETE`
- `FULL_SEMANTIC_ADAPTER_REBUILD_PASSED`
- `SEMANTIC_ADAPTED_DATASET_VALIDATION_PASSED`
- `OBSERVATION_COMPATIBILITY_RECHECK_PASSED`

Mapping spec patched, adapter rebuild passed, dataset validation passed, and observation compatibility verified. Safe to proceed to Stage 10D.7: Build Semantic BC-ready Dataset and Loader Dry-run.

**Important**: `GO_FOR_SEMANTIC_BC_READY_REBUILD` does NOT authorize BC retraining in this stage. Retraining is authorised only after Stage 10D.7 completes.

## 10. Explicit Non-Claims

- No retraining / PPO / checkpoint mutation performed or authorised in this stage.
- No raw rollout overwritten.
- No adapted datasets overwritten.
- No BC-ready datasets built or overwritten.
- No claim of exact Gym-microRTS to Unity semantic parity beyond recovered owner/unit_type channels.
- No silent channel remap performed.
