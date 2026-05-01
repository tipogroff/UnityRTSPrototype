# LEGACY032 Week5 Export-Adaptation-Packaging Runbook

## Scope

This runbook covers the full data pipeline chain:
1. raw rollout export;
2. adaptation to Unity v2;
3. strict validation;
4. BC-ready packaging;
5. dry-run loader check.

Constraints:
- No teacher training continuation.
- No 5M run.
- No BC training in this step.
- No PPO fine-tune in this step.
- No direct weight transfer claims.
- No semantic parity claims between Gym-microRTS and Unity.
- No action semantics remap.
- No fallback to v1 contract.

## 1) Raw Rollout Export

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
  python/week5_teacher_legacy032/scripts/export_teacher_rollout_legacy032.py `
  --checkpoint-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260430T130208Z/stage_003000000/agent_final.pt `
  --model-metadata-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260430T130208Z/stage_003000000/model_metadata.json `
  --run-label legacy032_3m_unity_v2_rollout_export `
  --episodes 16 `
  --seed 42 `
  --device cpu `
  --env-mode target_24x24_gridmode `
  --require-mask true `
  --max-steps-per-episode 6000 `
  --output-dir python/week5_teacher_legacy032/teacher_rollouts `
  --write-jsonl debug
```

## 2) Adaptation to Unity v2

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
  python/week5_teacher_legacy032/scripts/adapt_legacy032_to_unity_v2.py `
  --raw-rollout-dir python/week5_teacher_legacy032/teacher_rollouts/legacy032_3m_unity_v2_rollout_export_20260501T125015Z `
  --run-label legacy032_3m_unity_v2_adapted `
  --output-dir python/week5_teacher_legacy032/teacher_adapted `
  --fail-on-contract-mismatch true `
  --write-debug-sample true
```

## 3) Strict Validation

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
  python/week5_teacher_legacy032/scripts/validate_legacy032_unity_v2_dataset.py `
  --adapted-dir python/week5_teacher_legacy032/teacher_adapted/legacy032_3m_unity_v2_adapted_20260501T161820Z `
  --output-dir python/week5_teacher_legacy032/reports `
  --fail-on-hard-errors true `
  --write-debug-json true
```

## 4) BC-Ready Packaging

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
  python/week5_teacher_legacy032/scripts/build_bc_ready_dataset_legacy032_v2.py `
  --adapted-dir python/week5_teacher_legacy032/teacher_adapted/legacy032_3m_unity_v2_adapted_20260501T161820Z `
  --validation-report python/week5_teacher_legacy032/reports/LEGACY032_UNITY_V2_DATASET_VALIDATION_REPORT.json `
  --output-dir python/week5_teacher_legacy032/teacher_exports_bc `
  --run-label day6_bc_ready_legacy032_3m_unity_v2 `
  --validation-split 0.15 `
  --debug-samples 512 `
  --seed 17 `
  --fail-on-contract-mismatch true
```

## 5) Dry-Run Loader

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
  python/week5_teacher_legacy032/scripts/dry_run_bc_loader_legacy032_v2.py `
  --bc-ready-dir <OUTPUT_DIR_FROM_PACKAGER> `
  --batch-size 32 `
  --fail-on-contract-mismatch true `
  --write-report true `
  --output-dir python/week5_teacher_legacy032/reports
```

## Expected Artifacts from Current Step

Packaging output directory:
- `python/week5_teacher_legacy032/teacher_exports_bc/day6_bc_ready_legacy032_3m_unity_v2_<timestamp>/`

Required files:
- `bc_train.npz`
- `bc_validation.npz`
- `bc_debug.npz`
- `bc_manifest.json`
- `bc_summary.json`
- `bc_summary.md`

Dry-run report files:
- `python/week5_teacher_legacy032/reports/LEGACY032_BC_READY_DRY_RUN_REPORT.json`
- `python/week5_teacher_legacy032/reports/LEGACY032_BC_READY_DRY_RUN_REPORT.md`
