# Stage5P4 — BC-ready packaging from adapted Legacy032 Unity v2 dataset + loader dry-run

**Date:** 2026-05-06
**Project:** UnityRTSPrototype Thesis
**Stage:** 5P4 — BC-ready packaging + loader dry-run (no BC training)

## 1. Executive summary

Stage5P4 completed successfully. The validated Stage5P3 adapted dataset was packaged into BC-ready train/validation/debug splits and passed loader dry-run checks with zero hard failures.

**Final classification:** `STAGE5P4_BC_READY_PACKAGING_PASS_READY_FOR_WEEK6_BC_SMOKE`

## 2. Packager CLI discovered

Packager help confirms this CLI:

```text
usage: build_bc_ready_dataset_legacy032_v2.py [-h] --adapted-dir ADAPTED_DIR
                                              --validation-report VALIDATION_REPORT
                                              --output-dir OUTPUT_DIR --run-label RUN_LABEL
                                              [--validation-split VALIDATION_SPLIT]
                                              [--debug-samples DEBUG_SAMPLES]
                                              [--seed SEED]
                                              [--fail-on-contract-mismatch FAIL_ON_CONTRACT_MISMATCH]
```

Required args:

- `--adapted-dir`
- `--validation-report`
- `--output-dir`
- `--run-label`

Optional args:

- `--validation-split`
- `--debug-samples`
- `--seed`
- `--fail-on-contract-mismatch`

## 3. Exact packager command executed

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
  python/week5_teacher_legacy032/scripts/build_bc_ready_dataset_legacy032_v2.py `
  --adapted-dir python/week5_teacher_legacy032/teacher_exports/legacy032_3m_unity_v2_adapted_stage5p3_20260506T152734Z `
  --validation-report python/week5_teacher_legacy032/teacher_exports/legacy032_3m_unity_v2_adapted_stage5p3_20260506T152734Z/LEGACY032_UNITY_V2_DATASET_VALIDATION_REPORT.json `
  --output-dir python/week5_teacher_legacy032/teacher_exports_bc `
  --run-label legacy032_3m_unity_v2_bc_ready_stage5p4 `
  --seed 17 `
  --fail-on-contract-mismatch true
```

## 4. Input adapted dataset directory

- `python/week5_teacher_legacy032/teacher_exports/legacy032_3m_unity_v2_adapted_stage5p3_20260506T152734Z`

## 5. Output BC-ready directory and files

Output directory:

- `python/week5_teacher_legacy032/teacher_exports_bc/legacy032_3m_unity_v2_bc_ready_stage5p4_20260506T153632Z`

Files present:

1. `bc_train.npz`
2. `bc_validation.npz`
3. `bc_debug.npz`
4. `bc_manifest.json`
5. `bc_summary.json`
6. `bc_summary.md`
7. `LEGACY032_BC_READY_DRY_RUN_REPORT.json`
8. `LEGACY032_BC_READY_DRY_RUN_REPORT.md`

## 6. BC-ready manifest summary

From `bc_manifest.json`:

- `dataset_type`: `bc_ready_legacy032_unity_v2`
- `teacher_lineage`: `legacy032`
- `source_pipeline`: `gym_microrts==0.3.2`
- `target_action_contract`: `unity_v2_legacy032_gridnet`
- `observation_shape_per_sample`: `[576,27]`
- `action_shape_per_sample`: `[576,7]`
- `branch_sizes`: `[6,4,4,4,4,7,49]`
- `attack_target_semantics`: `local_7x7_49`
- `direct_weight_transfer_claim`: `false`
- `semantic_parity_claim`: `false`
- split seed: `17`
- validation split: `0.15`

## 7. Split statistics

From `bc_summary.json` and `bc_manifest.json`:

- source sample count: `37343`
- train count: `31742`
- validation count: `5601`
- debug count: `512`
- train + validation: `37343` (exact match to source; no train/validation loss)
- debug: extra subset artifact for inspection

## 8. Schema validation of train/validation/debug splits

Direct NPZ inspection:

- keys in each split: `observations`, `actions`, `episode_id`, `step_id`, `reward_t`, `done_t`, `terminated_t`, `truncated_t`, `action_mask_available_t`
- train: `observations [31742,576,27] float32`, `actions [31742,576,7] int16`
- validation: `observations [5601,576,27] float32`, `actions [5601,576,7] int16`
- debug: `observations [512,576,27] float32`, `actions [512,576,7] int16`
- all split files load successfully
- no NaN/Inf reported by dry-run checks

## 9. Branch bounds validation

Packager summary and dry-run report both show in-bounds values for all branches in train/validation:

- branch 0 (`action_type`, size 6): min=0 max=5
- branch 1 (`move_dir`, size 4): min=0 max=3
- branch 2 (`harvest_dir`, size 4): min=0 max=3
- branch 3 (`return_dir`, size 4): min=0 max=3
- branch 4 (`produce_dir`, size 4): min=0 max=3
- branch 5 (`produce_unit_type`, size 7): min=0 max=6
- branch 6 (`attack_target`, size 49): min=0 max=48

## 10. v1 regression check

PASS. No v1 regression indicators detected:

- branch sizes are **not** `[6,4,4,4,4,4,9]`
- attack target remains local 49-way (`local_7x7_49`), not 9-way
- action shape remains `[N,576,7]`

## 11. Loader dry-run CLI discovered

Loader help confirms this CLI:

```text
usage: dry_run_bc_loader_legacy032_v2.py [-h] --bc-ready-dir BC_READY_DIR
                                         [--batch-size BATCH_SIZE]
                                         [--fail-on-contract-mismatch FAIL_ON_CONTRACT_MISMATCH]
                                         [--write-report WRITE_REPORT]
                                         --output-dir OUTPUT_DIR
```

Required args:

- `--bc-ready-dir`
- `--output-dir`

Optional args:

- `--batch-size`
- `--fail-on-contract-mismatch`
- `--write-report`

## 12. Exact loader dry-run command executed

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
  python/week5_teacher_legacy032/scripts/dry_run_bc_loader_legacy032_v2.py `
  --bc-ready-dir python/week5_teacher_legacy032/teacher_exports_bc/legacy032_3m_unity_v2_bc_ready_stage5p4_20260506T153632Z `
  --batch-size 8 `
  --fail-on-contract-mismatch true `
  --write-report true `
  --output-dir python/week5_teacher_legacy032/teacher_exports_bc/legacy032_3m_unity_v2_bc_ready_stage5p4_20260506T153632Z
```

## 13. Loader dry-run result

Dry-run result:

- status: `pass`
- hard failures: `0`

Checks demonstrated by report:

- `bc_manifest.json` loads: PASS
- `bc_train.npz` loads: PASS
- `bc_validation.npz` loads: PASS
- `bc_debug.npz` exists and loads in package: PASS
- batch construction works with `B=8`: PASS
- train batch shape: observations `[8,576,27]`, actions `[8,576,7]`
- validation batch shape: observations `[8,576,27]`, actions `[8,576,7]`
- manifest contract fields and branch sizes `[6,4,4,4,4,7,49]`: PASS
- bounds and dtype checks: PASS
- no NaN/Inf in checked tensors: PASS

## 14. Warnings

None.

## 15. Final decision

`STAGE5P4_BC_READY_PACKAGING_PASS_READY_FOR_WEEK6_BC_SMOKE`

## 16. Recommended next stage

Proceed to:

**Stage5P5 / Week6A — Student BC training smoke on BC-ready package**

Recommended next command (do not run in Stage5P4):

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
  python/week6_student/scripts/train_student_bc_smoke_legacy032_v2.py `
  --bc-ready-dir python/week5_teacher_legacy032/teacher_exports_bc/legacy032_3m_unity_v2_bc_ready_stage5p4_20260506T153632Z `
  --device cpu
```

Boundary confirmation:

- BC training was not run.
- Unity was not launched.
- Teacher training/PPO fine-tuning was not run.
