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

## Preferred teacher artifacts (Stage5O 3M continuation)
- Checkpoint:
  - python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/agent_final.pt
- Metadata:
  - python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/model_metadata.json
- Full trainer checkpoint (preserve lineage):
  - python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/trainer_state_final.pt

## Action path contract (final export)
- Stored dataset action (BC target): per-cell policy branch action [T,576,7].
- Env stepping action (runtime execution): training-compatible Java valid-action payload.

Canonical execution path:
1. policy action [N,576,7]
2. source-indexed real action [N,576,8]
3. source-valid filtering via mask[:,:,0]
4. JPype payload JArray(JArray(JArray(JInt)))
5. env.step(java_valid_actions)

Final export must use step mode training_compatible.
Raw env.step([N,576,7]) is kept only for diagnostic experiments and is not valid final evidence.

## PowerShell command (recommended Stage5P path)

```powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"

c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
  python/week5_teacher_legacy032/scripts/export_teacher_rollout_legacy032.py `
  --checkpoint-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/agent_final.pt `
  --model-metadata-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/model_metadata.json `
  --trainer-state-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/trainer_state_final.pt `
  --map-path maps/24x24/basesWorkers24x24.xml `
  --run-label legacy032_3m_unity_v2_rollout_export `
  --episodes 16 `
  --max-steps-per-episode 6000 `
  --seed 17 `
  --device cpu `
  --export-mode stochastic `
  --step-mode training_compatible `
  --require-mask true `
  --output-root python/week5_teacher_legacy032/teacher_rollouts
```

Optional deterministic baseline split:

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
  python/week5_teacher_legacy032/scripts/export_teacher_rollout_legacy032.py `
  --checkpoint-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/agent_final.pt `
  --model-metadata-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/model_metadata.json `
  --trainer-state-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/trainer_state_final.pt `
  --map-path maps/24x24/basesWorkers24x24.xml `
  --run-label legacy032_3m_unity_v2_rollout_export_det `
  --episodes 16 `
  --max-steps-per-episode 6000 `
  --seed 17 `
  --device cpu `
  --export-mode deterministic `
  --step-mode training_compatible `
  --require-mask true `
  --output-root python/week5_teacher_legacy032/teacher_rollouts
```

## Expected output directory

```text
python/week5_teacher_legacy032/teacher_rollouts/<run_label>_<timestamp>/
```

Expected files:
- teacher_rollout_raw.npz
- teacher_rollout_manifest.json
- teacher_rollout_summary.json

## Hard-fail conditions
The exporter stops with error if any of these conditions happen:
- checkpoint is missing;
- model metadata is missing;
- metadata contract mismatch (observation/action nvec);
- runtime env contract mismatch;
- observation shape is not [24,24,27];
- action nvec is not [576,6,4,4,4,4,7,49];
- map path mismatch from expected map;
- --require-mask true and action mask is unavailable;
- action branch values are out of bounds;
- any path implying v1 remap is detected.

## Notes
- Raw observation is exported as [24,24,27] per step in observation_t.
- per_cell_action_t is exported as [576,7] with branch sizes [6,4,4,4,4,7,49].
- attack_target remains local 0..48.
- produce_unit_type remains 0..6.
- Manifest schema is legacy032.teacher_rollout_raw.v2.
- This step does not perform Unity adaptation.
- Recommended Stage5P source split is stochastic export mode.
