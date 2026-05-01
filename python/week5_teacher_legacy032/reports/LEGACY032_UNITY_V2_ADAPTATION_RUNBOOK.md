# LEGACY032 -> Unity v2 Adaptation Runbook

## Scope

This runbook executes tensor-only adaptation from Legacy032 raw rollout export to Unity v2 dataset contract.

Constraints for this step:
- No training continuation.
- No 5M run.
- No BC training.
- No PPO fine-tune.
- No direct weight transfer claims.
- No semantic parity claim between Gym-microRTS and Unity.
- No v1 action contract usage (`[6,4,4,4,4,4,9]`).
- No remap of `attack_target 49 -> 9`.
- No remap of `produce_unit_type 7 -> 4`.
- No validator and no BC-ready packager in this step.

## Command (PowerShell)

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
  python/week5_teacher_legacy032/scripts/adapt_legacy032_to_unity_v2.py `
  --raw-rollout-dir python/week5_teacher_legacy032/teacher_rollouts/legacy032_3m_unity_v2_rollout_export_20260501T125015Z `
  --run-label legacy032_3m_unity_v2_adapted `
  --output-dir python/week5_teacher_legacy032/teacher_adapted `
  --fail-on-contract-mismatch true `
  --write-debug-sample true
```

## Expected Outputs

A timestamped directory under:

`python/week5_teacher_legacy032/teacher_adapted/<run_label>_<timestamp>/`

Expected files:
- `adapted_dataset.npz`
- `adapted_manifest.json`
- `adaptation_summary.json`
- `adaptation_summary.md`

Optional when `--write-debug-sample true`:
- `adaptation_debug_sample.json`

## Quick Post-Run Checks

- `status` in script stdout is `success`.
- `adaptation_summary.json` reports:
  - source/output sample counts equal;
  - observation transform `[N,24,24,27] -> [N,576,27]`;
  - action shape preserved `[N,576,7]`;
  - branch bounds valid for `[6,4,4,4,4,7,49]`;
  - no NaN/Inf;
  - warnings/hard_failures recorded.
