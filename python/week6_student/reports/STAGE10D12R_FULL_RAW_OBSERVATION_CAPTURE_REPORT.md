# Stage10D.12R Full Raw Runtime Observation Capture Report

**Generated:** 2026-05-03T14:09:32.347183Z

## Executive Summary

Stage10D.12R observation capture completed. True raw tensor is valid and suitable for strict probes. Primary next gate: GO_FOR_STAGE10D12R_STRICT_PROBE_RERUN

## Section 1: Capture Implementation

- **Location:** Assets/Scripts/ML/Week6StudentPolicyAdapter.cs
- **Method:** `CaptureFullRawObservationDiagnostic`
- **Capture Point:** After observation validation, before Python bridge send (line ~610)
- **Behavior Changes:** None - read-only instrumentation only
- **Checkpoint Modified:** False
- **Weights Modified:** False

## Section 2: Artifact Validation

| Metric | Value |
|--------|-------|
| Validation Passed | True |
| Classification | FULL_RAW_576_CAPTURED |
| Tensor Shape | [24, 24, 27] |
| Cell Count | 576 |
| Channel Count | 27 |
| NaN Values | 0 |
| Inf Values | 0 |
| B2 Found | True |
| C3 Found | True |

## Section 3: Full Raw Observation Summary

### Focus Cell B2 (Player1 Worker at position [1,1])
- **Decoded Owner:** player1
- **Decoded Unit:** worker
- **Decoded Action:** noop
- **Semantics:** VALID_BUT_NOOP_STATE
- **Matches BC Reference:** True

### Focus Cell C3 (Player1 Base at position [2,2])
- **Decoded Owner:** player1
- **Decoded Unit:** base
- **Decoded Action:** noop
- **Semantics:** VALID_BUT_NOOP_STATE
- **Matches BC Reference:** True

## Section 4: True Raw vs Reconstructed

- **Comparison Performed:** False
- **Classification:** RECONSTRUCTION_COMPARISON_UNAVAILABLE
- **Global L2 Difference:** None
- **B2 L2 Difference:** None
- **C3 L2 Difference:** None

**Interpretation:** Comparison unavailable

## Section 5: Strict Replay Baseline

- **Probes Generated:** True
- **Model Checkpoint Loaded:** True
- **Inference Status:** real_model_execution_completed
- **B2:** action=noop, p_noop=0.785167, p_harvest=0.066120, p_produce=0.044780
- **C3:** action=noop, p_noop=0.994619, p_harvest=0.001104, p_produce=0.001276

## Section 6: B2 BC-Reference Strict Probes

- **Nearest BC Worker+Harvest Reference:** split=train, sample=0, flat=25, xy=(1,1), l2_to_runtime_b2=2.449490
- **Reference Prediction:** {'predicted_action': 'harvest', 'p_harvest': 0.9985673427581787, 'p_noop': 1.8848053215434922e-29}

### B2 Group Probe Table

| Probe | Predicted | p_noop | p_harvest | harvest_top1 | delta_p_noop | delta_p_harvest |
|------|-----------|--------|-----------|--------------|--------------|-----------------|
| current_action_only | harvest | 0.000210 | 0.526017 | True | -0.784956 | 0.459897 |
| direction_only | harvest | 0.019092 | 0.469950 | True | -0.766074 | 0.403830 |
| scalars_only | noop | 0.802023 | 0.063623 | False | 0.016857 | -0.002497 |
| current_action_plus_direction | harvest | 0.000000 | 0.713748 | True | -0.785167 | 0.647628 |
| scalars_plus_current_action_plus_direction | harvest | 0.000000 | 0.785149 | True | -0.785167 | 0.719029 |
| owner_plus_unit_type | noop | 0.785167 | 0.066120 | False | 0.000000 | 0.000000 |
| owner_plus_unit_type_plus_current_action_plus_direction | harvest | 0.000000 | 0.713748 | True | -0.785167 | 0.647628 |
| full_b2_cell | harvest | 0.000000 | 0.785149 | True | -0.785167 | 0.719029 |

### B2 Per-Channel Top Ranking

| Rank | Channel | Combined Score |
|------|---------|----------------|
| 1 | action_harvest | 1.104407 |
| 2 | dir_west | 1.023740 |
| 3 | action_noop | 0.987809 |
| 4 | dir_south | 0.221840 |
| 5 | resources | 0.135538 |

- **B2 Conclusion:** STRICT_B2_CHANNEL_MISMATCH_CONFIRMED

## Section 7: C3 BC-Reference Strict Probes

- **Nearest BC Base+Produce Reference:** split=train, sample=6, flat=50, xy=(2,2), l2_to_runtime_c3=2.000000
- **Reference Prediction:** {'predicted_action': 'produce', 'p_produce': 0.99201899766922, 'p_noop': 1.1058978274830632e-20}

### C3 Radius Probe Table

| Probe | Predicted | p_noop | p_produce | produce_top1 | delta_p_noop | delta_p_produce |
|------|-----------|--------|-----------|--------------|--------------|-----------------|
| cell_only | noop | 0.537225 | 0.196194 | False | -0.457394 | 0.194918 |
| patch_3x3 | produce | 0.000000 | 0.931560 | True | -0.994619 | 0.930284 |
| patch_5x5 | produce | 0.000000 | 0.993462 | True | -0.994619 | 0.992186 |
| patch_7x7 | produce | 0.000000 | 0.992244 | True | -0.994619 | 0.990967 |
| neighbor_only_5x5 | produce | 0.000007 | 0.870853 | True | -0.994612 | 0.869576 |
| center_only | noop | 0.537225 | 0.196194 | False | -0.457394 | 0.194918 |

### C3 Semantic Group Probe Table

| Probe | Predicted | p_noop | p_produce | produce_top1 | delta_p_noop | delta_p_produce |
|------|-----------|--------|-----------|--------------|--------------|-----------------|
| owner_only_all_cells_5x5 | noop | 0.994619 | 0.001276 | False | 0.000000 | 0.000000 |
| unit_type_only_all_cells_5x5 | noop | 0.994452 | 0.001305 | False | -0.000168 | 0.000028 |
| current_action_only_all_cells_5x5 | produce | 0.000672 | 0.747130 | True | -0.993948 | 0.745853 |
| direction_only_all_cells_5x5 | noop | 0.992069 | 0.002085 | False | -0.002551 | 0.000808 |
| scalar_only_all_cells_5x5 | noop | 0.982693 | 0.004980 | False | -0.011926 | 0.003704 |
| owner_plus_unit_type | noop | 0.994452 | 0.001305 | False | -0.000168 | 0.000028 |
| owner_plus_unit_type_plus_current_action_plus_direction | produce | 0.000000 | 0.927616 | True | -0.994619 | 0.926340 |
| all_non_scalar_onehot_groups | produce | 0.000000 | 0.966670 | True | -0.994619 | 0.965393 |
| all_groups_except_center_c3 | produce | 0.000007 | 0.870853 | True | -0.994612 | 0.869576 |
| only_neighbor_cells_excluding_center | produce | 0.000007 | 0.870853 | True | -0.994612 | 0.869576 |
| only_center_c3 | noop | 0.537225 | 0.196194 | False | -0.457394 | 0.194918 |

- **C3 Conclusion:** STRICT_C3_LOCAL_CONTEXT_REQUIRED_CONFIRMED

## Section 8: True Raw Scene/Context Summary

- **True Raw Scene Counts:** {'owner_distribution': {'neutral': 572, 'self': 2, 'enemy': 2, 'none': 0}, 'unit_distribution': {'resource': 4, 'base': 2, 'barracks': 0, 'worker': 2, 'light': 0, 'heavy': 0, 'ranged': 0, 'none': 568}, 'action_distribution': {'noop': 8, 'move': 0, 'harvest': 0, 'return': 0, 'produce': 0, 'attack': 0, 'none': 568}, 'friendly_actor_count': 2, 'enemy_actor_count': 2, 'workers_count': 2, 'bases_count': 2, 'barracks_count': 0, 'resources_count': 4, 'empty_cells_count': 568, 'B2_decoded': {'owner': 'self', 'unit': 'worker', 'action': 'noop'}, 'C3_decoded': {'owner': 'self', 'unit': 'base', 'action': 'noop'}}
- **BC Reference Scene Counts:** {'owner_distribution': {'neutral': 570, 'self': 2, 'enemy': 4, 'none': 0}, 'unit_distribution': {'resource': 4, 'base': 2, 'barracks': 1, 'worker': 3, 'light': 0, 'heavy': 0, 'ranged': 0, 'none': 566}, 'action_distribution': {'noop': 574, 'move': 0, 'harvest': 1, 'return': 0, 'produce': 1, 'attack': 0, 'none': 0}, 'friendly_actor_count': 2, 'enemy_actor_count': 4, 'workers_count': 3, 'bases_count': 2, 'barracks_count': 1, 'resources_count': 4, 'empty_cells_count': 566, 'B2_decoded': {'owner': 'self', 'unit': 'worker', 'action': 'harvest'}, 'C3_decoded': {'owner': 'self', 'unit': 'base', 'action': 'produce'}}
- **Scene OOD Deltas:** {'enemy_actor_count_delta': 2, 'workers_count_delta': 1, 'empty_cells_count_delta': 2}
- **Scene OOD Conclusion:** STRICT_SCENE_OOD_NOT_CONFIRMED

## Section 9: Evidence-Based Classification

- **Labels:** REAL_STRICT_REPLAY_COMPLETED, REAL_MODEL_CHECKPOINT_LOADED, BC_REFERENCE_PATCH_PROBES_COMPLETED, STRICT_B2_BASELINE_NOOP_CONFIRMED, STRICT_C3_BASELINE_NOOP_CONFIRMED, STRICT_B2_CHANNEL_MISMATCH_CONFIRMED, STRICT_C3_LOCAL_CONTEXT_REQUIRED_CONFIRMED, STRICT_SCENE_OOD_NOT_CONFIRMED, STRICT_PROBES_INCONCLUSIVE
- **Capture Quality:** FULL_RAW_576_CAPTURED
- **Semantic Validity:** VALID
- **B2 Classification:** VALID_BUT_NOOP_STATE
- **C3 Classification:** VALID_BUT_NOOP_STATE
- **Scene OOD Status:** SCENE_MATCHES_BC_REFERENCE

## Section 10: Primary Next Gate

**Selected:** `GO_FOR_STAGE10D12R_STRICT_PROBE_RERUN`

**Probe Execution Valid:** True

**Probe Status:** Real model execution successful with required BC-reference probe fields.

**Missing Fields:** None

**Rationale:** Capture successful; rerun strict probes with full model

**Other Candidates:** GO_FOR_STAGE10D12R_STRICT_PROBE_RERUN, GO_FOR_TARGETED_BC_AUGMENTATION_WITH_UNITY_LIKE_STATES

## Artifacts Generated

- stage10d12r_full_raw_runtime_observation_step{STEP}.json
- stage10d12r_full_raw_observation_validation.json
- stage10d12r_full_raw_vs_reconstructed_diff.json
- stage10d12r_strict_replay_probe_results.json

## Conclusion

Stage10D.12R observation capture completed. True raw tensor is valid and suitable for strict probes. Primary next gate: GO_FOR_STAGE10D12R_STRICT_PROBE_RERUN
