# LEGACY032 Raw Rollout Export Runbook

## Scope
This runbook covers only raw rollout export for the trained Legacy032 3M teacher.

- No training continuation.
- No 5M run.
- No adapter execution.
- No validator execution.
- No BC-ready packaging.
- No BC training or PPO fine-tune.
- No direct weight transfer claims.
- No Gym-μRTS vs Unity semantic parity claims.

## Exporter
- Script: python/week5_teacher_legacy032/scripts/export_teacher_rollout_legacy032.py
- Output root: python/week5_teacher_legacy032/teacher_rollouts

The script exports raw trajectories only and does not perform Unity adaptation in this step.

## PowerShell command (current checkpoint)

```powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"

c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
  python/week5_teacher_legacy032/scripts/export_teacher_rollout_legacy032.py `
  --checkpoint-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260430T130208Z/stage_003000000/agent_final.pt `
  --model-metadata-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260430T130208Z/stage_003000000/model_metadata.json `
  --run-label legacy032_3m_unity_v2_rollout_export `
  --episodes 16 `
  --seed 17 `
  --device cpu `
  --env-mode target_24x24_gridmode `
  --require-mask true `
  --max-steps-per-episode 6000 `
  --output-dir python/week5_teacher_legacy032/teacher_rollouts `
  --write-jsonl debug
```

## Expected output directory

```text
python/week5_teacher_legacy032/teacher_rollouts/<run_label>_<timestamp>/
```

Expected files:
- teacher_rollout_raw.npz
- teacher_rollout_manifest.json
- teacher_rollout_summary.json
- teacher_rollout_summary.md
- teacher_rollout_debug.jsonl (when --write-jsonl debug)

## Hard-fail conditions
The exporter stops with error if any of these conditions happen:
- checkpoint is missing;
- model metadata is missing;
- metadata contract mismatch (observation/action nvec);
- runtime env contract mismatch;
- observation shape is not [24,24,27];
- action nvec is not [576,6,4,4,4,4,7,49];
- --require-mask true and action mask is unavailable;
- action branch values are out of bounds;
- any path implying v1 remap is detected.

## Notes
- Raw observation is exported as [24,24,27] per step.
- per_cell_action_t is exported as [576,7] with branch sizes [6,4,4,4,4,7,49].
- attack_target remains local 0..48.
- produce_unit_type remains 0..6.
- This step does not perform Unity adaptation.
