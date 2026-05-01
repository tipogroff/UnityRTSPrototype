# LEGACY032 Unity v2 Dataset Validation Runbook

## Scope

This step runs an independent strict validator for the adapted Legacy032 Unity v2 dataset.

Constraints:
- No training continuation.
- No 5M runs.
- No BC training.
- No PPO fine-tune.
- No BC-ready packager creation in this step.
- No direct weight transfer claims.
- No semantic parity claims between Gym-microRTS and Unity.
- No action semantics remap.
- No fallback to legacy v1 action contract.

## Command (PowerShell)

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
  python/week5_teacher_legacy032/scripts/validate_legacy032_unity_v2_dataset.py `
  --adapted-dir python/week5_teacher_legacy032/teacher_adapted/legacy032_3m_unity_v2_adapted_20260501T161820Z `
  --output-dir python/week5_teacher_legacy032/reports `
  --fail-on-hard-errors true `
  --write-debug-json true
```

## Expected Outputs

Under `python/week5_teacher_legacy032/reports`:
- `LEGACY032_UNITY_V2_DATASET_VALIDATION_REPORT.json`
- `LEGACY032_UNITY_V2_DATASET_VALIDATION_REPORT.md`
- `LEGACY032_UNITY_V2_DATASET_VALIDATION_DEBUG.json` (when `--write-debug-json true`)

## Notes

The validator is independent by design:
- reads `adapted_dataset.npz` directly;
- reads `adapted_manifest.json` directly;
- recalculates all checks and statistics without trusting adaptation summary files.
