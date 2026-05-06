# Stage5P3 — Adapt Main Legacy032 3M Rollout To Unity v2

**Date:** 2026-05-06
**Project:** UnityRTSPrototype Thesis
**Stage:** 5P3 — Adapt Main Legacy032 3M Rollout To Unity v2

## 1. Executive summary

Stage5P3 adaptation completed successfully from the validated Stage5P2 raw rollout into the Unity v2 dataset contract using the existing Legacy032 adapter. Strict adapted-dataset validation passed with zero hard failures and zero warnings.

**Final classification:** `STAGE5P3_ADAPT_MAIN_EXPORT_PASS_READY_FOR_VALIDATION_OR_BC_PACKAGING`

## 2. Exact adapter CLI discovered

Adapter help output confirmed this exact CLI:

```text
usage: adapt_legacy032_to_unity_v2.py [-h] --raw-rollout-dir RAW_ROLLOUT_DIR
                                      --run-label RUN_LABEL --output-dir OUTPUT_DIR
                                      [--fail-on-contract-mismatch FAIL_ON_CONTRACT_MISMATCH]
                                      [--write-debug-sample WRITE_DEBUG_SAMPLE]
```

Supported args:

- `--raw-rollout-dir` (required)
- `--run-label` (required)
- `--output-dir` (required)
- `--fail-on-contract-mismatch` (optional bool)
- `--write-debug-sample` (optional bool)

## 3. Exact adapter command executed

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
  python/week5_teacher_legacy032/scripts/adapt_legacy032_to_unity_v2.py `
  --raw-rollout-dir python/week5_teacher_legacy032/teacher_rollouts/legacy032_3m_unity_v2_rollout_export_20260506T144700Z `
  --run-label legacy032_3m_unity_v2_adapted_stage5p3 `
  --output-dir python/week5_teacher_legacy032/teacher_exports `
  --fail-on-contract-mismatch true `
  --write-debug-sample true
```

## 4. Input raw rollout directory

- `python/week5_teacher_legacy032/teacher_rollouts/legacy032_3m_unity_v2_rollout_export_20260506T144700Z`

Input contract summary (from Stage5P2):

- episodes: `16`
- total steps: `37343`
- `observation_t`: `[37343,24,24,27]`, `float32`
- `per_cell_action_t`: `[37343,576,7]`, `int16`
- branch sizes: `[6,4,4,4,4,7,49]`
- step mode: `training_compatible`
- export mode: `stochastic`
- `semantic_parity_claim`: `false`
- `direct_weight_transfer_claim`: `false`

## 5. Output adapted dataset directory and files

Output directory:

- `python/week5_teacher_legacy032/teacher_exports/legacy032_3m_unity_v2_adapted_stage5p3_20260506T152734Z`

Files generated:

1. `adapted_dataset.npz`
2. `adapted_manifest.json`
3. `adaptation_summary.json`
4. `adaptation_summary.md`
5. `adaptation_debug_sample.json`
6. `LEGACY032_UNITY_V2_DATASET_VALIDATION_REPORT.json`
7. `LEGACY032_UNITY_V2_DATASET_VALIDATION_REPORT.md`
8. `LEGACY032_UNITY_V2_DATASET_VALIDATION_DEBUG.json`

## 6. Source raw rollout contract summary

Verified source contract:

- source teacher lineage: `legacy032`
- source pipeline: `gym_microrts==0.3.2`
- source action nvec: `[576,6,4,4,4,4,7,49]`
- source branch sizes: `[6,4,4,4,4,7,49]`
- source observation per sample: `[24,24,27]`
- source action per sample: `[576,7]`

## 7. Target Unity v2 contract summary

Verified target manifest fields:

- `target_action_contract`: `unity_v2_legacy032_gridnet`
- `observation_shape_per_sample`: `[576,27]`
- `action_shape_per_sample`: `[576,7]`
- `branch_sizes`: `[6,4,4,4,4,7,49]`
- `attack_target_semantics`: `local_7x7_49`
- `semantic_parity_claim`: `false`
- `direct_weight_transfer_claim`: `false`

## 8. Adapter conversion results

- source sample count: `37343`
- output sample count: `37343`
- source observation shape: `[37343,24,24,27]`
- output observation shape: `[37343,576,27]`
- source action shape: `[37343,576,7]`
- output action shape: `[37343,576,7]`
- action mask available share: `1.0`
- adapter warnings: none
- adapter hard failures: none

## 9. Adapted dataset schema validation

Validator CLI discovered:

```text
usage: validate_legacy032_unity_v2_dataset.py [-h] --adapted-dir ADAPTED_DIR
                                              --output-dir OUTPUT_DIR
                                              [--fail-on-hard-errors FAIL_ON_HARD_ERRORS]
                                              [--write-debug-json WRITE_DEBUG_JSON]
```

Validator command executed:

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
  python/week5_teacher_legacy032/scripts/validate_legacy032_unity_v2_dataset.py `
  --adapted-dir python/week5_teacher_legacy032/teacher_exports/legacy032_3m_unity_v2_adapted_stage5p3_20260506T152734Z `
  --output-dir python/week5_teacher_legacy032/teacher_exports/legacy032_3m_unity_v2_adapted_stage5p3_20260506T152734Z `
  --fail-on-hard-errors true `
  --write-debug-json true
```

Validator result:

- status: `pass`
- decision: `GO_FOR_BC_READY_PACKAGER`
- hard failures: `0`
- warnings: `0`

Schema checks (strict):

- `adapted_dataset.npz` exists: PASS
- `adapted_manifest.json` exists: PASS
- observations shape `[37343,576,27]`: PASS
- actions shape `[37343,576,7]`: PASS
- observations dtype `float32`: PASS
- actions integer dtype (`int16`): PASS
- NaN/Inf in observations: none (PASS)
- all required metadata arrays present and length-consistent: PASS

## 10. Manifest validation

All strict manifest checks passed:

- `teacher_lineage == legacy032`
- `source_pipeline == gym_microrts==0.3.2`
- `target_action_contract == unity_v2_legacy032_gridnet`
- `observation_shape_per_sample == [576,27]`
- `action_shape_per_sample == [576,7]`
- `branch_sizes == [6,4,4,4,4,7,49]`
- `attack_target_semantics == local_7x7_49`
- `semantic_parity_claim == false`
- `direct_weight_transfer_claim == false`

## 11. Action branch bounds validation

Strict branch bounds all PASS:

- branch 0 (`action_type`, size 6): min=0 max=5
- branch 1 (`move_dir`, size 4): min=0 max=3
- branch 2 (`harvest_dir`, size 4): min=0 max=3
- branch 3 (`return_dir`, size 4): min=0 max=3
- branch 4 (`produce_dir`, size 4): min=0 max=3
- branch 5 (`produce_unit_type`, size 7): min=0 max=6
- branch 6 (`attack_target`, size 49): min=0 max=48

No v1 regression signature detected (`[6,4,4,4,4,4,9]` not present).

## 12. Data loss / remap / drop statistics

Adapter is contract-only reshape/validation, not semantic remapping. Observed stats:

- sample loss: `0` (`source_sample_count=37343`, `output_sample_count=37343`)
- sample drop share: `0.0`
- branch remap count: `0` (no remap path taken; v2 bounds preserved)
- v1 downgrade indicators: `0`
- hard failures related to contract mismatch: `0`
- warnings related to data quality/remap: `0`

## 13. Debug sample status

- `adaptation_debug_sample.json` generated: yes
- contains sample index 0 with observation and action excerpts: yes

## 14. Warnings

None.

## 15. Final decision

`STAGE5P3_ADAPT_MAIN_EXPORT_PASS_READY_FOR_VALIDATION_OR_BC_PACKAGING`

## 16. Recommended next stage

Proceed to **Stage5P4 — BC-ready packaging from adapted dataset**.

Recommended next command (do not run in Stage5P3):

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
  python/week5_teacher_legacy032/scripts/build_bc_ready_dataset_legacy032_v2.py `
  --adapted-dir python/week5_teacher_legacy032/teacher_exports/legacy032_3m_unity_v2_adapted_stage5p3_20260506T152734Z
```

Stage boundary confirmation:

- BC training was not run.
- Unity was not launched.
- BC packaging was not run.
